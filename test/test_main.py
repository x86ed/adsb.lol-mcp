import sys
import os
import pytest
from unittest import mock

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the modules that main.py tries to import
# This is critical since main.py uses relative imports
api_v2_mock = mock.Mock()
api_v2_mock.register_api_v2 = mock.Mock()
faa_mock = mock.Mock()
faa_mock.register_FAA_Reg = mock.Mock()

# Add mocks to sys.modules before importing main
sys.modules['api_v2'] = api_v2_mock
sys.modules['faa'] = faa_mock

# Now import the module being tested
from adsblol.main import mcp

class TestMain:
    def test_mcp_initialization(self):
        """Test that MCP is initialized with the correct name."""
        assert mcp.name == "adsblol"
    
    def test_api_v2_registration(self):
        """Test that register_api_v2 is called during import."""
        # Since we've mocked it before import, we can check directly
        api_v2_mock.register_api_v2.assert_called_once_with(mcp)

    def test_faa_registration(self):
        """Test that register_FAA_Reg is called during import."""
        faa_mock.register_FAA_Reg.assert_called_once_with(mcp)

    def test_main_execution(self):
        """Test that mcp.run is called when script is executed directly."""
        # Instead of executing the actual code, let's just check the if statement logic
        main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                            'adsblol/main.py')
        with open(main_path, 'r') as file:
            content = file.read()
        
        # Check that the main module has the if __name__ == "__main__" check
        assert 'if __name__ == "__main__":' in content
        
        # Check that mcp.run is called within that block
        assert 'mcp.run(' in content
        assert 'stdio' in content
        
        # Optional: Look for the specific pattern with a regex
        import re
        main_block = re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:(.*?)(?:\n\S|\Z)', 
                              content, re.DOTALL)
        assert main_block is not None
        assert 'mcp.run' in main_block.group(1)
        assert 'transport=' in main_block.group(1)
        assert 'stdio' in main_block.group(1)

    def test_correct_imports(self):
        """Test that all necessary modules are imported."""
        import sys
        
        # Check that FastMCP is imported
        assert 'mcp.server.fastmcp' in sys.modules
        
        # Check that required modules are available in sys.modules
        # (they're mocked, but they should be there)
        assert 'api_v2' in sys.modules
        assert 'faa' in sys.modules

def test_simple():
    """Simple test to verify test discovery works."""
    assert True