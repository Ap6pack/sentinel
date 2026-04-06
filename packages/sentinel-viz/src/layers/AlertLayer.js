

import {
  Cartesian2,
  Cartesian3,
  Color,
  DistanceDisplayCondition,
  LabelStyle,
  NearFarScalar,
  VerticalOrigin,
} from 'cesium';
import { BaseLayer } from './LayerManager.js';

const MAX_ALERTS = 500;

/**
 * Renders AI-generated alerts as red pins on the globe with a confidence badge.
 * Stores full alert data so AlertDrawer and InfoPanel can display details.
 */
export class AlertLayer extends BaseLayer {
  /**
   * @param {import('cesium').Viewer} viewer
   * @param {import('../ui/CameraPresets.js').CameraPresets} [cameraPresets]
   */
  constructor(viewer, cameraPresets = null) {
    super(viewer);
    /** @type {Map<string, {entity: import('cesium').Entity, alert: Object}>} */
    this._byId = new Map();
    this._cameraPresets = cameraPresets;
    /** @type {Array<function(Object): void>} */
    this._listeners = [];
  }

  /**
   * Register a callback for new alert events (used by AlertDrawer).
   * @param {function(Object): void} fn
   */
  onAlert(fn) {
    this._listeners.push(fn);
  }

  /** @param {Object} envelope */
  onEvent(envelope) {
    if (envelope.kind !== 'alert') return;
    const { entity_id, lat, lon, payload } = envelope;
    if (lat == null || lon == null) return;
    if (this._byId.has(entity_id)) return;
    if (this._byId.size >= MAX_ALERTS) return;

    const confidence = payload?.confidence ?? 0;
    const pct = Math.round(confidence * 100);
    const title = payload?.summary || payload?.title || 'ALERT';
    const labelText = `${title}  ${pct}%`;

    const entity = this.viewer.entities.add({
      id: `alert-${entity_id}`,
      position: Cartesian3.fromDegrees(lon, lat, 0),
      point: {
        pixelSize: 14,
        color: Color.RED.withAlpha(0.9),
        outlineColor: Color.WHITE,
        outlineWidth: 2,
        scaleByDistance: new NearFarScalar(1e3, 1.5, 5e5, 0.6),
        show: this.enabled,
      },
      label: {
        text: labelText,
        font: '12px monospace',
        fillColor: Color.RED,
        outlineColor: Color.BLACK,
        outlineWidth: 2,
        style: LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cartesian2(0, -20),
        verticalOrigin: VerticalOrigin.BOTTOM,
        distanceDisplayCondition: new DistanceDisplayCondition(0, 2e5),
        show: this.enabled,
      },
    });

    const alertData = {
      entity_id,
      lat,
      lon,
      ts: envelope.ts,
      confidence,
      summary: payload?.summary || '',
      reasoning: payload?.reasoning || '',
      recommended_action: payload?.recommended_action || '',
      title: payload?.title || '',
      payload,
    };

    this._byId.set(entity_id, { entity, alert: alertData });
    this._entities.push(entity);
    this.viewer.scene.requestRender();

    // Notify listeners (AlertDrawer)
    for (const fn of this._listeners) {
      fn(alertData);
    }
  }

  /**
   * Fly the camera to an alert's location.
   * @param {string} entityId
   */
  flyToAlert(entityId) {
    const rec = this._byId.get(entityId);
    if (!rec) return;
    const { lat, lon } = rec.alert;
    this.viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(lon, lat, 5000),
      duration: 2.0,
    });
  }

  /**
   * Look up stored alert data for an entity_id.
   * @param {string} entityId — may be "alert-{id}" from Cesium entity or raw id
   * @returns {Object|null}
   */
  getAlert(entityId) {
    // Strip "alert-" prefix if present (Cesium entity ids use it)
    const rawId = entityId.startsWith('alert-') ? entityId.slice(6) : entityId;
    return this._byId.get(rawId)?.alert ?? null;
  }
}
