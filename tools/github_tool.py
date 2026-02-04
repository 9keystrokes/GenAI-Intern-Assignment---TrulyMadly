"""
GitHub Tool - Integration with GitHub REST API
Provides repository search, details retrieval, and user repository listing
"""

import os
import logging
from typing import Any, Dict, List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def _get_headers() -> Dict[str, str]:
    """Get headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-Ops-Assistant"
    }
    if GITHUB_TOKEN and GITHUB_TOKEN != "your_github_token_here":
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def _make_request(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Make a request to the GitHub API.

    Args:
        endpoint: API endpoint (relative to base URL)
        params: Query parameters

    Returns:
        API response as dictionary
    """
    url = f"{GITHUB_API_BASE}{endpoint}"
    headers = _get_headers()

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, params=params)

            # Handle rate limiting
            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    reset_time = response.headers.get("X-RateLimit-Reset", "unknown")
                    return {
                        "error": "GitHub API rate limit exceeded",
                        "reset_time": reset_time,
                        "suggestion": "Add a GITHUB_TOKEN to your .env file for higher rate limits"
                    }

            if response.status_code == 404:
                return {"error": "Resource not found", "status_code": 404}

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


def search_repositories(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Search GitHub repositories by keyword.

    Args:
        query: Search query string
        limit: Maximum number of results to return (default 5, max 100)

    Returns:
        Dictionary containing search results with repository information
    """
    logger.info(f"Searching GitHub repositories for: {query}")

    # Ensure limit is within bounds
    limit = min(max(1, limit), 100)

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": limit
    }

    result = _make_request("/search/repositories", params)

    if "error" in result:
        return result

    # Format the results
    repositories = []
    for repo in result.get("items", [])[:limit]:
        repositories.append({
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "owner": repo.get("owner", {}).get("login"),
            "description": repo.get("description"),
            "url": repo.get("html_url"),
            "stars": repo.get("stargazers_count"),
            "forks": repo.get("forks_count"),
            "language": repo.get("language"),
            "topics": repo.get("topics", []),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "open_issues": repo.get("open_issues_count")
        })

    return {
        "success": True,
        "query": query,
        "total_count": result.get("total_count", 0),
        "returned_count": len(repositories),
        "repositories": repositories
    }


def get_repository_details(owner: str, repo: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific repository.

    Args:
        owner: Repository owner username
        repo: Repository name

    Returns:
        Dictionary containing detailed repository information
    """
    logger.info(f"Getting details for repository: {owner}/{repo}")

    result = _make_request(f"/repos/{owner}/{repo}")

    if "error" in result:
        return result

    # Get additional information - languages
    languages_result = _make_request(f"/repos/{owner}/{repo}/languages")
    languages = languages_result if "error" not in languages_result else {}

    # Get recent commits count (just check if we can access them)
    contributors_result = _make_request(f"/repos/{owner}/{repo}/contributors", {"per_page": 5})
    top_contributors = []
    if "error" not in contributors_result and isinstance(contributors_result, list):
        for contributor in contributors_result[:5]:
            top_contributors.append({
                "username": contributor.get("login"),
                "contributions": contributor.get("contributions")
            })

    return {
        "success": True,
        "repository": {
            "name": result.get("name"),
            "full_name": result.get("full_name"),
            "owner": result.get("owner", {}).get("login"),
            "description": result.get("description"),
            "url": result.get("html_url"),
            "homepage": result.get("homepage"),
            "stars": result.get("stargazers_count"),
            "forks": result.get("forks_count"),
            "watchers": result.get("watchers_count"),
            "open_issues": result.get("open_issues_count"),
            "primary_language": result.get("language"),
            "languages": languages,
            "topics": result.get("topics", []),
            "license": result.get("license", {}).get("name") if result.get("license") else None,
            "created_at": result.get("created_at"),
            "updated_at": result.get("updated_at"),
            "pushed_at": result.get("pushed_at"),
            "default_branch": result.get("default_branch"),
            "is_fork": result.get("fork"),
            "is_archived": result.get("archived"),
            "top_contributors": top_contributors
        }
    }


def get_user_repos(username: str, limit: int = 10) -> Dict[str, Any]:
    """
    Get public repositories for a GitHub user.

    Args:
        username: GitHub username
        limit: Maximum number of repositories to return

    Returns:
        Dictionary containing user's repository information
    """
    logger.info(f"Getting repositories for user: {username}")

    # First get user info
    user_result = _make_request(f"/users/{username}")

    if "error" in user_result:
        return user_result

    # Get user's repositories
    params = {
        "sort": "updated",
        "direction": "desc",
        "per_page": min(limit, 100)
    }
    repos_result = _make_request(f"/users/{username}/repos", params)

    if "error" in repos_result:
        return repos_result

    repositories = []
    for repo in repos_result[:limit]:
        repositories.append({
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "url": repo.get("html_url"),
            "stars": repo.get("stargazers_count"),
            "forks": repo.get("forks_count"),
            "language": repo.get("language"),
            "updated_at": repo.get("updated_at")
        })

    return {
        "success": True,
        "user": {
            "username": user_result.get("login"),
            "name": user_result.get("name"),
            "bio": user_result.get("bio"),
            "public_repos": user_result.get("public_repos"),
            "followers": user_result.get("followers"),
            "following": user_result.get("following"),
            "profile_url": user_result.get("html_url")
        },
        "repositories": repositories,
        "returned_count": len(repositories)
    }


# Tool metadata for the executor
TOOL_INFO = {
    "name": "github",
    "description": "GitHub API integration for searching and retrieving repository information",
    "functions": {
        "search_repositories": {
            "description": "Search GitHub repositories by keyword",
            "parameters": ["query", "limit"],
            "handler": search_repositories
        },
        "get_repository_details": {
            "description": "Get detailed information about a specific repository",
            "parameters": ["owner", "repo"],
            "handler": get_repository_details
        },
        "get_user_repos": {
            "description": "Get public repositories for a GitHub user",
            "parameters": ["username", "limit"],
            "handler": get_user_repos
        }
    }
}
