

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from sentinel_ai.engine.correlator import correlate_batch

FIXTURES = Path(__file__).parent / "fixtures"


def _make_mock_client(response_file: str) -> AsyncMock:
    """Create a mock AsyncAnthropic client that returns fixture data."""
    response_text = (FIXTURES / response_file).read_text()

    mock_content_block = MagicMock()
    mock_content_block.text = response_text

    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


def _wifi_event() -> EventEnvelope:
    return EventEnvelope(
        source="rf",
        kind=EventKind.WIFI,
        lat=51.5074,
        lon=-0.1278,
        entity_id="WIFI-AA:BB:CC:DD:EE:FF",
        payload={"bssid": "AA:BB:CC:DD:EE:FF", "ssid": "HomeNetwork_5G"},
    )


def _profile() -> dict:
    return {
        "entity_id": "profile-abc123",
        "lat": 51.5075,
        "lon": -0.1279,
        "confidence": 0.8,
        "sources": ["wigle"],
        "identifiers": {"bssid": "AA:BB:CC:DD:EE:FF"},
    }


async def test_correlate_batch_generates_alert():
    mock_client = _make_mock_client("claude_alert_response.json")

    alert = await correlate_batch(
        [_wifi_event()],
        [_profile()],
        client=mock_client,
    )

    assert alert is not None
    assert alert.confidence == 0.87
    assert "profile-abc123" in alert.linked_entity_ids
    assert "WiFi BSSID" in alert.summary
    assert alert.lat == 51.5074
    assert alert.lon == -0.1278

    # Verify Claude was called with correct structure
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-sonnet-4-6"
    assert call_args.kwargs["max_tokens"] == 1000


async def test_correlate_batch_no_alert():
    mock_client = _make_mock_client("claude_no_alert_response.json")

    alert = await correlate_batch(
        [_wifi_event()],
        [_profile()],
        client=mock_client,
    )

    assert alert is None


async def test_correlate_batch_no_profiles():
    alert = await correlate_batch([_wifi_event()], [])
    assert alert is None


async def test_correlate_batch_handles_invalid_json():
    mock_content_block = MagicMock()
    mock_content_block.text = "This is not valid JSON at all"

    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    alert = await correlate_batch(
        [_wifi_event()],
        [_profile()],
        client=mock_client,
    )

    assert alert is None


async def test_correlate_batch_handles_api_error():
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        side_effect=Exception("API connection failed")
    )

    alert = await correlate_batch(
        [_wifi_event()],
        [_profile()],
        client=mock_client,
    )

    assert alert is None


async def test_correlate_batch_event_ids_recorded():
    mock_client = _make_mock_client("claude_alert_response.json")

    events = [_wifi_event(), _wifi_event()]
    alert = await correlate_batch(events, [_profile()], client=mock_client)

    assert alert is not None
    assert len(alert.event_ids) == 2
    assert alert.event_ids[0] == events[0].id
    assert alert.event_ids[1] == events[1].id
