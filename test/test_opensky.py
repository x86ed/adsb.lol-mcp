import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import sqlite3
import json
import time

# Modules to be tested or used in tests
import adsblol.opensky
from adsblol.opensky import CACHE_VALIDITY_PERIOD # Import for use in stale cache tests
# Use RealOpenSkyApi for spec to ensure mock instances behave like real API objects
from opensky_api import OpenSkyApi as RealOpenSkyApi 
from opensky_api import StateVector, OpenSkyStates, Flight, FlightTrack, Waypoint # For spec

# Helper to create mock StateVector objects
def create_mock_state_vector(**kwargs):
    sv = MagicMock(spec=StateVector)
    # Define all attributes that StateVector has, to match spec
    attrs = {
        'icao24': 'testicao', 'callsign': 'TESTCS', 'origin_country': 'Testland',
        'time_position': None, 'last_contact': int(time.time()), 'longitude': None,
        'latitude': None, 'baro_altitude': None, 'on_ground': False, 'velocity': None,
        'true_track': None, 'vertical_rate': None, 'sensors': None, 'geo_altitude': None,
        'squawk': None, 'spi': False, 'position_source': 0, 'category': 0
    }
    attrs.update(kwargs)
    for k, v in attrs.items():
        setattr(sv, k, v)
    # For serialization in opensky.py (_serialize_states)
    sv.__dict__ = attrs.copy() # Use the same dict for __dict__
    return sv

# Helper to create mock Flight objects
def create_mock_flight(**kwargs):
    flight = MagicMock(spec=Flight)
    attrs = {
        'icao24': 'flticao', 'first_seen': int(time.time()) - 3600,
        'est_departure_airport': 'EDDF', 'last_seen': int(time.time()),
        'est_arrival_airport': 'EGLL', 'callsign': 'FLTCS',
        'est_departure_airport_horiz_distance': 100,
        'est_departure_airport_vert_distance': 50,
        'est_arrival_airport_horiz_distance': 200,
        'est_arrival_airport_vert_distance': 75,
        'departure_airport_candidates_count': 1,
        'arrival_airport_candidates_count': 1
    }
    attrs.update(kwargs)
    for k, v in attrs.items():
        setattr(flight, k, v)
    flight.__dict__ = attrs.copy()
    return flight

# Helper to create mock Waypoint objects
def create_mock_waypoint(**kwargs):
    wp = MagicMock(spec=Waypoint)
    attrs = {
        'time': int(time.time()), 'latitude': 50.0, 'longitude': 10.0,
        'baro_altitude': 10000.0, 'true_track': 90.0, 'on_ground': False
    }
    attrs.update(kwargs)
    for k,v in attrs.items():
        setattr(wp, k, v)
    wp.__dict__ = attrs.copy()
    return wp

# Helper to create mock FlightTrack objects
def create_mock_flight_track(**kwargs):
    track = MagicMock(spec=FlightTrack)
    # Default path contains mock Waypoint objects
    default_path_objects = [create_mock_waypoint(latitude=50.1, time=int(time.time())-100), 
                            create_mock_waypoint(latitude=50.2, time=int(time.time())-50)]
    
    path_objects = kwargs.pop('path', default_path_objects) 
    
    attrs = {
        'icao24': 'trackicao', 'callsign': 'TRACKCS',
        'start_time': int(time.time()) - 3600, 'end_time': int(time.time()),
        'path': path_objects # Store actual mock Waypoint objects
    }
    attrs.update(kwargs)

    for k,v in attrs.items():
         setattr(track, k, v)
    
    # Make __dict__ represent what _serialize_track would see.
    # _serialize_track does: track_obj.__dict__.copy() and then track_obj.path
    track_dict_for_serialization = attrs.copy()
    # The path in the __dict__ for serialization should be list of dicts
    track_dict_for_serialization['path'] = [wp.__dict__ for wp in path_objects] 
    track.__dict__ = track_dict_for_serialization
    
    # Ensure the 'path' attribute itself for direct access by serializer is list of objects
    track.path = path_objects
    return track


