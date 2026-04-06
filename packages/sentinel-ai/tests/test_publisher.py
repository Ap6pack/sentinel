

import uuid
from unittest.mock import AsyncMock

from sentinel_ai.models.alert import AlertRecord
from sentinel_ai.publisher import publish_alert


async def test_publish_alert():
    mock_bus = AsyncMock()
    mock_bus.publish = AsyncMock()

    alert = AlertRecord(
        id=str(uuid.uuid4()),
        confidence=0.87,
        summary="BSSID match detected",
        reasoning="Test reasoning",
        recommended_action="Review profile",
        linked_entity_ids=["entity-1", "entity-2"],
        lat=51.5074,
        lon=-0.1278,
        event_ids=["evt-1"],
    )

    await publish_alert(mock_bus, alert)

    mock_bus.publish.assert_called_once()
    envelope = mock_bus.publish.call_args[0][0]
    assert envelope.source == "ai"
    assert envelope.kind == "alert"
    assert envelope.entity_id == alert.id
    assert envelope.lat == 51.5074
    assert envelope.payload["confidence"] == 0.87
    assert envelope.payload["summary"] == "BSSID match detected"
    assert "entity-1" in envelope.payload["linked_entity_ids"]
