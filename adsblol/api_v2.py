from typing import Any
import httpx

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
        """
        url = f"{API_BASE}/v2/pia"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No PIA aircraft found."

        if not data["ac"]:
            return "No PIA aircraft found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_mil() -> str:
        """Returns all military registered aircraft.
        """
        url = f"{API_BASE}/v2/mil"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No military aircraft found."

        if not data["ac"]:
            return "No military aircraft found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

    @mcp.tool()
    async def get_ladd() -> str:
        """Returns all LADD aircraft. https://www.faa.gov/pilots/ladd
        """
        url = f"{API_BASE}/v2/ladd"
        data = await make_api_request(url)

        if not data or "ac" not in data:
            return "No LADD aircraft found."

        if not data["ac"]:
            return "No LADD aircraft found."

        aircraft = [format_markdown(acItem) for acItem in data["ac"]]
        return "\n---\n".join(aircraft)

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
    
    return mcp