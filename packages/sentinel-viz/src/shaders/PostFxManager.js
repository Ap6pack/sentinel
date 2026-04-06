

import { PostProcessStage } from 'cesium';
import nvgSource from './nvg.glsl?raw';
import flirSource from './flir.glsl?raw';
import crtSource from './crt.glsl?raw';

/**
 * Manages full-screen GLSL post-processing passes (NVG, FLIR, CRT).
 * Only one mode can be active at a time; 'none' disables all.
 */
export class PostFxManager {
  /** @param {import('cesium').Scene} scene */
  constructor(scene) {
    this._scene = scene;
    this._stages = {};
    this._active = 'none';
  }

  /** @private */
  _createStage(name, fragmentShader) {
    return new PostProcessStage({ name, fragmentShader, uniforms: {} });
  }

  /** Add all shader stages to the scene (disabled by default). */
  loadAll() {
    this._stages.nvg = this._scene.postProcessStages.add(
      this._createStage('nvg', nvgSource)
    );
    this._stages.flir = this._scene.postProcessStages.add(
      this._createStage('flir', flirSource)
    );
    this._stages.crt = this._scene.postProcessStages.add(
      this._createStage('crt', crtSource)
    );
    Object.values(this._stages).forEach((s) => {
      s.enabled = false;
    });
  }

  /**
   * Activate a shader mode. Pass 'none' to disable all.
   * @param {string} mode - 'nvg' | 'flir' | 'crt' | 'none'
   */
  setMode(mode) {
    Object.entries(this._stages).forEach(([name, stage]) => {
      stage.enabled = name === mode;
    });
    this._active = mode;
    this._scene.requestRender();
  }

  /** @returns {string} Currently active mode name */
  get active() {
    return this._active;
  }

  /** @returns {string[]} Available mode names */
  get modes() {
    return ['none', ...Object.keys(this._stages)];
  }
}
