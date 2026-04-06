

import {
  Cartesian2,
  Cartesian3,
  Color,
  DistanceDisplayCondition,
  LabelStyle,
  NearFarScalar,
} from 'cesium';
import { BaseLayer } from './LayerManager.js';

const MAX_VESSELS = 2000;
const PRUNE_INTERVAL_MS = 60_000;
const STALE_MS = 120_000;

/**
 * Renders AIS vessel positions as yellow points with name labels.
 */
export class VesselLayer extends BaseLayer {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    super(viewer);
    this._byId = new Map();
    this._pruneInterval = setInterval(() => this._prune(), PRUNE_INTERVAL_MS);
  }

  /** @param {Object} envelope */
  onEvent(envelope) {
    if (envelope.kind !== 'vessel') return;
    const { entity_id, lat, lon, payload } = envelope;
    if (lat == null || lon == null) return;

    const pos = Cartesian3.fromDegrees(lon, lat, 0);
    const label = payload?.name || payload?.mmsi || entity_id;

    if (this._byId.has(entity_id)) {
      const rec = this._byId.get(entity_id);
      rec.entity.position = pos;
      rec.entity.label.text = label;
      rec.lastSeen = Date.now();
    } else {
      if (this._byId.size >= MAX_VESSELS) return;
      const entity = this.viewer.entities.add({
        id: entity_id,
        position: pos,
        point: {
          pixelSize: 6,
          color: Color.YELLOW,
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
          distanceDisplayCondition: new DistanceDisplayCondition(0, 5e5),
          show: this.enabled,
        },
      });
      this._byId.set(entity_id, { entity, lastSeen: Date.now() });
      this._entities.push(entity);
    }

    this.viewer.scene.requestRender();
  }

  /** @private */
  _prune() {
    const cutoff = Date.now() - STALE_MS;
    for (const [id, { entity, lastSeen }] of this._byId) {
      if (lastSeen < cutoff) {
        this.viewer.entities.remove(entity);
        this._entities = this._entities.filter((e) => e !== entity);
        this._byId.delete(id);
      }
    }
  }
}
