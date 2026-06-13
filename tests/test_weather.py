"""
Tests for weather integration (Open-Meteo API).
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server import extract_city, WMO_CODES, WEATHER_KEYWORDS


def test_extract_city_default():
    """No known city → returns Natolin (default)."""
    name, lat, lon = extract_city("Jaka jest pogoda?")
    assert name == "Natolin"
    assert lat == 52.136393
    assert lon == 20.622824


def test_extract_city_warszawa():
    """Detects Warszawa in query."""
    name, lat, lon = extract_city("Jaka pogoda w Warszawie jutro?")
    assert name == "warszawie"
    assert lat == 52.23


def test_extract_city_pruszkow():
    """Detects Pruszków in query (matched by 'pruszkow' key)."""
    name, lat, lon = extract_city("Czy w Pruszkowie będzie padać?")
    assert name == "pruszkow"  # without diacritic — matches substring
    assert lat == 52.17


def test_extract_city_krakow():
    """Detects Kraków in query (matched by 'krakow' key)."""
    name, lat, lon = extract_city("Pogoda w Krakowie")
    assert name == "krakow"  # without diacritic — matches substring
    assert lat == 50.06


def test_wmo_codes_cover_all_common():
    """WMO codes mapping covers all used codes."""
    for code in [0, 1, 2, 3, 45, 51, 61, 63, 65, 71, 80, 95]:
        assert code in WMO_CODES, f"Missing WMO code {code}"


def test_weather_keywords_match_polish():
    """Polish weather keywords are matched."""
    assert WEATHER_KEYWORDS.search("Jaka będzie pogoda jutro?")
    assert WEATHER_KEYWORDS.search("Czy będzie padać deszcz?")
    assert WEATHER_KEYWORDS.search("Jaka jest temperatura?")
    assert WEATHER_KEYWORDS.search("Czy będzie śnieg?")
    assert WEATHER_KEYWORDS.search("Czy będzie zimno?")


def test_weather_keywords_no_false_positive():
    """Non-weather queries don't trigger weather detection."""
    assert not WEATHER_KEYWORDS.search("Jaki jest dzisiaj dzień?")
    assert not WEATHER_KEYWORDS.search("Kto ma imieniny?")
