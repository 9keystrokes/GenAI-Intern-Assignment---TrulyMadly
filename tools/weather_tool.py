"""
Weather Tool - Integration with OpenWeatherMap API
Provides current weather information by city name or coordinates
"""

import os
import logging
from typing import Any, Dict, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# OpenWeatherMap API configuration
OPENWEATHER_API_BASE = "https://api.openweathermap.org/data/2.5"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")


def _validate_api_key() -> Optional[str]:
    """Validate that the API key is configured."""
    if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY == "your_openweathermap_api_key_here":
        return "OpenWeatherMap API key not configured. Please set OPENWEATHER_API_KEY in your .env file."
    return None


def _make_request(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make a request to the OpenWeatherMap API.

    Args:
        endpoint: API endpoint
        params: Query parameters

    Returns:
        API response as dictionary
    """
    # Add API key to params
    params["appid"] = OPENWEATHER_API_KEY

    url = f"{OPENWEATHER_API_BASE}/{endpoint}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)

            if response.status_code == 401:
                return {"error": "Invalid API key. Please check your OPENWEATHER_API_KEY."}

            if response.status_code == 404:
                return {"error": "Location not found. Please check the city name or coordinates."}

            if response.status_code == 429:
                return {"error": "API rate limit exceeded. Please try again later."}

            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        logger.error(f"Timeout requesting {endpoint}")
        return {"error": "Request timed out"}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return {"error": f"HTTP error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return {"error": str(e)}


def _kelvin_to_celsius(kelvin: float) -> float:
    """Convert Kelvin to Celsius."""
    return round(kelvin - 273.15, 1)


def _kelvin_to_fahrenheit(kelvin: float) -> float:
    """Convert Kelvin to Fahrenheit."""
    return round((kelvin - 273.15) * 9/5 + 32, 1)


def _format_weather_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format the weather API response into a clean structure.

    Args:
        data: Raw API response

    Returns:
        Formatted weather data
    """
    main = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    wind = data.get("wind", {})
    clouds = data.get("clouds", {})
    sys = data.get("sys", {})

    temp_kelvin = main.get("temp", 0)
    feels_like_kelvin = main.get("feels_like", 0)
    temp_min_kelvin = main.get("temp_min", 0)
    temp_max_kelvin = main.get("temp_max", 0)

    return {
        "success": True,
        "location": {
            "city": data.get("name"),
            "country": sys.get("country"),
            "coordinates": {
                "latitude": data.get("coord", {}).get("lat"),
                "longitude": data.get("coord", {}).get("lon")
            }
        },
        "weather": {
            "condition": weather.get("main"),
            "description": weather.get("description"),
            "icon": weather.get("icon")
        },
        "temperature": {
            "current": {
                "celsius": _kelvin_to_celsius(temp_kelvin),
                "fahrenheit": _kelvin_to_fahrenheit(temp_kelvin)
            },
            "feels_like": {
                "celsius": _kelvin_to_celsius(feels_like_kelvin),
                "fahrenheit": _kelvin_to_fahrenheit(feels_like_kelvin)
            },
            "min": {
                "celsius": _kelvin_to_celsius(temp_min_kelvin),
                "fahrenheit": _kelvin_to_fahrenheit(temp_min_kelvin)
            },
            "max": {
                "celsius": _kelvin_to_celsius(temp_max_kelvin),
                "fahrenheit": _kelvin_to_fahrenheit(temp_max_kelvin)
            }
        },
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "visibility": data.get("visibility"),
        "wind": {
            "speed_ms": wind.get("speed"),
            "speed_mph": round(wind.get("speed", 0) * 2.237, 1),
            "direction_degrees": wind.get("deg"),
            "gust_ms": wind.get("gust")
        },
        "clouds": {
            "coverage_percent": clouds.get("all")
        },
        "sun": {
            "sunrise_utc": sys.get("sunrise"),
            "sunset_utc": sys.get("sunset")
        },
        "timezone_offset": data.get("timezone")
    }


def get_current_weather(city: str) -> Dict[str, Any]:
    """
    Get current weather for a city.

    Args:
        city: City name (can include country code, e.g., "London,UK")

    Returns:
        Dictionary containing current weather information
    """
    logger.info(f"Getting weather for city: {city}")

    # Validate API key
    error = _validate_api_key()
    if error:
        return {"error": error}

    params = {
        "q": city,
        "units": "standard"  # We'll convert manually to provide both C and F
    }

    result = _make_request("weather", params)

    if "error" in result:
        return result

    return _format_weather_response(result)


def get_weather_by_coordinates(lat: float, lon: float) -> Dict[str, Any]:
    """
    Get current weather by geographic coordinates.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dictionary containing current weather information
    """
    logger.info(f"Getting weather for coordinates: {lat}, {lon}")

    # Validate API key
    error = _validate_api_key()
    if error:
        return {"error": error}

    params = {
        "lat": lat,
        "lon": lon,
        "units": "standard"
    }

    result = _make_request("weather", params)

    if "error" in result:
        return result

    return _format_weather_response(result)


# Tool metadata for the executor
TOOL_INFO = {
    "name": "weather",
    "description": "OpenWeatherMap API integration for current weather information",
    "functions": {
        "get_current_weather": {
            "description": "Get current weather for a city",
            "parameters": ["city"],
            "handler": get_current_weather
        },
        "get_weather_by_coordinates": {
            "description": "Get current weather by geographic coordinates",
            "parameters": ["lat", "lon"],
            "handler": get_weather_by_coordinates
        }
    }
}
