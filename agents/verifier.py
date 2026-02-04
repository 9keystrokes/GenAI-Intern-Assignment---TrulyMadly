"""
Verifier Agent - Validates and formats execution results
Uses LLM to ensure completeness and create user-friendly responses
"""

import logging
from typing import Any, Dict, List, Optional
from llm.client import get_llm_client

logger = logging.getLogger(__name__)


class VerifierAgent:
    """
    The Verifier Agent is responsible for validating execution results
    and formatting them into user-friendly responses.

    It:
    1. Validates that all requested information was obtained
    2. Identifies missing or incomplete data
    3. Formats results into clean, readable responses
    4. Can request re-execution of failed steps
    """

    def __init__(self):
        """Initialize the Verifier Agent."""
        self.llm_client = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of LLM client."""
        if not self._initialized:
            self.llm_client = get_llm_client()
            self._initialized = True

    def verify_and_format(
        self,
        original_task: str,
        plan: Dict[str, Any],
        execution_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify execution results and format them for the user.

        Args:
            original_task: The user's original query
            plan: The execution plan that was used
            execution_results: Results from the Executor Agent

        Returns:
            Verification result with formatted answer
        """
        logger.info("Verifying and formatting execution results")

        # Extract step results
        step_results = execution_results.get("step_results", [])

        # Check for complete failures
        if not step_results:
            return {
                "is_complete": False,
                "formatted_answer": "No results were obtained. The execution plan was empty or all steps failed.",
                "missing_info": ["All requested information"],
                "failed_steps": [],
                "suggestions": ["Please try rephrasing your query"]
            }

        # Identify failed steps
        failed_steps = [
            {
                "step_id": r.get("step_id"),
                "action": r.get("action"),
                "error": r.get("error")
            }
            for r in step_results
            if not r.get("success")
        ]

        # Identify successful results
        successful_results = [
            r for r in step_results if r.get("success")
        ]

        # If all steps failed, return error summary
        if not successful_results:
            return self._format_all_failed(original_task, failed_steps)

        try:
            self._ensure_initialized()

            # Use LLM to verify and format results
            verification = self.llm_client.verify_results(
                original_task,
                plan,
                step_results
            )

            # Add metadata to verification
            verification["failed_steps"] = failed_steps
            verification["successful_steps"] = len(successful_results)
            verification["total_steps"] = len(step_results)

            # If some steps failed, add note to the answer
            if failed_steps and verification.get("formatted_answer"):
                failure_note = self._format_failure_note(failed_steps)
                verification["formatted_answer"] += failure_note

            return verification

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            # Fall back to basic formatting
            return self._basic_format(original_task, step_results, failed_steps)

    def _format_all_failed(
        self,
        original_task: str,
        failed_steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Format response when all steps failed.

        Args:
            original_task: The user's original query
            failed_steps: List of failed steps with errors

        Returns:
            Formatted error response
        """
        error_details = []
        for step in failed_steps:
            error_details.append(f"- Step {step.get('step_id')}: {step.get('error', 'Unknown error')}")

        formatted_answer = f"""I was unable to complete your request: "{original_task}"

All execution steps failed with the following errors:
{chr(10).join(error_details)}

**Suggestions:**
- Check that all required API keys are configured in your .env file
- Verify your internet connection
- Try simplifying your query
- Check if the requested resources exist (e.g., valid city names, repository names)"""

        return {
            "is_complete": False,
            "formatted_answer": formatted_answer,
            "missing_info": ["All requested information due to execution failures"],
            "failed_steps": failed_steps,
            "suggestions": [
                "Verify API keys are configured",
                "Check internet connection",
                "Try a simpler query"
            ]
        }

    def _basic_format(
        self,
        original_task: str,
        step_results: List[Dict[str, Any]],
        failed_steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Basic formatting when LLM verification fails.

        Args:
            original_task: The user's original query
            step_results: All step results
            failed_steps: List of failed steps

        Returns:
            Basic formatted response
        """
        formatted_parts = [f"**Results for:** {original_task}\n"]

        for result in step_results:
            if result.get("success"):
                tool = result.get("tool", "unknown")
                data = result.get("data", {})

                formatted_parts.append(f"\n**{tool.upper()} Results:**")
                formatted_parts.append(self._format_tool_data(tool, data))

        if failed_steps:
            formatted_parts.append(self._format_failure_note(failed_steps))

        return {
            "is_complete": len(failed_steps) == 0,
            "formatted_answer": "\n".join(formatted_parts),
            "failed_steps": failed_steps,
            "suggestions": []
        }

    def _format_tool_data(self, tool: str, data: Dict[str, Any]) -> str:
        """
        Format data from a specific tool.

        Args:
            tool: The tool name
            data: The tool's response data

        Returns:
            Formatted string representation
        """
        if tool == "github":
            return self._format_github_data(data)
        elif tool == "weather":
            return self._format_weather_data(data)
        elif tool == "news":
            return self._format_news_data(data)
        else:
            return str(data)

    def _format_github_data(self, data: Dict[str, Any]) -> str:
        """Format GitHub API response."""
        lines = []

        # Handle repository search results
        if "repositories" in data:
            for repo in data.get("repositories", [])[:5]:
                lines.append(f"- **{repo.get('full_name')}**: {repo.get('description', 'No description')}")
                lines.append(f"  ⭐ {repo.get('stars', 0)} | 🍴 {repo.get('forks', 0)} | Language: {repo.get('language', 'N/A')}")

        # Handle single repository details
        elif "repository" in data:
            repo = data["repository"]
            lines.append(f"**{repo.get('full_name')}**")
            lines.append(f"- Description: {repo.get('description', 'No description')}")
            lines.append(f"- Stars: {repo.get('stars', 0)} | Forks: {repo.get('forks', 0)}")
            lines.append(f"- Language: {repo.get('primary_language', 'N/A')}")
            lines.append(f"- URL: {repo.get('url', 'N/A')}")

        # Handle user repos
        elif "user" in data:
            user = data["user"]
            lines.append(f"**User: {user.get('username')}** ({user.get('name', 'N/A')})")
            lines.append(f"Public repos: {user.get('public_repos', 0)} | Followers: {user.get('followers', 0)}")

        return "\n".join(lines) if lines else str(data)

    def _format_weather_data(self, data: Dict[str, Any]) -> str:
        """Format Weather API response."""
        if not data.get("success"):
            return f"Error: {data.get('error', 'Unknown error')}"

        location = data.get("location", {})
        weather = data.get("weather", {})
        temp = data.get("temperature", {}).get("current", {})

        lines = [
            f"**{location.get('city', 'Unknown')}, {location.get('country', '')}**",
            f"- Conditions: {weather.get('description', 'N/A').title()}",
            f"- Temperature: {temp.get('celsius', 'N/A')}°C / {temp.get('fahrenheit', 'N/A')}°F",
            f"- Humidity: {data.get('humidity', 'N/A')}%",
            f"- Wind: {data.get('wind', {}).get('speed_ms', 'N/A')} m/s"
        ]

        return "\n".join(lines)

    def _format_news_data(self, data: Dict[str, Any]) -> str:
        """Format News API response."""
        lines = []

        for article in data.get("articles", [])[:5]:
            lines.append(f"- **{article.get('title', 'No title')}**")
            lines.append(f"  Source: {article.get('source', 'Unknown')} | {article.get('published_at', 'N/A')[:10] if article.get('published_at') else 'N/A'}")
            if article.get("description"):
                lines.append(f"  {article['description'][:150]}...")

        return "\n".join(lines) if lines else str(data)

    def _format_failure_note(self, failed_steps: List[Dict[str, Any]]) -> str:
        """
        Format a note about failed steps.

        Args:
            failed_steps: List of failed steps

        Returns:
            Formatted failure note
        """
        if not failed_steps:
            return ""

        lines = ["\n\n**Note:** Some information could not be retrieved:"]
        for step in failed_steps:
            lines.append(f"- {step.get('action', 'Unknown action')}: {step.get('error', 'Unknown error')}")

        return "\n".join(lines)

    def get_steps_to_retry(
        self,
        verification_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get list of steps that should be retried.

        Args:
            verification_result: The verification result

        Returns:
            List of steps that need re-execution
        """
        return verification_result.get("failed_steps", [])


# Singleton instance
_verifier_instance: Optional[VerifierAgent] = None


def get_verifier() -> VerifierAgent:
    """Get or create the singleton Verifier Agent instance."""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = VerifierAgent()
    return _verifier_instance
