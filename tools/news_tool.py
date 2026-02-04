"""
News Tool - Integration with NewsAPI
Provides news search and top headlines retrieval
"""

import os
import logging
from typing import Any, Dict, List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# NewsAPI configuration
NEWS_API_BASE = "https://newsapi.org/v2"
NEWS_API_KEY = os.getenv("NEWS_API_KEY")


def _validate_api_key() -> Optional[str]:
    """Validate that the API key is configured."""
    if not NEWS_API_KEY or NEWS_API_KEY == "your_newsapi_key_here":
        return "NewsAPI key not configured. Please set NEWS_API_KEY in your .env file."
    return None


def _make_request(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make a request to the NewsAPI.

    Args:
        endpoint: API endpoint
        params: Query parameters

    Returns:
        API response as dictionary
    """
    # Add API key to params
    params["apiKey"] = NEWS_API_KEY

    url = f"{NEWS_API_BASE}/{endpoint}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)

            data = response.json()

            if response.status_code == 401:
                return {"error": "Invalid API key. Please check your NEWS_API_KEY."}

            if response.status_code == 426:
                return {"error": "NewsAPI free tier does not support this request. Upgrade your plan or try a different query."}

            if response.status_code == 429:
                return {"error": "API rate limit exceeded. Free tier allows 100 requests/day."}

            if data.get("status") == "error":
                return {"error": data.get("message", "Unknown error from NewsAPI")}

            response.raise_for_status()
            return data

    except httpx.TimeoutException:
        logger.error(f"Timeout requesting {endpoint}")
        return {"error": "Request timed out"}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return {"error": f"HTTP error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return {"error": str(e)}


def _format_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a single article into a clean structure.

    Args:
        article: Raw article data

    Returns:
        Formatted article
    """
    return {
        "title": article.get("title"),
        "description": article.get("description"),
        "source": article.get("source", {}).get("name"),
        "author": article.get("author"),
        "url": article.get("url"),
        "image_url": article.get("urlToImage"),
        "published_at": article.get("publishedAt"),
        "content_preview": article.get("content")
    }


def search_news(query: str, limit: int = 5, language: str = "en") -> Dict[str, Any]:
    """
    Search for news articles by keyword.

    Args:
        query: Search query string
        limit: Maximum number of results to return (default 5, max 100)
        language: Language code (default "en")

    Returns:
        Dictionary containing search results with articles
    """
    logger.info(f"Searching news for: {query}")

    # Validate API key
    error = _validate_api_key()
    if error:
        return {"error": error}

    # Ensure limit is within bounds
    limit = min(max(1, limit), 100)

    params = {
        "q": query,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": limit
    }

    result = _make_request("everything", params)

    if "error" in result:
        return result

    articles = [_format_article(article) for article in result.get("articles", [])[:limit]]

    return {
        "success": True,
        "query": query,
        "total_results": result.get("totalResults", 0),
        "returned_count": len(articles),
        "articles": articles
    }


def get_top_headlines(
    country: str = "us",
    category: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Get top news headlines for a country and/or category.

    Args:
        country: Two-letter country code (default "us")
        category: News category (business, entertainment, general, health, science, sports, technology)
        limit: Maximum number of results to return (default 5)

    Returns:
        Dictionary containing top headlines
    """
    logger.info(f"Getting top headlines for country: {country}, category: {category}")

    # Validate API key
    error = _validate_api_key()
    if error:
        return {"error": error}

    # Validate category if provided
    valid_categories = ["business", "entertainment", "general", "health", "science", "sports", "technology"]
    if category and category.lower() not in valid_categories:
        return {
            "error": f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        }

    # Ensure limit is within bounds
    limit = min(max(1, limit), 100)

    params = {
        "country": country,
        "pageSize": limit
    }

    if category:
        params["category"] = category.lower()

    result = _make_request("top-headlines", params)

    if "error" in result:
        return result

    articles = [_format_article(article) for article in result.get("articles", [])[:limit]]

    return {
        "success": True,
        "country": country,
        "category": category,
        "total_results": result.get("totalResults", 0),
        "returned_count": len(articles),
        "articles": articles
    }


# Tool metadata for the executor
TOOL_INFO = {
    "name": "news",
    "description": "NewsAPI integration for searching news and getting headlines",
    "functions": {
        "search_news": {
            "description": "Search for news articles by keyword",
            "parameters": ["query", "limit", "language"],
            "handler": search_news
        },
        "get_top_headlines": {
            "description": "Get top news headlines for a country and/or category",
            "parameters": ["country", "category", "limit"],
            "handler": get_top_headlines
        }
    }
}
