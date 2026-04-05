// Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

import { Cartesian3, Math as CesiumMath } from 'cesium';

/**
 * Camera fly-to presets bound to keyboard shortcuts.
 * Q / W / E mapped to landmark views.
 */
export class CameraPresets {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    this._viewer = viewer;
    this._presets = {};
  }

  /**
   * Register a named camera preset.
   * @param {string} key - preset name
   * @param {{name: string, lat: number, lon: number, alt: number, heading?: number, pitch?: number}} preset
   */
  register(key, preset) {
    this._presets[key] = preset;
  }

  /**
   * Fly the camera to a registered preset.
   * @param {string} key
   */
  flyTo(key) {
    const p = this._presets[key];
    if (!p) return;
    this._viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(p.lon, p.lat, p.alt),
      orientation: {
        heading: CesiumMath.toRadians(p.heading ?? 0),
        pitch: CesiumMath.toRadians(p.pitch ?? -45),
        roll: 0,
      },
      duration: 2.0,
    });
  }

  /**
   * Bind keyboard keys to preset names.
   * @param {Object<string, string>} keyMap - e.g. { q: 'london', w: 'heathrow' }
   */
  bindKeys(keyMap) {
    document.addEventListener('keydown', (e) => {
      // Don't trigger when typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      const presetKey = keyMap[e.key.toLowerCase()];
      if (presetKey) this.flyTo(presetKey);
    });
  }
}
