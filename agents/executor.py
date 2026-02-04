"""
Executor Agent - Executes plan steps by calling appropriate tools
Handles API calls, retries, and error management
"""

import logging
import time
from typing import Any, Dict, List, Optional
from tools import TOOLS_REGISTRY

logger = logging.getLogger(__name__)


class ExecutorAgent:
    """
    The Executor Agent is responsible for executing the steps in a plan.

    It:
    1. Iterates through each step in the plan
    2. Calls the appropriate tool for each step
    3. Handles errors and retries
    4. Collects and returns aggregated results
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the Executor Agent.

        Args:
            max_retries: Maximum number of retry attempts per step
            retry_delay: Delay between retries in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.tools_registry = TOOLS_REGISTRY

    def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all steps in a plan.

        Args:
            plan: The execution plan from the Planner Agent

        Returns:
            Execution results including all step outputs and metadata
        """
        logger.info(f"Executing plan: {plan.get('task', 'Unknown task')}")

        results = {
            "plan": plan,
            "step_results": [],
            "tools_used": set(),
            "total_steps": len(plan.get("steps", [])),
            "successful_steps": 0,
            "failed_steps": 0,
            "execution_start": time.time()
        }

        steps = plan.get("steps", [])

        if not steps:
            logger.warning("No steps to execute in plan")
            results["error"] = "No executable steps in plan"
            results["execution_time"] = 0
            return results

        for step in steps:
            step_result = self._execute_step(step)
            results["step_results"].append(step_result)

            if step_result.get("success"):
                results["successful_steps"] += 1
                results["tools_used"].add(step.get("tool", "unknown"))
            else:
                results["failed_steps"] += 1

        results["execution_time"] = round(time.time() - results["execution_start"], 2)
        results["tools_used"] = list(results["tools_used"])

        logger.info(
            f"Plan execution completed: {results['successful_steps']}/{results['total_steps']} steps successful"
        )

        return results

    def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single step from the plan with retry logic.

        Args:
            step: The step to execute

        Returns:
            Step execution result
        """
        step_id = step.get("step_id", "unknown")
        tool_name = step.get("tool", "").lower()
        function_name = step.get("function", "")
        parameters = step.get("parameters", {})

        logger.info(f"Executing step {step_id}: {step.get('action', 'Unknown action')}")

        result = {
            "step_id": step_id,
            "tool": tool_name,
            "function": function_name,
            "action": step.get("action", ""),
            "success": False,
            "data": None,
            "error": None,
            "attempts": 0
        }

        # Validate tool exists
        if tool_name not in self.tools_registry:
            result["error"] = f"Unknown tool: {tool_name}"
            logger.error(f"Step {step_id} failed: {result['error']}")
            return result

        tool_info = self.tools_registry[tool_name]
        functions = tool_info.get("functions", {})

        # Validate function exists
        if function_name not in functions:
            # Try to infer function from action or parameters
            function_name = self._infer_function(tool_name, step)
            if not function_name:
                result["error"] = f"Unknown function '{function_name}' for tool '{tool_name}'"
                logger.error(f"Step {step_id} failed: {result['error']}")
                return result

        function_info = functions.get(function_name, {})
        handler = function_info.get("handler")

        if not handler:
            result["error"] = f"No handler found for function: {function_name}"
            logger.error(f"Step {step_id} failed: {result['error']}")
            return result

        # Execute with retries
        for attempt in range(self.max_retries):
            result["attempts"] = attempt + 1

            try:
                # Clean parameters - only pass what the function expects
                clean_params = self._clean_parameters(parameters, function_info.get("parameters", []))

                logger.debug(f"Calling {tool_name}.{function_name} with params: {clean_params}")
                response = handler(**clean_params)

                # Check if response indicates an error
                if isinstance(response, dict) and response.get("error"):
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"Step {step_id} attempt {attempt + 1} failed: {response['error']}. Retrying..."
                        )
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        result["error"] = response.get("error")
                        logger.error(f"Step {step_id} failed after {self.max_retries} attempts")
                        return result

                result["success"] = True
                result["data"] = response
                logger.info(f"Step {step_id} completed successfully")
                return result

            except Exception as e:
                logger.warning(f"Step {step_id} attempt {attempt + 1} raised exception: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    result["error"] = str(e)
                    logger.error(f"Step {step_id} failed after {self.max_retries} attempts: {e}")

        return result

    def _infer_function(self, tool_name: str, step: Dict[str, Any]) -> Optional[str]:
        """
        Try to infer the correct function based on step details.

        Args:
            tool_name: The tool name
            step: The step details

        Returns:
            Inferred function name or None
        """
        parameters = step.get("parameters", {})
        action = step.get("action", "").lower()

        if tool_name == "github":
            if "owner" in parameters and "repo" in parameters:
                return "get_repository_details"
            elif "username" in parameters:
                return "get_user_repos"
            else:
                return "search_repositories"

        elif tool_name == "weather":
            if "lat" in parameters and "lon" in parameters:
                return "get_weather_by_coordinates"
            else:
                return "get_current_weather"

        elif tool_name == "news":
            if "headline" in action or "top" in action:
                return "get_top_headlines"
            else:
                return "search_news"

        return None

    def _clean_parameters(self, parameters: Dict[str, Any], expected_params: List[str]) -> Dict[str, Any]:
        """
        Clean parameters to only include expected ones.

        Args:
            parameters: Raw parameters from the plan
            expected_params: List of parameter names the function expects

        Returns:
            Cleaned parameters dictionary
        """
        # If no expected params defined, return all
        if not expected_params:
            return parameters

        cleaned = {}
        for param in expected_params:
            if param in parameters:
                value = parameters[param]
                # Convert types if needed
                if param in ["limit", "lat", "lon"]:
                    try:
                        if param == "limit":
                            value = int(value)
                        else:
                            value = float(value)
                    except (ValueError, TypeError):
                        pass
                cleaned[param] = value

        return cleaned

    def execute_single_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single step (useful for re-execution of failed steps).

        Args:
            step: The step to execute

        Returns:
            Step execution result
        """
        return self._execute_step(step)


# Singleton instance
_executor_instance: Optional[ExecutorAgent] = None


def get_executor() -> ExecutorAgent:
    """Get or create the singleton Executor Agent instance."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = ExecutorAgent()
    return _executor_instance
