"""Foundations curriculum — authored, learner-facing content.

Four hand-written projects walk the full 17-section engineering lifecycle and
escalate from basic to intermediate across discrete and process automation.
Each project carries its own graded fault scenarios. install_curriculum() is
idempotent: it only creates projects whose slug is not already present, so it is
safe to run at every startup and from the Admin UI.

Track map (recommended order):
  1. motor-starter-basics      basic        discrete foundations
  2. instrument-loop-checkout  basic        process/loop foundations
  3. conveyor-sorter-cell      intermediate discrete systems
  4. chlorine-dosing-skid      intermediate packaged process unit
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.fault.palette import palette
from app.models import FaultScenario, Project, ProjectSection

SECTION_KEYS = [
    "project_brief",
    "process_description",
    "p_and_id",
    "io_list",
    "tag_list",
    "control_philosophy",
    "plc_program",
    "hmi",
    "scada",
    "alarms",
    "interlocks",
    "networking",
    "testing",
    "fault_injection",
    "troubleshooting",
    "commissioning",
    "final_documentation",
]

DIFFICULTY_LEVEL = {"basic": 1, "intermediate": 2, "advanced": 3, "expert": 4}

CURRICULUM_TRACK = {
    "name": "Automation Technician Foundations",
    "blurb": (
        "A hands-on path from zero to confident plant technician: four projects "
        "across discrete and process automation, each a complete 17-section "
        "engineering package with graded fault scenarios."
    ),
    "levels": [
        {
            "level": 1,
            "label": "Foundations",
            "slug": "motor-starter-basics",
            "competency": "Safe control of a single motor: start/stop circuits, e-stop, permissives, basic HMI.",
        },
        {
            "level": 1,
            "label": "Foundations",
            "slug": "instrument-loop-checkout",
            "competency": "Field-to-PLC 4-20 mA loops: loop checks, scaling, fail-safe behaviour, calibration.",
        },
        {
            "level": 2,
            "label": "Core systems",
            "slug": "conveyor-sorter-cell",
            "competency": "Discrete systems: sensing, actuation, sequencing, interlocks, HMI, counters.",
        },
        {
            "level": 2,
            "label": "Core systems",
            "slug": "chlorine-dosing-skid",
            "competency": "Packaged process unit: duty/standby pumping, trim control, leak & drum safety.",
        },
    ],
}

CURRICULUM_PROJECTS: list[dict] = [
    {
        "slug": "motor-starter-basics",
        "title": "Motor Starter — Start, Stop, and a Safe Hold",
        "industry": "manufacturing",
        "difficulty": "basic",
        "hours": 12,
        "description": (
            "The trade entry point. Take a single three-phase motor from a panel drawing to a "
            "working start/stop control loop: contactor and overload protection, e-stop and a "
            "run permissive, seal-in logic, and an HMI pushbutton pair. Everything after this "
            "project builds on the discipline it teaches."
        ),
        "sections": [
            {
                "key": "project_brief",
                "title": "Project Brief",
                "content": """You are the automation technician handed a small production cell for its first
commissioning task. The cell has one three-phase conveyor motor that must start and stop
from the HMI, protect itself against overload and loss of cooling, and drop immediately
on the emergency stop. No sequence logic yet — just a bullet-proof single-motor control.

Your deliverables are the complete 17-section engineering package that a real service
team would hand to a client: panel drawing, I/O and tag structure, ladder program with
seal-in and permissive, HMI screens, alarm and interlock definitions, a factory
acceptance test script, and an installation report.

Complete every section. When you reach Fault Injection, expect three realistic faults to
diagnose under time pressure — how you behave on a non-running motor matters more than
the final ladder rung.""",
            },
            {
                "key": "process_description",
                "title": "Process Description",
                "content": """A single conveyor moves finished workpieces from the packing press to the lift-in
position — about 6 m at 0.8 m/s. The motor is a 1.5 kW three-phase induction motor
direct-on-line through a contactor; no VFD is fitted yet.

Normal operation:
1. An operator (or the cell computer) presses Start from the HMI.
2. The PLC energises the main contactor; the motor runs.
3. A green running lamp lights. The PLC also watches a shaft-mounted feedback switch
   (K-con) to prove rotation, rather than trusting only the contactor.
4. Pressing Stop opens the contactor and the conveyor coasts to a standstill.

Abnormal conditions: overload relay tripped, cooling fan off, e-stop pressed, or a
discrepancy (contact asked but no running feedback). Each must stop the motor and
light an alarm. The e-stop is a safety-rated chain separate from the control logic —
the PLC is NOT the safety device.""",
            },
            {
                "key": "p_and_id",
                "title": "Process / Electrical Drawing",
                "content": """**Control panel drawing.**

- Incoming 400 V 3-phase, fuses, main isolator.
- Q: contactor coil 24 V DC, driven by PLC output Q0.0.
- F: thermal overload relay (electronic, self-powered) with 97-98 NC auxiliary contact
  wired to the PLC input card — the relay alone drives the coil the classic way AND
  reports to the PLC so we get an alarm.
- Motor circuit: contactor → overload → motor with a local/remote selector for a manual
  motor-only start (used only during commissioning on site).
- 24 V DC supply for PLC and HMI from a PSU with its own isolating transformer.

**Signal circuits (I/O card side):**

- Digital input for the Start pushbutton (NO). One for Stop (NC to catch wire-break).
- One DI for overload auxiliary (97-98), one for e-stop mirror, one for the K-con
  rotation feedback switch, one for the motor-cubicle cooling-fan differential.
- One DO (relay out) to the contactor coil, and the HMI covers start/stop visually.

Conceptually this is at the level of a single-loop valve or motor skid P&ID: one control
object, clear isolation, and a visible safety chain. Sketch it before you wire anything.""",
            },
            {
                "key": "io_list",
                "title": "I/O List",
                "content": """Digital inputs (24 V DC sink):

| Ref | Description | Device | Default |
| --- | --- | --- | --- |
| DI0 | Start pushbutton (NO) | Remote/HMI or panel PB | 0 |
| DI1 | Stop pushbutton (NC) | Panel PB | 1 |
| DI2 | Overload auxiliary 97-98 (NC) | Electronic OL | 1 |
| DI3 | E-stop chain mirror (NC) | Safety relay output | 1 |
| DI4 | Rotation feedback K-con (NO) | Shaft-mounted switch | 0 |
| DI5 | Cooling fan differential (NO) | Fan duct switch | 0 |

Digital outputs:

| Ref | Description | Device | Note |
| --- | --- | --- | --- |
| DO0 | Main contactor coil | Contactor Q | Seal-in hold |
| DO1 | Running lamp (green) | Panel lamp | Also HMI |

The relay outputs are contacts, not transistor drivers — the 24 V coil draw of the
contactor must not exceed the card's rating. Note the NC convention: Stop, overload and
e-stop are wired NC so a cut wire reads as a safe fault, not as a start signal.""",
            },
            {
                "key": "tag_list",
                "title": "Tag List",
                "content": """PLC tags (IEC 61131-3 style):

| Tag | Type | Origin |
| --- | --- | --- |
| `MTR_RUN_CMD` | BOOL, output DO0 | Ladder: seal-in rung |
| `MTR_START_PB` | BOOL, DI0 | Start pushbutton |
| `MTR_STOP_PB` | BOOL, DI1 (NC) | Stop pushbutton |
| `MTR_OL_TRIP` | BOOL, DI2 (NC) | Overload relay |
| `MTR_ESTOP_OK` | BOOL, DI3 (NC) | Safety chain mirror |
| `MTR_ROT_FB` | BOOL, DI4 | K-con rotation switch |
| `MTR_FAN_OK` | BOOL, DI5 (NC) | Cooling fan guard |
| `MTR_RUN_LAMP` | BOOL, DO1 | Green lamp |
| `MTR_ALARM` | BOOL, internal | Any abnormal |
| `MTR_AUTO_MODE` | BOOL, internal | System armed |

Convention: TRUE in the first scan of the branch = `MTR_RUN_CMD` sealed via its own
contact plus `MTR_AUTO_MODE`. NC inputs store TRUE for "healthy" lines, so all
permissives read positively when healthy. Label both ends of every wire with the tag.""",
            },
            {
                "key": "control_philosophy",
                "title": "Control Philosophy",
                "content": """**C1 — Start truth table.** The motor starts when all of the following are true:
auto mode, no e-stop, overload healthy, cooling healthy, and an operator Start. The
Start pushbutton latches the run through a seal-in contact.

**C2 — Stop priority.** Any of Stop pressed, e-stop, overload trip, loss of cooling,
or a lost rotation-feedback discrepancy removes the run output immediately. Stop has
absolute priority over start in the rung order: the stop/e-stop/healthy network is
in series, not in parallel.

**C3 — Discrepancy.** If the PLC asks the contactor to close but sees no rotation
feedback within 2 s, it declares a discrepancy, trips to manual-safe, and sounds the
alarm. The motor is not restarted until the operator clears the alarm at the HMI.

**C4 — Auto vs local.** The panel local/remote selector bypasses the PLC for the
motor-only circuit during commissioning. In normal mode the HMI is the only
authorized start source — the physical Start button remains on the panel door.

**C5 — Restart latch.** After any trip, the start is denied until the cause is
annunciated and reset. No auto-restart of a conveyor.""",
            },
            {
                "key": "plc_program",
                "title": "PLC Program",
                "content": """Executed every scan in LADDER. Rung order is the safety contract — do not reorder:

**Rung 1 — Healthy header.** `MTR_AUTO_MODE AND MTR_ESTOP_OK AND MTR_OL_TRIP AND
MTR_FAN_OK` → `RUN_HEALTHY`. (NC contacts test TRUE when healthy.)

**Rung 2 — Seal-in.** `RUN_HEALTHY AND (MTR_START_PB OR MTR_RUN_CMD) AND MTR_STOP_PB`
→ `MTR_RUN_CMD`. Seal-in holds on once Start pulses; Stop releases.

**Rung 3 — Discrepancy check.** Network-store: if `MTR_RUN_CMD AND NOT MTR_ROT_FB`
persists 2 s → `MTR_DISCREP` set, run dropped (rung 2 is forced false by logic
`NOT MTR_DISCREP` in series).

**Rung 4 — Outputs.** `MTR_RUN_CMD AND NOT MTR_DISCREP` → contactor DO0 and lamp DO1.

**Rung 5 — Alarm.** `MTR_DISCREP` or trip → `MTR_ALARM`, with a latch that needs an
HMI reset. An online simulation of `MTR_ESTOP_OK` going false must drop `MTR_RUN_CMD`
within one scan.""",
            },
            {
                "key": "hmi",
                "title": "HMI",
                "content": """One screen, three controls, no clutter — the whole discipline of a starter page:

**Header.** Cell name, current time, operator name.

**Motor group.**

- Start pushbutton (green): allowed only when `MTR_AUTO_MODE` and healthy.
- Stop pushbutton (red): always enabled, breaks the hold.
- Running lamp: green lamp bound to `MTR_RUN_CMD`.
- Alarm lamp + Silently reset (only enabled with a present alarm) — clears `MTR_ALARM`.

**Status row.** ICONS for: e-stop released (safe), overload OK, cooling fan OK,
rotation feedback present, auto mode.

**Behaviour tests you should plan into the HMI spec:** Start button disabled when the
e-stop is pulled; Stop does not require any permissive; the running lamp mirrors state,
not command; and a blinking alarm indicator when a discrepancy latches. No one should
need a manual to run this page.""",
            },
            {
                "key": "scada",
                "title": "SCADA / Upper-Level System",
                "content": """This project has no full SCADA, but the discipline starts here: define the OPC UA
interface you WILL provide. A starter cell typically exposes to the MES/supervisor:

