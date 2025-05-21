import sqlite3
import json
import time
from opensky_api import OpenSkyApi # Assuming this is the correct import

# Cache validity period in seconds (1 hour)
CACHE_VALIDITY_PERIOD = 3600

def setup_database(db_path='opensky_cache.db'):
    """
    Sets up the SQLite database for caching OpenSky API responses.
    Creates the necessary tables if they don't already exist.
    Args:
        db_path (str): Path to the SQLite database file.
    Returns:
        sqlite3.Connection: A connection object to the database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS states_cache (
            params_json TEXT PRIMARY KEY,
            timestamp INTEGER,
            data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flights_cache (
            params_json TEXT PRIMARY KEY,
            timestamp INTEGER,
            data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracks_cache (
            params_json TEXT PRIMARY KEY,
            timestamp INTEGER,
            data TEXT
        )
    ''')
    conn.commit()
    return conn

def _serialize_states(states_obj):
    if not states_obj:
        return None
    return {
        'time': states_obj.time,
        'states': [s.__dict__ for s in states_obj.states if s]
    }

def _serialize_flights(flights_list):
    if not flights_list:
        return None
    return [f.__dict__ for f in flights_list if f]

def _serialize_track(track_obj):
    if not track_obj:
        return None
    path_as_dicts = [wp.__dict__ for wp in track_obj.path if wp] if track_obj.path else []
    serialized_track = track_obj.__dict__.copy()
    serialized_track['path'] = path_as_dicts
    return serialized_track

def register_opensky(mcp):
    """
    Registers all OpenSky API tools with the FastMCP instance.
    Args:
        mcp: An instance of FastMCP.
    Returns:
        mcp: The FastMCP instance with registered tools.
    """

    @mcp.tool
    def get_arrivals_by_airport(airport: str, begin: int, end: int, username: str = None, password: str = None, db_path: str = 'opensky_cache.db'):
        """
        Retrieves arrival flights for a given airport within a specified time interval.
        Args:
            airport (str): ICAO24 code of the airport.
            begin (int): Start of the time interval as Unix timestamp (seconds).
            end (int): End of the time interval as Unix timestamp (seconds).
            username (str, optional): OpenSky Network username.
            password (str, optional): OpenSky Network password.
            db_path (str, optional): Path to the SQLite cache database.
        Returns:
            list: A list of flight data dictionaries, or None.
        """
        params = {'airport': airport, 'begin': begin, 'end': end}
        params_json = json.dumps(params, sort_keys=True)
        cache_table = 'flights_cache'

        conn = setup_database(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT timestamp, data FROM {cache_table} WHERE params_json = ?", (params_json,))
        row = cursor.fetchone()

        if row and (time.time() - row[0] < CACHE_VALIDITY_PERIOD):
            conn.close()
            return json.loads(row[1])

        api = OpenSkyApi(username=username, password=password)
        try:
            flights_list = api.get_arrivals_by_airport(airport, begin, end)
        except Exception as e:
            conn.close()
            return f"Error calling OpenSky API: {str(e)}"


        if flights_list is None:
            conn.close()
            return None

        serialized_data = _serialize_flights(flights_list)
        if serialized_data:
            cursor.execute(f"INSERT OR REPLACE INTO {cache_table} (params_json, timestamp, data) VALUES (?, ?, ?)",
                           (params_json, int(time.time()), json.dumps(serialized_data)))
            conn.commit()
        
        conn.close()
        return serialized_data

    @mcp.tool
    def get_departures_by_airport(airport: str, begin: int, end: int, username: str = None, password: str = None, db_path: str = 'opensky_cache.db'):
        """
        Retrieves departure flights for a given airport within a specified time interval.
        Args:
            airport (str): ICAO24 code of the airport.
            begin (int): Start of the time interval as Unix timestamp (seconds).
            end (int): End of the time interval as Unix timestamp (seconds).
            username (str, optional): OpenSky Network username.
            password (str, optional): OpenSky Network password.
            db_path (str, optional): Path to the SQLite cache database.
        Returns:
            list: A list of flight data dictionaries, or None.
        """
        params = {'airport': airport, 'begin': begin, 'end': end}
        params_json = json.dumps(params, sort_keys=True)
        cache_table = 'flights_cache'

        conn = setup_database(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT timestamp, data FROM {cache_table} WHERE params_json = ?", (params_json,))
        row = cursor.fetchone()

        if row and (time.time() - row[0] < CACHE_VALIDITY_PERIOD):
            conn.close()
            return json.loads(row[1])

        api = OpenSkyApi(username=username, password=password)
        try:
            flights_list = api.get_departures_by_airport(airport, begin, end)
        except Exception as e:
            conn.close()
            return f"Error calling OpenSky API: {str(e)}"


        if flights_list is None:
            conn.close()
            return None
        
        serialized_data = _serialize_flights(flights_list)
        if serialized_data:
            cursor.execute(f"INSERT OR REPLACE INTO {cache_table} (params_json, timestamp, data) VALUES (?, ?, ?)",
                           (params_json, int(time.time()), json.dumps(serialized_data)))
            conn.commit()

        conn.close()
        return serialized_data

    @mcp.tool
    def get_flights_by_aircraft(icao24: str, begin: int, end: int, username: str = None, password: str = None, db_path: str = 'opensky_cache.db'):
        """
        Retrieves flights for a specific aircraft within a specified time interval.
        Args:
            icao24 (str): ICAO24 address of the aircraft.
            begin (int): Start of the time interval as Unix timestamp (seconds).
            end (int): End of the time interval as Unix timestamp (seconds).
            username (str, optional): OpenSky Network username.
            password (str, optional): OpenSky Network password.
            db_path (str, optional): Path to the SQLite cache database.
        Returns:
            list: A list of flight data dictionaries, or None.
        """
        params = {'icao24': icao24, 'begin': begin, 'end': end}
        params_json = json.dumps(params, sort_keys=True)
        cache_table = 'flights_cache'

        conn = setup_database(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT timestamp, data FROM {cache_table} WHERE params_json = ?", (params_json,))
        row = cursor.fetchone()

        if row and (time.time() - row[0] < CACHE_VALIDITY_PERIOD):
            conn.close()
            return json.loads(row[1])

        api = OpenSkyApi(username=username, password=password)
        try:
            flights_list = api.get_flights_by_aircraft(icao24, begin, end)
        except Exception as e:
            conn.close()
            return f"Error calling OpenSky API: {str(e)}"

        if flights_list is None:
            conn.close()
            return None

        serialized_data = _serialize_flights(flights_list)
        if serialized_data:
            cursor.execute(f"INSERT OR REPLACE INTO {cache_table} (params_json, timestamp, data) VALUES (?, ?, ?)",
                           (params_json, int(time.time()), json.dumps(serialized_data)))
            conn.commit()
        
        conn.close()
        return serialized_data

    @mcp.tool
    def get_flights_from_interval(begin: int, end: int, username: str = None, password: str = None, db_path: str = 'opensky_cache.db'):
        """
        Retrieves all flights within a specified time interval.
        Args:
            begin (int): Start of the time interval as Unix timestamp (seconds).
            end (int): End of the time interval as Unix timestamp (seconds).
            username (str, optional): OpenSky Network username.
            password (str, optional): OpenSky Network password.
            db_path (str, optional): Path to the SQLite cache database.
        Returns:
            list: A list of flight data dictionaries, or None.
        """
        params = {'begin': begin, 'end': end}
        params_json = json.dumps(params, sort_keys=True)
        cache_table = 'flights_cache'

        conn = setup_database(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT timestamp, data FROM {cache_table} WHERE params_json = ?", (params_json,))
        row = cursor.fetchone()

        if row and (time.time() - row[0] < CACHE_VALIDITY_PERIOD):
            conn.close()
            return json.loads(row[1])

        api = OpenSkyApi(username=username, password=password)
        try:
            flights_list = api.get_flights_from_interval(begin, end)
        except Exception as e:
            conn.close()
            return f"Error calling OpenSky API: {str(e)}"

        if flights_list is None:
            conn.close()
            return None
        
        serialized_data = _serialize_flights(flights_list)
        if serialized_data:
            cursor.execute(f"INSERT OR REPLACE INTO {cache_table} (params_json, timestamp, data) VALUES (?, ?, ?)",
                           (params_json, int(time.time()), json.dumps(serialized_data)))
            conn.commit()

        conn.close()
        return serialized_data

    @mcp.tool
    def get_my_states(time_secs: int = 0, icao24: list = None, serials: list = None, username: str = None, password: str = None, db_path: str = 'opensky_cache.db'):
        """
        Retrieves state vectors for your own sensors. Requires authentication.
        Args:
            time_secs (int, optional): Unix timestamp. If 0, current time.
            icao24 (list, optional): List of ICAO24 addresses.
            serials (list, optional): List of serial numbers of receivers.
            username (str): OpenSky Network username (required).
            password (str): OpenSky Network password (required).
            db_path (str, optional): Path to the SQLite cache database.
        Returns:
            dict: State vectors data, or an error message string.
        """
        if not username or not password:
            return "Error: Username and password are required for get_my_states."

        params = {'time_secs': time_secs, 'icao24': sorted(icao24) if icao24 else None, 'serials': sorted(serials) if serials else None}
        # Exclude username/password from params_json for cache key privacy/consistency
        params_key_dict = {'time_secs': time_secs, 'icao24': sorted(icao24) if icao24 else None, 'serials': sorted(serials) if serials else None, '_func_': 'get_my_states'}

        params_json = json.dumps(params_key_dict, sort_keys=True)
        cache_table = 'states_cache'

        conn = setup_database(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT timestamp, data FROM {cache_table} WHERE params_json = ?", (params_json,))
        row = cursor.fetchone()

        if row and (time.time() - row[0] < CACHE_VALIDITY_PERIOD):
            conn.close()
            return json.loads(row[1])

        api = OpenSkyApi(username=username, password=password)
        try:
            states_obj = api.get_my_states(time_secs=time_secs, icao24=icao24, serials=serials)
        except Exception as e:
            conn.close()
            return f"Error calling OpenSky API: {str(e)}"

        if states_obj is None:
            conn.close()
            return None
        
        serialized_data = _serialize_states(states_obj)
        if serialized_data:
            cursor.execute(f"INSERT OR REPLACE INTO {cache_table} (params_json, timestamp, data) VALUES (?, ?, ?)",
                           (params_json, int(time.time()), json.dumps(serialized_data)))
            conn.commit()
        
        conn.close()
        return serialized_data

    @mcp.tool
    def get_states(time_secs: int = 0, icao24: list = None, bbox: tuple = (), username: str = None, password: str = None, db_path: str = 'opensky_cache.db'):
        """
        Retrieves state vectors for aircraft.
        Args:
            time_secs (int, optional): Unix timestamp. If 0, current time.
            icao24 (list or str, optional): List of ICAO24 addresses or single ICAO24.
            bbox (tuple, optional): Bounding box (min_lat, max_lat, min_lon, max_lon).
            username (str, optional): OpenSky Network username.
            password (str, optional): OpenSky Network password.
            db_path (str, optional): Path to the SQLite cache database.
        Returns:
            dict: State vectors data, or None.
        """
        # Ensure icao24 is a list for consistent hashing if it's a string
        icao24_list = None
        if isinstance(icao24, str):
            icao24_list = [icao24]
        elif isinstance(icao24, list):
            icao24_list = sorted(icao24)


        params = {'time_secs': time_secs, 'icao24': icao24_list, 'bbox': bbox}
        params_json = json.dumps(params, sort_keys=True)
        cache_table = 'states_cache'

        conn = setup_database(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT timestamp, data FROM {cache_table} WHERE params_json = ?", (params_json,))
        row = cursor.fetchone()

        if row and (time.time() - row[0] < CACHE_VALIDITY_PERIOD):
            conn.close()
            return json.loads(row[1])

        api = OpenSkyApi(username=username, password=password)
        try:
            # API expects single icao24 as str, or list. Our icao24_list is fine.
            states_obj = api.get_states(time_secs=time_secs, icao24=icao24_list, bbox=bbox if bbox else None)
        except Exception as e:
            conn.close()
            return f"Error calling OpenSky API: {str(e)}"
        
        if states_obj is None:
            conn.close()
            return None

        serialized_data = _serialize_states(states_obj)
        if serialized_data:
            cursor.execute(f"INSERT OR REPLACE INTO {cache_table} (params_json, timestamp, data) VALUES (?, ?, ?)",
                           (params_json, int(time.time()), json.dumps(serialized_data)))
            conn.commit()

        conn.close()
        return serialized_data

    @mcp.tool
    def get_track_by_aircraft(icao24: str, t: int = 0, username: str = None, password: str = None, db_path: str = 'opensky_cache.db'):
        """
        Retrieves the track for a specific aircraft.
        Args:
            icao24 (str): ICAO24 address of the aircraft.
            t (int, optional): Unix timestamp for historical tracks. If 0, current track.
            username (str, optional): OpenSky Network username.
            password (str, optional): OpenSky Network password.
            db_path (str, optional): Path to the SQLite cache database.
        Returns:
            dict: Track data, or None.
        """
        params = {'icao24': icao24, 'time': t} # API uses 'time', docstring used 't'
        params_json = json.dumps(params, sort_keys=True)
        cache_table = 'tracks_cache'

        conn = setup_database(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT timestamp, data FROM {cache_table} WHERE params_json = ?", (params_json,))
        row = cursor.fetchone()

        if row and (time.time() - row[0] < CACHE_VALIDITY_PERIOD):
            conn.close()
            return json.loads(row[1])

        api = OpenSkyApi(username=username, password=password)
        try:
            track_obj = api.get_track_by_aircraft(icao24, time=t)
        except Exception as e:
            conn.close()
            return f"Error calling OpenSky API: {str(e)}"

        if track_obj is None:
            conn.close()
            return None
        
        serialized_data = _serialize_track(track_obj)
        if serialized_data:
            cursor.execute(f"INSERT OR REPLACE INTO {cache_table} (params_json, timestamp, data) VALUES (?, ?, ?)",
                           (params_json, int(time.time()), json.dumps(serialized_data)))
            conn.commit()

        conn.close()
        return serialized_data

    return mcp
