import sys
import os
import time
import unittest
from unittest import mock
import sqlite3
import tempfile
from bs4 import BeautifulSoup

# Add the parent directory to sys.path to properly import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the functions from faa.py with the correct path
from adsblol.faa import (
    parse_faa_aircraft_data, process_html_content, setup_database, 
    save_aircraft_data, register_FAA_Reg
)

class TestFAARegistration(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method is run."""
        # Create sample HTML content for testing
        self.sample_html = """
        <html>
        <body>
            <div id="mainDiv">
                <table class="devkit-table">
                    <caption class="devkit-table-title">Aircraft Information</caption>
                    <tr>
                        <td>N-Number</td>
                        <td>N12345</td>
                    </tr>
                    <tr>
                        <td>Serial Number</td>
                        <td>12345</td>
                    </tr>
                    <tr>
                        <td>Manufacturer</td>
                        <td>CESSNA</td>
                    </tr>
                </table>
                <table class="devkit-table">
                    <caption class="devkit-table-title">Engine Information</caption>
                    <tr>
                        <td>Type Engine</td>
                        <td>Reciprocating</td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """
        
        # Create a temporary database for testing
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        self.conn = setup_database(self.temp_db_path)

    def tearDown(self):
        """Tear down test fixtures after each test method is run."""
        self.conn.close()
        os.close(self.temp_db_fd)
        os.unlink(self.temp_db_path)

    def test_process_html_content(self):
        """Test that HTML content is correctly processed."""
        result = process_html_content(self.sample_html, "N12345")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["n_number"], "N12345")
        self.assertEqual(result["serial_number"], "12345")
        self.assertEqual(result["manufacturer"], "CESSNA")
        self.assertEqual(result["type_engine"], "Reciprocating")

    def test_process_html_content_no_data(self):
        """Test that empty HTML returns None."""
        result = process_html_content("<html><body></body></html>", "N12345")
        self.assertIsNone(result)

    def test_save_aircraft_data(self):
        """Test saving aircraft data to database."""
        aircraft_data = {
            "n_number": "N12345",
            "manufacturer": "BOEING",
            "model": "747"
        }
        
        success = save_aircraft_data(self.conn, aircraft_data)
        self.assertTrue(success)
        
        # Updated table name from aircraft to faa_reg
        cursor = self.conn.cursor()
        cursor.execute("SELECT manufacturer, model FROM faa_reg WHERE n_number = ?", 
                      ("N12345",))
        result = cursor.fetchone()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "BOEING")
        self.assertEqual(result[1], "747")

    def test_save_aircraft_data_duplicate(self):
        """Test that saving duplicate n_number replaces the old record."""
        # Insert initial data
        aircraft_data1 = {
            "n_number": "N12345",
            "manufacturer": "BOEING",
            "model": "747"
        }
        save_aircraft_data(self.conn, aircraft_data1)
        
        # Insert duplicate with updated data
        aircraft_data2 = {
            "n_number": "N12345",
            "manufacturer": "BOEING",
            "model": "787"
        }
        success = save_aircraft_data(self.conn, aircraft_data2)
        self.assertTrue(success)
        
        # Updated table name from aircraft to faa_reg
        cursor = self.conn.cursor()
        cursor.execute("SELECT model FROM faa_reg WHERE n_number = ?", ("N12345",))
        result = cursor.fetchone()
        
        self.assertEqual(result[0], "787")

    @mock.patch('adsblol.faa.urlopen')
    def test_parse_faa_aircraft_data(self, mock_urlopen):
        """Test parsing FAA aircraft data with mocked HTTP response."""
        # Mock the HTTP response
        mock_response = mock.Mock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = self.sample_html.encode('utf-8')
        mock_urlopen.return_value = mock_response
        
        # Test the function
        result = parse_faa_aircraft_data("N12345")
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertEqual(result["n_number"], "N12345")
        self.assertEqual(result["manufacturer"], "CESSNA")

    @mock.patch('adsblol.faa.urlopen')
    def test_parse_faa_aircraft_data_http_error(self, mock_urlopen):
        """Test handling of HTTP errors."""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(url="", code=404, msg="Not Found", hdrs={}, fp=None)
        
        result = parse_faa_aircraft_data("N12345")
        self.assertIsNone(result)

    def test_parse_faa_aircraft_data_local_file(self):
        """Test parsing from a local file."""
        # Create a temporary file with the sample HTML
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(self.sample_html)
            temp_path = temp_file.name
        
        try:
            # Test with the local file
            result = parse_faa_aircraft_data("N12345", use_local_file=True, local_file_path=temp_path)
            
            # Verify the result
            self.assertIsNotNone(result)
            self.assertEqual(result["n_number"], "N12345")
            self.assertEqual(result["manufacturer"], "CESSNA")
        finally:
            # Clean up the temporary file
            os.unlink(temp_path)

    def test_register_faa_reg(self):
        """Test registering FAA tools with MCP."""
        # Create a mock MCP
        class MockMCP:
            def __init__(self):
                self.tools = {}
                
            def tool(self):
                def decorator(func):
                    self.tools[func.__name__] = func
                    return func
                return decorator
        
        mock_mcp = MockMCP()
        
        # Register FAA tools
        register_FAA_Reg(mock_mcp)
        
        # Verify the tool was registered
        self.assertIn('batch_process_n_numbers', mock_mcp.tools)

    @mock.patch('adsblol.faa.parse_faa_aircraft_data')
    @mock.patch('adsblol.faa.save_aircraft_data')
    def test_batch_process_n_numbers(self, mock_save, mock_parse):
        """Test the batch_process_n_numbers function."""
        # Create mock MCP
        class MockMCP:
            def __init__(self):
                self.tools = {}
                
            def tool(self):
                def decorator(func):
                    self.tools[func.__name__] = func
                    return func
                return decorator
        
        mock_mcp = MockMCP()
        register_FAA_Reg(mock_mcp)
        
        # Mock parse_faa_aircraft_data to return test data
        mock_parse.side_effect = [
            {"n_number": "N12345", "manufacturer": "BOEING"},  # Success
            None,  # Failure
            {"n_number": "N54321", "manufacturer": "AIRBUS"}   # Success
        ]
        
        # Mock save_aircraft_data to return True when called
        mock_save.return_value = True
        
        # Test the batch processing function
        result = mock_mcp.tools['batch_process_n_numbers'](["N12345", "INVALID", "N54321"], self.temp_db_path)
        
        # Verify result
        self.assertIn("Success: 2, Failed: 1", result)
        
        # Verify parse_faa_aircraft_data was called for each n_number
        self.assertEqual(mock_parse.call_count, 3)
        
        # Verify save_aircraft_data was called twice (for the two successful parses)
        self.assertEqual(mock_save.call_count, 2)

    def test_save_aircraft_data_with_foreign_key(self):
        """Test saving aircraft data with a foreign key relationship."""
        # Insert a record into faa_reg to satisfy the foreign key constraint
        faa_data = {
            "n_number": "N12345",
            "manufacturer": "CESSNA",
            "model": "172S"
        }
        save_aircraft_data(self.conn, faa_data)
    
        cursor = self.conn.cursor()

        # Ensure lol_aircraft table exists for this specific test
        # Minimal schema for this test, including the foreign key
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lol_aircraft (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            hex TEXT NOT NULL,
            r TEXT,
            flight TEXT,
            FOREIGN KEY (r) REFERENCES faa_reg(n_number) ON DELETE CASCADE
        )
        ''')
        self.conn.commit() # Commit the table creation

        # Now insert a record into lol_aircraft referencing the n_number in faa_reg
        cursor.execute('''
        INSERT INTO lol_aircraft (timestamp, hex, r, flight) 
        VALUES (?, ?, ?, ?)
        ''', (int(time.time()), "a1b2c3", "N12345", "UAL123"))
        self.conn.commit()

        # Verify the record was saved
        cursor.execute("SELECT hex, r, flight FROM lol_aircraft WHERE r = ?", ("N12345",))
        result = cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "a1b2c3")
        self.assertEqual(result[1], "N12345")
        self.assertEqual(result[2], "UAL123")


if __name__ == '__main__':
    unittest.main()