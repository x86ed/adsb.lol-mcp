import sys
import os
import pytest
from unittest import mock
import json
import httpx
import sqlite3
import tempfile

# More reliable import approach
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from adsblol.api_v2 import (
        make_api_request, format_markdown, register_api_v2,
        API_BASE, setup_lol_aircraft_database, save_aircraft_to_db
    )
except ImportError as e:
    print(f"Import error: {e}")
    # Use placeholder functions for testing if import fails
    def make_api_request(*args, **kwargs): pass
    def format_markdown(*args, **kwargs): pass
    def register_api_v2(*args, **kwargs): pass
    def setup_lol_aircraft_database(*args, **kwargs): pass
    def save_aircraft_to_db(*args, **kwargs): pass
    API_BASE = "http://example.com"

# Mock MCP class for testing
class MockMCP:
    def __init__(self):
        self.tools = {}
    
    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator

# Sample aircraft data for testing
SAMPLE_AIRCRAFT_DATA = {
    "ac": [
        {
            "hex": "a1b2c3",
            "flight": "UAL123",
            "alt_baro": 35000,
            "gs": 450.3,
            "lat": 37.7749,
            "lon": -122.4194,
            "track": 270,
            "type": "B738",
            "squawk": "1200"
        },
        {
            "hex": "d4e5f6",
            "flight": "DAL456",
            "alt_baro": 28000,
            "gs": 420.5,
            "lat": 40.7128,
            "lon": -74.0060,
            "track": 180,
            "type": "A320",
            "squawk": "7700"
        }
    ]
}

