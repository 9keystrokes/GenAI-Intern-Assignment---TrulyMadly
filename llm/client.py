"""
LLM Client - Unified interface for OpenAI and Groq LLM providers
Handles plan generation, result verification, and parameter extraction
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client supporting OpenAI and Groq providers.
    Provides methods for generating plans, verifying results, and extracting parameters.
    """

    def __init__(self):
        """Initialize the LLM client based on environment configuration."""
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        self.client = None
        self.model = None

        if self.provider == "openai":
            self._init_openai()
        elif self.provider == "groq":
            self._init_groq()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Use 'openai' or 'groq'")

    def _init_openai(self):
        """Initialize OpenAI client."""
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            raise ValueError("OPENAI_API_KEY not set or invalid. Please set it in your .env file.")

        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # Cost-effective model with JSON mode support
        logger.info(f"Initialized OpenAI client with model: {self.model}")

    def _init_groq(self):
        """Initialize Groq client."""
        from groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            raise ValueError("GROQ_API_KEY not set or invalid. Please set it in your .env file.")

        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"  # Powerful model with good JSON capabilities
        logger.info(f"Initialized Groq client with model: {self.model}")

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        max_retries: int = 3
    ) -> str:
        """
        Make a call to the LLM with retry logic.

        Args:
            system_prompt: The system instruction for the LLM
            user_prompt: The user's input/query
            json_mode: Whether to enforce JSON output format
            max_retries: Number of retry attempts on failure

        Returns:
            The LLM's response content as a string
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        for attempt in range(max_retries):
            try:
                if self.provider == "openai":
                    kwargs = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 4096
                    }
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}

                    response = self.client.chat.completions.create(**kwargs)
                    return response.choices[0].message.content

                elif self.provider == "groq":
                    kwargs = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 4096
                    }
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}

                    response = self.client.chat.completions.create(**kwargs)
                    return response.choices[0].message.content

            except Exception as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"LLM call failed after {max_retries} attempts: {str(e)}")

        return ""

    def generate_plan(self, user_input: str) -> Dict[str, Any]:
        """
        Generate a structured execution plan from user's natural language input.

        Args:
            user_input: The user's natural language query/task

        Returns:
            A structured plan dictionary with task, steps, and expected_output
        """
        system_prompt = """You are an AI task planner. Your job is to analyze user requests and create structured execution plans.

You have access to these tools:
1. "github" - Search GitHub repositories, get repository details, get user repos
   - Functions: search_repositories(query, limit), get_repository_details(owner, repo), get_user_repos(username)
2. "weather" - Get current weather information
   - Functions: get_current_weather(city), get_weather_by_coordinates(lat, lon)
3. "news" - Search news articles and get headlines
   - Functions: search_news(query, limit), get_top_headlines(country, category)

IMPORTANT: You must respond with ONLY a valid JSON object in this exact format:
{
  "task": "the original user query",
  "steps": [
    {
      "step_id": 1,
      "action": "description of what this step does",
      "tool": "tool_name (github, weather, or news)",
      "function": "function_name",
      "parameters": {"param1": "value1", "param2": "value2"}
    }
  ],
  "expected_output": "description of what the final result should contain"
}

