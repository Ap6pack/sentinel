

from sentinel_core.health.aggregator import aggregate_health


async def test_aggregate_health_no_modules_running():
    """When no modules are running, all should show unreachable."""
    result = await aggregate_health()
    assert result["overall"] == "degraded"
    assert "modules" in result
    for name in ("rf", "osint", "ai"):
        assert result["modules"][name]["status"] == "unreachable"
    assert "ts" in result
