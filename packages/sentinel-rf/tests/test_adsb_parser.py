

import json
from pathlib import Path

import pytest

from sentinel_common.kinds import EventKind
from sentinel_rf.decoders.adsb import ADSBDecoder, parse_aircraft

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_data() -> dict:
    return json.loads((FIXTURES_DIR / "aircraft_sample.json").read_text())


def test_parse_valid_aircraft():
    ac = {
        "hex": "3c4a6f",
        "flight": "DLH441  ",
        "lat": 51.5074,
        "lon": -0.1278,
        "altitude": 35000,
        "speed": 430,
        "track": 278,
        "squawk": "1000",
        "rssi": -8.5,
        "messages": 142,
    }
    envelope = parse_aircraft(ac)
    assert envelope is not None
    assert envelope.entity_id == "ICAO-3C4A6F"
    assert envelope.kind == EventKind.AIRCRAFT
    assert envelope.source == "rf"
    assert envelope.lat == 51.5074
    assert envelope.lon == -0.1278
    assert envelope.alt_m == pytest.approx(35000 * 0.3048)
    assert envelope.payload["callsign"] == "DLH441"
    assert envelope.payload["speed_kts"] == 430
    assert envelope.payload["heading"] == 278
    assert envelope.payload["squawk"] == "1000"


def test_parse_missing_coords():
    """Aircraft without lat/lon should return None."""
    ac = {"hex": "nocoord", "flight": "GHOST", "altitude": 10000, "messages": 5}
    assert parse_aircraft(ac) is None


def test_parse_empty_hex():
    """Aircraft with empty hex should return None."""
    ac = {"hex": "", "lat": 50.0, "lon": 0.0, "altitude": 5000}
    assert parse_aircraft(ac) is None


def test_parse_invalid_lat_returns_none():
    """Aircraft with out-of-range lat should return None (pre-validated before envelope)."""
    ac = {"hex": "bad000", "lat": 200.0, "lon": 0.0, "altitude": 1000}
    assert parse_aircraft(ac) is None


def test_parse_no_altitude():
    """Aircraft without altitude should produce envelope with alt_m=None."""
    ac = {"hex": "abc123", "lat": 40.0, "lon": -74.0}
    envelope = parse_aircraft(ac)
    assert envelope is not None
    assert envelope.alt_m is None


def test_parse_all_valid_from_fixture(sample_data):
    """The fixture should produce exactly 3 valid envelopes (3 valid, 1 invalid-lat, 1 no-coord, 1 empty-hex)."""
    valid = []
    for ac in sample_data["aircraft"]:
        try:
            env = parse_aircraft(ac)
            if env is not None:
                valid.append(env)
        except ValueError:
            pass  # Expected for out-of-range coords
    assert len(valid) == 3
    icaos = {e.entity_id for e in valid}
    assert icaos == {"ICAO-3C4A6F", "ICAO-40762F", "ICAO-A1B2C3"}


def test_adsb_decoder_attributes():
    """ADSBDecoder should have correct name and default config."""
    decoder = ADSBDecoder(device_index=0)
    assert decoder.name == "adsb"
    assert decoder.device_index == 0
    assert decoder._running is False


def test_adsb_decoder_build_command():
    decoder = ADSBDecoder(device_index=2)
    cmd = decoder._build_command()
    assert cmd[0] == "dump1090_rs"
    assert "--device-index" in cmd
    assert "2" in cmd


def test_adsb_decoder_parse_line_returns_none():
    """_parse_line is not used for poll-based decoder."""
    decoder = ADSBDecoder()
    assert decoder._parse_line("anything") is None
