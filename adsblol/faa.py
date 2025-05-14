import ssl
import time
import random
from typing import List
from bs4 import BeautifulSoup
import sqlite3
import re
import argparse
import os
from urllib.parse import quote
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from urllib.error import URLError, HTTPError
import http.cookiejar

# Disable certificate verification
ssl._create_default_https_context = ssl._create_unverified_context

def parse_faa_aircraft_data(n_number, max_retries=3, use_local_file=False, local_file_path=None):
    """
    Fetches and parses aircraft registration data from the FAA registry or a local file
    
    Args:
        n_number (str): The aircraft N-Number (e.g., "464DF")
        max_retries (int): Maximum number of retry attempts
        use_local_file (bool): If True, use local HTML file instead of making a request
        local_file_path (str): Path to local HTML file
        
    Returns:
        dict: Dictionary containing the extracted aircraft data, or None if not found
    """
    if use_local_file:
        # Use local file instead of making a request
        file_path = local_file_path or os.path.join(os.path.dirname(__file__), "payload.html")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return process_html_content(html_content, n_number)
        except Exception as e:
            print(f"Error reading local file: {e}")
            return None
    
    # Format the URL with the N-Number
    base_url = "https://registry.faa.gov/AircraftInquiry/Search/NNumberResult"
    url = f"{base_url}?nNumberTxt={quote(n_number)}"
    
    # Headers to match the curl request exactly
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    
    # Set up cookies exactly as in the curl request
    cookie_string = 'AMCVS_AC781C8B53308D4B0A490D4D%40AdobeOrg=1; s_cc=true; AMCV_AC781C8B53308D4B0A490D4D%40AdobeOrg=1099438348%7CMCIDTS%7C20219%7CMCMID%7C39334329760870330892294039190202014585%7CMCAAMLH-1747524812%7C9%7CMCAAMB-1747537088%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1746939488s%7CNONE%7CMCAID%7C2F8DCFFF8515BE9C-40000B6C8E685D99%7CvVersion%7C2.1.0'
    headers['Cookie'] = cookie_string
    
    # Retry mechanism
    for attempt in range(max_retries):
        try:
            # Add a small random delay between attempts
            if attempt > 0:
                time.sleep(2 + random.random())
            
            # Make the request with the exact headers and cookies
            req = Request(url, headers=headers)
            response = urlopen(req)
            
            # Check if the request was successful
            if response.getcode() != 200:
                print(f"Attempt {attempt+1}: Error fetching data: HTTP {response.getcode()}")
                continue
                
            # Read and decode the response
            html_content = response.read().decode('utf-8')
            
            # Process the HTML content
            return process_html_content(html_content, n_number)
            
        except (HTTPError, URLError) as e:
            print(f"Attempt {attempt+1}: Error - {e}")
            if attempt == max_retries - 1:
                print(f"Failed to retrieve data after {max_retries} attempts")
                return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            if attempt == max_retries - 1:
                return None
    
    return None

