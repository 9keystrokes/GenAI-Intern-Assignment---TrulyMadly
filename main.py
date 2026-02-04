"""
AI Operations Assistant - FastAPI Application
Main entry point for the multi-agent AI assistant with third-party API integrations
"""

import logging
import time
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import agents
from agents import get_planner, get_executor, get_verifier
from tools import TOOLS_REGISTRY


# Pydantic models for request/response
class QueryRequest(BaseModel):
    """Request model for the query endpoint."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language query or task for the AI assistant"
    )


class StepResult(BaseModel):
    """Model for individual step execution result."""
    step_id: int
    tool: str
    function: str
    action: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    attempts: int


class ExecutionMetadata(BaseModel):
    """Model for execution metadata."""
    steps_executed: int
    successful_steps: int
    failed_steps: int
    tools_used: list
    execution_time: float


class QueryResponse(BaseModel):
    """Response model for the query endpoint."""
    success: bool
    query: str
    plan: Dict[str, Any]
    execution_results: list
    final_answer: str
    metadata: ExecutionMetadata


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    message: str
    version: str


class ToolInfo(BaseModel):
    """Model for tool information."""
    name: str
    description: str
    functions: list


class ToolsResponse(BaseModel):
    """Response model for tools listing."""
    available_tools: list


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    logger.info("AI Operations Assistant starting up...")
    logger.info(f"Available tools: {list(TOOLS_REGISTRY.keys())}")
    yield
    logger.info("AI Operations Assistant shutting down...")


# Create FastAPI application
app = FastAPI(
    title="AI Operations Assistant",
    description="""
    A multi-agent AI assistant that processes natural language tasks using:
    - **Planner Agent**: Converts queries into structured execution plans
    - **Executor Agent**: Executes plans by calling external APIs
    - **Verifier Agent**: Validates results and formats responses
    
    ## Available Tools
    - **GitHub**: Search repositories, get repo details, list user repos
    - **Weather**: Get current weather by city or coordinates
    - **News**: Search news articles, get top headlines
    
    ## Example Queries
    - "Find popular Python machine learning repositories on GitHub"
    - "What's the weather in Tokyo?"
    - "Get the latest technology news"
    - "Search for FastAPI repos and check weather in San Francisco"
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect to docs."""
    return {
        "message": "AI Operations Assistant API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of the API service.
    """
    return HealthResponse(
        status="healthy",
        message="AI Operations Assistant is running",
        version="1.0.0"
    )


@app.get("/tools", response_model=ToolsResponse, tags=["System"])
async def list_tools():
    """
    List available tools.
    
    Returns information about all integrated tools and their functions.
    """
    tools = []
    for name, info in TOOLS_REGISTRY.items():
        tool_info = {
            "name": name,
            "description": info.get("description", ""),
            "functions": list(info.get("functions", {}).keys())
        }
        tools.append(tool_info)
    
    return ToolsResponse(available_tools=tools)


@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def process_query(request: QueryRequest):
    """
    Process a natural language query.
    
    This endpoint:
    1. Receives a natural language query
    2. Uses the Planner Agent to create an execution plan
    3. Uses the Executor Agent to execute the plan
    4. Uses the Verifier Agent to validate and format results
    
    ## Example Request
    ```json
    {
        "query": "Find the top 5 Python machine learning repositories on GitHub"
    }
    ```
    
    ## Example Response
    The response includes the execution plan, raw results, and a formatted answer.
    """
    start_time = time.time()
    query = request.query.strip()
    
    logger.info(f"Processing query: {query[:100]}...")
    
    try:
        # Step 1: Create execution plan using Planner Agent
        logger.info("Step 1: Creating execution plan...")
        planner = get_planner()
        plan = planner.create_plan(query)
        
        if not plan.get("steps"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Failed to create execution plan",
                    "message": plan.get("error", "No executable steps generated"),
                    "suggestion": "Try rephrasing your query to be more specific"
                }
            )
        
        logger.info(f"Plan created with {len(plan['steps'])} steps")
        
        # Step 2: Execute plan using Executor Agent
        logger.info("Step 2: Executing plan...")
        executor = get_executor()
        execution_results = executor.execute_plan(plan)
        
        logger.info(
            f"Execution complete: {execution_results['successful_steps']}/{execution_results['total_steps']} steps successful"
        )
        
        # Step 3: Verify and format results using Verifier Agent
        logger.info("Step 3: Verifying and formatting results...")
        verifier = get_verifier()
        verification = verifier.verify_and_format(
            original_task=query,
            plan=plan,
            execution_results=execution_results
        )
        
        total_time = round(time.time() - start_time, 2)
        
        # Build response
        response = QueryResponse(
            success=verification.get("is_complete", False) or execution_results["successful_steps"] > 0,
            query=query,
            plan=plan,
            execution_results=execution_results.get("step_results", []),
            final_answer=verification.get("formatted_answer", "No answer generated"),
            metadata=ExecutionMetadata(
                steps_executed=execution_results.get("total_steps", 0),
                successful_steps=execution_results.get("successful_steps", 0),
                failed_steps=execution_results.get("failed_steps", 0),
                tools_used=execution_results.get("tools_used", []),
                execution_time=total_time
            )
        )
        
        logger.info(f"Query processed successfully in {total_time}s")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": str(e),
                "suggestion": "Check your API keys and try again"
            }
        )


@app.post("/plan", tags=["Debug"])
async def create_plan_only(request: QueryRequest):
    """
    Create an execution plan without executing it.
    
    Useful for debugging and understanding how queries are interpreted.
    """
    try:
        planner = get_planner()
        plan = planner.create_plan(request.query.strip())
        return {
            "success": True,
            "query": request.query,
            "plan": plan
        }
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e)}
        )


# Run with: uvicorn main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
