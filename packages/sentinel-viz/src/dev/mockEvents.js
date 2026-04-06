

/**
 * Mock event generator for development without a running backend.
 * Feeds synthetic EventEnvelope objects into the LayerManager
 * at realistic intervals.
 */

const MOCK_PROFILES = [
  {
    entity_id: 'profile-mock-001',
    lat: 51.5055,
    lon: -0.1285,
    confidence: 0.85,
    sources: ['wigle', 'strava'],
    identifiers: { bssid: 'AA:BB:CC:DD:EE:01', strava_id: 'athlete-42', ssid: 'HomeNet_Smith' },
  },
  {
    entity_id: 'profile-mock-002',
    lat: 51.4712,
    lon: -0.4511,
    confidence: 0.55,
    sources: ['google_reviews'],
    identifiers: { username: 'jdoe_reviews' },
  },
  {
    entity_id: 'profile-mock-003',
    lat: 51.5124,
    lon: -0.0918,
    confidence: 0.35,
    sources: ['property'],
    identifiers: {},
  },
];

const MOCK_ALERTS = [
  {
    entity_id: 'alert-mock-001',
    lat: 51.5090,
    lon: -0.1310,
    confidence: 0.92,
    summary: 'Unusual RF cluster near Parliament',
    reasoning: 'Three unregistered WiFi APs appeared within 200m of Westminster in the last 30 minutes, correlated with a Strava user whose home cluster is 150km away.',
    recommended_action: 'Cross-reference with CCTV feeds and dispatch ground unit for visual confirmation.',
    title: 'RF Anomaly',
  },
  {
    entity_id: 'alert-mock-002',
    lat: 51.4700,
    lon: -0.4540,
    confidence: 0.68,
    summary: 'Profile match near Heathrow perimeter',
    reasoning: 'OSINT profile with 3 linked identifiers detected within the restricted zone. Username match across GitHub and Strava with route origin clustering inside the airport fence line.',
    recommended_action: 'Review profile identifiers and compare against watchlist. Consider elevated monitoring.',
    title: 'Identity Correlation',
  },
];

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

  // Emit profile events once at startup (profiles are static)
  for (const p of MOCK_PROFILES) {
    onEvent({
      id: crypto.randomUUID(),
      ts: new Date().toISOString(),
      source: 'osint',
      kind: 'profile',
      lat: p.lat,
      lon: p.lon,
      entity_id: p.entity_id,
      payload: {
        confidence: p.confidence,
        sources: p.sources,
        identifiers: p.identifiers,
      },
    });
  }

  // Emit alert events once at startup (after a short delay for visual effect)
  setTimeout(() => {
    for (const a of MOCK_ALERTS) {
      onEvent({
        id: crypto.randomUUID(),
        ts: new Date().toISOString(),
        source: 'ai',
        kind: 'alert',
        lat: a.lat,
        lon: a.lon,
        entity_id: a.entity_id,
        payload: {
          confidence: a.confidence,
          summary: a.summary,
          reasoning: a.reasoning,
          recommended_action: a.recommended_action,
          title: a.title,
        },
      });
    }
  }, 2000);

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