- `Motor1.EngVal` — RUN_CMD as a writable start command for remote scripted runs.
- `Motor1.Status` — run, stopped, alarmed (enum).
- `Motor1.Interlock` — the satisfied/unsatisfied permissive list.
- `Motor1.RunHours` — accumulated run hours for predictive maintenance.
- `Motor1.TripCount` — counters per trip cause.

**Contract:** all values are read-only except `EngVal`. The SCADA never bypasses the
HMI's stop; a remote start also requires the same healthy header (rung 1). Trends:
running status and run-hours over 8 hours, alarm acknowledge events logged with a time
stamp so the maintenance history is reconstructable.""",
            },
            {
                "key": "alarms",
                "title": "Alarms",
                "content": """Define the alarm register before commissioning:

| Tag | Priority | Message | % is suppressed? |
| --- | --- | --- | --- |
| `MOTOR_ESTOP_ACTIVE` | High | E-stop pressed — motor dropped | Never |
| `MOTOR_OVERLOAD_TRIP` | High | Overload relay tripped — manual repair | Never |
| `MOTOR_DISCREP` | Medium | Command vs rotation feedback mismatch | Only in local mode |
| `MOTOR_FAN_TRIP` | Medium | Cooling fault — motor derated | Never |
| `MOTOR_LOW_VOLTAGE` | Medium | Supply dip detected | 5 s deadband |

Rules:
- High-priority alarms latch, require acknowledge and clear.
- Alarm-to-HMI latency must be under 1 s; the audit entry includes operator and time.
- A cut wire must produce a fault (NC convention) rather than a missing alarm.
- No alarm spam: a single cause may raise one alarm plus one summary, never six.

Every alarm needs a documented consequence and a documented recovery action — that text
lives beside the tag in the maintenance system.""",
            },
            {
                "key": "interlocks",
                "title": "Interlocks",
                "content": """The interlock list for one motor is short — and that is the point. Learn matrix
discipline here.

| Interlock | Sensor | Action | Restart |
| --- | --- | --- | --- |
| I1 E-stop dropped | E-stop chain (DI3 NC) | Open contactor immediately | Operator reset |
| I2 Overload | OL auxiliary (DI2 NC) | Open contactor, latch alarm | Manual reset |
| I3 Cooling | Fan differential (DI5 NC) | Open contactor at trip, warn below derate | Auto once healthy |
| I4 Rotation discrepancy | K-con (DI4) | Drop run within 2 s, latch | HMI acknowledge |
| I5 Open door | Door-switch contact | Blocked start (cell doors) | Auto when closed |

**I1 overrides everything.** The e-stop acts on the safety relay independently of the
PLC; the PLC only mirrors `MTR_ESTOP_OK` to prevent a start. I2 determines the NC
wiring. Interlock I4 is a monitoring interlock: it cannot cause a safe stop of a real
faulty drive by itself, but it catches the discrepancy a breaker trip or a contactor
weld would cause. On any I-active the HMI shows exactly which interlock is holding.""",
            },
            {
                "key": "networking",
                "title": "Networking",
                "content": """Small fixed architecture, drawn once:

```
[HMI] --Profinet-- [PLC] --Profinet/OPC UA-- [Cell PC / SCADA]
                     |
                  24 V DC PSU         [Safety relay] --- e-stop chain
```

- One managed switch, VLAN for control traffic (VLAN 10), MES on VLAN 20.
- Fixed IP addressing documented on a printed schedule in the panel.
- The PLC is the time master (SNTP) so audits and alarm stamps agree; the HMI and
  SCADA take time from it.
- No internet at the cell layer. Remote access (if ever) via a locked-down VPN jump
  host, never a direct port forward.
- Wire at least one future spare in the trunk and label it — cheap insurance.

Document the switch config, the IP schedule, and the VLAN mapping in this section.
A network you cannot redraw is a network you cannot repair.""",
            },
            {
                "key": "testing",
                "title": "Testing / FAT",
                "content": """**Factory acceptance test (pre-wiring bench):**

1. Continuity: every I/O wire traced against the panel drawing.
2. Input checks: each DI toggles the correct tag in the program's monitor view.
3. Output checks: each DO operates the correct relay/lamp; coil draw measured.
4. Function test T1 — Start/Stop: Start closes contactor (lamp on), Stop opens it.
5. Function test T2 — E-stop from running: contactor drops, `MTR_ESTOP_OK` false,
   alarm latches, Start is disabled until reset.
6. Function test T3 — Overload: trip the OL auxiliary; same drop + latch.
7. Function test T4 — Discrepancy: block rotation feedback; run trips in 2 s.
8. Function test T5 — Restart: verify no auto-restart after any trip.
9. Kill the 24 V PSU: whole loop fails safe, no false start pulses.
10. EMC sanity: run the motor contactor on/off 50 times and confirm the DI input
    statuses are stable (no chatter picked up on the digital inputs).

Sign off FAT only when every line is witnessed. Record measured values, not just
PASS.""",
            },
            {
                "key": "fault_injection",
                "title": "Fault Injection",
                "content": """The exercise phase. Three crafted failures live in this project. For each one:
read the symptom, use the recommended check sequence, and give a written diagnosis.

- **Fault 1 — motor will not start**, though Auto is shown and no alarm is lit. The
  healthy header is quietly false.
- **Fault 2 — motor keeps running after Stop.** The run command goes away but the
  output stays; check where the power actually is.
- **Fault 3 — e-stop does not drop the motor.** The safety chain says "ok" but the
  motor runs anyway. Find who bypassed what.

Your diagnosis must state the root cause (not the component), name the evidence that
proved it, and name the one thing you would NOT change while troubleshooting a
running contactor with a pulled e-stop. Attempt all faults before Commissioning.""",
            },
            {
                "key": "troubleshooting",
                "title": "Troubleshooting",
                "content": """The method that wins: **verify the command, then verify the power at the device,
then verify the feedback.** Never guess.

1. **Symptom to state.** Restate the fault as a state mismatch: "HMI says run, motor
   not running" is a different tree than "motor stopped on its own".
2. **Half-split.** From the HMI, is `MTR_RUN_CMD` true? If false, follow the rung
   from the healthy header back. If true, the problem is downstream — contactor,
   coil supply, or the motor circuit.
3. **Measure, don't ohm it blind.** Check coil voltage at the contactor A1-A2 with a
   meter before touching the motor circuit. LV work: gloves, barriers, tester
   and prove-dead before any contact.
4. **Feedback.** K-con shows rotation only if shaft rotates — a "feedback missing"
   alarm on a running motor means check the switch and its wire, not the motor.
5. **Time-based cues.** A fault that appears after 10 minutes of running is thermal
   (cooling/overload victim); one that appears at power-up is supply or latch.

Keep a dated fault log: symptom, checks performed, measurements, root cause. Future
emails to the OEM live or die on that record.""",
            },
            {
                "key": "commissioning",
                "title": "Commissioning",
                "content": """On-site sequence, in order:

1. **Isolation & shot.** Prove the panel dead, carry out lockout/tagout, and verify
   the motor winding insulation resistance (megger) against the OEM sheet.
2. **Power-up.** Energise controls only (PLC, HMI, PSU). Verify 24 V rails and card
   LED states against the I/O list.
3. **Drive check.** Test the e-stop chain first — before anyone runs the motor.
4. **Local run.** Local/remote selector in local: jog the motor directly (this is the
   only place motor-only start is legitimate), check rotation arrow against conveyor
   direction and phasing.
5. **Remote run.** Return to remote, run the full Function tests T1-T5 from the HMI.
6. **Interaction.** Introduce one trip mid-run (fan fault) and confirm clean stop,
   no auto-restart, correct alarm and audit entry.
7. **Handover.** Operation manual, as-built drawing set, FAT sheet, interlock matrix,
   and a 1-hour witnessed run at full conveyor speed. Leave the run-hours counter
   reset and the trip counters zeroed.""",
            },
            {
                "key": "final_documentation",
                "title": "Final Documentation",
                "content": """The handover package for this project must contain:

- As-built control panel drawing (annotated: every deviation from the design).
- Signed I/O list with terminal numbers.
- Final ladder print with rung numbers and tag revisions.
- Interlock matrix + alarm register with consequences and recovery.
- FAT results and the on-site commissioning record with measured values.
- Operation manual: one page on how to start, how to stop, and exactly what to do
  when an interlock holds the motor — no six-page theory.
- The troubleshooting fault log from the injection phase.

This folder is what a client or a future technician opens first. If they can restart,
understand, and safely isolate the motor from the drawing alone, you have finished.""",
            },
        ],
        "faults": [
            {
                "slug": "motor-wont-start",
                "title": "Motor will not start although Auto mode is shown",
                "symptom": "Operator presses Start on the HMI. No alarm is lit and the HMI shows Auto. The motor does not start.",
                "description": "The start command exists but the healthy header is quietly false.",
                "injected_fault": "Motor cubicle door interlock contact in the healthy chain is open, blocking the seal-in header.",
                "operation_notes": "The HMI shows only the group lamp; the interlock page is available. The rung 1 header has five series contacts; find the one that is false.",
                "expected_checks": [
                    "check_start_command",
                    "check_estop_chain",
                    "check_overload_relay",
                    "check_cooling_fan_switch",
                    "check_door_interlock",
                    "check_plc_output_state",
                    "check_auto_mode_selector",
                ],
                "correct_diagnosis": "Motor cubicle door interlock open in the healthy header, blocking the run command.",
                "correct_diagnosis_keys": ["door interlock", "healthy header", "run blocked"],
                "common_misdiagnoses": ["estop", "overload", "contact", "plc output"],
            },
            {
                "slug": "motor-keeps-running-after-stop",
                "title": "Motor keeps running after Stop is pressed",
                "symptom": "HMI shows the run lamp OFF and Stop acknowledged, but the motor keeps rotating.",
                "description": "The PLC has removed the run command; the motor circuit still has power.",
                "injected_fault": "Contactor main tips appear welded shut, keeping the motor energised after the coil drops out.",
                "operation_notes": "A command/state mismatch: this is a power-path fault downstream of the contactor coil, not a logic fault.",
                "expected_checks": [
                    "check_stop_command",
                    "check_plc_output_state",
                    "check_contactor_coil_voltage",
                    "check_contactor_tips",
                    "check_motor_circuit_isolation",
                    "compare_plc_to_physical_state",
                ],
                "correct_diagnosis": "Welded contactor main tips keeping the motor energised despite coil de-energisation.",
                "correct_diagnosis_keys": ["welded contactor", "contactor tips", "motor power path"],
                "common_misdiagnoses": ["seal in logic", "stop button", "plc tag"],
            },
            {
                "slug": "estop-does-not-stop-motor",
                "title": "E-stop pressed but the motor does not drop",
                "symptom": "Operator pulls the e-stop. Alarm does NOT latch and the motor keeps running.",
                "description": "The safety chain reports healthy while the motor is still on — a bypassed safety circuit.",
                "injected_fault": "The e-stop mirror contact is jumpered out at the terminal block, so the PLC never sees the chain open.",
                "operation_notes": "Safety-circuit bypass is the most serious fault in this pack. The correct diagnosis names WHERE the bypass is, not just the symptom.",
                "expected_checks": [
                    "check_estop_chain",
                    "check_safety_relay_inputs",
                    "check_estop_physical_button",
                    "check_terminal_block_wiring",
                    "check_plc_input_status",
                    "review_estop_test_log",
                ],
                "correct_diagnosis": "E-stop mirror contact jumpered at the terminal block; the safety chain never reaches the PLC input.",
                "correct_diagnosis_keys": ["estop bypass", "jumper", "terminal block", "safety chain"],
                "common_misdiagnoses": ["safety relay fault", "plc input card", "contactor"],
            },
        ],
    },
    {
        "slug": "instrument-loop-checkout",
        "title": "4-20 mA Loop & I/O Checkout — Pressure on a Clearwell Filter",
        "industry": "water",
        "difficulty": "basic",
        "hours": 14,
        "description": (
            "Every technician's bread-and-butter: take a pressure transmitter from the field "
            "through the marshalling panel to the PLC analog input, uphold a healthy 4-20 mA "
            "live-zero loop, set scaling so the HMI reads true engineering units, and prove "
            "the loop fails safe. The natural companion to the motor starter project."
        ),
        "sections": [
            {
                "key": "project_brief",
                "title": "Project Brief",
                "content": """A clean-water utility installs a pressure transmitter (PT-001) on the discharge of
