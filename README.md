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

```bash
# Clone the repository
git clone https://github.com/yourusername/adsb.lol-mcp.git
cd adsb.lol-mcp

# Initialize the OpenSky API submodule (if cloned without --recursive)
git submodule update --init --recursive

# Install dependencies using UV
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### OpenSky API Setup

This project uses a local copy of the OpenSky API Python library located in the `opensky-api/python` directory. The project is configured to use this local version rather than the PyPI package to ensure compatibility and access to the latest features.

The local OpenSky API dependency is automatically handled by the `pyproject.toml` configuration:

```toml
[tool.uv.sources]
opensky-api = { path = "opensky-api/python" }
```

If you encounter issues with the OpenSky integration, ensure the `opensky-api` directory is present and contains the Python module.

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
