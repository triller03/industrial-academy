"""Diagnostic decision trees — branch the same check sequence a real technician runs."""


def build_tree(nodes: list[dict], start_id: str) -> dict:
    """Build a navigable tree from a flat node list. Terminal leaves are nodes with no yes/no."""
    by_id = {n["id"]: n for n in nodes}
    if start_id not in by_id:
        raise ValueError(f"Decision tree start unknown: {start_id}")
    for node in nodes:
        for key in ("yes", "no"):
            target = node.get(key)
            if target is not None and target not in by_id:
                raise ValueError(f"Decision tree node references unknown node: {target}")
    return {"start": start_id, "nodes": by_id}


MOTOR_WONT_START_TREE = build_tree(
    [
        {"id": "start", "text": "Is the motor running feedback present?", "yes": "check_command",
         "no": "check_start_cmd"},
        {"id": "check_command", "text": "Is a start command present at the PLC output?", "yes": "check_maintain",
         "no": "check_permissive"},
        {"id": "check_permissive", "text": "Is an interlock or permissive holding the command?", "yes": "interlock_blocked",
         "no": "logic_not_running"},
        {"id": "check_maintain", "text": "Is the feedback true with the output commanded?", "yes": "motor_running_normal",
         "no": "feedback_wrong"},
        {"id": "check_start_cmd", "text": "Is there power at the motor terminals?", "yes": "contact_open",
         "no": "loss_of_power"},
        {"id": "interlock_blocked", "text": "Root cause: a permissive/interlock is blocking the start command."},
        {"id": "logic_not_running", "text": "Root cause: the control logic did not issue a start command."},
        {"id": "motor_running_normal", "text": "Root cause: no fault — the motor is running correctly."},
        {"id": "feedback_wrong", "text": "Root cause: feedback signalling fault (aux contact/wiring), motor state unknown."},
        {"id": "contact_open", "text": "Root cause: starter contactor not closing despite command and power."},
        {"id": "loss_of_power", "text": "Root cause: loss of power to the motor circuit (breaker/fuse/supply)."},
    ],
    "start",
)

FLOW_NO_RISE_TREE = build_tree(
    [
        {"id": "start", "text": "Is the flow transmitter reading a plausible value?", "yes": "check_valve",
         "no": "check_loop"},
        {"id": "check_valve", "text": "Is the discharge valve open and passing flow?", "yes": "check_pump",
         "no": "valve_blocked"},
        {"id": "check_loop", "text": "Is the transmitter loop healthy (no open wire, power present)?", "yes": "transducer_fault",
         "no": "loop_fault"},
        {"id": "check_pump", "text": "Is the pump running at correct speed/pressure?", "yes": "piping_blockage",
         "no": "pump_underperforming"},
        {"id": "valve_blocked", "text": "Root cause: discharge valve blocked or not fully open."},
        {"id": "transducer_fault", "text": "Root cause: flow transmitter/transducer fault."},
        {"id": "loop_fault", "text": "Root cause: broken loop or missing power to the transmitter."},
        {"id": "piping_blockage", "text": "Root cause: pipe or suction blockage limiting flow."},
        {"id": "pump_underperforming", "text": "Root cause: pump underperforming (air, wear, speed)."},
    ],
    "start",
)

LEVEL_STUCK_TREE = build_tree(
    [
        {"id": "start", "text": "Does the level reading change when the pump runs?", "yes": "check_scale",
         "no": "check_transmitter"},
        {"id": "check_scale", "text": "Is the 4-20 mA scaling correct (0-10 m)?", "yes": "process_question",
         "no": "scaling_wrong"},
        {"id": "check_transmitter", "text": "Is the transmitter powered and loop intact?", "yes": "sensor_stuck",
         "no": "loop_fault"},
        {"id": "process_question", "text": "Is the actual level changing as expected?", "yes": "reading_ok",
         "no": "vessel_physical"},
        {"id": "scaling_wrong", "text": "Root cause: 4-20 mA scaling/range misconfigured."},
        {"id": "sensor_stuck", "text": "Root cause: level sensor/transmitter stuck."},
        {"id": "loop_fault", "text": "Root cause: broken loop or missing transmitter power."},
        {"id": "reading_ok", "text": "Root cause: no instrument fault; reading is correct."},
        {"id": "vessel_physical", "text": "Root cause: physical vessel/level issue (siphoning, gauge, hanger)."},
    ],
    "start",
)

TREES = {
    "motor_wont_start": MOTOR_WONT_START_TREE,
    "flow_no_rise": FLOW_NO_RISE_TREE,
    "level_stuck": LEVEL_STUCK_TREE,
}


def walk(tree: dict, answers: dict[str, str]) -> str:
    """Walk a tree given a mapping of node_id -> 'yes'|'no'. Returns the leaf node id."""
    node_id = tree["start"]
    while node_id in tree["nodes"]:
        node = tree["nodes"][node_id]
        if "yes" not in node and "no" not in node:
            return node_id
        answer = answers.get(node_id)
        if answer not in ("yes", "no"):
            return f"{node_id}:needs_answer"
        next_id = node.get(answer)
        if next_id is None:
            return node_id
        node_id = next_id
    return node_id