Rules:
- Analyze the user's request carefully to identify ALL required information
- Create a step for EACH piece of information needed
- Use the appropriate tool and function for each step
- Parameters must be concrete values extracted from the user's request
- For GitHub searches, extract relevant keywords from the query
- For weather, extract city names or coordinates
- For news, extract search topics or categories
- If a request mentions multiple cities or topics, create separate steps for each
- Always include realistic parameter values based on the user's request"""

        user_prompt = f"""Create an execution plan for this request:

"{user_input}"

Respond with ONLY the JSON plan object, no other text."""

        try:
            response = self._call_llm(system_prompt, user_prompt, json_mode=True)
            plan = json.loads(response)

            # Validate plan structure
            if "task" not in plan:
                plan["task"] = user_input
            if "steps" not in plan or not isinstance(plan["steps"], list):
                plan["steps"] = []
            if "expected_output" not in plan:
                plan["expected_output"] = "Processed results based on user query"

            logger.info(f"Generated plan with {len(plan['steps'])} steps")
            return plan

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            # Return a minimal valid plan
            return {
                "task": user_input,
                "steps": [],
                "expected_output": "Unable to parse plan",
                "error": str(e)
            }

    def verify_results(
        self,
        original_task: str,
        plan: Dict[str, Any],
        results: list
    ) -> Dict[str, Any]:
        """
        Verify and format execution results using LLM.

        Args:
            original_task: The user's original query
            plan: The execution plan that was used
            results: List of results from each executed step

        Returns:
            Verification result with formatted answer and status
        """
        system_prompt = """You are a results verifier and formatter. Your job is to:
1. Check if the execution results answer the user's original question
2. Identify any missing or incomplete information
3. Format the results into a clear, user-friendly response

You must respond with ONLY a valid JSON object in this format:
{
  "is_complete": true/false,
  "missing_info": ["list of missing information if any"],
  "formatted_answer": "A well-formatted, comprehensive answer to the user's question using the provided results",
  "suggestions": ["any suggestions for the user if applicable"]
}

Rules:
- The formatted_answer should be comprehensive and directly address the user's query
- Include specific data from the results (numbers, names, descriptions)
- If results contain errors, acknowledge them gracefully
- Format the answer in a readable way with clear sections if multiple topics are covered
- Be helpful and informative in your response"""

        # Prepare results summary for verification
        results_text = json.dumps(results, indent=2, default=str)

        user_prompt = f"""Original user request: "{original_task}"

Execution plan: {json.dumps(plan, indent=2)}

Execution results:
{results_text}

Verify these results and provide a formatted answer. Respond with ONLY the JSON object."""

        try:
            response = self._call_llm(system_prompt, user_prompt, json_mode=True)
            verification = json.loads(response)

            # Ensure required fields exist
            if "is_complete" not in verification:
                verification["is_complete"] = True
            if "formatted_answer" not in verification:
                verification["formatted_answer"] = "Results processed successfully."

            return verification

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse verification JSON: {e}")
            return {
                "is_complete": True,
                "formatted_answer": "Results were obtained but formatting failed. Raw results are available in execution_results.",
                "error": str(e)
            }

    def extract_parameters(self, text: str, tool_name: str) -> Dict[str, Any]:
        """
        Extract API parameters from natural language text for a specific tool.

        Args:
            text: Natural language text containing parameter information
            tool_name: The tool for which to extract parameters

        Returns:
            Dictionary of extracted parameters
        """
        tool_schemas = {
            "github": {
                "search_repositories": {"query": "string", "limit": "integer (default 5)"},
                "get_repository_details": {"owner": "string", "repo": "string"},
                "get_user_repos": {"username": "string"}
            },
            "weather": {
                "get_current_weather": {"city": "string"},
                "get_weather_by_coordinates": {"lat": "float", "lon": "float"}
            },
            "news": {
                "search_news": {"query": "string", "limit": "integer (default 5)"},
                "get_top_headlines": {"country": "string (default 'us')", "category": "string (optional)"}
            }
        }

        schema = tool_schemas.get(tool_name, {})

        system_prompt = f"""Extract parameters from the user's text for the {tool_name} tool.

Available functions and their parameters:
{json.dumps(schema, indent=2)}

Respond with ONLY a valid JSON object containing the extracted parameters.
If a parameter cannot be determined, use a reasonable default or omit it."""

        user_prompt = f'Extract parameters from: "{text}"'

        try:
            response = self._call_llm(system_prompt, user_prompt, json_mode=True)
            return json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Parameter extraction failed: {e}")
            return {}


# Singleton instance for easy import
_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient()
    return _client_instance
