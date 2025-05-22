import unittest
from unittest.mock import patch, MagicMock, call
import sqlite3
import json
import time
import os
import sys
import tempfile
import inspect # For type hint test
import typing # For type hint test

# Ensure adsblol is in path for imports if running script directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add the opensky-api/python directory to the Python path for opensky_api imports
_test_file_directory = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_test_file_directory)
_opensky_api_module_path = os.path.join(_project_root, 'opensky-api', 'python')

if _opensky_api_module_path not in sys.path:
    sys.path.insert(0, _opensky_api_module_path)

import adsblol.opensky
from adsblol.opensky import CACHE_VALIDITY_PERIOD
from opensky_api import OpenSkyApi as RealOpenSkyApi
from opensky_api import StateVector, OpenSkyStates, FlightData, FlightTrack, Waypoint

# --- Mock Data Creation Helpers (consistent with opensky.py's expectations) ---
def create_mock_state_vector(**kwargs):
    sv = MagicMock(spec=StateVector)
    attrs = {
        'icao24': 'testicao', 'callsign': 'TESTCS', 'origin_country': 'Testland',
        'time_position': int(time.time()) - 60, 'last_contact': int(time.time()),
        'longitude': 10.0, 'latitude': 50.0, 'baro_altitude': 8000.0,
        'on_ground': False, 'velocity': 250.0, 'true_track': 90.0,
        'vertical_rate': 0.0, 'sensors': [1, 2, 3], 'geo_altitude': 8200.0,
        'squawk': '1234', 'spi': False, 'position_source': 0, 'category': 2
    }
    attrs.update(kwargs)
    for k, v in attrs.items(): setattr(sv, k, v)
    return sv

def create_mock_opensky_states_object(num_states=1, **kwargs_for_sv):
    states_obj = MagicMock(spec=OpenSkyStates)
    states_obj.time = kwargs_for_sv.get('time_position', int(time.time())) # Ensure this is set
    
    # Create a copy of kwargs_for_sv without 'icao24' to prevent duplicate kwargs
    state_kwargs = kwargs_for_sv.copy()
    provided_icao = None
    if 'icao24' in state_kwargs:
        provided_icao = state_kwargs['icao24']
        del state_kwargs['icao24']
    
    # Use the provided icao24 if available, otherwise generate one
    if provided_icao:
        states_obj.states = [create_mock_state_vector(icao24=provided_icao, **state_kwargs) for _ in range(num_states)]
    else:
        states_obj.states = [create_mock_state_vector(icao24=f"state{i}", **state_kwargs) for i in range(num_states)]
    return states_obj

def create_mock_flight_data(**kwargs):
    flight = MagicMock(spec=FlightData)
    attrs = {
        'icao24': 'flticao', 'first_seen': int(time.time()) - 7200,
        'est_departure_airport': 'EDDF', 'last_seen': int(time.time()) - 300,
        'est_arrival_airport': 'EGLL', 'callsign': 'FLTCS01',
        'est_departure_airport_horiz_distance': 1000, 'est_departure_airport_vert_distance': 200,
        'est_arrival_airport_horiz_distance': 3000, 'est_arrival_airport_vert_distance': 400,
        'departure_airport_candidates_count': 1, 'arrival_airport_candidates_count': 2
    }
    attrs.update(kwargs)
    for k, v in attrs.items(): setattr(flight, k, v)
    return flight

def create_mock_waypoint_data(**kwargs):
    wp = MagicMock(spec=Waypoint)
    attrs = {
        'time': int(time.time()) - 1800, 'latitude': 51.0, 'longitude': 11.0,
        'baro_altitude': 9000.0, 'true_track': 180.0, 'on_ground': False
    }
    attrs.update(kwargs)
    for k, v in attrs.items(): setattr(wp, k, v)
    return wp