the filter-to-clearwell line so the plant can monitor backpressure and trend filter
loading. Your job: select and wire the loop, configure the card and scaling, and prove
the loop behaves correctly — including how it fails. This project has no motion and no
pumps; it is pure instrument craft: mA, scaling, loops, and honest measurements.

Deliverables: a single-loop P&ID, I/O and tag documentation, the scaling calculation
(ma% → engineering unit), realistic alarm/fail-safe settings, a loop sheet with
measured voltages and currents, and a signed calibration sheet. The Fault Injection
phase hides the loop failures a plant truly sees — a pinned 4 mA, a pinned 20 mA, and
a 10x-scaling mistake.""",
            },
            {
                "key": "process_description",
                "title": "Process Description",
                "content": """Filtered water leaves the filter on the discharge header at roughly 2.2-2.8 barg,
depending on filter loading. PT-001 (2-wire smart pressure transmitter, 4-20 mA,
0-10 barg) reports that pressure to the PLC so the plant can:

1. Trend filter backpressure vs run time to schedule backwash (rising pressure =
   blinding bed).
2. Detect a pump fault wherever a supply pump commands flow against pressure.
3. Supply the HMI with a live discharge-pressure readout.

The loop is electrically simple: transmitter → marshalling panel terminal block →
analog input card (AI) → PLC → HMI/SCADA. The 4 mA live zero means a dead or broken
loop reads 0 % = 0.000 barg at the HMI unless the fail-safe detection is configured.
This is the point of the project: make the measurement honest and make its failure
obvious.""",
            },
            {
                "key": "p_and_id",
                "title": "P&ID / Loop Diagram",
                "content": """**Loop diagram (single line):**

```
PT-001 (2-wire, 0-10 barg)
  |--+24 V (supply)-----------------------------------> terminal block
  |--signal (4-20 mA, current return)-----------------> AI card (0-20 mA / 4-20)
  |                                                       |
PLC --------- HMI (discharge pressure barg)              |-- 250 ohm receiver
```

Key notes on the drawing:

- Two-wire loop uses the same two conductors for power and signal; polarity matters.
- The AI card is configured for current input, not voltage; a voltage card would need
  a precision 250 ohm shunt (and the drawing must show it).
- Cable is screened twisted pair, screening earthed at the panel end only.
- The loop sheet annotates terminal numbers on BOTH ends and the expected mA at the
  mid-range point.

The P&ID for the process shows PT-001 on the discharge line with the loop tied to the
filter-control function block; this project drawing is the electrical execution of it.""",
            },
            {
                "key": "io_list",
                "title": "I/O List",
                "content": """Analog input (4-20 mA, 0-10 barg):

| Ref | Description | Device | Range (mA) | Engineering |
| --- | --- | --- | --- | --- |
| AI0 | Filter discharge pressure | PT-001 | 4-20 | 0.000-10.00 barg |

Hardware facts to record:

- Card type, channel number, and the internal (configurable) receiver termination.
- Whether the card accepts a 2-wire loop directly or needs a termination shunt.
- Input filter time constant (set to 500 ms; too fast rides process noise, too slow
  hides real swings).
- Wiring: screened pair, both ends labelled `AI0+ / AI0-` exactly matching the loop
  sheet.

Optional spare channel documented for a future flowmeter. Digital I/O: none in this
project — deliberately. Learn the analog craft before adding force variables.""",
            },
            {
                "key": "tag_list",
                "title": "Tag List",
                "content": """| Tag | Type | Meaning | Source range | Scale to |
| --- | --- | --- | --- | --- |
| `FT_HEADER_PRESSURE` | AI REAL | Discharge pressure raw | 4-20 mA | 0-10 barg |
| `FT_HEADER_PRESSURE_PCT` | AI REAL internal | Percentage | 0-100 % | — |
| `FT_HEADER_PRESSURE_OK` | BOOL internal | Loop healthy (2.5-3.6 mA range check in) | — | — |
| `FT_HEADER_PRESSURE_LOW` | ALARM internal | < 0.4 barg | — | — |
| `FT_HEADER_PRESSURE_HIGH` | ALARM internal | > 8.5 barg | — | — |

Tag naming discipline:

- Instrument tag PT-001 is the field device; PLC tag is the process value.
- The scaling is stored once, nowhere else (no magic numbers scattered in rungs).
- The `_OK` bit exists so a dead loop reads as an alarm, never as a 0.000 barg
  process value. This is the single most valuable tag on this project.""",
            },
            {
                "key": "control_philosophy",
                "title": "Control Philosophy",
                "content": """**C1 — Measurement integrity first.** The loop must be proven healthy before its
value is trusted. `FT_HEADER_PRESSURE_OK` requires the received current to sit inside
the live signal band with margin (3.6-20.4 mA) — values at scale-minimum (4.0 mA) are
signals, not faults.

**C2 — Scaling is linear.** % = (I − 4) / 16 × 100; barg = % × 10. Documented once,
applied by the PLC's scale function block with the same range constants.

**C3 — Fail-safe.** If `_OK` is false the HMI shows "TRIP / LOOP FAULT" not "0.00".
Alarm processing uses the process value only when healthy; a dead loop suppresses
derived alarms (no cascade of nonsense).

**C4 — Filtering.** The 500 ms input filter is applied at the card; the PLC does not
double-filter. Judged response: a step of +1 barg at the process reaches 90 % of the
recorder value within ~3 filter time constants.

**C5 — Latency.** Total loop latency card-to-HMI below 2 s including filters; proven
at FAT with a two-point mA step test. Nothing fancy — honest and slow-enough is
correct for a utility alarm.""",
            },
            {
                "key": "plc_program",
                "title": "PLC Program",
                "content": """Small, legible function blocks — no one-liners.

**FB_scaling(PT-001 channel):**
```
raw_pct = (I_mA - 4.0) / 16.0 * 100.0
barg    = raw_pct * 10.0
safe    = (I_mA in [3.6 .. 20.4])
```
Store raw mA, percent, and the derived barg and `_OK` bits.

**Rung/alarm logic:**

1. `_OK` bit per scan: `safe AND card_online`.
2. Low/high alarm contacts on `barg` only when `_OK`.
3. HMI value = `barg` when `_OK`, otherwise `TRIP` — an explicit branch, never a raw
   zero.
4. A diagnostic word logs the last 10 outlier samples (mA out of band) for the fault
   log.

**Why so little?** The loop has one value. The engineering is in filtering, range
checking, and fail-safe presentation — which the program makes explicit. A reviewer
should be able to read the fail-safe behaviour in ten seconds.""",
            },
            {
                "key": "hmi",
                "title": "HMI",
                "content": """Single faceplate for `PT-001 Discharge pressure`:

- Process value, large: **barg** with one decimal; units locked to the tag.
- Bargraph with scale ticks 0-10 barg; setpoint/high-low markers optional.
- Live mA readout and the derived % — technicians LOVE seeing mA without a meter.
- Status banner: `OK · LOOP FAULT · CARD OFFLINE` per the `_OK` branch.
- Alarm row: `PRESSURE HIGH` / `PRESSURE LOW` / `LOOP FAULT`, each with
  acknowledge and history.

Interaction rules:

- The faceplate is read-mostly: no start/stop objects on a measurement page.
- When `_OK` is false, the numeric field shows "----" or "TRIP" — never 0.000.
- The operator can open a 10-hour trend of barg with a maintenance overlay showing
  the mA band edges.

A *good* faceplate lets an operator see in three seconds whether the reading is
healthy and what it means.""",
            },
            {
                "key": "scada",
                "title": "SCADA / Upper-Level System",
                "content": """The utility SCADA subscribes to:

- `PT-001.PV` (barg) — trended on the filter overview.
- `PT-001.OK` — fed into the filter service status for backwash scheduling.
- `PT-001.LFAULT` — raise a station alarm if a loop is out for more than 30 min.
- `PT-001.DIAGNOSTICS` — mA samples + card status packet every minute.

Fail-safe at SCADA level mirrors the PLC: a dead loop shows `LOOP FAULT`, never a
healthy zero-pressure state that could tell a remote operator "line empty".

**One rule matters at this level:** SCADA trends and alarms derive from the PLC's
published tags, and scaling lives in the PLC. The SCADA never re-scales; it only
formats. Two places holding the same scale constant guarantee that someday they
diverge — and the HMI and SCADA will disagree by exactly that factor.""",
            },
            {
                "key": "alarms",
                "title": "Alarms",
                "content": """| Tag | Priority | Message | Consequence | Recovery |
| --- | --- | --- | --- | --- |
| `PT_LOOP_FAULT` | High | Loop fault/invalid signal on PT-001 | Unsafe to schedule backwash by pressure | Restore loop, verify mA, clear |
| `PT_PRESSURE_HIGH` | Medium | Discharge pressure > 8.5 barg | Possible filter-binding or downstream restriction | Check filter DP, valves, pump |
| `PT_PRESSURE_LOW` | Low | Pressure < 0.4 barg | Unlikely with supply; confirm loop health | Confirm `_OK`, process check |

Alarm realism:

- A loop fault is HIGH because a silent dead loop has misdirected operators onto the
  wrong diagnosis more than once.
- Suppression: pressure alarms only evaluate when `_OK` true — a dead loop produces
  exactly ONE alarm (`PT_LOOP_FAULT`), not three.
- All three carry a digital stamp and operator/ack history; the maintenance history
  is a troubleshooting goldmine that most plants waste.
- No alarm without a consequence and a recovery action. If you cannot write the
  recovery, you do not understand the tag.""",
            },
            {
                "key": "interlocks",
                "title": "Interlocks",
                "content": """The loop contributes measurement interlocks, not motion interlocks:

| Interlock | Logic | Purpose |
| --- | --- | --- |
| I1 Signal validity | `_OK` false blocks value-derived logic | Stop false trips/scheduling |
| I2 Fail-safe presentation | HMI/SCADA show TRIP, not 0.000 | Prevent operator misdiagnosis |
| I3 Filter bound | Input filter 500 ms max | Keep response meaningful |
| I4 Range sanity | `barg` never above 10.1 (upper cap) in display | Clamp noisy artefacts |

Why interlock I1 matters mechanically: the backwash scheduler on the filter uses
discharge pressure as a "binding" proxy. If the loop dies and reads 0.000, the
scheduler would call the filter "clean", skip backwash, and blind the bed. `_OK`
prevents that. This is the loop's version of the motor e-stop interlock — a live
zero is only trustworthy when proven live.""",
            },
            {
                "key": "networking",
                "title": "Networking",
                "content": """The loop's network is short on purpose:

```
PT-001 --(analog pair, screened)--> Marshalling TB -> AI card -> PLC
                                                                  |
[HMI] ---- Profinet ring ---- [PLC] ---- OPC UA ---- [Utility SCADA]
```

What to document:

- Analog cable: 2 twisted screened pairs, one used, one spare; screen earthed panel
  side only (ground-loop rule).
