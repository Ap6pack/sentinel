

/**
 * Centralised configuration — all env vars read here, nowhere else.
 * Values come from .env.local via Vite's import.meta.env.
 */
export const config = {
  cesiumToken: import.meta.env.VITE_CESIUM_TOKEN || '',
  wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws/stream',
  osintApi: import.meta.env.VITE_OSINT_API || 'http://localhost:8080/api/osint',
};
