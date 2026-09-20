"""Desktop orchestration package (blueprint engine 1/5)."""

from app.orchestrator.apps import TOOL_SPECS, detect_tools
from app.orchestrator.engine import OrchestrationEngine, orchestration_engine
from app.orchestrator.launcher import launch_tool
from app.orchestrator.pipeline import PIPELINE, pipeline, stage_at, stage_key

__all__ = [
    "PIPELINE",
    "TOOL_SPECS",
    "OrchestrationEngine",
    "detect_tools",
    "launch_tool",
    "orchestration_engine",
    "pipeline",
    "stage_at",
    "stage_key",
]