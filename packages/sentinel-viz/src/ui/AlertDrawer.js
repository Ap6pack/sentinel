

const MAX_DRAWER_ALERTS = 50;

/**
 * Right sidebar alert feed. Displays AI-generated alerts with
 * confidence score, summary, reasoning, recommended action, and
 * a fly-to button that centres the globe on the alert location.
 */
export class AlertDrawer {
  /**
   * @param {import('../layers/AlertLayer.js').AlertLayer} alertLayer
   */
  constructor(alertLayer) {
    this._alertLayer = alertLayer;
    this._el = null;
    this._listEl = null;
    this._count = 0;
    this._collapsed = false;
  }

  /** Mount the drawer into the DOM and subscribe to alert events. */
  mount() {
    this._el = document.createElement('div');
    this._el.id = 'alert-drawer';
    this._el.innerHTML = `
      <div class="ad-header">
        <span>ALERTS</span>
        <span id="ad-count" class="ad-count">0</span>
        <button id="ad-toggle" class="ad-toggle-btn" title="Collapse">&ndash;</button>
      </div>
      <div id="ad-list" class="ad-list"></div>
    `;
    document.body.appendChild(this._el);

    this._listEl = this._el.querySelector('#ad-list');
    this._countEl = this._el.querySelector('#ad-count');
    this._el.querySelector('#ad-toggle').addEventListener('click', () => {
      this._collapsed = !this._collapsed;
      this._listEl.style.display = this._collapsed ? 'none' : 'block';
      this._el.querySelector('#ad-toggle').textContent = this._collapsed ? '+' : '\u2013';
    });

    // Subscribe to new alerts from the layer
    this._alertLayer.onAlert((alert) => this._addAlert(alert));
  }

  /**
   * Add an alert card to the drawer.
   * @param {Object} alert
   * @private
   */
  _addAlert(alert) {
    if (this._count >= MAX_DRAWER_ALERTS) {
      // Remove oldest card
      const last = this._listEl.lastElementChild;
      if (last) last.remove();
    } else {
      this._count++;
    }

    this._countEl.textContent = String(this._count);

    const pct = Math.round((alert.confidence ?? 0) * 100);
    const barColor = pct >= 80 ? '#e74c3c' : pct >= 50 ? '#f39c12' : '#888';
    const ts = alert.ts ? new Date(alert.ts).toLocaleTimeString() : '';

    const card = document.createElement('div');
    card.className = 'ad-card';
    card.innerHTML = `
      <div class="ad-card-top">
        <div class="ad-conf-bar-wrap">
          <div class="ad-conf-bar" style="width:${pct}%;background:${barColor}"></div>
          <span class="ad-conf-text">${pct}%</span>
        </div>
        <span class="ad-ts">${this._esc(ts)}</span>
      </div>
      <div class="ad-summary">${this._esc(alert.summary || alert.title || 'Alert')}</div>
      ${alert.reasoning ? `<div class="ad-section"><span class="ad-section-label">REASONING</span><div class="ad-section-text">${this._esc(alert.reasoning)}</div></div>` : ''}
      ${alert.recommended_action ? `<div class="ad-section"><span class="ad-section-label">ACTION</span><div class="ad-section-text">${this._esc(alert.recommended_action)}</div></div>` : ''}
      <button class="ad-flyto" data-id="${this._esc(alert.entity_id)}">FLY TO</button>
    `;

    card.querySelector('.ad-flyto').addEventListener('click', () => {
      this._alertLayer.flyToAlert(alert.entity_id);
    });

    // Prepend — newest on top
    this._listEl.prepend(card);
  }

  /**
   * Escape HTML to prevent XSS.
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
