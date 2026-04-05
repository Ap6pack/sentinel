// Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

/**
 * Base class for all data layers. Subclasses implement onEvent() and
 * manage their own CesiumJS entities.
 */
export class BaseLayer {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    this.viewer = viewer;
    this.enabled = false;
    this._entities = [];
  }

  /**
   * Called with a parsed EventEnvelope when this layer's kind arrives.
   * @param {Object} envelope
   */
  onEvent(envelope) {}

  /**
   * Show or hide all entities managed by this layer.
   * @param {boolean} visible
   */
  setVisible(visible) {
    this.enabled = visible;
    this._entities.forEach((e) => {
      e.show = visible;
    });
    this.viewer.scene.requestRender();
  }

  /** Remove all entities from the globe. */
  clear() {
    this._entities.forEach((e) => this.viewer.entities.remove(e));
    this._entities = [];
  }
}

/**
 * Registry and router — maps event kinds to layer instances.
 */
export class LayerManager {
  constructor() {
    /** @type {Map<string, BaseLayer>} */
    this._layers = new Map();
  }

  /**
   * Register a layer for a given event kind.
   * @param {string} kind
   * @param {BaseLayer} layer
   */
  register(kind, layer) {
    this._layers.set(kind, layer);
  }

  /**
   * Route an envelope to the appropriate layer.
   * @param {Object} envelope
   */
  route(envelope) {
    const layer = this._layers.get(envelope.kind);
    if (layer?.enabled) layer.onEvent(envelope);
  }

  /**
   * Toggle a layer's visibility.
   * @param {string} kind
   * @param {boolean} visible
   */
  toggle(kind, visible) {
    this._layers.get(kind)?.setVisible(visible);
  }

  /** @returns {Map<string, BaseLayer>} */
  get layers() {
    return this._layers;
  }
}
