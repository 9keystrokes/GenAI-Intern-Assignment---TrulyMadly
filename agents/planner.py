"""
Planner Agent - Converts natural language tasks into structured execution plans
Uses LLM to analyze user requests and generate step-by-step JSON plans
"""

import logging
from typing import Any, Dict, Optional
from llm.client import get_llm_client

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    The Planner Agent is responsible for converting natural language user inputs
    into structured, actionable execution plans.

    It uses an LLM to:
    1. Understand the user's intent
    2. Identify which tools are needed
    3. Determine the correct parameters
    4. Create a step-by-step execution plan
    """

    def __init__(self):
        """Initialize the Planner Agent."""
        self.llm_client = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of LLM client."""
        if not self._initialized:
            self.llm_client = get_llm_client()
            self._initialized = True

    def create_plan(self, user_input: str) -> Dict[str, Any]:
        """
        Create an execution plan from user's natural language input.

        Args:
            user_input: The user's natural language query or task

        Returns:
            A structured plan dictionary containing:
            - task: Original user query
            - steps: List of execution steps with tools and parameters
            - expected_output: Description of expected final result
        """
        logger.info(f"Creating plan for input: {user_input[:100]}...")

        # Validate input
        if not user_input or not user_input.strip():
            return {
                "task": "",
                "steps": [],
                "expected_output": "No input provided",
                "error": "Empty input provided"
            }

        try:
            self._ensure_initialized()

            # Use LLM to generate the plan
            plan = self.llm_client.generate_plan(user_input)

            # Validate and enhance the plan
            plan = self._validate_plan(plan, user_input)

            logger.info(f"Plan created successfully with {len(plan.get('steps', []))} steps")
            return plan

        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            return {
                "task": user_input,
                "steps": [],
                "expected_output": "Failed to generate plan",
                "error": str(e)
            }

    def _validate_plan(self, plan: Dict[str, Any], original_input: str) -> Dict[str, Any]:
        """
        Validate and enhance the generated plan.

        Args:
            plan: The generated plan from LLM
            original_input: The original user input

        Returns:
            Validated and enhanced plan
        """
        # Ensure task field is set
        if not plan.get("task"):
            plan["task"] = original_input

        # Ensure steps is a list
        if not isinstance(plan.get("steps"), list):
            plan["steps"] = []

        # Validate each step
        valid_tools = {"github", "weather", "news"}
        validated_steps = []

        for i, step in enumerate(plan.get("steps", [])):
            # Ensure step has required fields
            if not isinstance(step, dict):
                continue

            # Validate tool
            tool = step.get("tool", "").lower()
            if tool not in valid_tools:
                logger.warning(f"Invalid tool '{tool}' in step {i+1}, skipping")
                continue

            # Ensure step_id
            if "step_id" not in step:
                step["step_id"] = i + 1

            # Ensure action description
            if not step.get("action"):
                step["action"] = f"Execute {step.get('function', 'unknown')} on {tool}"

            # Ensure parameters is a dict
            if not isinstance(step.get("parameters"), dict):
                step["parameters"] = {}

            validated_steps.append(step)

        plan["steps"] = validated_steps

        # Ensure expected_output is set
        if not plan.get("expected_output"):
            plan["expected_output"] = "Processed results based on user query"

        return plan

    def refine_plan(self, plan: Dict[str, Any], feedback: str) -> Dict[str, Any]:
        """
        Refine an existing plan based on feedback.

        Args:
            plan: The current plan to refine
            feedback: Feedback or additional information to incorporate

        Returns:
            Refined plan
        """
        logger.info("Refining plan based on feedback")

        # Create a new query that incorporates the feedback
        original_task = plan.get("task", "")
        refined_input = f"{original_task}\n\nAdditional context: {feedback}"

        return self.create_plan(refined_input)


# Singleton instance
_planner_instance: Optional[PlannerAgent] = None


def get_planner() -> PlannerAgent:
    """Get or create the singleton Planner Agent instance."""
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = PlannerAgent()
    return _planner_instance
