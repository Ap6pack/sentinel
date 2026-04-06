

import { ScreenSpaceEventHandler, ScreenSpaceEventType, defined } from 'cesium';

/**
 * Click-on-entity info popup. Shows entity payload in a floating panel.
 * When a ProfileLayer pin is clicked, renders OSINT-specific details.
 * When an AlertLayer pin is clicked, renders alert details.
 */
export class InfoPanel {
  /**
   * @param {import('cesium').Viewer} viewer
   * @param {import('../layers/ProfileLayer.js').ProfileLayer} [profileLayer]
   * @param {import('../layers/AlertLayer.js').AlertLayer} [alertLayer]
   */
  constructor(viewer, profileLayer = null, alertLayer = null) {
    this._viewer = viewer;
    this._profileLayer = profileLayer;
    this._alertLayer = alertLayer;
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

  /**
   * Set or replace the profile layer reference (for deferred wiring).
   * @param {import('../layers/ProfileLayer.js').ProfileLayer} layer
   */
  setProfileLayer(layer) {
    this._profileLayer = layer;
  }

  /** @private */
  _show(entity) {
    const entityId = typeof entity.id === 'string' ? entity.id : entity.id?.toString();

    // Check if this is a profile entity
    const profile = this._profileLayer?.getProfile(entityId);
    if (profile) {
      this._showProfile(profile);
      return;
    }

    // Check if this is an alert entity
    const alert = this._alertLayer?.getAlert(entityId);
    if (alert) {
      this._showAlert(alert);
      return;
    }

    // Generic entity display
    const props = [];
    if (entityId) props.push(`<strong>ID:</strong> ${this._esc(entityId)}`);
    if (entity.label?.text?._value) {
      props.push(`<strong>Label:</strong> ${this._esc(entity.label.text._value)}`);
    }
    this._render('Entity Info', props.join('<br>'));
  }

  /**
   * Render OSINT profile details.
   * @param {Object} profile
   * @private
   */
  _showProfile(profile) {
    const conf = profile.confidence ?? 0;
    const pct = Math.round(conf * 100);
    const barColor = conf >= 0.8 ? '#e74c3c' : conf >= 0.5 ? '#ff69b4' : '#f39c12';

    const sourceTags = (profile.sources || [])
      .map((s) => `<span class="ip-tag">${this._esc(s)}</span>`)
      .join(' ');

    const idRows = Object.entries(profile.identifiers || {})
      .map(
        ([k, v]) =>
          `<tr><td class="ip-id-key">${this._esc(k)}</td><td class="ip-id-val">${this._esc(String(v))}</td></tr>`
      )
      .join('');

    const body = `
      <div class="ip-field">
        <span class="ip-label">Entity ID</span>
        <span class="ip-value ip-mono">${this._esc(profile.entity_id)}</span>
      </div>
      <div class="ip-field">
        <span class="ip-label">Confidence</span>
        <div class="ip-confidence">
          <div class="ip-conf-bar" style="width:${pct}%;background:${barColor}"></div>
          <span class="ip-conf-text">${pct}%</span>
        </div>
      </div>
      <div class="ip-field">
        <span class="ip-label">Sources</span>
        <div class="ip-sources">${sourceTags || '<em>none</em>'}</div>
      </div>
      ${
        idRows
          ? `<div class="ip-field">
              <span class="ip-label">Identifiers</span>
              <table class="ip-id-table">${idRows}</table>
            </div>`
          : ''
      }
      <div class="ip-field">
        <span class="ip-label">Coordinates</span>
        <span class="ip-value ip-mono">${profile.lat?.toFixed(5) ?? '?'}, ${profile.lon?.toFixed(5) ?? '?'}</span>
      </div>
    `;

    this._render('OSINT Profile', body);
  }

  /**
   * Render AI alert details.
   * @param {Object} alert
   * @private
   */
  _showAlert(alert) {
    const conf = alert.confidence ?? 0;
    const pct = Math.round(conf * 100);
    const barColor = pct >= 80 ? '#e74c3c' : pct >= 50 ? '#f39c12' : '#888';

    const body = `
      <div class="ip-field">
        <span class="ip-label">Confidence</span>
        <div class="ip-confidence">
          <div class="ip-conf-bar" style="width:${pct}%;background:${barColor}"></div>
          <span class="ip-conf-text">${pct}%</span>
        </div>
      </div>
      ${alert.summary ? `<div class="ip-field"><span class="ip-label">Summary</span><span class="ip-value">${this._esc(alert.summary)}</span></div>` : ''}
      ${alert.reasoning ? `<div class="ip-field"><span class="ip-label">Reasoning</span><span class="ip-value" style="font-size:11px">${this._esc(alert.reasoning)}</span></div>` : ''}
      ${alert.recommended_action ? `<div class="ip-field"><span class="ip-label">Recommended Action</span><span class="ip-value" style="color:#f39c12">${this._esc(alert.recommended_action)}</span></div>` : ''}
      <div class="ip-field">
        <span class="ip-label">Coordinates</span>
        <span class="ip-value ip-mono">${alert.lat?.toFixed(5) ?? '?'}, ${alert.lon?.toFixed(5) ?? '?'}</span>
      </div>
    `;

    this._render('AI Alert', body);
  }

  /**
   * Render panel with title and body HTML.
   * @param {string} title
   * @param {string} bodyHtml
   * @private
   */
  _render(title, bodyHtml) {
    this._el.innerHTML = `
      <div class="ip-header">
        <span>${this._esc(title)}</span>
        <button id="ip-close">&times;</button>
      </div>
      <div class="ip-body">${bodyHtml}</div>
    `;
    this._el.style.display = 'block';
    this._el.querySelector('#ip-close').addEventListener('click', () => this._hide());
  }

  /** @private */
  _hide() {
    this._el.style.display = 'none';
  }

  /**
   * Escape HTML to prevent XSS from profile data.
   * @param {string} str
   * @returns {string}
   * @private
   */
  _esc(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }
}