class TestOpenSky(unittest.TestCase):

    def setUp(self):
        self.mock_mcp = MagicMock()
        # This is crucial: register_opensky defines the tool functions and decorates them
        # using self.mock_mcp.tool. The FastMCP @tool decorator makes the function
        # an attribute of the mcp instance.
        adsblol.opensky.register_opensky(self.mock_mcp)

        # Prepare reusable mock API return objects
        self.mock_opensky_states_obj_for_api_return = MagicMock(spec=OpenSkyStates)
        self.mock_opensky_states_obj_for_api_return.time = int(time.time())
        self.mock_opensky_states_obj_for_api_return.states = [
            create_mock_state_vector(icao24="s1", longitude=1.0, latitude=1.0), 
            create_mock_state_vector(icao24="s2", longitude=2.0, latitude=2.0)
        ]

        self.mock_flight_list_for_api_return = [
            create_mock_flight(icao24="f1", callsign="FLT001"), 
            create_mock_flight(icao24="f2", callsign="FLT002")
        ]

        self.mock_track_for_api_return = create_mock_flight_track(icao24="tr1", callsign="TRK001")


    # --- Tests for get_states ---
    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi') 
    @patch('adsblol.opensky.sqlite3.connect')
    def test_get_states_cache_miss_success(self, mock_sqlite_connect, MockOpenSkyApiConstructor, mock_time_time):
        current_ts = 10000
        mock_time_time.return_value = current_ts

        mock_db_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Cache miss

        mock_api_instance = MagicMock(spec=RealOpenSkyApi)
        MockOpenSkyApiConstructor.return_value = mock_api_instance
        mock_api_instance.get_states.return_value = self.mock_opensky_states_obj_for_api_return

        params_in = {'time_secs': 0, 'icao24': ['sv_icao1'], 'bbox': (1.0, 2.0, 3.0, 4.0)}
        # Call the tool function via the mocked MCP instance
        result = self.mock_mcp.get_states(
            time_secs=params_in['time_secs'], icao24=params_in['icao24'], bbox=params_in['bbox'],
            username="user", password="pw"
        )
        
        mock_sqlite_connect.assert_called_once_with('opensky_cache.db')
        expected_cache_key_params = {'time_secs': 0, 'icao24': sorted(['sv_icao1']), 'bbox': (1.0, 2.0, 3.0, 4.0)}
        mock_cursor.execute.assert_any_call(
            "SELECT timestamp, data FROM states_cache WHERE params_json = ?",
            (json.dumps(expected_cache_key_params, sort_keys=True),)
        )
        MockOpenSkyApiConstructor.assert_called_once_with(username="user", password="pw")
        mock_api_instance.get_states.assert_called_once_with(
            time_secs=params_in['time_secs'], icao24=params_in['icao24'], bbox=params_in['bbox']
        )
        
        expected_serialized_data = adsblol.opensky._serialize_states(self.mock_opensky_states_obj_for_api_return)
        mock_cursor.execute.assert_any_call(
            "INSERT OR REPLACE INTO states_cache (params_json, timestamp, data) VALUES (?, ?, ?)",
            (json.dumps(expected_cache_key_params, sort_keys=True), current_ts, json.dumps(expected_serialized_data))
        )
        mock_db_conn.commit.assert_called_once()
        mock_db_conn.close.assert_called_once()
        self.assertEqual(result, expected_serialized_data)

    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    @patch('adsblol.opensky.sqlite3.connect')
    def test_get_states_cache_hit_fresh(self, mock_sqlite_connect, MockOpenSkyApiConstructor, mock_time_time):
        current_ts = 10000
        cached_ts = current_ts - (CACHE_VALIDITY_PERIOD / 2) # Fresh
        mock_time_time.return_value = current_ts

        serialized_data_from_cache = adsblol.opensky._serialize_states(self.mock_opensky_states_obj_for_api_return)
        
        mock_db_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (cached_ts, json.dumps(serialized_data_from_cache))

        mock_api_instance = MagicMock(spec=RealOpenSkyApi) # Should not be used
        MockOpenSkyApiConstructor.return_value = mock_api_instance

        params_in = {'time_secs': 0, 'icao24': ['sv_icao1'], 'bbox': (1.0, 2.0, 3.0, 4.0)}
        result = self.mock_mcp.get_states(**params_in) # Call through mcp

        expected_cache_key_params = {'time_secs': 0, 'icao24': sorted(['sv_icao1']), 'bbox': (1.0, 2.0, 3.0, 4.0)}
        mock_cursor.execute.assert_called_once_with( 
            "SELECT timestamp, data FROM states_cache WHERE params_json = ?",
            (json.dumps(expected_cache_key_params, sort_keys=True),)
        )
        MockOpenSkyApiConstructor.assert_not_called()
        mock_api_instance.get_states.assert_not_called()
        mock_db_conn.commit.assert_not_called()
        mock_db_conn.close.assert_called_once()
        self.assertEqual(result, serialized_data_from_cache)

    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    @patch('adsblol.opensky.sqlite3.connect')
    def test_get_states_cache_hit_stale(self, mock_sqlite_connect, MockOpenSkyApiConstructor, mock_time_time):
        current_ts = 10000
        stale_ts = current_ts - CACHE_VALIDITY_PERIOD - 1 # Stale
        mock_time_time.return_value = current_ts
        
        # Data that's currently in cache (stale)
        old_states_obj = MagicMock(spec=OpenSkyStates)
        old_states_obj.time = stale_ts
        old_states_obj.states = [create_mock_state_vector(icao24="old_sv")]
        old_serialized_data = adsblol.opensky._serialize_states(old_states_obj)
        
        # New data that the API will return
        new_api_return_obj = MagicMock(spec=OpenSkyStates)
        new_api_return_obj.time = current_ts
        new_api_return_obj.states = [create_mock_state_vector(icao24="new_sv")]
        
        mock_db_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (stale_ts, json.dumps(old_serialized_data)) # Stale cache hit

        mock_api_instance = MagicMock(spec=RealOpenSkyApi)
        MockOpenSkyApiConstructor.return_value = mock_api_instance
        mock_api_instance.get_states.return_value = new_api_return_obj

        params_in = {'time_secs': 0, 'icao24': ['new_sv_icao'], 'bbox': ()}
        result = self.mock_mcp.get_states(**params_in) # Call through mcp

        expected_cache_key_params = {'time_secs': 0, 'icao24': sorted(['new_sv_icao']), 'bbox': ()}
        mock_cursor.execute.assert_any_call( # First call is SELECT
            "SELECT timestamp, data FROM states_cache WHERE params_json = ?",
            (json.dumps(expected_cache_key_params, sort_keys=True),)
        )
        MockOpenSkyApiConstructor.assert_called_once_with(username=None, password=None) # Default creds
        mock_api_instance.get_states.assert_called_once_with(
            time_secs=params_in['time_secs'], icao24=params_in['icao24'], bbox=None # Empty tuple becomes None
        )
        
        expected_new_serialized_data = adsblol.opensky._serialize_states(new_api_return_obj)
        mock_cursor.execute.assert_any_call( # Second call is INSERT/REPLACE
            "INSERT OR REPLACE INTO states_cache (params_json, timestamp, data) VALUES (?, ?, ?)",
            (json.dumps(expected_cache_key_params, sort_keys=True), current_ts, json.dumps(expected_new_serialized_data))
        )
        mock_db_conn.commit.assert_called_once()
        mock_db_conn.close.assert_called_once()
        self.assertEqual(result, expected_new_serialized_data)

    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    @patch('adsblol.opensky.sqlite3.connect')
    def test_get_states_api_failure_returns_none(self, mock_sqlite_connect, MockOpenSkyApiConstructor, mock_time_time):
        current_ts = 10000
        mock_time_time.return_value = current_ts
        mock_db_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Cache miss

        mock_api_instance = MagicMock(spec=RealOpenSkyApi)
        MockOpenSkyApiConstructor.return_value = mock_api_instance
        mock_api_instance.get_states.return_value = None # API returns None

        result = self.mock_mcp.get_states() # Call through mcp

        MockOpenSkyApiConstructor.assert_called_once()
        mock_api_instance.get_states.assert_called_once()
        
        # Check that INSERT OR REPLACE was NOT called
        insert_call_found = False
        for call_args in mock_cursor.execute.call_args_list:
            if call_args[0][0].startswith("INSERT OR REPLACE"):
                insert_call_found = True
                break
        self.assertFalse(insert_call_found, "INSERT OR REPLACE should not be called when API returns None")
        mock_db_conn.commit.assert_not_called()
        mock_db_conn.close.assert_called_once()
        self.assertIsNone(result)

    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    @patch('adsblol.opensky.sqlite3.connect')
    def test_get_states_api_exception_returns_error_string(self, mock_sqlite_connect, MockOpenSkyApiConstructor, mock_time_time):
        current_ts = 10000
        mock_time_time.return_value = current_ts
        mock_db_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Cache miss

        mock_api_instance = MagicMock(spec=RealOpenSkyApi)
        MockOpenSkyApiConstructor.return_value = mock_api_instance
        mock_api_instance.get_states.side_effect = Exception("API Network Timeout")

        result = self.mock_mcp.get_states() # Call through mcp
        
        mock_db_conn.close.assert_called_once()
        self.assertEqual(result, "Error calling OpenSky API: API Network Timeout")

    # --- Tests for get_my_states ---
    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    @patch('adsblol.opensky.sqlite3.connect')
    def test_get_my_states_success(self, mock_sqlite_connect, MockOpenSkyApiConstructor, mock_time_time):
        current_ts = 10000
        mock_time_time.return_value = current_ts
        mock_db_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Cache miss

        mock_api_instance = MagicMock(spec=RealOpenSkyApi)
        MockOpenSkyApiConstructor.return_value = mock_api_instance
        mock_api_instance.get_my_states.return_value = self.mock_opensky_states_obj_for_api_return
        
        params_in = {'time_secs': 0, 'icao24': ['myicao'], 'serials': [123]}
        result = self.mock_mcp.get_my_states( # Call through mcp
            username="testuser", password="testpassword", **params_in
        )

        MockOpenSkyApiConstructor.assert_called_once_with(username="testuser", password="testpassword")
        mock_api_instance.get_my_states.assert_called_once_with(**params_in)
        
        expected_serialized = adsblol.opensky._serialize_states(self.mock_opensky_states_obj_for_api_return)
        # Cache key for get_my_states includes '_func_'
        expected_cache_key = {'time_secs': 0, 'icao24': sorted(['myicao']), 
                              'serials': sorted([123]), '_func_': 'get_my_states'}
        mock_cursor.execute.assert_any_call(
            "INSERT OR REPLACE INTO states_cache (params_json, timestamp, data) VALUES (?, ?, ?)",
            (json.dumps(expected_cache_key, sort_keys=True), current_ts, json.dumps(expected_serialized))
        )
        self.assertEqual(result, expected_serialized)

    def test_get_my_states_no_auth_returns_error_string(self):
        # Call through mcp
        self.assertEqual(self.mock_mcp.get_my_states(username=None, password="pw"), 
                         "Error: Username and password are required for get_my_states.")
        self.assertEqual(self.mock_mcp.get_my_states(username="user", password=None), 
                         "Error: Username and password are required for get_my_states.")

    # --- Generic test structure for Flight list returning functions ---
    def _test_flight_list_function_cache_miss(self, func_name_on_mcp, api_method_name_on_client, cache_table_name):
        with patch('adsblol.opensky.time.time') as mock_time_time, \
             patch('adsblol.opensky.OpenSkyApi') as MockOpenSkyApiConstructor, \
             patch('adsblol.opensky.sqlite3.connect') as mock_sqlite_connect:

            current_ts = 20000
            mock_time_time.return_value = current_ts
            mock_db_conn = MagicMock(spec=sqlite3.Connection)
            mock_cursor = MagicMock(spec=sqlite3.Cursor)
            mock_sqlite_connect.return_value = mock_db_conn
            mock_db_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None # Cache miss

            mock_api_instance = MagicMock(spec=RealOpenSkyApi)
            MockOpenSkyApiConstructor.return_value = mock_api_instance
            # Make the mock API client's method return the prepared list of flights
            getattr(mock_api_instance, api_method_name_on_client).return_value = self.mock_flight_list_for_api_return
            
            tool_func_on_mcp = getattr(self.mock_mcp, func_name_on_mcp)
            
            # Define params based on function signature
            if func_name_on_mcp in ["get_arrivals_by_airport", "get_departures_by_airport"]:
                params_in = {'airport': 'EDDF', 'begin': 1000, 'end': 2000}
            elif func_name_on_mcp == "get_flights_by_aircraft":
                params_in = {'icao24': 'flt_icao1', 'begin': 1000, 'end': 2000}
            elif func_name_on_mcp == "get_flights_from_interval":
                 params_in = {'begin': 1000, 'end': 2000}
            else:
                raise ValueError(f"Unsupported func_name_on_mcp: {func_name_on_mcp}")

            result = tool_func_on_mcp(**params_in, username="user", password="pw") # Call through mcp

            MockOpenSkyApiConstructor.assert_called_once_with(username="user", password="pw")
            getattr(mock_api_instance, api_method_name_on_client).assert_called_once_with(**params_in)
            
            expected_serialized = adsblol.opensky._serialize_flights(self.mock_flight_list_for_api_return)
            expected_cache_key_json = json.dumps(params_in, sort_keys=True)
            mock_cursor.execute.assert_any_call( # SELECT call
                f"SELECT timestamp, data FROM {cache_table_name} WHERE params_json = ?", (expected_cache_key_json,)
            )
            mock_cursor.execute.assert_any_call( # INSERT call
                f"INSERT OR REPLACE INTO {cache_table_name} (params_json, timestamp, data) VALUES (?, ?, ?)",
                (expected_cache_key_json, current_ts, json.dumps(expected_serialized))
            )
            mock_db_conn.commit.assert_called_once()
            mock_db_conn.close.assert_called_once()
            self.assertEqual(result, expected_serialized)

    def test_get_arrivals_by_airport_cache_miss_success(self):
        self._test_flight_list_function_cache_miss("get_arrivals_by_airport", "get_arrivals_by_airport", "flights_cache")

    def test_get_departures_by_airport_cache_miss_success(self):
        self._test_flight_list_function_cache_miss("get_departures_by_airport", "get_departures_by_airport", "flights_cache")

    def test_get_flights_by_aircraft_cache_miss_success(self):
        self._test_flight_list_function_cache_miss("get_flights_by_aircraft", "get_flights_by_aircraft", "flights_cache")

    def test_get_flights_from_interval_cache_miss_success(self):
        self._test_flight_list_function_cache_miss("get_flights_from_interval", "get_flights_from_interval", "flights_cache")

    # --- Tests for get_track_by_aircraft ---
    @patch('adsblol.opensky.time.time')
    @patch('adsblol.opensky.OpenSkyApi')
    @patch('adsblol.opensky.sqlite3.connect')
    def test_get_track_by_aircraft_cache_miss_success(self, mock_sqlite_connect, MockOpenSkyApiConstructor, mock_time_time):
        current_ts = 30000
        mock_time_time.return_value = current_ts
        mock_db_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Cache miss

        mock_api_instance = MagicMock(spec=RealOpenSkyApi)
        MockOpenSkyApiConstructor.return_value = mock_api_instance
        mock_api_instance.get_track_by_aircraft.return_value = self.mock_track_for_api_return

        params_in_mcp_call = {'icao24': 'trk_icao1', 't': 0} # 't' is arg name for mcp tool
        # The actual API call inside opensky.py uses 'time' for the parameter 't'
        api_call_params = {'icao24': 'trk_icao1', 'time': 0} 
        
        result = self.mock_mcp.get_track_by_aircraft(**params_in_mcp_call, username="u", password="p") # Call through mcp

        MockOpenSkyApiConstructor.assert_called_once_with(username="u", password="p")
        mock_api_instance.get_track_by_aircraft.assert_called_once_with(**api_call_params)
        
        expected_serialized = adsblol.opensky._serialize_track(self.mock_track_for_api_return)
        # Cache key uses 'time' as param name for 't', as defined in opensky.py
        cache_key_params = {'icao24': 'trk_icao1', 'time': 0} 
        expected_cache_key_json = json.dumps(cache_key_params, sort_keys=True)
        
        mock_cursor.execute.assert_any_call( # SELECT call
            "SELECT timestamp, data FROM tracks_cache WHERE params_json = ?", (expected_cache_key_json,)
        )
        mock_cursor.execute.assert_any_call( # INSERT call
            "INSERT OR REPLACE INTO tracks_cache (params_json, timestamp, data) VALUES (?, ?, ?)",
            (expected_cache_key_json, current_ts, json.dumps(expected_serialized))
        )
        mock_db_conn.commit.assert_called_once()
        mock_db_conn.close.assert_called_once()
        self.assertEqual(result, expected_serialized)


if __name__ == '__main__':
    #This allows running the tests directly from the file if needed for debugging
    #but typically tests are run by a test runner (e.g. `python -m unittest discover`)
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
