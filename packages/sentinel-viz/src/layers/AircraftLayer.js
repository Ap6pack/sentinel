

import {
  Cartesian2,
  Cartesian3,
  Color,
  DistanceDisplayCondition,
  LabelStyle,
  NearFarScalar,
} from 'cesium';
import { BaseLayer } from './LayerManager.js';

const MAX_AIRCRAFT = 2000;
const PRUNE_INTERVAL_MS = 30_000;
const STALE_MS = 60_000;

/**
 * Renders live aircraft positions as cyan points with callsign labels.
 * Entities are pruned if not updated within 60 seconds.
 */
export class AircraftLayer extends BaseLayer {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    super(viewer);
    /** @type {Map<string, {entity: import('cesium').Entity, lastSeen: number}>} */
    this._byId = new Map();
    this._pruneInterval = setInterval(() => this._prune(), PRUNE_INTERVAL_MS);
  }

  /** @param {Object} envelope */
  onEvent(envelope) {
    if (envelope.kind !== 'aircraft') return;
    const { entity_id, lat, lon, alt_m, payload } = envelope;
    if (lat == null || lon == null) return;

    const pos = Cartesian3.fromDegrees(lon, lat, alt_m ?? 0);
    const label = payload?.callsign || entity_id;

    if (this._byId.has(entity_id)) {
      const rec = this._byId.get(entity_id);
      rec.entity.position = pos;
      rec.entity.label.text = label;
      rec.lastSeen = Date.now();
    } else {
      if (this._byId.size >= MAX_AIRCRAFT) return;
      const entity = this.viewer.entities.add({
        id: entity_id,
        position: pos,
        point: {
          pixelSize: 6,
          color: Color.CYAN,
          outlineColor: Color.BLACK,
          outlineWidth: 1,
          scaleByDistance: new NearFarScalar(1e4, 1.2, 1e6, 0.4),
          show: this.enabled,
        },
        label: {
          text: label,
          font: '11px monospace',
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 2,
          style: LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cartesian2(0, -14),
          distanceDisplayCondition: new DistanceDisplayCondition(0, 1e6),
          show: this.enabled,
        },
      });
      this._byId.set(entity_id, { entity, lastSeen: Date.now() });
      this._entities.push(entity);
    }

    this.viewer.scene.requestRender();
  }

  /** Remove aircraft not seen in the last 60 seconds. */
  _prune() {
    const cutoff = Date.now() - STALE_MS;
    for (const [id, { entity, lastSeen }] of this._byId) {
      if (lastSeen < cutoff) {
        this.viewer.entities.remove(entity);
        this._entities = this._entities.filter((e) => e !== entity);
        this._byId.delete(id);
      }
    }
    if (this._byId.size > 0) {
      this.viewer.scene.requestRender();
    }
  }
}