- Loop signal path voltage budget: transmitter minimum supply 12 V DC at 4-20 mA
  across the cable run — 24 V rail minus cable drop must clear it (checked at FAT).
- The 1 s full-path latency target and how it was measured.
- Where the single point of failure is (panel PSU, card failure) and the spare-card
  / redundant loop policy in this plant — name it, even if out of scope.

**Grounding half-split:** if the HMI value dances, suspect the screen earthing and
the PSU isolation before touching the transmitter range.""",
            },
            {
                "key": "testing",
                "title": "Testing / FAT",
                "content": """The acceptance script for a single loop — every item witnessed and recorded:

1. **Continuity & polarity** against the loop sheet, both ends.
2. **Card config** read back: current input, filter 500 ms, termination fitted.
3. **mA injection:** loop calibrator at 4.0 / 8.0 / 12.0 / 16.0 / 20.0 mA; the HMI
   must read 0.0 / 2.5 / 5.0 / 7.5 / 10.0 barg and the trend must agree within ±0.1 %.
4. **Scaling check:** percent readout matches the mA (this is the 10x trap).
5. **Open-loop test:** open the signal wire → `_OK` false → HMI shows LOOP FAULT —
   NOT 0.000. Alarm `PT_LOOP_FAULT` latches.
6. **Short-loop test:** short the signal to supply → pinned 20 mA → `_OK` false → LOOP
   FAULT. Same single alarm.
7. **Step response:** step 4→20 mA; recorder reaches 90 % inside 2 s.
8. **Latency:** measured card-to-HMI under 2 s.
9. **Filter sanity:** 50 mA-injection noise bursts on the spare pair do NOT move the
   displayed value (screening + filter working).
10. **Calibration:** dead-weight calibration of PT-001 across 0-10 barg, 5 points,
    as-found/as-left tolerances, both columns signed.

A failure at any step sends the package back to the drawing — that is the point.""",
            },
            {
                "key": "fault_injection",
                "title": "Fault Injection",
                "content": """Three loop faults to diagnose this phase:

- **Fault 1 — reading pinned at 4.00 mA**: a flat 0.000 barg across hours while the
  plant visibly holds pressure. Classic open-loop behaviour on a live-zero signal.
- **Fault 2 — reading pinned near 20 mA**: The same transmitter now reads screaming
  high while physical conditions are normal. A fail-high transmitter or a shorted
  signal path.
- **Fault 3 — every reading is exactly 10x off**: values crawl like a scaling table
  error — yet injected mA is perfect at both ends. Find who scaled the tag.

For each: take mA measurements in sequence, compare the two ends of the loop, name
the root cause with evidence, and state which component path you would and would NOT
replace. No meter, no diagnosis.""",
            },
            {
                "key": "troubleshooting",
                "title": "Troubleshooting",
                "content": """Loop troubleshooting, disciplined:

1. **Establish the loop health first.** Inject 4.0 mA at the field terminal and see
   what the card reads. Matches? Loop is intact up to the card — fault is the field
   device. No match? Fault is the wire/card side.
2. **Half-split the cable.** Move the calibrator from the transmitter terminals to the
   marshalling panel; if the read recovers, the fault sits between panel and field.
3. **Two known points, not one.** A reading pinned at exactly 4.00 mA is an open loop;
   pinned near 20 mA is signal-to-supply short or transmitter fail-high; drifting
   randomly is screen/earthing or a dying supply. One fixed point at mid-range is
   almost never a coincidence — distrust it.
4. **Compare ends.** HMI says 2.5 barg; the meter at the AI card says 8.0 mA = 2.5 barg
   — then the scaling is right and the "10x" view is a TAG problem downstream.
5. **Safe work.** Never break a live loop without a meter in series or a jumpered
   terminal; the loop is powered. Prove the transmitter supply before assuming device
   death.

Every reading you take is a data point for the fault log: date, mA, both ends, card
state. That log is the credential reviewers trust.""",
            },
            {
                "key": "commissioning",
                "title": "Commissioning",
                "content": """Site sequence:

1. **Pre-power.** Injected-loop sheet complete; polarity, screening, isolations proven.
2. **Power-up.** Energise the 24 V PSU; measure transmitter supply voltage at the
   terminals — must exceed the device minimum at all measured points.
3. **Calibration on site.** Dead-weight 5-point run, as-found recorded, as-left
   tolerance met (≤ ±0.1 %), both signed. Tag the unit with the calibration date.
4. **Process tie-in.** Open the impulse line to the header; watch the value behave
   with filter loading over a 1-minute window — it must track, not jump.
5. **Fail-safe drill.** Pull the signal wire; confirm LOOP FAULT in under 2 s. Refit,
   loop must self-clear on restore and stop alarming once `_OK` returns (with ack).
6. **Handover.** Loop sheet, calibration sheets, card config read-back, FAT results,
   alarm register entries, and the as-built deviation list. Put the mA budget and
   filter settings on the front sheet — the next technician should never re-derive
   them.""",
            },
            {
                "key": "final_documentation",
                "title": "Final Documentation",
                "content": """Handover packet for the pressure loop:

- Single-loop P&ID and the electrical loop diagram.
- Complete loop sheet: both ends, terminal numbers, expected mA at 0/25/50/75/100 %.
- Tag list including `_OK` and alarm tags with consequence/recovery.
- Scaling calculation (mA → % → barg) printed exactly as configured.
- Calibration certificate (as-found/as-left) and the injected-mA FAT table.
- Card configuration read-back (channel, range, filter, termination).
- The troubleshooting fault log from the injection phase.

A reviewer can reproduce every number in this packet with a meter and a calibrator
in one afternoon. If they can, the packet is done.""",
            },
        ],
        "faults": [
            {
                "slug": "pressure-pinned-4ma",
                "title": "Pressure pinned at 4.00 mA — open loop",
                "symptom": "PT-001 reads exactly 0.000 barg across several hours while the plant visibly holds pressure; no alarms are raised because the value looks healthy at scale-minimum.",
                "description": "The loop is open somewhere so the current pins at 4 mA (0 %).",
                "injected_fault": "Loose termination in the marshalling panel on the AI0+ screw; the loop opens.",
                "operation_notes": "A flat reading pinned at scale minimum is the classic live-zero open-loop signature.",
                "expected_checks": [
                    "measure_loop_current",
                    "check_transmitter_power",
                    "verify_terminal_connection",
                    "check_wiring_continuity",
                    "compare_manual_gauge_reading",
                    "check_plc_input_card_status",
                ],
                "correct_diagnosis": "Open loop on PT-001 (loose AI0+ termination) pinning the signal at 4 mA = 0 %.",
                "correct_diagnosis_keys": ["open loop", "loose terminal", "loop open", "4 ma pin"],
                "common_misdiagnoses": ["transmitter fault", "scale error", "card failure"],
            },
            {
                "slug": "pressure-pinned-20ma",
                "title": "Pressure pinned near 20 mA — fail-high",
                "symptom": "PT-001 reads about 10 barg and screaming high alarms while physical pressure is normal.",
                "description": "The transmitter or its loop path is driving the signal to top of range.",
                "injected_fault": "Internal transmitter fault drives the output to ~20 mA (fail-high) regardless of process.",
                "operation_notes": "Fail-high vs open-loop distinction: 20 mA pins high with healthy process; an open loop pins at 4 mA.",
                "expected_checks": [
                    "measure_loop_current",
                    "check_transmitter_span",
                    "verify_terminal_connection",
                    "check_loop_shunt",
                    "compare_manual_gauge_reading",
                    "inject_reference_current",
                ],
                "correct_diagnosis": "PT-001 internal fault driving the output fail-high to ~20 mA.",
                "correct_diagnosis_keys": ["transmitter fault", "fail high", "transmitter internal"],
                "common_misdiagnoses": ["open loop", "process high", "card range"],
            },
            {
                "slug": "pressure-10x-scaling",
                "title": "Every reading exactly 10x off",
                "symptom": "All values read ten times too high; injected mA at the card reads correctly at intermediate points but the HMI disagrees by a factor of ten.",
                "description": "The scaling constants applied at the HMI/SCADA layer are off by a factor of ten.",
                "injected_fault": "The HMI display scales with 0-100 barg instead of 0-10 barg.",
                "operation_notes": "mA is perfect end-to-end — this is a TAG/scaling problem downstream, not a loop-power problem.",
                "expected_checks": [
                    "verify_range_config",
                    "check_plc_scale_config",
                    "compare_manual_gauge_reading",
                    "cross_check_hmi_value",
                    "check_deadband_settings",
                    "check_transmitter_tag_units",
                ],
                "correct_diagnosis": "Scaling blown by a factor of ten at the HMI layer (0-100 barg instead of 0-10 barg).",
                "correct_diagnosis_keys": ["scaling", "10x", "range config", "hmi scaling"],
                "common_misdiagnoses": ["transmitter range", "loop fault", "card config"],
            },
        ],
    },
    {
        "slug": "conveyor-sorter-cell",
        "title": "Conveyor Sorter Cell — Sense, Actuate, Count",
        "industry": "manufacturing",
        "difficulty": "intermediate",
        "hours": 30,
        "description": (
            "Discrete automation fundamentals on a real production pattern: a belt infeed, a "
            "photocell position sensor, a pneumatic diverter, a capacitive quality gate and "
            "a counting register. Same anatomy as a FACTORY I/O conveyor station — sequence "
            "logic, zone interlocks, HMI counters and a reject memory."
        ),
        "sections": [
            {
                "key": "project_brief",
                "title": "Project Brief",
                "content": """A packaging line needs a sorting cell: parts arrive one-at-a-time on a belt, are
detected by a photocell at the sort position, and a good/bad test by a capacitive
gate decides whether the pneumatic diverter pushes the part to the reject bin or lets
it continue to the packer. The cell counts good, reject and total parts, jams the
belt on a missed part, and provides an HMI with counters, operators, and a reset.

Deliverables: the full 17-section package — P&ID/AutoCAD-equivalent, I/O list, tag
list, a state-machine and ladder program with zone interlocks, HMI screens with
counters, alarm and interlock matrices, FAT script, and commissioning record.

The Fault Injection phase hides the four most common sorter-cell gremlins: a sorter
that never diverts, spurious rejects from a noisy sensor, a false jam, and counter
drift. Diagnose all four.""",
            },
            {
                "key": "process_description",
                "title": "Process Description",
                "content": """The cell: 12 m flat belt at 0.9 m/s. Parts are evenly spaced by the infeed — the
cell does NOT control infeed pitch.

Sequence per part:

1. Part enters: photocell `PL_BELT_IN` detects the front edge.
2. Conveyor runs continuously while active (no start/stop per part — speed control is
   downstream feature, not this cell).
3. At the sort position, `PL_SORT_POS` confirms the part; the capacitive gate
   `QH_GOOD` classifies good vs reject (proximity threshold preset).
4. If reject: the sequencing diverts — `YV_DIVERT` energises, pneumatic diverter
   sweeps the part into the reject bin; if good: the diverter stays retracted.
5. Counters update: GOOD, REJECT, TOTAL.
6. A part that leaves the belt without a confirmed divert OR a missed detection raises
   a `JAM` / `MISS` fault and stops the infeed to protect downstream.

The conveyor stops only on: e-stop, jam/miss fault, or downstream interlock (packer
busy). Everything else runs.""",
            },
            {
                "key": "p_and_id",
                "title": "P&ID / Layout Drawing",
                "content": """Layout (simple AutoCAD-style sketch reproduced in the drawing set):

```
 INFEED >>> |----belt (0.9 m/s)----> [PL_BELT_IN] --> [QH_GOOD cap gate]            
                                       sort pos  [PL_SORT_POS]    |
                                              [YV_DIVERT] >-- reject bin
                                            (pneumatic diverter)
 GOOD path >>> >>> to packer
```

