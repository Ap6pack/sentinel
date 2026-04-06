

import {
  Cartesian3,
  Color,
  VerticalOrigin,
} from 'cesium';
import { BaseLayer } from './LayerManager.js';

const MAX_ALERTS = 500;

/**
 * Renders AI-generated alerts as red pulsing pins on the globe.
 */
export class AlertLayer extends BaseLayer {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    super(viewer);
    this._byId = new Map();
  }

  /** @param {Object} envelope */
  onEvent(envelope) {
    if (envelope.kind !== 'alert') return;
    const { entity_id, lat, lon, payload } = envelope;
    if (lat == null || lon == null) return;
    if (this._byId.has(entity_id)) return; // already shown
    if (this._byId.size >= MAX_ALERTS) return;

    const entity = this.viewer.entities.add({
      id: `alert-${entity_id}`,
      position: Cartesian3.fromDegrees(lon, lat, 0),
      point: {
        pixelSize: 12,
        color: Color.RED.withAlpha(0.9),
        outlineColor: Color.WHITE,
        outlineWidth: 2,
        show: this.enabled,
      },
      label: {
        text: payload?.title || 'ALERT',
        font: '13px monospace',
        fillColor: Color.RED,
        verticalOrigin: VerticalOrigin.BOTTOM,
        show: this.enabled,
      },
    });
    this._byId.set(entity_id, entity);
    this._entities.push(entity);
    this.viewer.scene.requestRender();
  }
}
