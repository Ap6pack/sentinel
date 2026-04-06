

import { ScreenSpaceEventHandler, ScreenSpaceEventType, defined } from 'cesium';

/**
 * Click-on-entity info popup. Shows entity payload in a floating panel.
 */
export class InfoPanel {
  /** @param {import('cesium').Viewer} viewer */
  constructor(viewer) {
    this._viewer = viewer;
    this._el = null;
    this._handler = null;
  }

  /** Mount the panel and bind click events. */
  mount() {
    this._el = document.createElement('div');
    this._el.id = 'info-panel';
    this._el.style.display = 'none';
    document.body.appendChild(this._el);

    this._handler = new ScreenSpaceEventHandler(this._viewer.scene.canvas);
    this._handler.setInputAction((click) => {
      const picked = this._viewer.scene.pick(click.position);
      if (defined(picked) && defined(picked.id)) {
        this._show(picked.id);
      } else {
        this._hide();
      }
    }, ScreenSpaceEventType.LEFT_CLICK);
  }

  /** @private */
  _show(entity) {
    const props = [];
    if (entity.id) props.push(`<strong>ID:</strong> ${entity.id}`);
    if (entity.label?.text?._value) {
      props.push(`<strong>Label:</strong> ${entity.label.text._value}`);
    }
    this._el.innerHTML = `
      <div class="ip-header">
        <span>Entity Info</span>
        <button id="ip-close">&times;</button>
      </div>
      <div class="ip-body">${props.join('<br>')}</div>
    `;
    this._el.style.display = 'block';
    this._el.querySelector('#ip-close').addEventListener('click', () => this._hide());
  }

  /** @private */
  _hide() {
    this._el.style.display = 'none';
  }
}