def process_html_content(html_content, n_number):
    """
    Process HTML content from FAA website or local file
    
    Args:
        html_content (str): HTML content as string
        n_number (str): N-Number being processed
        
    Returns:
        dict: Aircraft data or None if not found
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    aircraft_data = {'n_number': n_number}
    
    # Check if we're getting a "no results" page
    # Replace 'text=' with 'string=' to fix the deprecation warning
    no_results = soup.find(string=re.compile("No aircraft found"))
    if no_results:
        print(f"FAA database reports no aircraft found with N-Number: {n_number}")
        return None
    
    # Find all tables in the document with devkit-table class
    tables = soup.find_all('table', class_='devkit-table')
    
    if not tables:
        print(f"No data tables found for N-Number: {n_number}")
        return None
    
    # Process each table based on its caption
    for table in tables:
        caption = table.find('caption', class_='devkit-table-title')
        if not caption:
            continue
            
        section_name = caption.text.strip()
        
        # Process the table rows
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                # Handle different table formats
                if len(cells) == 2:
                    # Simple key-value pair
                    field_name = cells[0].text.strip().rstrip(':').lower().replace(' ', '_')
                    field_value = cells[1].text.strip()
                    aircraft_data[field_name] = field_value
                elif len(cells) == 4:
                    # Two key-value pairs per row
                    field_name1 = cells[0].text.strip().rstrip(':').lower().replace(' ', '_')
                    field_value1 = cells[1].text.strip()
                    field_name2 = cells[2].text.strip().rstrip(':').lower().replace(' ', '_')
                    field_value2 = cells[3].text.strip()
                    
                    aircraft_data[field_name1] = field_value1
                    aircraft_data[field_name2] = field_value2
    
    # Clean up the data - remove "None" string values and empty strings
    aircraft_data = {k: v for k, v in aircraft_data.items() if v and v != "None" and v.strip()}
    
    # If we found any data beyond just the N-number
    if len(aircraft_data) > 1:
        return aircraft_data
    else:
        print(f"No meaningful data extracted for N-Number: {n_number}")
        return None

def setup_database(db_path='aircraft.db'):
    """
    Sets up the SQLite database with appropriate tables
    
    Args:
        db_path (str): Path to the SQLite database file
        
    Returns:
        sqlite3.Connection: Database connection object
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the table already exists - changed table name to faa_reg
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faa_reg'")
    table_exists = cursor.fetchone() is not None
    
    if table_exists:
        # If table exists but with old schema, warn the user
        print("Warning: Using existing faa_reg table. If this was created with a previous version,")
        print("consider creating a new database to use n_number as primary key.")
    else:
        # Create table with n_number as primary key (not id) - changed table name to faa_reg
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS faa_reg (
            n_number TEXT PRIMARY KEY,
            serial_number TEXT,
            manufacturer TEXT,
            model TEXT,
            type_registrant TEXT,
            name TEXT,
            street TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            region TEXT,
            county TEXT,
            country TEXT,
            last_action_date TEXT,
            certificate_issue_date TEXT,
            certification TEXT,
            type_aircraft TEXT,
            type_engine TEXT,
            status TEXT,
            mode_s_code_hex TEXT,
            fractional_ownership TEXT,
            airworthiness_date TEXT,
            other_names TEXT,
            expiration_date TEXT,
            weight_category TEXT,
            date_change_authorization TEXT,
            other_change_authorization TEXT,
            date_of_registration TEXT,
            registered_owner TEXT,
            manufacturer_name TEXT,
            model_designation TEXT,
            series_name TEXT,
            aircraft_category TEXT,
            builder TEXT,
            year_manufactured TEXT,
            number_of_engines TEXT,
            number_of_seats TEXT,
            weight TEXT,
            cruising_speed TEXT,
            engine_manufacturer TEXT,
            engine_model TEXT,
            propeller_manufacturer TEXT,
            propeller_model TEXT,
            fetch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    
    conn.commit()
    return conn

def save_aircraft_data(conn, aircraft_data):
    """
    Saves aircraft data to the database
    
    Args:
        conn (sqlite3.Connection): Database connection object
        aircraft_data (dict): Dictionary containing aircraft data
        
    Returns:
        bool: True if data was saved successfully, False otherwise
    """
    if not aircraft_data:
        return False
    
    cursor = conn.cursor()
    
    # Get all column names from the faa_reg table (changed from aircraft)
    cursor.execute("PRAGMA table_info(faa_reg)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Filter the aircraft_data to only include columns that exist in the table
    filtered_data = {k: v for k, v in aircraft_data.items() if k in columns}
    
    # Prepare SQL query
    columns_str = ', '.join(filtered_data.keys())
    placeholders = ', '.join(['?' for _ in filtered_data])
    
    # Prepare insert or update query (upsert) - changed table name to faa_reg
    query = f'''
    INSERT OR REPLACE INTO faa_reg (
        {columns_str}
    ) VALUES (
        {placeholders}
    )
    '''
    
    # Execute the query
    try:
        cursor.execute(query, list(filtered_data.values()))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        return False

def register_FAA_Reg(mcp): 
    @mcp.tool()
    def batch_process_n_numbers(n_numbers:List[str], db_path='aircraft.db', use_local_file=False):
        """
        Processes a batch of N-Numbers and saves the data to the database
        
        Args:
            n_numbers (list): List of aircraft N-Numbers to process
            db_path (str): Path to the SQLite database file
            use_local_file (bool): If True, use local HTML files instead of making requests
            
        Returns:
            str: Summary of the processing results
        """
        conn = setup_database(db_path)
        success_count = 0
        fail_count = 0
        
        for n_number in n_numbers:
            print(f"Processing N-Number: {n_number}")
            # If using local files, look for a file named [n_number].html
            local_file = f"{n_number}.html" if use_local_file else None
            aircraft_data = parse_faa_aircraft_data(n_number, use_local_file=use_local_file, local_file_path=local_file)
            
            if aircraft_data and save_aircraft_data(conn, aircraft_data):
                print(f"Successfully saved data for N-Number: {n_number}")
                success_count += 1
            else:
                print(f"Failed to process N-Number: {n_number}")
                fail_count += 1
        
        conn.close()
        return f"Processing complete. Success: {success_count}, Failed: {fail_count}"
    return mcp