Field devices on the drawing:

- `PL_BELT_IN` — retro-reflective photocell, belt entry.
- `PL_SORT_POS` — through-beam photocell pair at the sort position.
- `QH_GOOD` — capacitive proximity gate on a swing-arm bracket above the belt
  (threshold: good = metallic/mass passing).
- `YV_DIVERT` — 5/2 solenoid valve + single-acting cylinder with retract spring;
  energised = extend (sweep), de-energised = retract.
- `S_DR`/`S_RR` — cylinder extended/retracted limit switches.
- Lamp stack `L_GREEN`, `L_AMBER`, `L_RED` above the cell.
- Pneumatic supply with pressure switch `PS_AIR` (min 6 bar to run).

The drawing shows the direction of travel, sensor fields, the reject bin, and the
physical guards — a sorter cell's accidents live in the changeover area between belt
and bin.""",
            },
            {
                "key": "io_list",
                "title": "I/O List",
                "content": """Digital inputs (24 V DC):

| Ref | Description | Device |
| --- | --- | --- |
| DI0 | Belt entry photocell | PL_BELT_IN |
| DI1 | Sort position photocell | PL_SORT_POS |
| DI2 | Diverter extended limit | S_DR |
| DI3 | Diverter retracted limit | S_RR |
| DI4 | Air pressure OK (NC) | PS_AIR |
| DI5 | E-stop chain mirror (NC) | Safety |
| DI6 | Conveyor thermal overload (NC) | OL_CV |
| DI7 | Packer ready (downstream) | X_PACKER | may 'gate'

Digital outputs:

| Ref | Description | Device |
| --- | --- | --- |
| DO0 | Belt motor contactor | M_CV |
| DO1 | Diverter solenoid | YV_DIVERT |
| DO2 | Green beacon | L_GREEN |
| DO3 | Amber beacon | L_AMBER |
| DO4 | Red beacon | L_RED |

Word of caution for the drawing: `PL_SORT_POS` is a through-beam with a dark-on
option for jam clarity; the I/O list must note the polarity convention so a snowy
lens reads as a "beam blocked", not a part.""",
            },
            {
                "key": "tag_list",
                "title": "Tag List",
                "content": """| Tag | Type | Source | Meaning |
| --- | --- | --- | --- |
| `SORT_ACTIVE` | BOOL int | Start+healthy | Cell armed (belt runs) |
| `PL_BELT_IN` | BOOL DI0 | Photocell | Part at entry |
| `PL_SORT_POS` | BOOL DI1 | Photocell | Part at sort position |
| `QH_GOOD` | BOOL DI (cap) | Gate | Part classified good |
| `YV_DIVERT` | BOOL DO1 | Solenoid | Diverter commanded out |
| `SR_DR`, `SR_RR` | BOOL DI2/DI3 | Cylinder limits | Diverter position |
| `PS_AIR` | BOOL DI4 | Press switch | Air available |
| `ESTOP_OK` | BOOL DI5 | Safety | Chain closed |
| `OL_CV_OK` | BOOL DI6 | OL | No trip |
| `CNT_GOOD`, `CNT_REJ`, `CNT_TOT` | UDINT int | Counters | Segment counters |
| `CNT_REJ_MEM` | UDINT int | Memory | Reject bits per part slot |
| `JAM_ACTIVE` | BOOL int | Logic | Belt fault — stop infeed |

Naming rules: sensors are the physical ref (`PL_`), commands are goals
(`YV_DIVERT`), counters are `CNT_`. No tag name ever carries its value in its name
(no `Belt_Running_True`).""",
            },
            {
                "key": "control_philosophy",
                "title": "Control Philosophy",
                "content": """**C1 — Continuous vs sequenced.** The belt runs while armed (`SORT_ACTIVE`). Part
handling is a per-part sequence, never a belt start/stop.

**C2 — Sort decision.** At `PL_SORT_POS` rising edge, capture `QH_GOOD` into a
one-part decision: good → no divert; reject → divert. The decision is latched for
exactly one part; it must not alias the next part.

**C3 — Diverter timing.** `YV_DIVERT` commands extend; acknowledge via `SR_DR` must
arrive within 400 ms or a `DIVERT_TIMEOUT` alarm. On divert complete the cylinder
retracts; position is proven by `SR_RR` before the next part may be processed.

**C4 — Jam/miss interlock.** If a part detected at entry never reaches the sort
position within a travel-time window, or a divert fires but `SR_DR` never confirms,
the belt stops and `JAM_ACTIVE` latches. Recovery is operator reset at the HMI after
clearing the physical gap.

**C5 — Counters.** Total counts every detected part; good/reject count per decision.
A missed pulse anywhere means counter drift — the counter must count actual parts,
not commanded decisions."""
            },
            {
                "key": "plc_program",
                "title": "PLC Program",
                "content": """The program is a small 3-state machine + I/O layer (ST shown, ladder-legal):

```
STATE: IDLE -> (Start+healthy) -> RUN
RUN:   per-part sequence (see below)
RUN:   any trip -> TRIP -> (reset) -> IDLE

per_part():
  wait PL_BELT_IN edge
  travel_timer = 4s   (belt speed * distance to sort pos)
  wait PL_SORT_POS edge within travel_timer  else JAM_ACTIVE
  decision = QH_GOOD    // sampled at sort-pos edge
  if reject:
     YV_DIVERT := true
     wait SR_DR within 400ms else DIVERT_TIMEOUT
     YV_DIVERT := false
     wait SR_RR within 400ms else DIVERT_TIMEOUT
  CNT_TOTAL++; (CNT_REJ or CNT_GOOD)++
```

Scan discipline:

- The state machine has no hidden timers longer than one part cycle; travel and
  diverter times are explicit function-block timers (TON), all reset on trip.
- Interlock header runs first: `SORT_ACTIVE AND ESTOP_OK AND OL_CV_OK AND
  PS_AIR AND X_PACKER`.
- Outputs are written once per scan at the end; nobody forces `YV_DIVERT` from HMI
  while in RUN (manual allowed only in TRIP, guarded by active maintenance mode).
- Counters are UDINT; the reset is a HMI command gated by `not RUN`.""",
            },
            {
                "key": "hmi",
                "title": "HMI",
                "content": """Cell overview screen (mirrors the layout drawing):

- Belt icon + part dot that travels with the part: the operator sees flow, not tags.
- Live reads: `PL_BELT_IN`, `PL_SORT_POS`, `QH_GOOD`, diverter symbol extend/retract.
- Digital readout **counters**: TOTAL / GOOD / REJECT plus a **9-bar rejection
  history** (last 10 parts) so a burst of rejects is visible as a block, not a number.
- Buttons: Start, Stop, Reset (only when tripped), and an Acknowledge for alarms.
- Banners: `RUN`, `TRIP — JAM`, `TRIP — DIVERT TIMEOUT`, `E-STOP`, `AIR LOW`,
  `PACKER BUSY` (+ which interlock holds, like the motor project).

Rules:

- The operator never touches a counter value from HMI.
- Reset is greyed out until the cause clears physically.
- The reject history number-bar is the single most useful diagnostic on the page —
  a sudden 8-reject bar says "gate/classifier changed", a 1-reject bar says
  "one bad part". Different repairs.""",
            },
            {
                "key": "scada",
                "title": "SCADA / Upper-Level System",
                "content": """Line SCADA subscribes to the sorter cell:

- `CNT_TOTAL/GOOD/REJ` — pushed every 10 s to the line OEE dashboard; resets are an
  audited event.
- Reject ratio trend (rejects/hour) over the shift — early alarm for gate drift.
- `JAM_ACTIVE`, `DIVERT_TIMEOUT`, `E-STOP` — top-of-page line alarms to the
  production supervisor.
- `SORT_ACTIVE` — merged into the line's interlocked sequence so the cell cannot run
  against a stopped packer.

Integration contract:

- Counters are OWNED by the PLC. SCADA reads, never writes.
- A count-event (total, reject) is timestamped in the PLC audit ring for traceability
  (batch/lot trace: which count belongs to which conveyor load).
- If SCADA loses comms, the PLC keeps counting and the counters carry on; SCADA shows
  a freshness badge on reconnection and never guesses values.

Runs the same VLAN/profinet pattern already used in the motor project; the cell is a
line asset, nothing exotic.""",
            },
            {
                "key": "alarms",
                "title": "Alarms",
                "content": """| Tag | Priority | Message | Consequence | Recovery |
| --- | --- | --- | --- | --- |
| `CELL_ESTOP_ACTIVE` | High | E-stop — belt & diverter dropped | Line stopped | Reset e-stop, acknowledge |
| `JAM_ACTIVE` | High | Part not sensed at sort pos | Belt stopped, downstream starved/packed | Clear belt, reset |
| `DIVERT_TIMEOUT` | Medium | Diverter failed to extend/retract | Missed reject, reject-stew risk | Check air, valve, limits |
| `REJ_RATE_HIGH` | Medium | > 20 rejects in rolling 10 min | Gate drift or feed quality | Check gate, feed |
| `AIR_PRESSURE_LOW` | Low | Supply < 6 bar | Diverter stalls | Restore air |

Rules:

- JAM and DIVERT are latched with belt stop; REJ_RATE_HIGH is monitoring-only (belt
  keeps running — stopping the line on a quality metric would hurt more).
- All counters-reset events are audited (who, when, why).
- Alarm burden: max 1 active alarm per cause; the cell never raises 6 alarms for one
  dropped wire (the interlock header collapses to one banner)."""
            },
            {
                "key": "interlocks",
                "title": "Interlocks",
                "content": """The cell's interlock matrix:

| Interlock | Condition | Action | Reset |
| --- | --- | --- | --- |
| I1 E-stop | Chain open | Belt + diverter drop instantly | Physical reset |
| I2 Air | `PS_AIR` low | Panel bra on diverter; belt derate warn | Auto on restore |
| I3 Conveyor OL | `OL_CV` trip | Belt stop, alarm | Manual |
| I4 Jam/miss | Travel timeout | Stop belt, latch | Oper reset w/ cause |
| I5 Diverter ack | Extend/retract timeout | Stop cell at divert, alarm | Oper reset |
| I6 Packer ready | `X_PACKER` false | Belt runs but diverter blocked for pass-through | Auto on ready |
| I7 Guard doors | Door-switch | Belt stopped, block start | Auto on closed |

Discipline notes:

- `I6` is the only interlock that degrades function (diverter disabled → pass-through
  with a running belt) — a deliberate design, documented in the matrix with its risk.
- Interlocks are listed top-down in priority; a top-row feed drops what is below.
- Every interlock has a reset path; jam/interlocks reset only when the physical
  cause clears AND the operator acknowledges — the two-step habit from motor project
  carries straight over."""
            },
            {
                "key": "networking",
                "title": "Networking",
                "content": """The cell joins the line network:

```
[Cell PLC] ---Profinet--- [cell HMI]
    |--Profinet-x2------> [line switch] ---> packer PLC ---> line SCADA
```

VLAN/segmentation as before (control vs MES), fixed IP schedule, PLC is time master.

Specific to a sorter:

- The diverter limits and the counters travel on the I/O network, NOT over a remote
  OPC hop — `SR_DR/S_RR` must be local to the PLC for the 400 ms ack window.
- Packer-ready (`X_PACKER`) is a hard-wired 24 V pair, not a network signal — the
  handshake that can kill the belt does not depend on software running on a router.
- Document the fibre/CU budget and spare pairs for `X_PACKER`?? — no, spare pairs are
  for SCADA readback.

If the sort position interrupts are routed via a remote I/O with a jittery switch,
the travel timer will lie. Keep motion-critical inputs local.""",
            },
            {
                "key": "testing",
                "title": "Testing / FAT",
                "content": """Cell FAT script (witness every step):