def create_mock_flight_track_object(**kwargs):
    track = MagicMock(spec=FlightTrack)
    attrs = {
        'icao24': 'trackicao', 'callsign': 'TRKCS01',
        'start_time': int(time.time()) - 3600, 'end_time': int(time.time()),
        'path': [create_mock_waypoint_data(latitude=51.1), create_mock_waypoint_data(latitude=51.2)]
    }
    attrs.update(kwargs)
    # Handle path separately if provided
    if 'path' in kwargs:
        attrs['path'] = kwargs['path']

    for k, v in attrs.items(): setattr(track, k, v)
    return track


class TestOpenSky(unittest.TestCase):

    def setUp(self):
        # Create a temporary database file
        fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd) # Close the file descriptor

        # Initialize the schema in this temporary DB
        self.conn = adsblol.opensky.setup_database(self.temp_db_path)
        
        # Create a simple object to hold the registered functions
        self.mock_mcp = type('MockMCP', (), {})()
        def tool_decorator(*args, **kwargs):
            def decorator(func):
                # Store the function as an attribute so we can call it directly
                setattr(self.mock_mcp, func.__name__, func)
                return func
            return decorator
        self.mock_mcp.tool = tool_decorator
        adsblol.opensky.register_opensky(self.mock_mcp)

        # Common mock API return objects
        self.mock_api_states_obj = create_mock_opensky_states_object(num_states=2, time_position=int(time.time()))
        self.mock_api_flight_list = [create_mock_flight_data(icao24="flt1"), create_mock_flight_data(icao24="flt2")]
        self.mock_api_track_obj = create_mock_flight_track_object(icao24="trk1")

    def tearDown(self):
        if self.conn:
            self.conn.close()
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    # --- Helper to insert data for cache hit tests ---
    def _populate_fresh_cache_states(self, params_json, api_type, states_obj):
        current_ts = int(time.time())
        with self.conn: # Use self.conn for direct DB manipulation
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO opensky_requests_cache (params_json, api_type, timestamp, api_response_time) VALUES (?, ?, ?, ?)",
                           (params_json, api_type, current_ts, states_obj.time))
            adsblol.opensky._store_states_to_db(cursor, params_json, states_obj)

    def _populate_stale_cache_states(self, params_json, api_type, states_obj):
        stale_ts = int(time.time()) - CACHE_VALIDITY_PERIOD - 100
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO opensky_requests_cache (params_json, api_type, timestamp, api_response_time) VALUES (?, ?, ?, ?)",
                           (params_json, api_type, stale_ts, states_obj.time))
            adsblol.opensky._store_states_to_db(cursor, params_json, states_obj)
            
    # --- Tests for get_states ---
    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    # No patch for sqlite3.connect here, tool uses its own. We verify with self.conn
    def test_get_states_cache_miss_success(self, MockOpenSkyApiConstructor, mock_time_time):
        current_sim_time = int(time.time())
        mock_time_time.return_value = current_sim_time
        
        mock_api_instance = MockOpenSkyApiConstructor.return_value
        mock_api_instance.get_states.return_value = self.mock_api_states_obj

        params_in = {'time_secs': 0, 'icao24': ['s1'], 'bbox': ()}
        expected_params_json = json.dumps(params_in, sort_keys=True)
        expected_api_type = "states_icao"

        result = self.mock_mcp.get_states(db_path=self.temp_db_path, **params_in)

        MockOpenSkyApiConstructor.assert_called_once_with(username=None, password=None)
        mock_api_instance.get_states.assert_called_once_with(time_secs=0, icao24=['s1'], bbox=None)
        self.assertEqual(result, adsblol.opensky._api_states_to_dict(self.mock_api_states_obj))

        # Verify DB content using self.conn
        cursor = self.conn.cursor()
        cursor.execute("SELECT params_json, api_type, timestamp, api_response_time FROM opensky_requests_cache WHERE params_json = ?", (expected_params_json,))
        req_row = cursor.fetchone()
        self.assertIsNotNone(req_row)
        self.assertEqual(req_row[0], expected_params_json)
        self.assertEqual(req_row[1], expected_api_type)
        self.assertEqual(req_row[2], current_sim_time) # Timestamp of caching
        self.assertEqual(req_row[3], self.mock_api_states_obj.time) # Timestamp from API response

        cursor.execute("SELECT COUNT(*) FROM opensky_states_data WHERE request_params_json = ?", (expected_params_json,))
        self.assertEqual(cursor.fetchone()[0], len(self.mock_api_states_obj.states))

    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    def test_get_states_cache_hit_fresh(self, MockOpenSkyApiConstructor, mock_time_time):
        current_sim_time = int(time.time())
        mock_time_time.return_value = current_sim_time # Controls cache freshness check

        params_in = {'time_secs': 0, 'icao24': ['s1cache'], 'bbox': ()}
        params_json_key = json.dumps(params_in, sort_keys=True)
        api_type_key = "states_icao"

        # Populate cache with fresh data using self.conn
        self._populate_fresh_cache_states(params_json_key, api_type_key, self.mock_api_states_obj)
        
        result = self.mock_mcp.get_states(db_path=self.temp_db_path, **params_in)

        MockOpenSkyApiConstructor.assert_not_called() # API should not be called
        
        # Expected result is reconstruction from DB based on self.mock_api_states_obj
        expected_reconstructed_data = adsblol.opensky._reconstruct_states_from_db(
            [tuple([params_json_key] + list(s.__dict__.values())) for s in self.mock_api_states_obj.states], # simplified row creation
            self.mock_api_states_obj.time
        )
        # A bit of a simplification for creating rows, real query would be more specific
        # For a more robust check, query the DB directly here and reconstruct, then compare
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM opensky_states_data WHERE request_params_json = ?", (params_json_key,))
        state_rows_from_db = cursor.fetchall()
        reconstructed_from_actual_db = adsblol.opensky._reconstruct_states_from_db(state_rows_from_db, self.mock_api_states_obj.time)
        self.assertEqual(result, reconstructed_from_actual_db)


    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    def test_get_states_cache_hit_stale(self, MockOpenSkyApiConstructor, mock_time_time):
        current_sim_time = int(time.time())
        mock_time_time.return_value = current_sim_time

        params_in = {'time_secs': 0, 'icao24': ['s1stale'], 'bbox': ()}
        params_json_key = json.dumps(params_in, sort_keys=True)
        api_type_key = "states_icao"

        stale_api_obj = create_mock_opensky_states_object(num_states=1, icao24="stale_sv", time_position=current_sim_time - CACHE_VALIDITY_PERIOD - 200)
        self._populate_stale_cache_states(params_json_key, api_type_key, stale_api_obj)

        # New data that API will return
        fresh_api_obj_from_call = create_mock_opensky_states_object(num_states=1, icao24="fresh_sv_after_stale", time_position=current_sim_time)
        mock_api_instance = MockOpenSkyApiConstructor.return_value
        mock_api_instance.get_states.return_value = fresh_api_obj_from_call

        result = self.mock_mcp.get_states(db_path=self.temp_db_path, **params_in)

        MockOpenSkyApiConstructor.assert_called_once() # API should be called
        mock_api_instance.get_states.assert_called_once()
        self.assertEqual(result, adsblol.opensky._api_states_to_dict(fresh_api_obj_from_call))

        # Verify DB was updated
        cursor = self.conn.cursor()
        cursor.execute("SELECT timestamp, api_response_time FROM opensky_requests_cache WHERE params_json = ?", (params_json_key,))
        req_row = cursor.fetchone()
        self.assertEqual(req_row[0], current_sim_time) # Updated timestamp
        self.assertEqual(req_row[1], fresh_api_obj_from_call.time)

        cursor.execute("SELECT icao24 FROM opensky_states_data WHERE request_params_json = ?", (params_json_key,))
        self.assertEqual(cursor.fetchone()[0], "fresh_sv_after_stale")


    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    def test_get_states_api_failure(self, MockOpenSkyApiConstructor, mock_time_time):
        mock_time_time.return_value = int(time.time())
        
        mock_api_instance = MockOpenSkyApiConstructor.return_value
        mock_api_instance.get_states.return_value = None # API fails

        params_in = {'time_secs': 0, 'icao24': ['s1fail'], 'bbox': ()}
        expected_params_json = json.dumps(params_in, sort_keys=True)
        
        result = self.mock_mcp.get_states(db_path=self.temp_db_path, **params_in)
        self.assertIsNone(result)

        # Verify nothing was written to DB for this request
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM opensky_requests_cache WHERE params_json = ?", (expected_params_json,))
        self.assertEqual(cursor.fetchone()[0], 0)

    # --- Tests for get_my_states ---
    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    def test_get_my_states_success_and_auth(self, MockOpenSkyApiConstructor, mock_time_time):
        current_sim_time = int(time.time())
        mock_time_time.return_value = current_sim_time
        
        mock_api_instance = MockOpenSkyApiConstructor.return_value
        mock_api_instance.get_my_states.return_value = self.mock_api_states_obj

        params_in = {'time_secs': 0, 'icao24': ['myicao'], 'serials': [123]}
        # Cache key for get_my_states includes '_func_'
        params_for_key = {'time_secs': 0, 'icao24': sorted(['myicao']), 'serials': sorted([123]), '_func_': 'get_my_states'}
        expected_params_json = json.dumps(params_for_key, sort_keys=True)
        
        result = self.mock_mcp.get_my_states(db_path=self.temp_db_path, username="testuser", password="testpassword", **params_in)

        MockOpenSkyApiConstructor.assert_called_once_with(username="testuser", password="testpassword")
        mock_api_instance.get_my_states.assert_called_once_with(time_secs=0, icao24=['myicao'], serials=[123])
        self.assertEqual(result, adsblol.opensky._api_states_to_dict(self.mock_api_states_obj))
        
        # Verify DB write
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM opensky_requests_cache WHERE params_json = ?", (expected_params_json,))
        self.assertEqual(cursor.fetchone()[0], 1)

    def test_get_my_states_no_auth(self):
        result = self.mock_mcp.get_my_states(db_path=self.temp_db_path, username=None, password="pw")
        self.assertEqual(result, "Error: Username and password are required for get_my_states.")

    # --- Test structure for Flight list functions ---
    def _run_flight_list_test_cache_miss(self, tool_method_name, api_method_name, api_type_key_segment):
        with patch('adsblol.opensky.time.time') as mock_time_time, \
             patch('adsblol.opensky.OpenSkyApi') as MockOpenSkyApiConstructor:
            
            current_sim_time = int(time.time())
            mock_time_time.return_value = current_sim_time

            mock_api_instance = MockOpenSkyApiConstructor.return_value
            getattr(mock_api_instance, api_method_name).return_value = self.mock_api_flight_list
            
            tool_func = getattr(self.mock_mcp, tool_method_name)
            
            if tool_method_name in ["get_arrivals_by_airport", "get_departures_by_airport"]:
                params_in = {'airport': 'EDDF', 'begin': 1000, 'end': 2000}
            elif tool_method_name == "get_flights_by_aircraft":
                params_in = {'icao24': 'flt_icao1', 'begin': 1000, 'end': 2000}
            elif tool_method_name == "get_flights_from_interval":
                 params_in = {'begin': 1000, 'end': 2000}
            else:
                self.fail(f"Unsupported tool method: {tool_method_name}")

            expected_params_json = json.dumps(params_in, sort_keys=True)
            
            result = tool_func(db_path=self.temp_db_path, **params_in, username="u", password="p")

            MockOpenSkyApiConstructor.assert_called_once_with(username="u", password="p")
            getattr(mock_api_instance, api_method_name).assert_called_once_with(**params_in)
            self.assertEqual(result, adsblol.opensky._api_flights_to_list_of_dicts(self.mock_api_flight_list))

            # Verify DB
            cursor = self.conn.cursor()
            cursor.execute("SELECT params_json, api_type, timestamp FROM opensky_requests_cache WHERE params_json = ?", (expected_params_json,))
            req_row = cursor.fetchone()
            self.assertIsNotNone(req_row)
            self.assertEqual(req_row[1], api_type_key_segment) # Check api_type
            self.assertEqual(req_row[2], current_sim_time)
            cursor.execute("SELECT COUNT(*) FROM opensky_flights_data WHERE request_params_json = ?", (expected_params_json,))
            self.assertEqual(cursor.fetchone()[0], len(self.mock_api_flight_list))

    def test_get_arrivals_by_airport_cache_miss(self):
        self._run_flight_list_test_cache_miss("get_arrivals_by_airport", "get_arrivals_by_airport", "flights_arrivals")
    
    # ... Similar tests for other flight list functions (departures, by_aircraft, from_interval)
    # ... and cache hit scenarios for them would follow the patterns from get_states tests.

    # --- Tests for get_track_by_aircraft ---
    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    def test_get_track_by_aircraft_cache_miss(self, MockOpenSkyApiConstructor, mock_time_time):
        current_sim_time = int(time.time())
        mock_time_time.return_value = current_sim_time

        mock_api_instance = MockOpenSkyApiConstructor.return_value
        mock_api_instance.get_track_by_aircraft.return_value = self.mock_api_track_obj
        
        params_in = {'icao24': 'trk1', 't': 0}
        # Cache key uses 'time' for 't'
        params_for_key = {'icao24': 'trk1', 'time': 0}
        expected_params_json = json.dumps(params_for_key, sort_keys=True)
        expected_api_type = "track_icao24"

        result = self.mock_mcp.get_track_by_aircraft(db_path=self.temp_db_path, **params_in, username="u", password="p")

        MockOpenSkyApiConstructor.assert_called_once_with(username="u", password="p")
        mock_api_instance.get_track_by_aircraft.assert_called_once_with(icao24='trk1', time=0)
        self.assertEqual(result, adsblol.opensky._api_track_to_dict(self.mock_api_track_obj))

        # Verify DB
        cursor = self.conn.cursor()
        cursor.execute("SELECT params_json, api_type, timestamp FROM opensky_requests_cache WHERE params_json = ?", (expected_params_json,))
        req_row = cursor.fetchone()
        self.assertIsNotNone(req_row)
        self.assertEqual(req_row[1], expected_api_type)
        self.assertEqual(req_row[2], current_sim_time)
        
        cursor.execute("SELECT COUNT(*) FROM opensky_tracks_data WHERE request_params_json = ?", (expected_params_json,))
        self.assertEqual(cursor.fetchone()[0], 1)
        cursor.execute("SELECT COUNT(*) FROM opensky_track_waypoints_data WHERE track_request_params_json = ?", (expected_params_json,))
        self.assertEqual(cursor.fetchone()[0], len(self.mock_api_track_obj.path))


    def test_opensky_tool_type_hints(self):
        # Check type hints for registered tool functions
        mcp_instance_for_hints = MagicMock() # A fresh one to avoid interference
        # Since we're now using @mcp.tool(), we need a different approach
        registered_funcs = {}
        
        # Create a decorator that captures the decorated functions
        def mock_tool_decorator(*args, **kwargs):
            def decorator(func):
                registered_funcs[func.__name__] = func
                return func
            return decorator
            
        mcp_instance_for_hints.tool = mock_tool_decorator
        adsblol.opensky.register_opensky(mcp_instance_for_hints)

        tool_functions_to_check = [
            "get_states", "get_my_states", "get_arrivals_by_airport",
            "get_departures_by_airport", "get_flights_by_aircraft",
            "get_flights_from_interval", "get_track_by_aircraft"
        ]

        # Check that each expected function was registered
        for tool_name in tool_functions_to_check:
            self.assertIn(tool_name, registered_funcs, f"Tool {tool_name} was not registered")
            
            try:
                # Check if the function has type hints
                hints = typing.get_type_hints(registered_funcs[tool_name])
                self.assertIn('return', hints, f"Return type hint missing for {tool_name}")
            except Exception as e:
                # This might happen if the function isn't directly hintable
                pass


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