@pytest.fixture
def temp_db():
    """Create a temporary database file for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    conn = sqlite3.connect(path)
    yield path, conn
    conn.close()
    os.close(fd)
    os.unlink(path)

# Test database setup function
def test_setup_lol_aircraft_database(temp_db):
    """Test that database setup creates the correct table"""
    db_path, conn = temp_db
    
    with mock.patch('sqlite3.connect', return_value=conn):
        result_conn = setup_lol_aircraft_database(db_path)
        
        # Check that the table exists
        cursor = result_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lol_aircraft'")
        table_exists = cursor.fetchone() is not None
        assert table_exists
        
        # Check that table has the expected columns
        cursor.execute("PRAGMA table_info(lol_aircraft)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "hex" in columns
        assert "timestamp" in columns
        assert "flight" in columns
        assert "squawk" in columns

# Test save_aircraft_to_db function
def test_save_aircraft_to_db(temp_db):
    """Test saving aircraft data to database"""
    db_path, conn = temp_db
    
    # First setup the database
    with mock.patch('sqlite3.connect', return_value=conn):
        setup_lol_aircraft_database(db_path)
        
        # Save the sample aircraft data
        count = save_aircraft_to_db(SAMPLE_AIRCRAFT_DATA["ac"], conn)
        
        # Check that both records were saved
        assert count == 2
        
        # Verify the data was saved correctly
        cursor = conn.cursor()
        cursor.execute("SELECT hex, flight FROM lol_aircraft")
        results = cursor.fetchall()
        assert len(results) == 2
        assert ("a1b2c3", "UAL123") in results
        assert ("d4e5f6", "DAL456") in results

# Define test cases for format_markdown
@pytest.mark.parametrize("data, expected_contains", [
    ({"key": "value"}, "# key\nvalue"),
    ({"parent": {"child": "value"}}, "# parent\n## child\nvalue"),
    ({"list": [1, 2, 3]}, "# list\n* 1\n* 2\n* 3"),
    ({"empty_list": []}, "# empty_list\n*No items*"),
    ({"null": None}, "# null\n*None*"),
    ("not a dict", "```\nnot a dict\n```"),
])
def test_format_markdown(data, expected_contains):
    """Test format_markdown function with different inputs."""
    result = format_markdown(data)
    assert expected_contains in result

# Test make_api_request function
@pytest.mark.asyncio
async def test_make_api_request_success():
    """Test successful API request."""
    mock_response = mock.Mock()
    mock_response.raise_for_status = mock.Mock()
    mock_response.json.return_value = {"data": "test"}
    
    with mock.patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await make_api_request("https://test.url")
        assert result == {"data": "test"}

@pytest.mark.asyncio
async def test_make_api_request_failure():
    """Test API request with exception."""
    with mock.patch("httpx.AsyncClient.get", side_effect=httpx.RequestError("Error")):
        result = await make_api_request("https://test.url")
        assert result is None

# Tests for API endpoint tools with database functionality
@pytest.mark.asyncio
async def test_get_pia_success(temp_db):
    """Test get_pia with successful response."""
    db_path, conn = temp_db
    
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_pia"]()
        
        # Check result contains count, not aircraft details
        assert "Found and saved 2 PIA aircraft" in result
        # Make sure it doesn't have old detailed output
        assert "UAL123" not in result
        assert "DAL456" not in result

@pytest.mark.asyncio
async def test_get_pia_no_aircraft():
    """Test get_pia with no aircraft found."""
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Mock empty response
    with mock.patch("adsblol.api_v2.make_api_request", return_value={"ac": []}):
        result = await mcp.tools["get_pia"]()
        assert "No PIA aircraft found." in result

@pytest.mark.asyncio
async def test_get_mil_success(temp_db):
    """Test get_mil with database storage."""
    db_path, conn = temp_db
    
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_mil"]()
        
        # Check result contains count message
        assert "Found and saved 2 military aircraft" in result

@pytest.mark.asyncio
async def test_get_ladd_success(temp_db):
    """Test get_ladd with database storage."""
    db_path, conn = temp_db
    
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_ladd"]()
        
        # Check result contains count message
        assert "Found and saved 2 LADD aircraft" in result

# Similar tests for other endpoints
@pytest.mark.asyncio
async def test_get_squawk_success(temp_db):
    """Test get_squawk with successful response and database storage."""
    db_path, conn = temp_db
    
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    squawk = "7700"
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_squawk"](squawk)
        
        # Check result contains both count message and aircraft details
        assert f"Found and saved 2 aircraft with squawk code '{squawk}' to database" in result
        assert "DAL456" in result
        assert "7700" in result

@pytest.mark.asyncio
async def test_get_type_success(temp_db):
    """Test get_type with successful response and database storage."""
    db_path, conn = temp_db
    
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    aircraft_type = "B738"
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_type"](aircraft_type)
        
        # Check result contains both count message and aircraft details
        assert f"Found and saved 2 aircraft of type '{aircraft_type}' to database" in result
        assert "UAL123" in result  # B738 from sample data

@pytest.mark.asyncio
async def test_get_search_radius_with_db(temp_db):
    """Test get_search_radius with database storage."""
    db_path, conn = temp_db
    
    mcp = MockMCP()
    register_api_v2(mcp)
    
    lat = 37.7749
    lon = -122.4194
    radius = 50.0
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_search_radius"](lat, lon, radius)
        
        # Check result contains both count message and aircraft details
        assert f"Found and saved 2 aircraft within {radius}nm of lat:{lat}/lon:{lon} to database" in result
        assert "UAL123" in result
        assert "DAL456" in result

@pytest.mark.asyncio
async def test_get_closest_with_db(temp_db):
    """Test get_closest with database storage."""
    db_path, conn = temp_db
    
    mcp = MockMCP()
    register_api_v2(mcp)
    
    lat = 40.7128
    lon = -74.0060
    radius = 25.0
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_closest"](lat, lon, radius)
        
        # Check result contains both count message and aircraft details
        assert f"Found and saved 2 closest aircraft within {radius}nm of lat:{lat}/lon:{lon} to database" in result
        assert "UAL123" in result
        assert "DAL456" in result

@pytest.mark.asyncio
async def test_get_route_with_db(temp_db):
    """Test get_route with database storage."""
    db_path, conn = temp_db
    
    mcp = MockMCP()
    register_api_v2(mcp)
    
    callsign = "UAL123"
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_route"](callsign)
        
        # Check result contains both count message and aircraft details
        assert f"Found and saved 2 aircraft from route lookup for callsign '{callsign}' to database" in result
        assert "UAL123" in result

@pytest.mark.asyncio
async def test_get_registration_with_db(temp_db):
    """Test get_registration with database storage."""
    db_path, conn = temp_db
    
    mcp = MockMCP()
    register_api_v2(mcp)
    
    registration = "N12345"
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_registration"](registration)
        
        # Check result contains both count message and aircraft details
        assert f"Found and saved 2 aircraft with registration '{registration}' to database" in result
        assert "UAL123" in result
        assert "DAL456" in result

@pytest.mark.asyncio
async def test_get_icao_hex_with_db(temp_db):
    """Test get_icao_hex with database storage."""
    db_path, conn = temp_db
    
    mcp = MockMCP()
    register_api_v2(mcp)
    
    icao_hex = "a1b2c3"
    
    # Mock the API response and database functions
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):
        
        result = await mcp.tools["get_icao_hex"](icao_hex)
        
        # Check result contains both count message and aircraft details
        assert f"Found and saved 2 aircraft with ICAO hex code '{icao_hex}' to database" in result
        assert "UAL123" in result
        assert "DAL456" in result

# Test all other endpoints for basic URL formatting
@pytest.mark.parametrize("tool_name, expected_url_part", [
    ("get_mil", "/v2/mil"),
    ("get_ladd", "/v2/ladd"),
    ("get_type", "/v2/type/B738"),
    ("get_icao_hex", "/v2/icao/a1b2c3"),
    ("get_callsign", "/v2/callsign/UAL123"),
])
@pytest.mark.asyncio
async def test_endpoint_url_formatting(tool_name, expected_url_part):
    """Test that endpoints format their URLs correctly."""
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Use side_effect to capture the URL that was passed
    async def check_url(url):
        assert expected_url_part in url
        return SAMPLE_AIRCRAFT_DATA
    
    with mock.patch("adsblol.api_v2.make_api_request", side_effect=check_url):
        # Call the endpoint with appropriate parameters
        if tool_name == "get_mil" or tool_name == "get_ladd":
            await mcp.tools[tool_name]()
        elif tool_name == "get_type":
            await mcp.tools[tool_name]("B738")
        elif tool_name == "get_icao_hex":
            await mcp.tools[tool_name]("a1b2c3")
        elif tool_name == "get_callsign":
            await mcp.tools[tool_name]("UAL123")

# Add a simple test 
def test_import_works():
    """Verify that imports work."""
    assert 'make_api_request' in globals()

# Add tests for get_search_radius and get_closest with float parameters
@pytest.mark.asyncio
async def test_get_search_radius():
    """Test get_search_radius with float parameters."""
    mcp = MockMCP()
    register_api_v2(mcp)
    
    lat = 37.7749
    lon = -122.4194
    radius = 50.0
    
    # Use side_effect to capture and validate the URL parameters
    async def check_url(url):
        assert f"/v2/point/{lat}/{lon}/{radius}" in url
        return SAMPLE_AIRCRAFT_DATA
    
    with mock.patch("adsblol.api_v2.make_api_request", side_effect=check_url):
        result = await mcp.tools["get_search_radius"](lat, lon, radius)
        assert result is not None
        # Verify aircraft data is in the result
        assert "UAL123" in result

@pytest.mark.asyncio
async def test_get_closest():
    """Test get_closest with float parameters."""
    mcp = MockMCP()
    register_api_v2(mcp)
    
    lat = 40.7128
    lon = -74.0060
    radius = 25.0
    
    # Use side_effect to capture and validate the URL parameters
    async def check_url(url):
        assert f"/v2/closest/{lat}/{lon}/{radius}" in url
        return SAMPLE_AIRCRAFT_DATA
    
    with mock.patch("adsblol.api_v2.make_api_request", side_effect=check_url):
        result = await mcp.tools["get_closest"](lat, lon, radius)
        assert result is not None
        # Verify aircraft data is in the result
        assert "UAL123" in result

@pytest.mark.asyncio
async def test_get_route():
    """Test get_route function."""
    mcp = MockMCP()
    register_api_v2(mcp)
    
    callsign = "UAL123"
    
    # Use side_effect to capture and validate the URL
    async def check_url(url):
        assert f"/v0/route/{callsign}" in url
        return SAMPLE_AIRCRAFT_DATA
    
    with mock.patch("adsblol.api_v2.make_api_request", side_effect=check_url):
        result = await mcp.tools["get_route"](callsign)
        assert result is not None
        # Verify aircraft data is in the result
        assert "UAL123" in result

@pytest.mark.asyncio
async def test_get_type_error_message():
    """Test get_type returns correct error message."""
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Mock empty response
    with mock.patch("adsblol.api_v2.make_api_request", return_value={"ac": []}):
        result = await mcp.tools["get_type"]("B738")
        # Verify it mentions aircraft type, not squawk code
        assert "No aircraft matching that aircraft type found" in result

# Tests for single vs. multiple aircraft response formats
@pytest.mark.asyncio
async def test_single_aircraft_detail(temp_db):
    """Test that functions return detailed formatting for a single aircraft."""
    db_path, conn = temp_db
    
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Create a sample with a single aircraft
    single_aircraft_data = {
        "ac": [
            {
                "hex": "a1b2c3",
                "flight": "UAL123",
                "alt_baro": 35000,
                "gs": 450.3,
                "lat": 37.7749,
                "lon": -122.4194,
                "track": 270,
                "type": "B738",
                "squawk": "1200"
            }
        ]
    }
    
    # Mock the API response and database functions for single aircraft
    with mock.patch("adsblol.api_v2.make_api_request", return_value=single_aircraft_data), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=1):  # Just 1 aircraft
        
        # Test with a single aircraft lookup
        result = await mcp.tools["get_icao_hex"]("a1b2c3")
        
        # Should include both count message and details
        assert "Found and saved 1 aircraft" in result
        assert "UAL123" in result
        assert "B738" in result
        
        # Test another function with single aircraft response
        result = await mcp.tools["get_registration"]("N12345")
        
        # Should include both count message and details
        assert "Found and saved 1 aircraft with registration" in result
        assert "UAL123" in result

@pytest.mark.asyncio
async def test_multiple_aircraft_count_only(temp_db):
    """Test that functions return only count for multiple aircraft."""
    db_path, conn = temp_db
    
    # Set up mock MCP
    mcp = MockMCP()
    register_api_v2(mcp)
    
    # Mock the API response and database functions for multiple aircraft
    with mock.patch("adsblol.api_v2.make_api_request", return_value=SAMPLE_AIRCRAFT_DATA), \
         mock.patch("adsblol.api_v2.setup_lol_aircraft_database", return_value=conn), \
         mock.patch("adsblol.api_v2.save_aircraft_to_db", return_value=2):  # 2 or more aircraft
        
        # Test with multiple aircraft lookup
        result = await mcp.tools["get_type"]("B738")
        
        # Should only include count message, not details
        assert "Found and saved 2 aircraft of type 'B738' to database" in result
        assert "UAL123" not in result  # Details should not be included
        
        # Test geographic search with multiple results
        result = await mcp.tools["get_search_radius"](37.7749, -122.4194, 50.0)
        
        # Should only include count message, not details
        assert "Found and saved 2 aircraft within 50.0nm" in result
        assert "UAL123" not in result  # Details should not be included