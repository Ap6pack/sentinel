

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path

import anthropic

from sentinel_common.envelope import EventEnvelope

from sentinel_ai.config import ai_settings
from sentinel_ai.models.alert import AlertRecord

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "correlate.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text()

# Rate limiting
_call_count = 0
_hour_start = time.monotonic()


def _check_rate_limit() -> None:
    global _call_count, _hour_start
    elapsed = time.monotonic() - _hour_start
    if elapsed > 3600:
        _call_count = 0
        _hour_start = time.monotonic()
    if _call_count >= ai_settings.max_calls_per_hour:
        raise RuntimeError(
            f"Claude API rate limit reached ({ai_settings.max_calls_per_hour}/hr)"
        )
    _call_count += 1


def _build_context(
    events: list[EventEnvelope],
    profiles: list[dict],
) -> dict:
    """Build the context payload for Claude."""
    return {
        "events": [
            {
                "kind": e.kind,
                "ts": e.ts.isoformat(),
                "lat": e.lat,
                "lon": e.lon,
                "entity_id": e.entity_id,
                "payload": e.payload,
            }
            for e in events
        ],
        "profiles": [
            {
                "entity_id": p.get("entity_id"),
                "lat": p.get("lat"),
                "lon": p.get("lon"),
                "confidence": p.get("confidence"),
                "sources": p.get("sources"),
                "identifiers": p.get("identifiers"),
            }
            for p in profiles
        ],
    }


async def correlate_batch(
    events: list[EventEnvelope],
    profiles: list[dict],
    client: anthropic.AsyncAnthropic | None = None,
) -> AlertRecord | None:
    """
    Given a batch of events and matching profiles, call Claude to reason
    about whether an alert should be raised. Returns None if no alert warranted.
    """
    if not profiles:
        return None

    _check_rate_limit()

    if client is None:
        client = anthropic.AsyncAnthropic(api_key=ai_settings.anthropic_api_key)

    context = _build_context(events, profiles)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyse this observation batch and profiles:\n\n"
                        + json.dumps(context, indent=2)
                    ),
                }
            ],
        )
        raw = response.content[0].text
        result = json.loads(raw)

        if not result.get("alert_warranted", False):
            logger.info("[correlator] no alert warranted for batch of %d events", len(events))
            return None

        alert = AlertRecord(
            id=str(uuid.uuid4()),
            confidence=float(result.get("confidence", 0.5)),
            summary=result.get("summary", ""),
            reasoning=result.get("reasoning", ""),
            recommended_action=result.get("recommended_action", ""),
            linked_entity_ids=result.get("linked_entity_ids", []),
            lat=result.get("lat"),
            lon=result.get("lon"),
            event_ids=[e.id for e in events],
        )
        logger.info(
            "[correlator] alert generated: %s (confidence=%.2f)",
            alert.id,
            alert.confidence,
        )
        return alert

    except json.JSONDecodeError:
        logger.warning("[correlator] Claude response was not valid JSON")
        return None
    except anthropic.RateLimitError:
        logger.warning("[correlator] Claude API rate limited")
        return None
    except Exception:
        logger.exception("[correlator] Claude API error")
        return None