1. **I/O contention:** toggle each sensor; verify the correct tag and only that tag.
2. **Air chain:** run with `PS_AIR` low — belt is allowed to run warm, diverter is
   locked out. This is the only degraded mode by design.
3. **Part sequence, 10× good:** belt run, place 10 good parts; expect 10 counts of
   `CNT_GOOD`, 0 reject, diverter never extends.
4. **Part sequence, 10× reject:** block the gate; every part diverts, `CNT_REJ` 10,
   `SR_RR` proven each time.
5. **Mixed burst:** 20 parts alternating; counters end TOTAL=20, GOOD+REJ=20; reject
   history bar shows the right pattern.
6. **Jam drill:** lift a part off the belt mid-travel; JAM_ACTIVE latches, belt
   stops, reset requires cause-clear + operator ack.
7. **Diverter timeout:** block `SR_DR`; divert fires, ack never arrives, alarm at
   400 ms, cell trips at the divert step.
8. **E-stop mid-part:** pull e-stop while a part is at the sort point; belt and
   diverter drop; on restore the part's travel timer has expired → JAM (safe default:
   never resume mid-flight).
9. **Count integrity vs physical:** with a stopwatch and 25 parts, TOTAL counter
   matches a manual tally — zero drift allowed.
10. **Guards:** open the door mid-run; belt stops as per I7 and blocks restart."""
            },
            {
                "key": "fault_injection",
                "title": "Fault Injection",
                "content": """Four faults to hunt in this cell:

- **F1 — sorter never diverts**: a reject part rides straight through to the
  packer. The decision happens, the solenoid seems dead.
- **F2 — spurious rejects**: every few parts the gate reports reject with no bad
  part; the counter bar shows a stutter of rejects that cleaning doesn't fix.
- **F3 — false jam**: cell stops on JAM though the belt is clear; the travel timer
  fires but no part was missing.
- **F4 — counter drift**: TOTAL ends one or two short of the physical tally after
  a full batch; evidence points at the pulse path not the logic.

For each: state the observed mismatch, run the check sequence, and name the root
cause plus the ONE fix that addresses it (and one tempting fix that would not)."""
            },
            {
                "key": "troubleshooting",
                "title": "Troubleshooting",
                "content": """Sorter gremlins, disciplined:

1. **Decision vs actuation.** A reject that does not divert: confirm `YV_DIVERT`
   in the DO map, then meter the valve coil at the card, then check air to the valve
   and the cylinder. The card output can be true and the cylinder dead — the half-
   split stops overlap at each stage.
2. **Signal integrity first.** Any "random" reject burst or false jam is a sensor
   SIGNAL problem until proven otherwise: check the photocell retro/through-beam
   alignment, lens cleanliness, screen/earthing, and the 24 V ripple from the drive
   near the cable run — in that order.
3. **Timing over logic.** If the jam fires on time but the belt is clear, the
   travel-time window is being run against a half-broken signal (e.g., a double-pulse
   from a dirty encoder-less photocell edge). Count edges first.
4. **Count the pulses.** Counter drift ALWAYS traces to a missed or doubled sensor
   edge, never to the UDINT math — prove the edge path with a scope/logic analyser.
5. **Live-work discipline.** The diverter cylinder can sweep 40 kg; lock out the
   air and the belt before reaching in. Guards do not count as the technician's
   hands.""",
            },
            {
                "key": "commissioning",
                "title": "Commissioning",
                "content": """On-site, in order:

1. **Isolation.** Belt lockout, air dump, e-stop drive test first (before anyone runs).
2. **Alignment.** Set PL_BELT_IN and PL_SORT_POS fields: sight the retro reflector,
   set through-beam edges with a test part at both extreme sizes in the product
   envelope; record the lens-clean gap check.
3. **Gate threshold.** Walk the capacitive gate across the accepted/reject part
   range; set the threshold at the midpoint of the gap, not at one end; log the value.
4. **Pneumatics.** Purge the line, set pressure to 6.5 bar, tune the diverter speed
   by the cylinder flow restrictors so extend/retract meet the 400 ms budget with
   margin.
5. **Sequence dry run.** Belt empty: run the state machine in manual, confirm ALL
   interlocks trip and recover — the matrix tests with the diverter disconnected.
6. **Live 50-part run.** Feed 50 parts, 20 known bad: counters match the manual
   tally exactly, reject history bar clean, jam drill re-run once.
7. **Handover** — as-built layout, I/O list, gate threshold, timing budget, FAT
   evidence, and the interlock matrix with reset columns signed off."""
            },
            {
                "key": "final_documentation",
                "title": "Final Documentation",
                "content": """Cell handover packet:

- Layout drawing with sensor fields and the reject bin geometry.
- I/O list with terminal numbers and polarity notes.
- Tag list with counters, alarms and interlocks.
- State machine description + program print with rung/FB numbers.
- Timing budget: travel timer, diverter extend/retract, gate settle.
- HMI screen description and the operating manual (start, stop, reset, what-jam-means).
- FAT results, commissioning record, and the troubleshooting fault log.

The packet must let a new technician restart the cell, read the counter log sensibly,
and safely isolate the air/belt in under ten minutes. That is the bar.""",
            },
        ],
        "faults": [
            {
                "slug": "sorter-never-diverts",
                "title": "Sorter never diverts — rejects ride through",
                "symptom": "Every part carries on to the packer regardless of class; the PLC shows divert decisions but the cylinder never moves.",
                "description": "The decision path works; the actuation path is dead.",
                "injected_fault": "Air supply to the sorter valve is turned off by a partially-open ball valve (maintenance left it closed).",
                "operation_notes": "Classic decision-vs-actuation keep: YV_DIVERT true, valve coil OK, no air to the cylinder.",
                "expected_checks": [
                    "check_divert_command",
                    "check_solenoid_coil_voltage",
                    "check_reject_air_supply",
                    "check_cylinder_limits",
                    "check_valve_position",
                    "check_plc_output_state",
                ],
                "correct_diagnosis": "Sorter air supply isolated (ball valve closed), starving the diverter cylinder despite a live command.",
                "correct_diagnosis_keys": ["air supply", "ball valve", "no air", "diverter air"],
                "common_misdiagnoses": ["solenoid valve fault", "decision logic", "cylinder"],
            },
            {
                "slug": "spurious-rejects",
                "title": "Spurious rejects — random gate hits",
                "symptom": "Every few parts the gate reports reject with no bad part present; cleaning the gate changes nothing; history bar shows a stutter.",
                "description": "The classification signal is being corrupted.",
                "injected_fault": "Capacitive gate cable runs parallel to the motor power cable in the trunking; switching noise triggers random hits.",
                "operation_notes": "Signal-integrity-first: the 'random rejects' that cleaning doesn't fix are electrical or routing noise until proven otherwise.",
                "expected_checks": [
                    "check_gate_threshold",
                    "check_gate_cable_route",
                    "check_signal_screening",
                    "check_noise_source_nearby",
                    "check_24v_ripple",
                    "check_gate_earthing",
                ],
                "correct_diagnosis": "Switching noise coupling into the capacitive gate cable from the motor power pair in shared trunking.",
                "correct_diagnosis_keys": ["noise", "cable route", "screening", "power cable"],
                "common_misdiagnoses": ["gate threshold", "gate sensor fault", "feed quality"],
            },
            {
                "slug": "false-jam",
                "title": "False jam — belt stops with belt clear",
                "symptom": "Cell trips JAM_ACTIVE though the belt is visibly empty; the travel timer fires with no part in transit.",
                "description": "The entry photocell is producing a phantom edge.",
                "injected_fault": "The belt-entry retro-reflective photocell has a half-clean lens reflecting intermittently, producing false part edges.",
                "operation_notes": "A false jam is a dead giveaway the detection layer aliases edges — checking alignment and the lens comes before the logic.",
                "expected_checks": [
                    "check_entry_photocell_beam",
                    "check_lens_condition",
                    "check_sensor_reflector",
                    "check_sensor_polarity",
                    "check_travel_timer_config",
                    "check_plc_input_state",
                ],
                "correct_diagnosis": "Belt-entry photocell lens partially fogged, aliasing phantom part edges that trip the travel timer.",
                "correct_diagnosis_keys": ["photocell", "lens", "phantom edge", "reflector dirt"],
                "common_misdiagnoses": ["timer config", "part spacing", "downstream jam"],
            },
            {
                "slug": "counter-drift",
                "title": "Counter drift — TOTAL short of physical tally",
                "symptom": "After a full batch, TOTAL is two or three parts short of the manual tally; good/reject split unchanged.",
                "description": "Part edges are occasionally lost at the counting point.",
                "injected_fault": "Input debounce on the sort-position input swallows rapid double parts at maximum infeed pitch.",
                "operation_notes": "Counter drift traces to the edge path: a debounce that merges two parts into one edge explains a short TOTAL with unchanged split.",
                "expected_checks": [
                    "check_entry_photocell_beam",
                    "check_sort_pos_beam",
                    "check_input_debounce",
                    "check_count_register",
                    "check_sensor_alignment_at_pitch",
                    "compare_tally_to_physical",
                ],
                "correct_diagnosis": "Input debounce time merging rapid parts at max pitch, dropping counts from the total.",
                "correct_diagnosis_keys": ["debounce", "input filter", "missed edge", "pitch"],
                "common_misdiagnoses": ["counter reset", "math error", "scada overwrite"],
            },
        ],
    },
    {
        "slug": "chlorine-dosing-skid",
        "title": "Chlorine Dosing Skid — Duty, Demand, and Safety",
        "industry": "water",
        "difficulty": "intermediate",
        "hours": 28,
        "description": (
            "A packaged chemical dosing skid, end to end: duplex diaphragm pumps with "
            "duty/standby alternation, residual analyser feedback, flow-paced demand with "
            "trim control, drum-low and leak-detection safety, and Profinet integration "
            "into the plant that owns it. The natural course between the foundations and the "
            "500 m³/h treatment plant."
        ),
        "sections": [
            {
                "key": "project_brief",
                "title": "Project Brief",
                "content": """A municipie has a packaged chlorine dosing skid fed from a bulk drum. The skid must
deliver chlorine to the clearwell at a demand rate paced by plant flow, tripped by a
residual analyser, and protected by drum-empty and leak-detection interlocks. Two
diaphragm pumps run duty, the other standby, auto-alternated on run-hours. The skid
is its own PLC with a local HMI and reports to the plant SCADA over Profinet.

Deliverables: skid P&ID, I/O and tag list, the dosing control narrative, program with
duty/standby + auto/manual modes, HMI screens, alarm and interlock matrices with a
leak/swab philosophy, FAT script, and commissioning record.

The Fault Injection phase hides the faults a real skid hands you: a pump that never
alternates, a drum not as empty as the low alarm claims, and a leak detector that
cries wolf.""",
            },
            {
                "key": "process_description",
                "title": "Process Description",
                "content": """The skid doses sodium hypochlorite into the filtered clearwell inlet.

Normal operation:

1. Plant flow (FT-010 on the inlet) drives a DOSE RATE demand: the higher the flow,
   the more chlorine the pumps should deliver.
2. Two diaphragm metering pumps (A = duty, B = standby). The duty pump strokes at a
   rate set by the controller; the standby is held but auto-starts if the duty trips.
3. Residual analyser AT-011 measures the finished-water residual (target ~0.5 mg/L).
4. A trim PID corrects the stroke set-point around the flow-paced demand so residual
   stays on target as chlorine demand varies.
5. Boundaries: drum low level (alarm + keep dosing), drum empty (STOP pumps), leak
   pan detector (STOP pumps + alarm), pump fault (changeover).
