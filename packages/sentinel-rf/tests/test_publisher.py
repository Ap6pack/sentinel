

from unittest.mock import MagicMock, patch

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind
from sentinel_rf.publisher import SyncRFPublisher


def _make_publisher() -> SyncRFPublisher:
    """Create a SyncRFPublisher with a mocked Redis client."""
    with patch("sentinel_rf.publisher.redis") as mock_redis:
        mock_client = MagicMock()
        mock_redis.from_url.return_value = mock_client
        pub = SyncRFPublisher(redis_url="redis://fake:6379")
    return pub, mock_client


def test_publish_passthrough():
    """Events with coords should pass through unchanged."""
    pub, mock_client = _make_publisher()

    env = EventEnvelope(
        source="rf", kind=EventKind.AIRCRAFT, lat=51.5, lon=-0.1, entity_id="TEST-1"
    )
    pub.publish(env)

    mock_client.xadd.assert_called_once()
    call_args = mock_client.xadd.call_args
    assert call_args[0][0] == "sentinel:events"


def test_gps_enrichment():
    """Events without coords should be enriched with cached GPS."""
    pub, mock_client = _make_publisher()
    pub._gps_lat = 48.8
    pub._gps_lon = 2.3

    env = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="WIFI-AA:BB:CC:DD:EE:FF"
    )
    pub.publish(env)

    mock_client.xadd.assert_called_once()
    # Verify the data was enriched by parsing the JSON
    import json
    data = json.loads(mock_client.xadd.call_args[0][1]["data"])
    assert data["lat"] == 48.8
    assert data["lon"] == 2.3


def test_no_gps_no_enrichment():
    """Without GPS fix, events without coords stay without coords."""
    pub, mock_client = _make_publisher()

    env = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="WIFI-AA:BB:CC:DD:EE:FF"
    )
    pub.publish(env)

    import json
    data = json.loads(mock_client.xadd.call_args[0][1]["data"])
    assert data["lat"] is None
    assert data["lon"] is None
