from typing import Any, List
import httpx
import sqlite3
import json
import time
import os

# Constants
API_BASE = "https://api.adsb.lol"

async def make_api_request(url: str) -> dict[str, Any] | None:
    """Make a request to the adsb.lol API with proper error handling."""
    headers = {
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def setup_lol_aircraft_database(db_path='aircraft.db'):
    """
    Sets up the SQLite database with the lol_aircraft table
    
    Args:
        db_path (str): Path to the SQLite database file
        
    Returns:
        sqlite3.Connection: Database connection object
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lol_aircraft'")
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        # Create table based on flattened V2Response_AcItem schema
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lol_aircraft (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            hex TEXT NOT NULL,
            alert INTEGER,
            alt_baro TEXT,
            alt_geom INTEGER,
            baro_rate INTEGER,
            category TEXT,
            emergency TEXT,
            flight TEXT,
            gs REAL,
            gva INTEGER,
            lat REAL,
            lon REAL,
            messages INTEGER,
            mlat TEXT,  -- JSON array as string
            nac_p INTEGER,
            nac_v INTEGER,
            nav_altitude_mcp INTEGER,
            nav_heading REAL,
            nav_qnh REAL,
            nic INTEGER,
            nic_baro INTEGER,
            r TEXT,
            rc INTEGER,
            rssi REAL,
            sda INTEGER,
            seen REAL,
            seen_pos REAL,
            sil INTEGER,
            sil_type TEXT,
            spi INTEGER,
            squawk TEXT,
            t TEXT,
            tisb TEXT,  -- JSON array as string
            track REAL,
            type TEXT,
            version INTEGER,
            geom_rate INTEGER,
            db_flags INTEGER,
            nav_modes TEXT,  -- JSON array as string
            true_heading REAL,
            ias INTEGER,
            mach REAL,
            mag_heading REAL,
            oat INTEGER,
            roll REAL,
            tas INTEGER,
            tat INTEGER,
            track_rate REAL,
            wd INTEGER,
            ws INTEGER,
            gps_ok_before REAL,
            gps_ok_lat REAL,
            gps_ok_lon REAL,
            last_position_lat REAL,
            last_position_lon REAL,
            last_position_nic INTEGER,
            last_position_rc INTEGER,
            last_position_seen_pos REAL,
            rr_lat REAL,
            rr_lon REAL,
            calc_track INTEGER,
            nav_altitude_fms INTEGER
        )
        ''')
    
    conn.commit()
    return conn

def save_aircraft_to_db(aircraft_data, conn):
    """
    Save aircraft data to the database
    
    Args:
        aircraft_data (list): List of aircraft dictionaries
        conn (sqlite3.Connection): Database connection
        
    Returns:
        int: Number of records saved
    """
    cursor = conn.cursor()
    timestamp = int(time.time())
    count = 0
    
    for aircraft in aircraft_data:
        # Handle nested lastPosition object
        last_position = aircraft.get('lastPosition', {})
        if last_position is None:
            last_position = {}
            
        # Prepare data with proper column names and flattened structure
        data = {
            'timestamp': timestamp,
            'hex': aircraft.get('hex', ''),
            'alert': aircraft.get('alert'),
            'alt_baro': str(aircraft.get('alt_baro', '')),  # Convert to string to handle mixed types
            'alt_geom': aircraft.get('alt_geom'),
            'baro_rate': aircraft.get('baro_rate'),
            'category': aircraft.get('category'),
            'emergency': aircraft.get('emergency'),
            'flight': aircraft.get('flight'),
            'gs': aircraft.get('gs'),
            'gva': aircraft.get('gva'),
            'lat': aircraft.get('lat'),
            'lon': aircraft.get('lon'),
            'messages': aircraft.get('messages'),
            'mlat': json.dumps(aircraft.get('mlat', [])),
            'nac_p': aircraft.get('nac_p'),
            'nac_v': aircraft.get('nac_v'),
            'nav_altitude_mcp': aircraft.get('nav_altitude_mcp'),
            'nav_heading': aircraft.get('nav_heading'),
            'nav_qnh': aircraft.get('nav_qnh'),
            'nic': aircraft.get('nic'),
            'nic_baro': aircraft.get('nic_baro'),
            'r': aircraft.get('r'),
            'rc': aircraft.get('rc'),
            'rssi': aircraft.get('rssi'),
            'sda': aircraft.get('sda'),
            'seen': aircraft.get('seen'),
            'seen_pos': aircraft.get('seen_pos'),
            'sil': aircraft.get('sil'),
            'sil_type': aircraft.get('sil_type'),
            'spi': aircraft.get('spi'),
            'squawk': aircraft.get('squawk'),
            't': aircraft.get('t'),
            'tisb': json.dumps(aircraft.get('tisb', [])),
            'track': aircraft.get('track'),
            'type': aircraft.get('type', ''),
            'version': aircraft.get('version'),
            'geom_rate': aircraft.get('geom_rate'),
            'db_flags': aircraft.get('dbFlags'),
            'nav_modes': json.dumps(aircraft.get('nav_modes', [])),
            'true_heading': aircraft.get('true_heading'),
            'ias': aircraft.get('ias'),
            'mach': aircraft.get('mach'),
            'mag_heading': aircraft.get('mag_heading'),
            'oat': aircraft.get('oat'),
            'roll': aircraft.get('roll'),
            'tas': aircraft.get('tas'),
            'tat': aircraft.get('tat'),
            'track_rate': aircraft.get('track_rate'),
            'wd': aircraft.get('wd'),
            'ws': aircraft.get('ws'),
            'gps_ok_before': aircraft.get('gpsOkBefore'),
            'gps_ok_lat': aircraft.get('gpsOkLat'),
            'gps_ok_lon': aircraft.get('gpsOkLon'),
            'last_position_lat': last_position.get('lat'),
            'last_position_lon': last_position.get('lon'),
            'last_position_nic': last_position.get('nic'),
            'last_position_rc': last_position.get('rc'),
            'last_position_seen_pos': last_position.get('seen_pos'),
            'rr_lat': aircraft.get('rr_lat'),
            'rr_lon': aircraft.get('rr_lon'),
            'calc_track': aircraft.get('calc_track'),
            'nav_altitude_fms': aircraft.get('nav_altitude_fms')
        }
        
        # Generate placeholders and column names for SQL
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        
        try:
            cursor.execute(
                f"INSERT INTO lol_aircraft ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
            count += 1
        except sqlite3.Error as e:
            print(f"Error inserting record: {e}")
    
    conn.commit()
    return count

def format_markdown(data: dict, level: int = 1) -> str:
    """Format a dictionary as a Markdown string.
    
    Args:
        data: Dictionary to format
        level: Current header level (defaults to 1)
        
    Returns:
        Markdown-formatted string representation of the dictionary
    """
    if not isinstance(data, dict):
        return f"```\n{data}\n```"
    
    result = []
    
    # Process each key in the dictionary
    for key, value in data.items():
        # Format key as header
        if level <= 6:  # Markdown supports headers up to level 6
            result.append(f"{'#' * level} {key}")
        else:
            result.append(f"**{key}**")
        
        # Format value based on its type
        if isinstance(value, dict):
            # Recursively format nested dictionaries
            result.append(format_markdown(value, level + 1))
        elif isinstance(value, list):
            # Format lists as bullet points
            if not value:
                result.append("*No items*")
            else:
                for item in value:
                    if isinstance(item, dict):
                        # For a list of dictionaries
                        result.append("* " + format_markdown(item, level + 1).replace("\n", "\n  "))
                    else:
                        # For a list of primitive values
                        result.append(f"* {item}")
        elif value is None:
            result.append("*None*")
        else:
            # For primitive values
            result.append(f"{value}")
        
        # Add spacing between sections
        result.append("")
    
    return "\n".join(result)

def register_api_v2(mcp):
    """Register the version functionality"""

    @mcp.tool()
    async def get_pia() -> str:
        """Returns all aircraft with [PIA](https://nbaa.org/aircraft-operations/security/privacy/privacy-icao-address-pia/) addresses.
        Data is stored in the database table 'lol_aircraft' and a count is returned.
        """
        url = f"{API_BASE}/v2/pia"
        data = await make_api_request(url)

        if not data or "ac" not in data or not data["ac"]:
            return "No PIA aircraft found."
        
        # Set up database connection
        conn = setup_lol_aircraft_database()
        
        # Save aircraft data to database
        count = save_aircraft_to_db(data["ac"], conn)
        
        # Close database connection
        conn.close()
        
        # Return count of aircraft saved
        return f"Found and saved {count} PIA aircraft to database."

    @mcp.tool()
    async def get_mil() -> str:
        """Returns all military registered aircraft.
        Data is stored in the database table 'lol_aircraft' and a count is returned.
        """
        url = f"{API_BASE}/v2/mil"
        data = await make_api_request(url)

        if not data or "ac" not in data or not data["ac"]:
            return "No military aircraft found."
        
        # Set up database connection
        conn = setup_lol_aircraft_database()
        
        # Save aircraft data to database
        count = save_aircraft_to_db(data["ac"], conn)
        
        # Close database connection
        conn.close()
        
        # Return count of aircraft saved
        return f"Found and saved {count} military aircraft to database."

    @mcp.tool()
    async def get_ladd() -> str:
        """Returns all LADD aircraft. https://www.faa.gov/pilots/ladd
        Data is stored in the database table 'lol_aircraft' and a count is returned.
        """
        url = f"{API_BASE}/v2/ladd"
        data = await make_api_request(url)

        if not data or "ac" not in data or not data["ac"]:
            return "No LADD aircraft found."
        
        # Set up database connection
        conn = setup_lol_aircraft_database()
        
        # Save aircraft data to database
        count = save_aircraft_to_db(data["ac"], conn)
        
        # Close database connection
        conn.close()
        
        # Return count of aircraft saved
        return f"Found and saved {count} LADD aircraft to database."

    @mcp.tool()
    async def get_squawk(squawk: str) -> str:
        """Returns aircraft filtered by "squawk" transponder code. https://en.wikipedia.org/wiki/List_of_transponder_codes

        Args: 
            squawk: The squawk code to search for.
        """
        url = f"{API_BASE}/v2/sqk/{squawk}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft matching that squawk code found."

        if not data["ac"]:
            return "No aircraft matching that squawk code found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_type(aircraft_type: str) -> str:
        """Returns aircraft filtered by aircraft type designator code. https://en.wikipedia.org/wiki/List_of_aircraft_type_designators

        Args:
            aircraft_type: The aircraft type designator code to search for.
        """
        url = f"{API_BASE}/v2/type/{aircraft_type}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft matching that squawk code found."

        if not data["ac"]:
            return "No aircraft matching that squawk code found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_registration(registration: str) -> str:
        """Returns aircraft filtered by aircraft registration code (G-KELS). https://en.wikipedia.org/wiki/Aircraft_registration

        Args:
            registration: The aircraft registration code to search for.
        """
        url = f"{API_BASE}/v2/reg/{registration}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft matching that registration code found."

        if not data["ac"]:
            return "No aircraft matching that registration code found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_icao_hex(icao_hex: str) -> str:
        """Returns aircraft filtered by transponder hex code. https://en.wikipedia.org/wiki/Mode_S_transponder

        Args:
            icao_hex: The ICAO hex code to search for.
        """
        url = f"{API_BASE}/v2/icao/{icao_hex}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft matching that hex code found."

        if not data["ac"]:
            return "No aircraft matching that hex code found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_callsign(callsign: str) -> str:
        """Returns aircraft filtered by callsign. https://en.wikipedia.org/wiki/Callsign

        Args:
            callsign: The callsign to search for.
        """
        url = f"{API_BASE}/v2/callsign/{callsign}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft matching that callsign found."

        if not data["ac"]:
            return "No aircraft matching that callsign found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_search_radius(lat: str,lon: str, radius:str) -> str:
        """Returns aircraft located in a circle described by the latitude and longtidude of its center and its radius.

        Args:
            lat: The latitude of the center of the circle.
            lon: The longitude of the center of the circle.
            radius: The radius of the circle in nautical miles.
        """
        url = f"{API_BASE}/v2/point/{lat}/{lon}/{radius}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft found."

        if not data["ac"]:
            return "No aircraft found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_closest(lat: str,lon: str, radius:str) -> str:
        """Returns the closest aircraft to a point described by the latitude and longtidude within a radius up to 250nm.

        Args:
            lat: The latitude of the center of the circle.
            lon: The longitude of the center of the circle.
            radius: The radius of the circle in nautical miles.
        """
        url = f"{API_BASE}/v2/closest/{lat}/{lon}/{radius}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft found."

        if not data["ac"]:
            return "No aircraft found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)
    @mcp.tool()
    async def get_route(callsign: str) -> str:
        """Returns route of aircraft by callsign

        Args:
            callsign: The calsign to search for.
        """
        url = f"{API_BASE}/v0/route/{callsign}"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No aircraft matching that route found."

        if not data["ac"]:
            return "No aircraft matching that route found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)
    
    return mcp