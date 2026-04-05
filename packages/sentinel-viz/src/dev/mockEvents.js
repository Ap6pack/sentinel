// Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

/**
 * Mock event generator for development without a running backend.
 * Feeds synthetic EventEnvelope objects into the LayerManager
 * at realistic intervals.
 */

const MOCK_AIRCRAFT = [
  {
    entity_id: 'ICAO-3C4A6F',
    callsign: 'DLH441',
    lat: 51.5074,
    lon: -0.1278,
    alt_m: 10668,
    speed_kts: 430,
    heading: 278,
  },
  {
    entity_id: 'ICAO-40762F',
    callsign: 'BAW256',
    lat: 51.47,
    lon: -0.4543,
    alt_m: 1585,
    speed_kts: 180,
    heading: 90,
  },
  {
    entity_id: 'ICAO-A1B2C3',
    callsign: 'UAL901',
    lat: 48.8566,
    lon: 2.3522,
    alt_m: 12497,
    speed_kts: 490,
    heading: 45,
  },
];

/**
 * Start feeding mock aircraft events into the given callback.
 * Aircraft drift slightly on each tick to simulate movement.
 * @param {function(Object): void} onEvent
 * @param {number} intervalMs
 * @returns {number} interval ID for clearInterval
 */
export function startMockFeed(onEvent, intervalMs = 1000) {
  const state = MOCK_AIRCRAFT.map((a) => ({ ...a }));

  return setInterval(() => {
    for (const ac of state) {
      // Drift position slightly
      ac.lat += (Math.random() - 0.5) * 0.005;
      ac.lon += (Math.random() - 0.5) * 0.005;

      onEvent({
        id: crypto.randomUUID(),
        ts: new Date().toISOString(),
        source: 'rf',
        kind: 'aircraft',
        lat: ac.lat,
        lon: ac.lon,
        alt_m: ac.alt_m,
        entity_id: ac.entity_id,
        payload: {
          callsign: ac.callsign,
          speed_kts: ac.speed_kts,
          heading: ac.heading,
        },
      });
    }
  }, intervalMs);
}
