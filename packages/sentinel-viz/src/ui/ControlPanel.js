

/**
 * Left sidebar control panel — layer toggles and shader mode selector.
 * Pure DOM, no framework.
 */
export class ControlPanel {
  /**
   * @param {import('../layers/LayerManager.js').LayerManager} layerManager
   * @param {import('../shaders/PostFxManager.js').PostFxManager} postFx
   */
  constructor(layerManager, postFx) {
    this._lm = layerManager;
    this._postFx = postFx;
    this._el = null;
  }

  /** Mount the panel into the DOM. */
  mount() {
    this._el = document.createElement('div');
    this._el.id = 'control-panel';
    this._el.innerHTML = `
      <div class="cp-section">
        <h3>LAYERS</h3>
        <div id="cp-layers"></div>
      </div>
      <div class="cp-section">
        <h3>SHADER</h3>
        <div id="cp-shaders"></div>
      </div>
    `;
    document.body.appendChild(this._el);

    this._buildLayerToggles();
    this._buildShaderButtons();
  }

  /** @private */
  _buildLayerToggles() {
    const container = this._el.querySelector('#cp-layers');
    for (const [kind, layer] of this._lm.layers) {
      const label = document.createElement('label');
      label.className = 'cp-toggle';

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = layer.enabled;
      cb.addEventListener('change', () => {
        this._lm.toggle(kind, cb.checked);
      });

      const span = document.createElement('span');
      span.textContent = kind.toUpperCase();

      label.appendChild(cb);
      label.appendChild(span);
      container.appendChild(label);
    }
  }

  /** @private */
  _buildShaderButtons() {
    const container = this._el.querySelector('#cp-shaders');
    for (const mode of this._postFx.modes) {
      const btn = document.createElement('button');
      btn.className = 'cp-shader-btn';
      btn.textContent = mode.toUpperCase();
      btn.dataset.mode = mode;
      btn.addEventListener('click', () => {
        this._postFx.setMode(mode);
        container.querySelectorAll('.cp-shader-btn').forEach((b) => {
          b.classList.toggle('active', b.dataset.mode === mode);
        });
      });
      if (mode === 'none') btn.classList.add('active');
      container.appendChild(btn);
    }
  }
}
