"""Student-facing check palette: expected checks padded with plausible distractors."""

DISTRACTOR_CHECKS: list[str] = [
    "check_motor_winding_resistance",
    "check_hmi_touchscreen",
    "restart_scada_server",
    "check_panel_cooling_fan",
    "replace_transmitter_blind",
    "check_unrelated_loop_signal",
    "check_earthing_continuity",
    "check_cabinet_lighting",
]


def palette(expected: list[str], distractors: list[str] | None = None, extra: int = 3) -> list[str]:
    """Build the student-facing check palette: expected checks + plausible distractors."""
    pool = list(expected)
    for d in (distractors or DISTRACTOR_CHECKS):
        if d not in pool:
            pool.append(d)
        if len(pool) - len(expected) >= extra:
            break
    return pool