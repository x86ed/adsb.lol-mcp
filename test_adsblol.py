import json
import pytest
from unittest import mock
import httpx
from adsblol import (
    make_api_request, format_markdown, get_pia, get_mil, get_ladd, 
    get_squawk, get_type, get_registration, get_icao_hex, get_callsign,
    get_search_radius, get_closest
)

# Sample mock data for testing
MOCK_AIRCRAFT = {
    "hex": "a1b2c3",
    "flight": "UAL123  ",
    "alt_baro": 35000,
    "gs": 450.3,
    "lat": 37.7749,
    "lon": -122.4194,
    "track": 270,
    "type": "B738",
    "mlat": [],
    "tisb": [],
    "messages": 1234,
    "seen": 5,
    "rssi": -10.2,
    "squawk": "1200"
}

MOCK_RESPONSE = {
    "ac": [MOCK_AIRCRAFT],
    "total": 1,
    "ctime": 1616917200,
    "now": 1616917205,
    "ptime": 5,
    "msg": "No error"
}

EMPTY_RESPONSE = {
    "ac": [],
    "total": 0,
    "ctime": 1616917200,
    "now": 1616917205,
    "ptime": 5,
    "msg": "No error"
}


# Test the format_markdown function
def test_format_markdown():
    # Test simple dictionary formatting
    simple_dict = {"key1": "value1", "key2": 123}
    result = format_markdown(simple_dict)
    assert "# key1" in result
    assert "value1" in result
    assert "# key2" in result
    assert "123" in result

    # Test nested dictionary formatting
    nested_dict = {"parent": {"child1": "value1", "child2": 123}}
    result = format_markdown(nested_dict)
    assert "# parent" in result
    assert "## child1" in result
    assert "value1" in result
    assert "## child2" in result
    assert "123" in result

    # Test list formatting
    list_dict = {"items": [1, 2, 3]}
    result = format_markdown(list_dict)
    assert "# items" in result
    assert "* 1" in result
    assert "* 2" in result
    assert "* 3" in result

    # Test None value formatting
    none_dict = {"null_value": None}
    result = format_markdown(none_dict)
    assert "# null_value" in result
    assert "*None*" in result


# Mock the API request function
@pytest.fixture
def mock_api_response():
    with mock.patch("adsblol.make_api_request") as mock_request:
        yield mock_request


# Test the API request function
@pytest.mark.asyncio
async def test_make_api_request():
    # Mock a successful response
    with mock.patch.object(httpx.AsyncClient, 'get') as mock_get:
        mock_response = mock.MagicMock()
        mock_response.json.return_value = MOCK_RESPONSE
        mock_response.raise_for_status = mock.MagicMock()
        mock_get.return_value = mock_response

        result = await make_api_request("https://api.adsb.lol/v2/test")
        assert result == MOCK_RESPONSE
        mock_get.assert_called_once()

    # Mock an exception
    with mock.patch.object(httpx.AsyncClient, 'get') as mock_get:
        mock_get.side_effect = Exception("API Error")
        result = await make_api_request("https://api.adsb.lol/v2/test")
        assert result is None
        mock_get.assert_called_once()


# Test individual endpoint functions
@pytest.mark.asyncio
async def test_get_pia(mock_api_response):
    # Test successful response with aircraft
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_pia()
    assert "flight" in result
    assert "UAL123" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/pia")

    # Test empty response
    mock_api_response.return_value = EMPTY_RESPONSE
    result = await get_pia()
    assert "No PIA aircraft found." in result

    # Test error response
    mock_api_response.return_value = None
    result = await get_pia()
    assert "No PIA aircraft found." in result


@pytest.mark.asyncio
async def test_get_mil(mock_api_response):
    # Test successful response with aircraft
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_mil()
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/mil")

    # Test empty response
    mock_api_response.return_value = EMPTY_RESPONSE
    result = await get_mil()
    assert "No military aircraft found." in result


@pytest.mark.asyncio
async def test_get_ladd(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_ladd()
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/ladd")


@pytest.mark.asyncio
async def test_get_squawk(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_squawk("7700")
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/sqk/7700")


@pytest.mark.asyncio
async def test_get_type(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_type("B738")
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/type/B738")


@pytest.mark.asyncio
async def test_get_registration(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_registration("N12345")
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/reg/N12345")


@pytest.mark.asyncio
async def test_get_icao_hex(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_icao_hex("a1b2c3")
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/icao/a1b2c3")


@pytest.mark.asyncio
async def test_get_callsign(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_callsign("UAL123")
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/callsign/UAL123")


@pytest.mark.asyncio
async def test_get_search_radius(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_search_radius("37.7749", "-122.4194", "100")
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/point/37.7749/-122.4194/100")


@pytest.mark.asyncio
async def test_get_closest(mock_api_response):
    # Test successful response
    mock_api_response.return_value = MOCK_RESPONSE
    result = await get_closest("37.7749", "-122.4194", "100")
    assert "flight" in result
    mock_api_response.assert_called_with("https://api.adsb.lol/v2/closest/37.7749/-122.4194/100")


# Test error cases
@pytest.mark.asyncio
async def test_error_handling(mock_api_response):
    # Test handling of API errors
    mock_api_response.return_value = None
    result = await get_squawk("7700")
    assert "No aircraft matching that squawk code found." in result

    # Test handling of empty responses
    mock_api_response.return_value = {"msg": "Error", "total": 0}
    result = await get_squawk("7700")
    assert "No aircraft matching that squawk code found." in result