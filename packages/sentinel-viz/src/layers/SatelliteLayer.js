

import {
  Cartesian3,
  Color,
  NearFarScalar,
  Math as CesiumMath,
} from 'cesium';
import { twoline2satrec, propagate, gstime, eciToGeodetic } from 'satellite.js';
import { BaseLayer } from './LayerManager.js';

const TLE_URL = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle';
const MAX_SATS = 500;
const REFRESH_MS = 30_000;

/**
 * Loads TLE data from CelesTrak and propagates satellite positions
 * in real time using satellite.js (SGP4).
 */
export class SatelliteLayer extends BaseLayer {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    super(viewer);
    this._sats = [];
    this._animFrame = null;
  }

  /**
   * Fetch TLEs and start the animation loop.
   * Called once from main.js after the globe is ready.
   */
  async load() {
    try {
      const resp = await fetch(TLE_URL);
      const text = await resp.text();
      const lines = text.trim().split('\n');
      this._sats = [];
      for (let i = 0; i + 2 < lines.length && this._sats.length < MAX_SATS; i += 3) {
        const name = lines[i].trim();
        try {
          const satrec = twoline2satrec(lines[i + 1], lines[i + 2]);
          this._sats.push({ name, satrec, entity: null });
        } catch (e) {
          // Skip malformed TLE lines
        }
      }
      console.log(`[sat] loaded ${this._sats.length} satellites`);
      this._createEntities();
      this._startAnimation();
    } catch (e) {
      console.warn('[sat] failed to load TLEs', e);
    }
  }

  /** @private */
  _createEntities() {
    for (const sat of this._sats) {
      const entity = this.viewer.entities.add({
        position: Cartesian3.fromDegrees(0, 0, 400_000),
        point: {
          pixelSize: 3,
          color: Color.fromCssColorString('#88ff88'),
          scaleByDistance: new NearFarScalar(1e6, 1.0, 1e8, 0.2),
          show: this.enabled,
        },
      });
      sat.entity = entity;
      this._entities.push(entity);
    }
  }

  /** @private */
  _startAnimation() {
    const tick = () => {
      this._animFrame = requestAnimationFrame(tick);
      if (!this.enabled) return;

      const now = new Date();
      const gmst = gstime(now);
      let updated = false;

      for (const sat of this._sats) {
        if (!sat.entity) continue;
        try {
          const pv = propagate(sat.satrec, now);
          if (!pv.position || typeof pv.position === 'boolean') continue;
          const geo = eciToGeodetic(pv.position, gmst);
          const lat = CesiumMath.toDegrees(geo.latitude);
          const lon = CesiumMath.toDegrees(geo.longitude);
          const alt = geo.height * 1000; // km -> m
          sat.entity.position = Cartesian3.fromDegrees(lon, lat, alt);
          updated = true;
        } catch (e) {
          // propagation can fail for decayed sats
        }
      }

      if (updated) this.viewer.scene.requestRender();
    };
    this._animFrame = requestAnimationFrame(tick);
  }

  /** @override */
  setVisible(visible) {
    super.setVisible(visible);
    // Animation loop checks this.enabled, no extra work needed
  }

  /** Stop animation and clean up. */
  destroy() {
    if (this._animFrame != null) {
      cancelAnimationFrame(this._animFrame);
      this._animFrame = null;
    }
    this.clear();
  }
}