6. Alternation: after N= run hours the standby becomes duty (auto), logged.

The skid is the boomiest place a technician ever works: chlorines, moving pumps and a
live analyser. The safety interlocks in this project are not decoration.""",
            },
            {
                "key": "p_and_id",
                "title": "P&ID",
                "content": """Skid P&ID (simplified but complete for this scope):

```
                      DRUM (bulk hypochlorite)
   LT-020 (level)         |
   10-90%            ======V SPD-01 suction valve
        |             |            ^
   [P-A] <--> [P-B]   | diaphragm pumps (duty/standby)
        |       |     |  SPD-02 / SPD-03 stroke control
        M       M     |
        +-------+-----> FX-030 ?? no — to disch header
                     discharge non-return

     >---FT-010 (inlet flow) ---> [clearwell]
     analyser AT-011 (residual) on finished water

     LD-040 leak pan under drum+valves (conductivity)
     relief/cap: a vent and a drip tray to the leak pan
```

Controls on the drawing: LT-020 (drum level, 4-20 mA ultrasonic), FT-010 (magflow),
AT-011 (residual), drive stroke SPD-xx on each pump, K-con rotation feedback contacts
on both pumps, leak detector LD-040 (conductivity sensor in the pan), suction valve,
and a check valve on the discharge.

Safety valves and relief paths are drawn, not assumed — a dosing skid without a drawn
relief path is a sketch.""",
            },
            {
                "key": "io_list",
                "title": "I/O List",
                "content": """Analog:

| Ref | Signal | Device | Range | Scale |
| --- | --- | --- | --- | --- |
| AI0 | Drum level | LT-020 | 4-20 mA | 10-90 % |
| AI1 | Inlet flow | FT-010 | 4-20 mA | 0-300 m³/h |
| AI2 | Residual | AT-011 | 4-20 mA | 0-2.0 mg/L |
| AO0 | Pump A stroke | SPD-01 | 4-20 mA | 0-100 % |
| AO1 | Pump B stroke | SPD-02 | 4-20 mA | 0-100 % |

Digital:

| Ref | Description | Device |
| --- | --- | --- |
| DI0 | Pump A run feedback (K-con) | Contactor aux |
| DI1 | Pump B run feedback (K-con) | Contactor aux |
| DI2 | Pump A fault (OL) NC | OL |
| DI3 | Pump B fault (OL) NC | OL |
| DI4 | Drum low switch | LS-021 |
| DI5 | Leak detector alarm | LD-040 |
| DI6 | E-stop chain mirror NC | Safety |
DO0 / DO1: pump A/B contactors; DO2 suction valve open; DO3/4 auto-manual hint lamps.

Note: AO stroke 4-20 is SCCR-safe wiring; the stroke drives the pump's internal
frequency reference — treat like the analog scaling project.""",
            },
            {
                "key": "tag_list",
                "title": "Tag List",
                "content": """| Tag | Type | Source | Meaning |
| --- | --- | --- | --- |
| `DRUM_LEVEL` | AI REAL | LT-020 | Drum fill % |
| `FLOW_INLET` | AI REAL | FT-010 | Plant inlet flow |
| `RESIDUAL` | AI REAL | AT-011 | Finished-water residual mg/L |
| `DOSE_DEMAND` | REAL int | calc | Flow-paced demand setpoint |
| `STROKE_SP` | REAL int | PID | Trim-corrected stroke command |
| `P_A_RUN`, `P_B_RUN` | BOOL DI | K-con | Pump running |
| `P_A_FAULT`, `P_B_FAULT` | BOOL DI NC | OL | Pump fault |
| `LEAK_DETECT` | BOOL DI | LD-040 | Leak alarm |
| `DRUM_LOW` | BOOL DI | LS-021 | Drum low |
| `DUTY_NOW` | BOOL int | Alternator | A or B is duty |
| `MODE_AUTO` | BOOL int | HMI | Auto vs manual |
| `SKID_ESTOP_OK` | BOOL DI NC | Safety | Chain |

Every tag here is used exactly once in the program — the tag list and the program
must agree line-for-line (a reviewer audits that).""",
            },
            {
                "key": "control_philosophy",
                "title": "Control Philosophy",
                "content": """**C1 — Demand pacing.** `DOSE_DEMAND` is proportional to inlet flow (ppm × flow):
`DOSE_DEMAND = F * target* K`. The stroke set-point starts here.

**C2 — Trim.** A PID on residual error adjusts `STROKE_SP` around `DOSE_DEMAND`.
The PID is clamped so trim can never zero the dose — a residual dip must not stop
the pump (bacteria risk).

**C3 — Duty/standby.** One pump runs; the other is held at a minimal priming stroke
rate. On duty fault or after N run-hours (alternation) the other takes over with
de-bounce. The changeover is an alarm + logged event, not silent.

**C4 — Mode.** AUTO runs the algorithm; MANUAL lets an operator force stroke and
pump selection for maintenance — MANUAL is a retained, auditable mode (never a
hidden default).

**C5 — Chemically safe defaults.** DRUM EMPTY stops both pumps (no air-drawing
stroke). LEAK stops both pumps + closes the suction valve. E-stop drops pumps and
valve instantly. In every trip, `STROKE_SP` goes to zero; the analyser does NOT
re-authorise a restart — only the operator can."""
            },
            {
                "key": "plc_program",
                "title": "PLC Program",
                "content": """ST/PID discipline, one block per duty:

**FB_pace:** `DOSE_DEMAND = FLOW_INLET * K_PACE` with rate-of-change clamp (no stroke
jumps on flow spikes).

**FB_trim (PID):** PV = RESIDUAL, SP = 0.5 mg/L, output clamped
`[DOSE_DEMAND - 0.1* ] .. [DOSE_DEMAND + 0.2*]` so trim tightens, never kills.

**FB_alternate:** on run-hours counter of the duty pump; at N hours swap
`DUTY_NOW`; requires standby healthy. Blocked in MANUAL mode.

**Interlock header (highest in scan):**
```
HLT = SKID_ESTOP_OK AND NOT LEAK_DETECT AND NOT DRUM_EMPTY
      AND P_A_FAULT/... (handled by alternator)
RUN_ANY = HLT AND MODE_AUTO / (manual with operator confirm)
```

**Outputs:** `STROKE_SP` to the AO of the running pump only; the other pump's stroke
set to priming minimum. Both contactors follow `DUTY_NOW` + run logic.

**Watchdog:** any 2 s without a K-con feedback while commanded = pump trip →
changeover. Counters, run-hours and a stroked-word audit ring all live in the PLC.""",
            },
            {
                "key": "hmi",
                "title": "HMI",
                "content": """Skid HMI, three layers:

**Overview:** mimics the P&ID — drum level bar, both pumps with running lamp +
fault lamp, stroke bars, residual readout (mg/L big), flow, suction valve symbol, and
a leak-pan splash icon that turns red.

**Controls:** AUTO/MANUAL toggle (auditable, requires acknowledge), duty selection
(auto/forced A/forced B), pump start for maintenance, drum-empty reset, alarm
acknowledge, and an alternation run-hours readout.

**Faceplates:** LT-020, FT-010, AT-011 and both stroke AOs get the standard loop
faceplate from the pressure-loop project (mA, %, eng units, trip state) — consistency
across the platform is a feature.

HMI rules:

- MANUAL mode shows a black "MANUAL — operator mode" banner, always.
- Drum-empty and leak CANNOT be acknowledged away; they latch until the physical
  cause clears the input.
- Residual value is fault-lit (LOOP FAULT pattern of the loop project) when the
  analyser loop is dead — a 0.000 mg/L residual displayed as a real number would be
  dangerous."""
            },
            {
                "key": "scada",
                "title": "SCADA / Upper-Level System",
                "content": """The skid talks Profinet/OPC UA to the plant SCADA:

- `FLOW_INLET`, `DOSE_DEMAND`, `STROKE_SP`, `RESIDUAL` — 5 s trend subscription.
- `DUTY_NOW`, `MODE_AUTO`, pump health — asset tab on the plant overview.
- Drums: `DRUM_LEVEL`, `DRUM_LOW/EMPTY` — fed to the chemical ordering system
  (a drum-low triggers a reorder workflow upstream — the crown jewel of this
  integration).
- Alarms mirror the PLC: Low residual, No pump running, Leak, Drum low.
- Batch/audit: every changeover, manual-mode entry, and drum-empty trip carries a
  timestamp and operator id pushed to the plant historian.

Fail-safe contract: SCADA writes NOTHING to this skid except the acknowledge/heartbeat;
stroke and duty commands come only from the local HMI/PLC. The plant historian keeps
skid run-hours in the same clock as the line so maintenance events align.""",
            },
            {
                "key": "alarms",
                "title": "Alarms",
                "content": """| Tag | Priority | Message | Consequence | Recovery |
| --- | --- | --- | --- | --- |
| `SKID_ESTOP` | High | E-stop active | Pumps + suction valve drop | Reset + operator restart |
| `LEAK_DETECTED` | High | Leak in drum/valve pan | Pumps stop, suction closes | Clean pan, verify no chemical, reset |
| `DRUM_EMPTY` | High | Drum empty — pumps stopped | No dosing → residual falls | Change drum, reset, reprime |
| `DRUM_LOW` | Medium | Drum low — reorder | Dosing continues, ordering overdue | Order + monitor |
| `PUMP_TRIP` | Medium | Pump failed (K-con/OL) | Changeover to standby | Repair pump, log |
| `RESIDUAL_LOW` | Medium | Residual < 0.3 mg/L | Disinfection margin low | Check demand, pumps, analyser |

Rules:

- `LEAK_DETECTED` is the highest non-e-stop alarm and CANNOT be acknowledged off —
  it stays until the physical leak sensor clears (the pan dry).
- `DRUM_LOW` is the only alarm that keeps the plant flowing; everything else
  degrades toward stop.
- Alarm-to-HMI < 1 s; a drum-empty trip writes an audit record with the operator who
  acknowledges — the next shift reads why."""
            },
            {
                "key": "interlocks",
                "title": "Interlocks",
                "content": """| Interlock | Condition | Action | Reset |
| --- | --- | --- | --- | --- |
| I1 E-stop | Chain open | Drop pumps + suction valve | Physical reset |
| I2 Leak | LD-040 wet | Drop pumps, close suction, latch alarm | Sensor clear + operator |
| I3 Drum empty | LS-021 true | Block both pumps (air-draw protection) | Drum swap + reset |
| I4 Pump fault | OL / no K-con 2 s | Changeover to standby (if healthy) | Auto on standby |
| I5 Analyser dead | `_OK` false | Trim frozen at last value; alarm (never auto-stop) | Restore loop |
| I6 Mode mismatch | MANUAL retained | Banner + audit, no silent AUTO | Operator confirms |
| I7 Low residual | < 0.3 mg/L | Warning + demand bump; NO automatic stop | Monitored |

Design note on I5 and I7: the residual loop is the only sensor that could stop the
pumps, and it is deliberately NOT allowed to stop them — a failed analyser must never
reduce disinfection. That is a safety PHILOSOPHY, and it is documented here because
someone will one day propose wiring I5 to stop the skid. The interlock matrix is the
place where that argument is answered in advance."""
            },
            {
                "key": "networking",
                "title": "Networking",
                "content": """Skid networking:

```
[Skid PLC] --Profinet---- [skid HMI]
    |--Profinet------- plant switch --------- plant SCADA
    |                        |
  Profinet remote I/O? NO — stroke AOs and K-con are LOCAL
```

- Analog stroke AOs must be on-card, local to the skid PLC — remote I/O latency
  wobbles the stroke reference and the residual trim will fight itself.
- Plant backbone: ring or dual-CU with per-port rate limiting; the skid is one
  device on the ring, not the ring hub.
