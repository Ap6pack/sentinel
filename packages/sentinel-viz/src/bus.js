

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

/**
 * WebSocket client that consumes EventEnvelope objects from sentinel-core
 * and routes them to the LayerManager via the onEvent callback.
 */
export class BusClient {
  /**
   * @param {string} url - WebSocket endpoint URL
   * @param {function(Object): void} onEvent - called with each parsed envelope
   */
  constructor(url, onEvent) {
    this._url = url;
    this._onEvent = onEvent;
    this._ws = null;
    this._reconnectDelay = RECONNECT_BASE_MS;
    this._filterSpec = null;
  }

  /**
   * Open the WebSocket connection. Optionally send a filter spec so the
   * server only forwards matching event kinds.
   * @param {Object|null} filterSpec
   */
  connect(filterSpec = null) {
    this._filterSpec = filterSpec;
    this._open();
  }

  /** @private */
  _open() {
    this._ws = new WebSocket(this._url);

    this._ws.onopen = () => {
      console.log('[bus] connected');
      this._reconnectDelay = RECONNECT_BASE_MS;
      if (this._filterSpec) {
        this._ws.send(JSON.stringify({ type: 'filter', spec: this._filterSpec }));
      }
    };

    this._ws.onmessage = (evt) => {
      try {
        const envelope = JSON.parse(evt.data);
        this._onEvent(envelope);
      } catch (e) {
        console.warn('[bus] bad message', e);
      }
    };

    this._ws.onclose = () => {
      console.log(`[bus] closed, reconnecting in ${this._reconnectDelay}ms`);
      setTimeout(() => this._open(), this._reconnectDelay);
      this._reconnectDelay = Math.min(this._reconnectDelay * 2, RECONNECT_MAX_MS);
    };

    this._ws.onerror = (e) => {
      console.warn('[bus] error', e);
    };
  }

  /** Close the connection and stop reconnecting. */
  disconnect() {
    this._reconnectDelay = RECONNECT_MAX_MS * 2; // prevent reconnect
    this._ws?.close();
  }
}
