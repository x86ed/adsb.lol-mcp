import sqlite3
import json
import time
import sys # Added
import os  # Added

# Path setup to find the local opensky_api module
# This assumes that:
# 1. This file (opensky.py) is located in a directory (e.g., 'adsblol').
# 2. The 'adsblol' directory is a direct child of the project root.
# 3. The 'opensky-api/python' directory is also a child of the project root,
#    structured as 'project_root/opensky-api/python'.
_current_file_directory = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_file_directory) # Moves up from 'adsblol/' to the project root
_opensky_api_module_path = os.path.join(_project_root, 'opensky-api', 'python')

if _opensky_api_module_path not in sys.path:
    sys.path.insert(0, _opensky_api_module_path) # Prepend to prioritize this local version

from opensky_api import OpenSkyApi # Assuming this is the correct import

# Cache validity period in seconds (1 hour)
CACHE_VALIDITY_PERIOD = 3600

def setup_database(db_path='aircraft.db'):
    """
    Sets up the SQLite database for caching OpenSky API responses.
    Creates the necessary tables if they don't already exist.
    Args:
        db_path (str): Path to the SQLite database file.
    Returns:
        sqlite3.Connection: A connection object to the database.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opensky_requests_cache (
            params_json TEXT PRIMARY KEY,
            api_type TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            api_response_time INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opensky_flights_data (
            request_params_json TEXT NOT NULL,
            icao24 TEXT NOT NULL,
            firstSeen INTEGER NOT NULL,
            callsign TEXT,
            estDepartureAirport TEXT,
            lastSeen INTEGER,
            estArrivalAirport TEXT,
            estDepartureAirportHorizDistance INTEGER,
            estDepartureAirportVertDistance INTEGER,
            estArrivalAirportHorizDistance INTEGER,
            estArrivalAirportVertDistance INTEGER,
            departureAirportCandidatesCount INTEGER,
            arrivalAirportCandidatesCount INTEGER,
            PRIMARY KEY (request_params_json, icao24, firstSeen),
            FOREIGN KEY (request_params_json) REFERENCES opensky_requests_cache(params_json) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opensky_states_data (
            request_params_json TEXT NOT NULL,
            icao24 TEXT NOT NULL,
            last_contact INTEGER NOT NULL, /* Assuming last_contact is part of PK for states */
            callsign TEXT,
            origin_country TEXT,
            time_position INTEGER,
            longitude REAL,
            latitude REAL,
            baro_altitude REAL,
            on_ground BOOLEAN,
            velocity REAL,
            true_track REAL,
            vertical_rate REAL,
            sensors TEXT, /* Serialized list or JSON string */
            geo_altitude REAL,
            squawk TEXT,
            spi BOOLEAN,
            position_source INTEGER,
            category INTEGER,
            PRIMARY KEY (request_params_json, icao24, last_contact),
            FOREIGN KEY (request_params_json) REFERENCES opensky_requests_cache(params_json) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opensky_tracks_data (
            request_params_json TEXT NOT NULL PRIMARY KEY,
            icao24 TEXT NOT NULL,
            startTime INTEGER,
            endTime INTEGER,
            callsign TEXT,
            FOREIGN KEY (request_params_json) REFERENCES opensky_requests_cache(params_json) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opensky_track_waypoints_data (
            track_request_params_json TEXT NOT NULL,
            waypoint_index INTEGER NOT NULL,
            time INTEGER NOT NULL,
            latitude REAL,
            longitude REAL,
            baro_altitude REAL,
            true_track REAL,
            on_ground BOOLEAN,
            PRIMARY KEY (track_request_params_json, waypoint_index),
            FOREIGN KEY (track_request_params_json) REFERENCES opensky_tracks_data(request_params_json) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    return conn

# --- New Data Storage Helpers ---
def _store_states_to_db(cursor, request_params_json, states_obj):
    if not states_obj or not states_obj.states:
        return
    
    states_data_to_insert = []
    for s in states_obj.states:
        states_data_to_insert.append((
            request_params_json, s.icao24, s.last_contact, s.callsign, s.origin_country,
            s.time_position, s.longitude, s.latitude, s.baro_altitude,
            1 if s.on_ground else 0, s.velocity, s.true_track, s.vertical_rate,
            json.dumps(s.sensors) if s.sensors else None, s.geo_altitude, s.squawk,
            1 if s.spi else 0, s.position_source, s.category
        ))
    if states_data_to_insert:
        cursor.executemany('''
            INSERT INTO opensky_states_data (
                request_params_json, icao24, last_contact, callsign, origin_country, time_position,
                longitude, latitude, baro_altitude, on_ground, velocity, true_track,
                vertical_rate, sensors, geo_altitude, squawk, spi, position_source, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', states_data_to_insert)

def _store_flights_to_db(cursor, request_params_json, flights_list):
    if not flights_list:
        return
    flights_data_to_insert = []
    for f in flights_list:
        flights_data_to_insert.append((
            request_params_json, f.icao24, f.first_seen, f.callsign, f.est_departure_airport,
            f.last_seen, f.est_arrival_airport, f.est_departure_airport_horiz_distance,
            f.est_departure_airport_vert_distance, f.est_arrival_airport_horiz_distance,
            f.est_arrival_airport_vert_distance, f.departure_airport_candidates_count,
            f.arrival_airport_candidates_count
        ))
    if flights_data_to_insert:
        cursor.executemany('''
            INSERT INTO opensky_flights_data (
                request_params_json, icao24, firstSeen, callsign, estDepartureAirport,
                lastSeen, estArrivalAirport, estDepartureAirportHorizDistance,
                estDepartureAirportVertDistance, estArrivalAirportHorizDistance,
                estArrivalAirportVertDistance, departureAirportCandidatesCount,
                arrivalAirportCandidatesCount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', flights_data_to_insert)

def _store_track_to_db(cursor, request_params_json, track_obj):
    if not track_obj:
        return
    cursor.execute('''
        INSERT INTO opensky_tracks_data (
            request_params_json, icao24, startTime, endTime, callsign
        ) VALUES (?, ?, ?, ?, ?)
    ''', (request_params_json, track_obj.icao24, track_obj.start_time, track_obj.end_time, track_obj.callsign))

    if track_obj.path:
        waypoints_data_to_insert = []
        for i, wp in enumerate(track_obj.path):
            waypoints_data_to_insert.append((
                request_params_json, i, wp.time, wp.latitude, wp.longitude,
                wp.baro_altitude, wp.true_track, 1 if wp.on_ground else 0
            ))
        if waypoints_data_to_insert:
            cursor.executemany('''
                INSERT INTO opensky_track_waypoints_data (
                    track_request_params_json, waypoint_index, time, latitude, longitude,
                    baro_altitude, true_track, on_ground
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', waypoints_data_to_insert)

# --- New Data Reconstruction Helpers ---
def _reconstruct_states_from_db(rows, api_response_time):
    states_list = []
    for row in rows:
        # Order must match table definition + SELECT query
        states_list.append({
            'icao24': row[1], 'last_contact': row[2], 'callsign': row[3], 
            'origin_country': row[4], 'time_position': row[5], 'longitude': row[6],
            'latitude': row[7], 'baro_altitude': row[8], 'on_ground': bool(row[9]),
            'velocity': row[10], 'true_track': row[11], 'vertical_rate': row[12],
            'sensors': json.loads(row[13]) if row[13] else None, 'geo_altitude': row[14],
            'squawk': row[15], 'spi': bool(row[16]), 'position_source': row[17],
            'category': row[18]
            # request_params_json (row[0]) is not part of the state vector itself
        })
    return {'time': api_response_time, 'states': states_list}

def _reconstruct_flights_from_db(rows):
    flights_list = []
    for row in rows:
        flights_list.append({
            'icao24': row[1], 'firstSeen': row[2], 'callsign': row[3],
            'estDepartureAirport': row[4], 'lastSeen': row[5], 'estArrivalAirport': row[6],
            'estDepartureAirportHorizDistance': row[7], 'estDepartureAirportVertDistance': row[8],
            'estArrivalAirportHorizDistance': row[9], 'estArrivalAirportVertDistance': row[10],
            'departureAirportCandidatesCount': row[11], 'arrivalAirportCandidatesCount': row[12]
        })
    return flights_list

def _reconstruct_track_from_db(track_row, waypoint_rows):
    if not track_row:
        return None
    
    waypoints_list = []
    for wp_row in waypoint_rows:
        waypoints_list.append({
            'time': wp_row[2], 'latitude': wp_row[3], 'longitude': wp_row[4],
            'baro_altitude': wp_row[5], 'true_track': wp_row[6], 'on_ground': bool(wp_row[7])
        })
    
    return {
        'icao24': track_row[1], 'startTime': track_row[2], 'endTime': track_row[3],
        'callsign': track_row[4], 'path': waypoints_list
    }

# --- API Object to Dict Conversion (for consistent return format) ---
def _api_states_to_dict(states_obj):
    if not states_obj: return None
    return {
        'time': states_obj.time,
        'states': [s.__dict__ for s in states_obj.states if s] # Assuming StateVector has __dict__
    }

def _api_flights_to_list_of_dicts(flights_list):
    if not flights_list: return None
    return [f.__dict__ for f in flights_list if f] # Assuming FlightData has __dict__

def _api_track_to_dict(track_obj):
    if not track_obj: return None
    # Replicate structure of _reconstruct_track_from_db
    return {
        'icao24': track_obj.icao24,
        'callsign': track_obj.callsign,
        'startTime': track_obj.start_time,
        'endTime': track_obj.end_time,
        'path': [wp.__dict__ for wp in track_obj.path if wp] if track_obj.path else []
    }


def register_opensky(mcp):
    """
    Registers all OpenSky API tools with the FastMCP instance.
    Args:
        mcp: An instance of FastMCP.
    Returns:
        mcp: The FastMCP instance with registered tools.
    """

    @mcp.tool()
    def get_states(time_secs: int = 0, icao24: list = None, bbox: tuple = (), username: str = None, password: str = None, db_path: str = 'aircraft.db'):
        """
        Retrieves state vectors for all aircraft currently being tracked by OpenSky Network
        
        Args:
            time_secs: The time in seconds since epoch (Unix timestamp). If set to 0, the most recent data is returned.
            icao24: One or more ICAO24 transponder addresses represented as hex strings (e.g. 'abc9f3'). If None, all aircraft are returned.
            bbox: Bounding box coordinates as a tuple (min_latitude, max_latitude, min_longitude, max_longitude).
            username: OpenSky Network username. If not None, uses authenticated API access.
            password: OpenSky Network password. If not None, uses authenticated API access.
            db_path: Path to the SQLite database file for caching API responses.
            
        Returns:
            dict: Dictionary containing state vectors of aircraft, or None if no data is available
        """
        api_type = "states_general" # Generic type, can be refined based on params
        icao24_list = None
        if isinstance(icao24, str):
            icao24_list = [icao24]
            api_type = "states_icao"
        elif isinstance(icao24, list):
            icao24_list = sorted(icao24)
            api_type = "states_icao"
        
        if bbox:
            api_type = "states_bbox" if not icao24_list else "states_bbox_icao"

        params_for_key = {'time_secs': time_secs, 'icao24': icao24_list, 'bbox': bbox}
        params_json = json.dumps(params_for_key, sort_keys=True)
        
        conn = setup_database(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT timestamp, api_response_time FROM opensky_requests_cache WHERE params_json = ? AND api_type = ?", (params_json, api_type))
            cache_request_row = cursor.fetchone()

            if cache_request_row and (time.time() - cache_request_row[0] < CACHE_VALIDITY_PERIOD):
                api_response_time = cache_request_row[1]
                cursor.execute("SELECT * FROM opensky_states_data WHERE request_params_json = ?", (params_json,))
                state_rows = cursor.fetchall()
                conn.close()
                return _reconstruct_states_from_db(state_rows, api_response_time)

            # Cache miss or stale, call API
            api = OpenSkyApi(username=username, password=password)
            states_obj = api.get_states(time_secs=time_secs, icao24=icao24_list, bbox=bbox if bbox else None)

            if states_obj is None:
                conn.close()
                return None # Do not cache None results

            # API call successful, update cache
            conn.execute("BEGIN")
            # Clear old data for this specific params_json first (cascades to opensky_states_data)
            cursor.execute("DELETE FROM opensky_requests_cache WHERE params_json = ?", (params_json,))
            # Insert new request record
            cursor.execute("INSERT INTO opensky_requests_cache (params_json, api_type, timestamp, api_response_time) VALUES (?, ?, ?, ?)",
                           (params_json, api_type, int(time.time()), states_obj.time))
            # Store new states data
            _store_states_to_db(cursor, params_json, states_obj)
            conn.commit()
            
            return _api_states_to_dict(states_obj)

        except sqlite3.Error as e:
            if conn: conn.rollback()
            return f"Database error: {str(e)}"
        except Exception as e: # Catch other errors like API issues not returning None
            return f"Error calling OpenSky API or processing data: {str(e)}"
        finally:
            if conn: conn.close()
            
    @mcp.tool()
    def get_my_states(time_secs: int = 0, icao24: list = None, serials: list = None, username: str = None, password: str = None, db_path: str = 'aircraft.db'):
        """
        Retrieves state vectors for your own sensors, requires OpenSky Network credentials
        
        Args:
            time_secs: The time in seconds since epoch (Unix timestamp). If set to 0, the most recent data is returned.
            icao24: One or more ICAO24 transponder addresses represented as hex strings. If None, all aircraft from your sensors are returned.
            serials: Filter for specific sensors by serial numbers. If None, all your sensors are considered.
            username: OpenSky Network username (required).
            password: OpenSky Network password (required).
            db_path: Path to the SQLite database file for caching API responses.
            
        Returns:
            dict: Dictionary containing state vectors of aircraft from your sensors, or error message if authentication fails
        """
        if not username or not password:
            return "Error: Username and password are required for get_my_states."

        api_type = "my_states"
        params_for_key = {'time_secs': time_secs, 
                          'icao24': sorted(icao24) if icao24 else None, 
                          'serials': sorted(serials) if serials else None,
                          '_func_': 'get_my_states'} # Differentiate from general get_states
        params_json = json.dumps(params_for_key, sort_keys=True)

        conn = setup_database(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT timestamp, api_response_time FROM opensky_requests_cache WHERE params_json = ? AND api_type = ?", (params_json, api_type))
            cache_request_row = cursor.fetchone()
            if cache_request_row and (time.time() - cache_request_row[0] < CACHE_VALIDITY_PERIOD):
                api_response_time = cache_request_row[1]
                cursor.execute("SELECT * FROM opensky_states_data WHERE request_params_json = ?", (params_json,))
                state_rows = cursor.fetchall()
                conn.close()
                return _reconstruct_states_from_db(state_rows, api_response_time)

            api = OpenSkyApi(username=username, password=password)
            states_obj = api.get_my_states(time_secs=time_secs, icao24=icao24, serials=serials)
            if states_obj is None:
                conn.close()
                return None

            conn.execute("BEGIN")
            cursor.execute("DELETE FROM opensky_requests_cache WHERE params_json = ?", (params_json,))
            cursor.execute("INSERT INTO opensky_requests_cache (params_json, api_type, timestamp, api_response_time) VALUES (?, ?, ?, ?)",
                           (params_json, api_type, int(time.time()), states_obj.time))
            _store_states_to_db(cursor, params_json, states_obj)
            conn.commit()
            return _api_states_to_dict(states_obj)
        except sqlite3.Error as e:
            if conn: conn.rollback()
            return f"Database error: {str(e)}"
        except Exception as e:
            return f"Error calling OpenSky API or processing data: {str(e)}"
        finally:
            if conn: conn.close()

    # --- Flight Data Functions ---
    def _handle_flight_list_request(api_call_func, params_for_key, api_type, db_path, username, password):
        params_json = json.dumps(params_for_key, sort_keys=True)
        conn = setup_database(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT timestamp FROM opensky_requests_cache WHERE params_json = ? AND api_type = ?", (params_json, api_type))
            cache_request_row = cursor.fetchone()
            if cache_request_row and (time.time() - cache_request_row[0] < CACHE_VALIDITY_PERIOD):
                cursor.execute("SELECT * FROM opensky_flights_data WHERE request_params_json = ?", (params_json,))
                flight_rows = cursor.fetchall()
                conn.close()
                return _reconstruct_flights_from_db(flight_rows)

            # API call
            flights_list = api_call_func() # This needs to be a callable that executes the specific API method
            if flights_list is None: # Assuming API returns None on failure/no data
                conn.close()
                return None

            conn.execute("BEGIN")
            cursor.execute("DELETE FROM opensky_requests_cache WHERE params_json = ?", (params_json,))
            # For flights, there isn't a single 'api_response_time' like for states. Store current time or 0.
            cursor.execute("INSERT INTO opensky_requests_cache (params_json, api_type, timestamp, api_response_time) VALUES (?, ?, ?, ?)",
                           (params_json, api_type, int(time.time()), 0)) # 0 for api_response_time
            _store_flights_to_db(cursor, params_json, flights_list)
            conn.commit()
            return _api_flights_to_list_of_dicts(flights_list)
        except sqlite3.Error as e:
            if conn: conn.rollback()
            return f"Database error: {str(e)}"
        except Exception as e:
            return f"Error calling OpenSky API or processing data: {str(e)}"
        finally:
            if conn: conn.close()

    @mcp.tool()
    def get_arrivals_by_airport(airport: str, begin: int, end: int, username: str = None, password: str = None, db_path: str = 'aircraft.db'):
        """
        Retrieves flights arriving at the specified airport in the given time interval
        
        Args:
            airport: ICAO code of the airport (e.g., 'EDDF', 'KLAX')
            begin: Start time of the interval as Unix timestamp (seconds since epoch)
            end: End time of the interval as Unix timestamp (seconds since epoch)
            username: OpenSky Network username. If not None, uses authenticated API access.
            password: OpenSky Network password. If not None, uses authenticated API access.
            db_path: Path to the SQLite database file for caching API responses.
            
        Returns:
            list: List of flight objects arriving at the specified airport, or None if no data is available
        """
        api = OpenSkyApi(username=username, password=password)
        api_call = lambda: api.get_arrivals_by_airport(airport=airport, begin=begin, end=end)
        params = {'airport': airport, 'begin': begin, 'end': end}
        return _handle_flight_list_request(api_call, params, 'flights_arrivals', db_path, username, password)

    @mcp.tool()
    def get_departures_by_airport(airport: str, begin: int, end: int, username: str = None, password: str = None, db_path: str = 'aircraft.db'):
        """
        Retrieves flights departing from the specified airport in the given time interval
        
        Args:
            airport: ICAO code of the airport (e.g., 'EDDF', 'KLAX')
            begin: Start time of the interval as Unix timestamp (seconds since epoch)
            end: End time of the interval as Unix timestamp (seconds since epoch)
            username: OpenSky Network username. If not None, uses authenticated API access.
            password: OpenSky Network password. If not None, uses authenticated API access.
            db_path: Path to the SQLite database file for caching API responses.
            
        Returns:
            list: List of flight objects departing from the specified airport, or None if no data is available
        """
        api = OpenSkyApi(username=username, password=password)
        api_call = lambda: api.get_departures_by_airport(airport=airport, begin=begin, end=end)
        params = {'airport': airport, 'begin': begin, 'end': end}
        return _handle_flight_list_request(api_call, params, 'flights_departures', db_path, username, password)

    @mcp.tool()
    def get_flights_by_aircraft(icao24: str, begin: int, end: int, username: str = None, password: str = None, db_path: str = 'aircraft.db'):
        """
        Retrieves flights for a particular aircraft within the given time interval
        
        Args:
            icao24: ICAO24 transponder address of the aircraft as hex string (e.g. 'abc9f3')
            begin: Start time of the interval as Unix timestamp (seconds since epoch)
            end: End time of the interval as Unix timestamp (seconds since epoch)
            username: OpenSky Network username. If not None, uses authenticated API access.
            password: OpenSky Network password. If not None, uses authenticated API access.
            db_path: Path to the SQLite database file for caching API responses.
            
        Returns:
            list: List of flight objects for the specified aircraft, or None if no data is available
        """
        api = OpenSkyApi(username=username, password=password)
        api_call = lambda: api.get_flights_by_aircraft(icao24=icao24, begin=begin, end=end)
        params = {'icao24': icao24, 'begin': begin, 'end': end}
        return _handle_flight_list_request(api_call, params, 'flights_by_aircraft', db_path, username, password)

    @mcp.tool()
    def get_flights_from_interval(begin: int, end: int, username: str = None, password: str = None, db_path: str = 'aircraft.db'):
        """
        Retrieves all flights within the given time interval
        
        Args:
            begin: Start time of the interval as Unix timestamp (seconds since epoch)
            end: End time of the interval as Unix timestamp (seconds since epoch)
            username: OpenSky Network username. If not None, uses authenticated API access.
            password: OpenSky Network password. If not None, uses authenticated API access.
            db_path: Path to the SQLite database file for caching API responses.
            
        Returns:
            list: List of flight objects for the specified time interval, or None if no data is available
        """
        api = OpenSkyApi(username=username, password=password)
        api_call = lambda: api.get_flights_from_interval(begin=begin, end=end)
        params = {'begin': begin, 'end': end}
        return _handle_flight_list_request(api_call, params, 'flights_from_interval', db_path, username, password)

    @mcp.tool()
    def get_track_by_aircraft(icao24: str, t: int = 0, username: str = None, password: str = None, db_path: str = 'aircraft.db'):
        """
        Retrieves the trajectory for a particular aircraft at a given time
        
        Args:
            icao24: ICAO24 transponder address of the aircraft as hex string (e.g. 'abc9f3')
            t: Time in seconds since epoch (Unix timestamp). If set to 0, the most recent track is returned.
            username: OpenSky Network username. If not None, uses authenticated API access.
            password: OpenSky Network password. If not None, uses authenticated API access.
            db_path: Path to the SQLite database file for caching API responses.
            
        Returns:
            dict: Dictionary containing the track data including path waypoints, or None if no data is available
        """
        api_type = "track_icao24"
        params_for_key = {'icao24': icao24, 'time': t} # Use 'time' for consistency in key
        params_json = json.dumps(params_for_key, sort_keys=True)

        conn = setup_database(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT timestamp FROM opensky_requests_cache WHERE params_json = ? AND api_type = ?", (params_json, api_type))
            cache_request_row = cursor.fetchone()

            if cache_request_row and (time.time() - cache_request_row[0] < CACHE_VALIDITY_PERIOD):
                # Fetch track master data
                cursor.execute("SELECT * FROM opensky_tracks_data WHERE request_params_json = ?", (params_json,))
                track_master_row = cursor.fetchone()
                if not track_master_row: # Should not happen if request_cache entry exists
                    conn.close()
                    return None 
                # Fetch waypoints
                cursor.execute("SELECT * FROM opensky_track_waypoints_data WHERE track_request_params_json = ? ORDER BY waypoint_index ASC", (params_json,))
                waypoint_rows = cursor.fetchall()
                conn.close()
                return _reconstruct_track_from_db(track_master_row, waypoint_rows)

            api = OpenSkyApi(username=username, password=password)
            track_obj = api.get_track_by_aircraft(icao24=icao24, time=t) # API uses 'time'
            if track_obj is None:
                conn.close()
                return None

            conn.execute("BEGIN")
            cursor.execute("DELETE FROM opensky_requests_cache WHERE params_json = ?", (params_json,)) # Cascades
            # For tracks, use track_obj.start_time or current time if not available for api_response_time
            api_resp_time_for_cache = track_obj.start_time if track_obj.start_time else int(time.time())
            cursor.execute("INSERT INTO opensky_requests_cache (params_json, api_type, timestamp, api_response_time) VALUES (?, ?, ?, ?)",
                           (params_json, api_type, int(time.time()), api_resp_time_for_cache))
            _store_track_to_db(cursor, params_json, track_obj)
            conn.commit()
            return _api_track_to_dict(track_obj)
        except sqlite3.Error as e:
            if conn: conn.rollback()
            return f"Database error: {str(e)}"
        except Exception as e:
            return f"Error calling OpenSky API or processing data: {str(e)}"
        finally:
            if conn: conn.close()
            
    return mcp
