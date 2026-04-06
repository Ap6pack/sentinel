

import asyncio

from sentinel_common.envelope import EventEnvelope
from sentinel_common.kinds import EventKind

from sentinel_ai.engine.window import EventWindow


async def test_window_flushes_when_min_events_reached():
    """Window flushes batch when >= min_events are buffered."""
    received_batches: list[list[EventEnvelope]] = []

    async def on_ready(batch: list[EventEnvelope]) -> None:
        received_batches.append(batch)

    window = EventWindow(on_window_ready=on_ready, window_seconds=1, min_events=2)
    await window.start()

    e1 = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="w1",
        lat=51.5, lon=-0.1, payload={"bssid": "AA:BB:CC:DD:EE:01"},
    )
    e2 = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="w2",
        lat=51.5, lon=-0.1, payload={"bssid": "AA:BB:CC:DD:EE:02"},
    )

    await window.push(e1)
    await window.push(e2)

    # Wait for flush
    await asyncio.sleep(1.5)
    await window.stop()

    assert len(received_batches) == 1
    assert len(received_batches[0]) == 2


async def test_window_discards_below_min_events():
    """Window discards events when < min_events in the window."""
    received_batches: list[list[EventEnvelope]] = []

    async def on_ready(batch: list[EventEnvelope]) -> None:
        received_batches.append(batch)

    window = EventWindow(on_window_ready=on_ready, window_seconds=1, min_events=3)
    await window.start()

    e1 = EventEnvelope(
        source="rf", kind=EventKind.WIFI, entity_id="w1",
        lat=51.5, lon=-0.1, payload={},
    )
    await window.push(e1)

    await asyncio.sleep(1.5)
    await window.stop()

    assert len(received_batches) == 0
