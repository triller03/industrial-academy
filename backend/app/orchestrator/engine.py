"""OrchestrationEngine: per-project workflow state plus desktop tool status.

Owns nothing itself — matches the desktop-first blueprint by layering a
project-level state machine over the existing content, progress and fault
engines, and exposing the installed engineering tools (TIA / WinCC / Factory I/O).
"""

from __future__ import annotations

from app.config import get_settings
from app.orchestrator.apps import detect_tools
from app.orchestrator.pipeline import next_stage, pipeline as pipeline_definition, previous_stage, stage_at, stage_key


class OrchestrationEngine:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    @property
    def mode(self) -> str:
        mode = (self.settings.orchestrator_mode or "auto").strip().lower()
        if mode not in ("auto", "simulate", "live"):
            mode = "auto"
        if mode == "auto":
            # Auto: any tool detected on the host upgrades to live driving.
            tools = detect_tools(self.settings.orchestrator_app_paths, "simulate")
            return "live" if any(t.get("state") == "installed" for t in tools.values()) else "simulate"
        return mode

    def tools(self) -> dict:
        return detect_tools(self.settings.orchestrator_app_paths, self.mode)

    def status(self) -> dict:
        if not self.settings.orchestrator_enabled:
            return {
                "enabled": False,
                "detail": "Orchestrator disabled in settings (ORCHESTRATOR_ENABLED=false).",
            }
        return {
            "enabled": True,
            "mode": self.mode,
            "pipeline": pipeline_definition(),
            "tools": self.tools(),
            "detail": (
                "Project lifecycle state machine + desktop tool registry. "
                "Set ORCHESTRATOR_MODE=live to drive installed TIA Portal / WinCC / Factory I/O."
            ),
        }

    def run_from_stage(self, stage_index: int) -> dict:
        idx = max(0, min(stage_index, len(pipeline_definition()) - 1))
        return {
            "stage_index": idx,
            "stage_key": stage_key(idx),
            "stage": stage_at(idx),
            "completed": idx == len(pipeline_definition()) - 1,
        }

    def advance(self, stage_index: int, step: int = 1) -> dict:
        nxt = next_stage(stage_index, step=step)
        return self.run_from_stage(nxt)

    def rollback(self, stage_index: int, step: int = 1) -> dict:
        prev = previous_stage(stage_index, step=step)
        return self.run_from_stage(prev)


orchestration_engine = OrchestrationEngine()