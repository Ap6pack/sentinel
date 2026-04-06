

import {
  Cartesian2,
  Cartesian3,
  Color,
  DistanceDisplayCondition,
  LabelStyle,
  Math as CesiumMath,
  NearFarScalar,
  VerticalOrigin,
} from 'cesium';
import { BaseLayer } from './LayerManager.js';
import { config } from '../config.js';

const MAX_PROFILES = 5000;
const FETCH_DEBOUNCE_MS = 500;
const PIN_COLOR = Color.HOTPINK;
const PIN_COLOR_HIGH = Color.RED;
const PIN_COLOR_LOW = Color.ORANGE;

/**
 * OSINT profile pins on the globe. Fetches profiles from the OSINT API
 * when the camera moves, and also accepts real-time PROFILE events from
 * the bus. Click a pin to open the InfoPanel with identity details.
 */
export class ProfileLayer extends BaseLayer {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    super(viewer);
    /** @type {Map<string, {entity: import('cesium').Entity, profile: Object}>} */
    this._byId = new Map();
    this._fetchTimer = null;
    this._abortCtrl = null;
    this._cameraMoveListener = null;
  }

  /**
   * Enable or disable the layer. When enabled, starts listening for
   * camera movements to trigger bbox queries.
   * @param {boolean} visible
   */
  setVisible(visible) {
    super.setVisible(visible);
    if (visible) {
      this._bindCameraMove();
      this._scheduleFetch();
    } else {
      this._unbindCameraMove();
    }
  }

  /**
   * Handle a real-time PROFILE event from the bus.
   * @param {Object} envelope
   */
  onEvent(envelope) {
    if (envelope.kind !== 'profile') return;
    const profile = {
      entity_id: envelope.entity_id,
      lat: envelope.lat,
      lon: envelope.lon,
      confidence: envelope.payload?.confidence ?? 0,
      sources: envelope.payload?.sources ?? [],
      identifiers: envelope.payload?.identifiers ?? {},
    };
    this._upsertPin(profile);
  }

  /** Remove all entities from the globe. */
  clear() {
    super.clear();
    this._byId.clear();
  }

  /** @private — bind camera move to trigger fetches */
  _bindCameraMove() {
    if (this._cameraMoveListener) return;
    this._cameraMoveListener = this.viewer.camera.moveEnd.addEventListener(() => {
      this._scheduleFetch();
    });
  }

  /** @private */
  _unbindCameraMove() {
    if (this._cameraMoveListener) {
      this._cameraMoveListener();
      this._cameraMoveListener = null;
    }
  }

  /**
   * Debounced fetch — waits for camera to stop moving before querying.
   * @private
   */
  _scheduleFetch() {
    if (this._fetchTimer) clearTimeout(this._fetchTimer);
    this._fetchTimer = setTimeout(() => this._fetchProfiles(), FETCH_DEBOUNCE_MS);
  }

  /**
   * Query the OSINT API for profiles in the current camera bbox.
   * @private
   */
  async _fetchProfiles() {
    if (!this.enabled) return;

    // Abort any in-flight request
    if (this._abortCtrl) this._abortCtrl.abort();
    this._abortCtrl = new AbortController();

    const rect = this.viewer.camera.computeViewRectangle();
    if (!rect) return;

    const lat = CesiumMath.toDegrees((rect.south + rect.north) / 2);
    const lon = CesiumMath.toDegrees((rect.west + rect.east) / 2);
    // Approximate radius from bbox diagonal
    const dlat = CesiumMath.toDegrees(rect.north - rect.south);
    const dlon = CesiumMath.toDegrees(rect.east - rect.west);
    const radiusM = Math.max(dlat, dlon) * 111_000 * 0.5;

    // Don't fetch when zoomed out too far (radius > 500km)
    if (radiusM > 500_000) return;

    const url = `${config.osintApi}/profiles?lat=${lat}&lon=${lon}&radius_m=${Math.round(radiusM)}`;

    try {
      const resp = await fetch(url, { signal: this._abortCtrl.signal });
      if (!resp.ok) {
        console.warn(`[profile] API ${resp.status}`);
        return;
      }
      const profiles = await resp.json();
      for (const p of profiles) {
        this._upsertPin(p);
      }
      this.viewer.scene.requestRender();
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('[profile] fetch failed', err);
      }
    }
  }

  /**
   * Create or update a profile pin on the globe.
   * @param {Object} profile — { entity_id, lat, lon, confidence, sources, identifiers }
   * @private
   */
  _upsertPin(profile) {
    const { entity_id, lat, lon, confidence, sources, identifiers } = profile;
    if (lat == null || lon == null) return;

    const pos = Cartesian3.fromDegrees(lon, lat);
    const color = this._pinColor(confidence);
    const labelText = this._pinLabel(sources, identifiers);

    if (this._byId.has(entity_id)) {
      const rec = this._byId.get(entity_id);
      rec.entity.position = pos;
      rec.entity.point.color = color;
      rec.entity.label.text = labelText;
      rec.profile = profile;
    } else {
      if (this._byId.size >= MAX_PROFILES) return;
      const entity = this.viewer.entities.add({
        id: entity_id,
        position: pos,
        point: {
          pixelSize: 10,
          color,
          outlineColor: Color.WHITE,
          outlineWidth: 2,
          scaleByDistance: new NearFarScalar(1e3, 1.5, 5e5, 0.5),
          show: this.enabled,
        },
        label: {
          text: labelText,
          font: '11px monospace',
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 2,
          style: LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cartesian2(0, -18),
          verticalOrigin: VerticalOrigin.BOTTOM,
          distanceDisplayCondition: new DistanceDisplayCondition(0, 5e4),
          show: this.enabled,
        },
      });
      this._byId.set(entity_id, { entity, profile });
      this._entities.push(entity);
    }

    this.viewer.scene.requestRender();
  }

  /**
   * Choose pin color based on confidence score.
   * @param {number} confidence 0.0–1.0
   * @returns {import('cesium').Color}
   * @private
   */
  _pinColor(confidence) {
    if (confidence >= 0.8) return PIN_COLOR_HIGH;
    if (confidence >= 0.5) return PIN_COLOR;
    return PIN_COLOR_LOW;
  }

  /**
   * Build a short label from the best available identifier.
   * @param {string[]} sources
   * @param {Object} identifiers
   * @returns {string}
   * @private
   */
  _pinLabel(sources, identifiers) {
    if (identifiers?.ssid) return identifiers.ssid;
    if (identifiers?.username) return `@${identifiers.username}`;
    if (identifiers?.strava_id) return `strava:${identifiers.strava_id}`;
    if (identifiers?.bssid) return identifiers.bssid.substring(0, 8);
    if (sources?.length) return sources.join('+');
    return 'OSINT';
  }

  /**
   * Look up the stored profile data for an entity_id.
   * Used by InfoPanel to display details on click.
   * @param {string} entityId
   * @returns {Object|null}
   */
  getProfile(entityId) {
    return this._byId.get(entityId)?.profile ?? null;
  }
}
