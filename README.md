# adsb.lol-mcp

A Model Context Protocol (MCP) interface to the adsb.lol API and related aviation data services.

## Overview

This project provides a Model Context Protocol server that allows AI assistants to access real-time aircraft tracking data, FAA registration information, and OpenSky flight data. The server acts as a bridge between AI models and various aviation data sources.

## Features

- **ADSB.lol API Integration**: Query real-time aircraft data from the adsb.lol API
- **FAA Registration Data**: Look up aircraft registration details from the FAA registry
- **OpenSky Integration**: Access historical flight data through the OpenSky Network API
- **Local Data Caching**: SQLite database for efficient caching of aircraft and flight data
- **Formatted Output**: Structured data presentation for AI consumption
- **Emergency Services Tracking**: Specialized tracking for emergency and government aircraft

## Tech Stack

- **MCP**: Built on the Model Context Protocol for AI integration
- **Python 3.12+**: Modern Python features
- **UV**: For dependency management and virtual environment
- **Pytest**: Comprehensive test suite for all components
- **SQLite**: Local database for caching and persistence
- **HTTPX**: Asynchronous HTTP requests

## Installation

### Prerequisites

- Python 3.12 or higher
- UV package manager
- Git

### Cold Start Setup

```bash
# Clone the repository with submodules
git clone --recursive https://github.com/x86ed/adsb.lol-mcp.git
cd adsb.lol-mcp

# If you already cloned without --recursive, initialize submodules
git submodule update --init --recursive

# Set up Python environment with UV
uv venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate     # On Windows

# Install all dependencies
uv pip install -e .

# Initialize the aircraft database (creates aircraft.db if it doesn't exist)
python -c "from adsblol.api_v2 import setup_lol_aircraft_database; setup_lol_aircraft_database()"
```

### OpenSky API Setup

This project uses a local copy of the OpenSky API Python library located in the `opensky-api/python` directory. The project is configured to use this local version rather than the PyPI package to ensure compatibility and access to the latest features.

#### Pulling Down OpenSky Code

The OpenSky API is included as a Git submodule. To ensure you have the latest version:

```bash
# If setting up for the first time or the opensky-api directory is empty
git submodule update --init --recursive

# To update to the latest OpenSky API code
git submodule update --remote opensky-api

# If you need to manually clone the OpenSky repository (fallback option)
git clone https://github.com/openskynetwork/opensky-api.git
```

The local OpenSky API dependency is automatically handled by the `pyproject.toml` configuration:

```toml
[tool.uv.sources]
opensky-api = { path = "opensky-api/python" }
```

**Troubleshooting:**

- If the `opensky-api` directory is empty, run `git submodule update --init --recursive`
- Verify the Python module exists at `opensky-api/python/opensky_api.py`
- If you encounter import errors, ensure the submodule is properly initialized

## Testing

```bash
# Run the test suite
pytest
```

## Usage

```bash
# Run the MCP server
python -m adsblol.main
```

## License

See the [LICENSE](LICENSE) file for details.