- OPC UA gateway for SCADA with a dead-man heartbeat tag the SCADA supervises
  (SCADA alarms if the skid stops publishing — mirrored-skid reporting).
- Security: skid PLC on the control VLAN, no direct internet, PLC = time master;
  remote maintenance via the locked-down jump host used plant-wide.
- Document the IP schedule and VLAN map in one drawing inside this section; the
  maintenance folder has a copy."""
            },
            {
                "key": "testing",
                "title": "Testing / FAT",
                "content": """Skid FAT script:

1. **Continuity/loop checks:** every AI/AO injected with the loop-test procedure from
   the pressure-loop project (now at 8 mA / 12 mA / 16 mA on LT-020, FT-010, AT-011,
   both stroke AO). All reads agree within ±0.1 %.
2. **Analogue mode:** MANUAL — drive stroke, verify pump A and B respond, check stroke
   follows 0-100 % linearly.
3. **Demand pacing:** inject FT-010 at 100/200/300 m³/h with a healthy analyser;
   `DOSE_DEMAND` tracks and `STROKE_SP` rises to clamp — no stroke gaps.
4. **Trim:** ride residual to 0.5 mg/L with a sink model; verify the trim moves
   stroke around the pace value, clamped at the designed floor.
5. **Alternation:** force run-hours expiry of A → B takes duty with de-bounce; log
   event; repeat B→A.
6. **Trip drills:** OL trip on duty (changeover within 2 s), K-con blocked
   (changeover), drum-empty (both pumps stop, no stroke), leak (pumps stop +
   valve closes + latch), e-stop (instant drop).
7. **Analyser-dead test:** open AT-011 loop → `_OK` false → trim frozen, alarm, NO
   stop (the philosophy check).
8. **Restart discipline:** after every high priority trip, pump restart requires
   operator sequence — no auto-restart after drum-empty, leak, or e-stop.
9. **Both pumps dead:** with A tripped and B blocked, skid reports "NO PUMP" and
   residual falls — alarms, never false-health.
10. **Audit check:** every trip/changeover/manual-mode entry appears in the PLC
    audit ring with clock, operator, and value."""
            },
            {
                "key": "fault_injection",
                "title": "Fault Injection",
                "content": """Three scenarios, three different failure classes:

- **F1 — the duty pump never alternates.** Run-hours should swap A↔B but the same
  pump stays on all day. The machine is fine; the automation is not doing what the
  narrative promises.
- **F2 — drum 'low', actually empty.** The low alarm fires while the level gauge
  shows 45% and the liquid runs out mid-shift. The sensor says one thing, physics
  says another, and the reorder workflow was never triggered on the real emptiness.
- **F3 — the leak detector cries wolf.** A dry pan alarms LEAK several times a shift;
  the operator resets, it re-arms — real risk that a genuine leak is ignored the
  next time.

For each: run the check sequence, name the root cause with evidence, say what you
would and would NOT do to fix it, and describe the process change that would prevent
the recurrence."""
            },
            {
                "key": "troubleshooting",
                "title": "Troubleshooting",
                "content": """Skid discipline:

1. **Ask what the machine did, not what the tag says.** "Draft never alternated"
   is a logic-sequence question; "drum low with visible level" is an instrument/
   position question; "leak alarm with a dry pan" is an electrical question. Frame
   before touching.
2. **Alternation logic:** check the run-hours counter at both pumps, the health bit
   of the standby, and whether MANUAL is silently retained (a manual-mode latch is
   the #1 reason changeover never runs). The machine did what the mode told it.
3. **Level truth:** ultrasonic devices lie when the drum is foaming/condensing;
   cross-check LT-020 raw mA against the physical gauge and the LS-021 switch
   position. The "low at 45%" story is usually a transmitter or a mis-located switch,
   not a process lie.
4. **False leak:** conductivity detectors false-trip on washdown water or a foil
   crumb in the pan. Log the wet/trip pattern: dry-triggers are electrical/process
   invalidity; wet-triggers after washdown are cable/earthing. Never "acknowledge
   away" a leak red light without physically checking the pan — that is the job.
5. **Chemical safety first.** Any leak or uo-op probe happens with the suction
   valve closed, pumps isolated, and bleach PPE on. The fastest diagnosis is never
   worth a chlorine splash."""
            },
            {
                "key": "commissioning",
                "title": "Commissioning",
                "content": """Site sequence:

1. **Isolation/chemical read-in.** Chemical safety review, drum change procedure in
   place, PPE and eyewash verified, panic/leak drains confirmed clear.
2. **Instrument checks.** LT-020 ball-marker vs mA at 3 points; FT-010 magflow wet
   calibration; AT-011 = laboratory reference sample; stroke AOs injected at bench.
3. **Interlock dry tests.** With the suction valve closed and NO chemical in the
   line: run every interlock (I1-I7) to trip — verify actions and resets. Diverter...
   no, this is the skid — verify everything before any chemical flow.
4. **Priming run.** Acknowledge-in MANUAL, prime both pumps on water equivalent,
   verify K-con feedback at low stroke.
5. **Auto demand climb.** Step FT-010 through 100/200/300; watch DOSE_DEMAND,
   stroke, residual settling on trim; record the trim floor actually honoured.
6. **Changeover proof.** Force alternation both directions; confirm changeover event
   and audited log.
7. **Residual tuning.** 2-hour wet run holding AT-011 target with manual grab samples;
   record the controller's integral/gain identity in the handover.
8. **Living handover.** Operation manual, chemical handling sheet, interlock matrix,
   FAT + commissioning records, the drum-change procedure, and the audit export —
   plus a 24-hour witnessed unsupervised run."""
            },
            {
                "key": "final_documentation",
                "title": "Final Documentation",
                "content": """The skid handover packet, file-by-file:

- Skid P&ID (chemical paths drawn with relief/vent), layout, PPE zone map.
- I/O list with terminal numbers; tag list line-consistent with the program.
- Control narrative: demand pacing, trim, alternation, mode philosophy.
- Program print with FB/rung numbers and the interlock matrix with reset columns.
- Alarm register: consequence, recovery, suppression rules (I5/I7 philosophy).
- FAT results and commissioning record with tuned PID identity + residual data.
- Operation manual: dose, change drum, replace pump, respond to a leak — in under
  eight pages, with the chemical handling page first.

A reviewer can run this skid, change its drum, and know exactly why it stopped —
from the paper alone. That is a finished project."""
            },
        ],
        "faults": [
            {
                "slug": "skid-no-alternation",
                "title": "Duty pump never alternates",
                "symptom": "Run-hours expire every day but the same pump stays on duty; the alternator event never appears in the log.",
                "description": "The alternation function is not running as designed.",
                "injected_fault": "The skid is left in MANUAL mode from a maintenance session; the mode latch blocks the alternator and changeover.",
                "operation_notes": "Frame first: the machine followed its mode. The alternator only runs in AUTO; a retained MANUAL explains the absence of changeover perfectly.",
                "expected_checks": [
                    "check_mode_selector",
                    "check_alternation_run_hours",
                    "check_standby_health_bit",
                    "check_manual_latch",
                    "check_changeover_event_log",
                    "check_duty_selection_input",
                ],
                "correct_diagnosis": "Skid retained in MANUAL mode after maintenance, blocking the alternator and all changeovers.",
                "correct_diagnosis_keys": ["manual mode", "mode latch", "alternator blocked", "changeover"],
                "common_misdiagnoses": ["run-hours counter", "pump fault", "scada override"],
            },
            {
                "slug": "drum-alarm-disagrees",
                "title": "Drum 'low' while the gauge reads 45%",
                "symptom": "The low-level alarm fires daily and a reorder prompts despite the drum clearly half full; the drum then runs dry mid-shift.",
                "description": "The level measurement and the reality disagree — the automation believes one number, physics says another.",
                "injected_fault": "This is a wraparound pair: the LT-020 ultrasonic is aimed at the drum wall (false high), and the low SWITCH LS-021 is the source of truth — the gauge reads 45% because the transmitter lies while the switch correctly says empty.",
                "operation_notes": "A 'low while full' frame is an instrument placement/reading problem; the drum actually ran dry because the ordering workflow trusted the false-high LT.",
                "expected_checks": [
                    "check_low_level_switch",
                    "verify_transmitter_reading",
                    "check_transmitter_bracket",
                    "compare_physical_level_gauge",
                    "check_drum_empty_logic",
                    "check_reorder_workflow_trigger",
                ],
                "correct_diagnosis": "Level transmitter reporting a false high (aimed at the drum wall) while the low-level switch correctly reads empty — the ordering engine trusted the wrong source.",
                "correct_diagnosis_keys": ["transmitter false", "level switch", "ordering source", "ultrasonic"],
                "common_misdiagnoses": ["switch fault", "reorder bug", "dosing malfunction"],
            },
            {
                "slug": "leak-detect-wolf",
                "title": "Leak detector cries wolf",
                "symptom": "The dry leak pan alarms several times a shift; each reset re-arms, and no chemical is ever present.",
                "description": "The leak detector is electrically invalid — it fires without chemistry.",
                "injected_fault": "Washdown water reaches the conductivity probe via a swab tray drain pack, wetting only the probe while the pan stays dry.",
                "operation_notes": "Distinguish wet-when-true from dry-false: a probe reading conductivity from washdown residue is an invalid trip that trains the crew to ignore the real thing.",
                "expected_checks": [
                    "check_leak_pan_dry",
                    "check_probe_condition",
                    "check_probe_cable_route",
                    "check_washdown_path",
                    "check_probe_continuity",
                    "check_drain_tray_routing",
                ],
                "correct_diagnosis": "Conductivity probe wetted by washdown water through the swab tray drain, producing dry-pan leak alarms.",
                "correct_diagnosis_keys": ["washdown", "probe wet", "drain routing", "conductivity"],
                "common_misdiagnoses": ["leak sensor fault", "cable noise", "chemical leak"],
            },
        ],
    },
]


def install_curriculum(db: Session) -> list[str]:
    """Create any curriculum project whose slug is missing. Returns the slugs created.

    Idempotent and safe to call on every startup and from the Admin UI. Projects that
    already exist (e.g. the seeded water project) are left untouched.
    """
    created: list[str] = []
    existing = {slug for (slug,) in db.query(Project.slug).all()}
    for definition in CURRICULUM_PROJECTS:
        if definition["slug"] in existing:
            continue
        level = DIFFICULTY_LEVEL.get(definition["difficulty"], 2)
        project = Project(
            slug=definition["slug"],
            title=definition["title"],
            industry=definition["industry"],
            description=definition["description"],
            difficulty=definition["difficulty"],
            hours=definition["hours"],
            status="published",
        )
        db.add(project)
        db.flush()
        for i, section in enumerate(definition["sections"]):
            if section["key"] not in SECTION_KEYS:
                raise ValueError(f"{definition['slug']}: unexpected section key {section['key']!r}")
            db.add(ProjectSection(
                project_id=project.id,
                order=i,
                key=section["key"],
                title=section["title"],
                content=section["content"],
            ))
        for fault in definition["faults"]:
            db.add(FaultScenario(
                project_id=project.id,
                slug=fault["slug"],
                title=fault["title"],
                description=fault["description"],
                symptom=fault["symptom"],
                injected_fault=fault["injected_fault"],
                operation_notes=fault["operation_notes"],
                available_checks=palette(fault["expected_checks"]),
                expected_checks=fault["expected_checks"],
                correct_diagnosis=fault["correct_diagnosis"],
                correct_diagnosis_keys=fault["correct_diagnosis_keys"],
                common_misdiagnoses=fault["common_misdiagnoses"],
                difficulty=level,
                is_published=True,
            ))
        created.append(definition["slug"])
    db.commit()
    return created