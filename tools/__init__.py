"""
Tools Module - External API integrations for the AI Operations Assistant
"""

from .github_tool import (
    search_repositories,
    get_repository_details,
    get_user_repos,
    TOOL_INFO as GITHUB_TOOL_INFO
)
from .weather_tool import (
    get_current_weather,
    get_weather_by_coordinates,
    TOOL_INFO as WEATHER_TOOL_INFO
)
from .news_tool import (
    search_news,
    get_top_headlines,
    TOOL_INFO as NEWS_TOOL_INFO
)

# Registry of all available tools
TOOLS_REGISTRY = {
    "github": GITHUB_TOOL_INFO,
    "weather": WEATHER_TOOL_INFO,
    "news": NEWS_TOOL_INFO
}

__all__ = [
    # GitHub functions
    "search_repositories",
    "get_repository_details",
    "get_user_repos",
    # Weather functions
    "get_current_weather",
    "get_weather_by_coordinates",
    # News functions
    "search_news",
    "get_top_headlines",
    # Registry
    "TOOLS_REGISTRY"
]
