"""Seeds the flagship project and demo user on first startup."""

from datetime import timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.fault import evaluator
from app.fault.palette import palette
from app.models import FaultScenario, Project, ProjectSection, User
from app.content import ProjectDefinition, ProjectGenerator

WATER_SECTIONS: list[dict] = [
    {
        "key": "project_brief",
        "title": "Project Brief",
        "content": """# Project Brief — 500 m³/h Municipal Water Treatment Plant

**Client:** Local Water Authority
**Capacity:** 500 m³/h potable water
**Process train:** Coagulation &rarr; Flocculation &rarr; Sedimentation &rarr; Filtration &rarr; Disinfection &rarr; Distribution

## What the client actually asked for
"A reliable plant that runs with minimal operator attention, meters everything that leaves the site,
and cannot overflow, under-dose chlorine, or blind the filters without the operators knowing."

## Key requirements
- Duty/standby pump pair with automatic alternation to even out wear.
- Automatic filter backwash on differential-pressure / runtime trigger.
- PID-controlled coagulant and chlorine dosing holding setpoint with and without flow compensation.
- Fail-safe behaviour on loss of instrument signal or PLC-to-SCADA communications.
- Every alarm documented with a define operator response (ISA-18.2 rationalisation).

## Constraints
- The site has intermittent power and connectivity; the control system must degrade safely.
- All commissioning evidence must be captured for the as-built handover.

## Deliverable
A complete 17-section engineering package that a second engineer could take and commission.
""",
    },
    {
        "key": "process_description",
        "title": "Process Description",
        "content": """# Process Description

Raw water enters the plant and passes through coagulation, where a dosing pump adds coagulant
proportional to influent flow. The water then moves to flocculation (slow mixing), sedimentation
(clarifiers), filtration (multi-media beds backwashed on demand), and disinfection (chlorine dosing
with residual trim). Treated water is stored in a clearwell and pumped to the distribution network.

Instrumentation anchors: LT-001 clearwell level (4-20 mA, 0-10 m), FT-001 influent flow (magflow),
FT-002 chlorine dosing flow, PT-001 filter differential pressure.

## Steady state
Three of the five filter beds run, two are standby. Duty pump alternates each 24 h. Coagulant
dosing tracks flow; chlorine is trim-controlled on residual analyser AT-001 feedback.

## Abnormal states
- Low clearwell level &rarr; distribution pumps trip on low-level interlock.
- High filter DP &rarr; backwash requested; if over-ridden by operator, turbidity alarm escalates.
- Chlorine residual low &rarr; dosing pump raises rate, residual-low alarm at 30 s of deviation.
""",
    },
    {
        "key": "p_and_id",
        "title": "P&ID",
        "content": """# P&ID (Piping & Instrumentation Diagram)

Symbology per ISA-5.1. The control system boundary is drawn around the automation scope:
analog instruments (LT, FT, PT, AT) on 4-20 mA, digital feedbacks on 24 V DC, motor command outputs.

## Loop tags on the control scope
| Tag | Service | Signal | Card | Range |
|-----|---------|--------|------|-------|
| LT-001 | Clearwell level | AI 4-20 mA | IW0.0 | 0-10 m |
| FT-001 | Influent flow | AI 4-20 mA | IW0.2 | 0-700 m³/h |
| FT-002 | Coagulant dosing flow | AI 4-20 mA | IW0.4 | 0-200 L/h |
| AT-001 | Chlorine residual | AI 4-20 mA | IW0.6 | 0-5 mg/L |
| PT-001 | Filter DP | AI 4-20 mA | IW0.8 | 0-500 mbar |
| M-001 RUN | Duty pump running | DI | I1.0 | - |
| M-002 RUN | Standby pump running | DI | I1.1 | - |
| DP-001 RUN | Dosing pump running | DI | I1.2 | - |
| ESD | Emergency stop | DI (safety) | I1.6 | - |
| M-001 CMD | Duty pump command | DO | Q0.0 | - |
| M-002 CMD | Standby pump command | DO | Q0.1 | - |
| DP-001 CMD | Dosing pump command | DO | Q0.2 | - |
| BV-001 OPEN | Backwash valve open cmd | DO | Q0.3 | - |
| BV-001 CLS | Backwash valve close cmd | DO | Q0.4 | - |

*[Note for the student: this section must be redrawn with the site P&ID; the I/O in the table is the
contract that the PLC program and the HMI both implement.]*
""",
    },
    {
        "key": "io_list",
        "title": "I/O List",
        "content": """# I/O List

Every I/O point on the control scope, its address, range, and engineering documentation hook.
This is the section a maintenance technician uses first when commissioning.

| Module | Address | Tag | Description | Type | Range | Loop |
|--------|---------|-----|-------------|------|-------|------|
| AI | IW0.0 | LT-001 | Clearwell level | 4-20 mA | 0-10 m | 4-20 mA loop |
| AI | IW0.2 | FT-001 | Influent flow | 4-20 mA | 0-700 m³/h | magflow |
| AI | IW0.4 | FT-002 | Coagulant dosing flow | 4-20 mA | 0-200 L/h | dosing skid |
| AI | IW0.6 | AT-001 | Chlorine residual | 4-20 mA | 0-5 mg/L | analyser |
| AI | IW0.8 | PT-001 | Filter differential pressure | 4-20 mA | 0-500 mbar | filter bed |
| DI | I1.0 | RUN-001 | Duty pump running feedback | 24 V | - | starter aux |
| DI | I1.1 | RUN-002 | Standby pump running feedback | 24 V | - | starter aux |
| DI | I1.2 | RUN-003 | Dosing pump running feedback | 24 V | - | starter aux |
| DI | I1.6 | ESD-01 | Emergency stop (de-energise to trip) | 24 V | - | safety ckt |
| DO | Q0.0 | CMD-001 | Duty pump command | relay | - | starter coil |
| DO | Q0.1 | CMD-002 | Standby pump command | relay | - | starter coil |
| DO | Q0.2 | CMD-003 | Dosing pump command | relay | - | dosing skid |
| DO | Q0.3 | CMD-BV-O | Backwash valve open | relay | - | valve actuator |
| DO | Q0.4 | CMD-BV-C | Backwash valve close | relay | - | valve actuator |
""",
    },
    {
        "key": "tag_list",
        "title": "Tag List",
        "content": """# Tag List

The single source of truth shared by the PLC program, HMI, and SCADA historians.

| Tag | Description | Data type | Units | Range | Alias |
|-----|-------------|-----------|-------|-------|-------|
| LT-001 | Clearwell level | REAL | m | 0-10 | LVL.CW |
| FT-001 | Influent flow | REAL | m³/h | 0-700 | FLW.IN |
| FT-002 | Coagulant dosing flow | REAL | L/h | 0-200 | FLW.DOSE |
| AT-001 | Chlorine residual | REAL | mg/L | 0-5 | RESID.CL |
| PT-001 | Filter DP | REAL | mbar | 0-500 | DP.FILT |
| RUN-001 | Duty pump running | BOOL | - | - | PB1.RUN |
| RUN-002 | Standby pump running | BOOL | - | - | PB2.RUN |
| RUN-003 | Dosing pump running | BOOL | - | - | DP.RUN |
| ESD-01 | Emergency stop | BOOL | - | - | SAFE.ESD |
| CMD-001 | Duty pump command | BOOL | - | - | PB1.CMD |
| CMD-002 | Standby pump command | BOOL | - | - | PB2.CMD |
| CMD-003 | Dosing pump command | BOOL | - | - | DP.CMD |
| ALC-101 | Alarm: low clearwell | BOOL | - | - | ALM.LVL.LO |

Convention: every tag that appears on the HMI, SCADA, or alarm list must appear here first.
""",
    },
    {
        "key": "control_philosophy",
        "title": "Control Philosophy",
        "content": """# Control Philosophy

## Modes
- **AUTO** — loop runs from setpoint under PLC control.
- **MAN** — operator command through the HMI, interlocks still enforced.
- **LOCAL** — device-level control on the skid/fault; PLC only monitors alarms.

## Dosing control (coagulant)
Forward-feed on FT-001: dosing setpoint = k × influent flow. The PID loop on FT-002 trims the
dosing pump speed around the feed-forward value. On flow signal loss, the dosing pump ramps to a
predefined failsafe rate for 60 s then trips with an alarm, rather than continuing unchecked.

## Clearwell level control
Split-range control on the two distribution pumps. Pump 1 duty at 2.5-8 m band; pump 2 stages in
above 8 m and stages out below 3 m (staged to avoid hunting). Low-level interlock at 1.0 m trips both.

## Filter backwash
Triggered on PT-001 &gt; 300 mbar or run-time &gt; 24 h. Sequence: isolate filter bed &rarr; drain to low
level &rarr; air scour 5 min &rarr; backwash 10 min &rarr; settle 2 min &rarr; filter-to-waste 5 min &rarr; return to service.
Each step has completion feedback; the sequence halts on ESD and laps a valve position if unmatched.

## Chlorine trim control
AT-001 residual at 0.6 mg/L setpoint, cascade feed-forward from distribution flow. Safety: duty
dosing pump over-runs at a rate limit; residual-low alarm escalates after 30 s without recovery.
""",
    },
    {
        "key": "plc_program",
        "title": "PLC Program",
        "content": """# PLC Program

Standard: IEC 61131-3, Siemens TIA Portal (S7-1200/1500 reference implementation).

## Program organisation
| OB/FC/FB | Purpose |
|----------|---------|
| OB1 | Main cycle: calls control and status blocks |
| OB35 | Cyclic interrupt (100 ms) for PID loops |
| FB_PlantAlarms | Local alarm detection and latching |
| FB_PumpControl | Duty/standby alternation + interlocks |
| FB_DosingPID | Coagulant feed-forward + PID trim |
| FB_Backwash | Filter backwash sequencer (step machine) |
| FC_CommFail | Communications-loss safe-state logic |

## Signal flow
Every output is gated by its interlock block: `CMD_PUMP = (AUTO_OR_MAN) AND NOT ESD AND permissive_ok`.
No output can be forced by an HMI write if the interlock block is not satisfied.

## Comment discipline
Safety-affecting blocks carry a header comment naming the interlock list entry they implement,
so a reviewer can trace code &harr; cause-and-effect matrix.
""",
    },
    {
        "key": "hmi",
        "title": "HMI",
        "content": """# HMI (Human-Machine Interface)

Screens (Siemens WinCC Unified):
1. **Plant Overview** — flow train graphic, key values, global alarm banner.
2. **Pumps** — duty/standby selection, statuses, command buttons, interlock reasons.
3. **Filter Beds** — DP values, run-times, backwash initiate/reset.
4. **Dosing** — setpoints, actuals, pump speeds, failsafe status.
5. **Alarms** — live alarm list with accept/reset and cause text.
6. **Trends** — LT-001, FT-001, AT-001, PT-001 live and historical.

Rules: target values are editable only in the relevant screen; interlock reset is a
permissioned action with an operator log entry. Every alarm shows its owner and prescribed action.
""",
    },
    {
        "key": "scada",
        "title": "SCADA",
        "content": """# SCADA (Supervisory Control & Data Acquisition)

WinCC SCADA above the PLC layer provides:
- Historical trending and archiving of all historian tags (mirror of the Tag List).
- Remote monitoring of the four key values and all alarms.
- Report generation for compliance (flow delivered, chlorine residual, backwash events).
- Redundant communication to the PLC; on comms loss the SCADA raises "comm fail" for every
  affected tag and the PLC holds a defined safe state.

Offline-first note: the SCADA layer is read-heavy. The critical control intelligence stays in the
PLC so the plant keeps operating through communications interruptions.
""",
    },
    {
        "key": "alarms",
        "title": "Alarms",
        "content": """# Alarms

Rationalisation per ISA-18.2: every alarm has a priority (Low/Medium/High/Urgent),
a message, an owner, and a defined operator action. Targets for bad actors (chattering alarms)
are reviewed each month.

| Tag | Priority | Setpoint | Message | Operator action |
|-----|----------|----------|---------|-----------------|
| ALM.ESD | Urgent | - | E-Stop activated | Confirm plant safe, isolate, verify zero energy, investigate |
| ALM.LVL.LO | High | &lt; 1.0 m | Clearwell low level | Check inlet flow, restore supply, log trip cause |
| ALM.LVL.HI | High | &gt; 9.5 m | Clearwell high level | Check pump operation, restore duty/standby |
| ALM.DP.HI | High | &gt; 300 mbar | Filter DP high | Initiate backwash or start backup bed |
| ALM.TURB.HI | High | &gt; 1.0 NTU | Turbidity high | Confirm dosing, check filter, escalate |
| ALM.CL.LO | High | &lt; 0.4 mg/L | Chlorine residual low | Raise dose, check dosing pump, check analyser |
| ALM.COMM | Medium | - | Comms lost to device | Check switch/segments, verify cable |

No alarm may be suppressed without a supervisor reason recorded.
""",
    },
    {
        "key": "interlocks",
        "title": "Interlocks",
        "content": """# Interlocks

Cause-and-effect matrix. Safety interlocks are hardwired de-energise-to-trip; control interlocks
run in the PLC. Every start command is gated by its permissive group.

| Interlock | Effect | Type | Reset |
|-----------|--------|------|-------|
| ESD-01 open | Trip ALL pumps &amp; dosing, hold valves | Safety (hardwired) | Manual at ESD, then supervision |
| Clearwell &lt; 1.0 m | Block/trip distribution pumps | Control (PLC) | Recover level &gt; 1.5 m |
| Pump running feedback absent &lt; 4 s after cmd | Alarm + retry once, then block | Control (PLC) | Manual reset |
| Filter DP &gt; 300 mbar | Request backwash; block dirty bed duty | Control (PLC) | After successful backwash |
| Dosing flow mismatch &gt; 10% 30 s | Ramp to failsafe, then trip + alarm | Control (PLC) | Manual |

The HMI "interlocks" page shows exactly which permissive is holding each command, so an operator
never has to guess why a pump will not start.
""",
    },
    {
        "key": "networking",
        "title": "Networking",
        "content": """# Networking

- **Control network:** PROFINET, S7 PLC + HMI + field drives on a dedicated VLAN (no DHCP, fixed IPs).
- **Plant IT network:** SCADA and reporting; firewalled from control VLAN.
- **IP scheme:** 10.20.x.x/24 control, 10.30.x.x/24 supervision.

Failure semantics: PROFINET IO device loss raises comm alarms and drives the associated tags to
failsafe. The SCADA link is monitored by a comm watchdog; no process control relies on the IT path.

*Offline-first design note: the same architecture philosophy is why the student platform works fully
disconnected — the client device binds content locally and only syncs progress when a link exists.*
""",
    },
    {
        "key": "testing",
        "title": "Testing",
        "content": """# Testing

## Factory Acceptance Test (FAT)
- Loop check every I/O point against the I/O list (signals, scaling, alarms).
- Interlock matrix test: every cause-and-effect entry proven with the cause injected.
- Backwash sequence step test with time and feedback faults injected.
- FAT record: numbered step / expected result / result / tester / date. Sign-off gate before shipping.

## Site Acceptance Test (SAT)
- Power-up and comms verification on site.
- Live loop checks on real instruments; calibration records attached.
- Functional test of all alarms and interlocks under running conditions.
- 72 h soak trial; plant performance data logged and compared to design.

No exemption is accepted without a written deviation signed by the client.
""",
    },
    {
        "key": "fault_injection",
        "title": "Fault Injection",
        "content": """# Fault Injection

Fault injection is the heart of the learning platform: a working simulation is running, and a fault
is quietly injected into it. The student observes only the symptom and must run the checks and
identify the root cause — exactly like facing a real plant fault for the first time.

This project ships 8 scenarios covering the water train: dosing, flow, level, interlocks, backwash,
comms, and safety. Each scenario lists the checks the student may run, the correct diagnosis, and
known misdiagnoses the grader watches for.

[The full scenario list lives in the Fault Lab module; each scenario links to the Troubleshooting
decision tree for the affected loop.]
""",
    },
    {
        "key": "troubleshooting",
        "title": "Troubleshooting",
        "content": """# Troubleshooting

Diagnostic sequence taught across all scenarios:

1. **Observe** — exact symptom, values, timestamps (what changed when?).
2. **Instrument power** — is the device powered and signal healthy (4 mA = open loop)?
3. **Signal** — is the measured value plausible for the process state?
4. **Command** — is the PLC commanding what it should?
5. **Actuation** — does the device respond to the command?
6. **Permissive** — which interlock is holding the command (check HMI interlock page)?
7. **Diagnose**, don't guess — the decision trees force the same order.

Rule for the student: log each check with a result before moving on — a logged sequence is
reusable evidence; an unlogged guess is not.
""",
    },
    {
        "key": "commissioning",
        "title": "Commissioning",
        "content": """# Commissioning

Sequenced by area, not by luck:
1. Pre-commisioning: megger checks, continuity, calibration of instruments.
2. Loop checks: every AI/DI reads correctly, every DO/DOA operates the correct device.
3. Software dry-run: steps, interlocks, alarm setpoints with the process isolated.
4. Wet run: water in the plant, each control mode proven (AUTO/MAN/LOCAL).
5. Backwash sequence proven with real valves and feedback.
6. 72 h soak, then handover data pack: as-builts, test certificates, calibration records, O&M manual.

Handover gate: the plant is handed over only when every SAT item is signed and the deviation
register is empty or client-approved.
""",
    },
    {
        "key": "final_documentation",
        "title": "Final Documentation",
        "content": """# Final Documentation

The completed handover pack — and the reason the student's project folder is a genuine work sample:
- As-built P&ID and control schematics
- Final I/O list and tag list (as-built, marked against FAT/SAT changes)
- Test certificates (FAT + SAT) with sign-off records
- Alarm rationalisation tables
- Cause-and-effect matrix (as-built)
- O&M manual including failsafe behaviour and contact structure
- Training record for operators

This folder is what you would hand to a client; it is also what you put on your CV.
""",
    },
]

WATER_FAULTS: list[dict] = [
    {
        "slug": "dosing-pump-overrun",
        "title": "Coagulant dosing pump over-running demand",
        "symptom": "Dosing pump DP-001 keeps running at full speed even though influent flow has stopped; dosing tank level dropping fast.",
        "description": "Simulation of a dosing skid running normally. A fault is injected."
        " The dosing pump continues at high rate with the influent flow at zero.",
        "injected_fault": "Coagulant dosing flowmeter FT-002 reads high, so PID trim keeps running the pump.",
        "operation_notes": "The loop scales FT-002 at 0-200 L/h; a failed high reading pretends demand.",
        "expected_checks": [
            "confirm_flow_reading",
            "verify_flow_signal",
            "check_pump_command",
            "check_dosing_valve",
            "verify_analyser_or_level_response",
            "check_controller_mode",
        ],
        "correct_diagnosis": "Dosing flowmeter FT-002 failed high, over-driving the dosing pump.",
        "correct_diagnosis_keys": ["flowmeter failed high", "ft-002", "dosing flowmeter"],
        "common_misdiagnoses": ["pump", "valve", "controller"],
    },
    {
        "slug": "filter-bed-blinding",
        "title": "Filter bed blinding with rising turbidity",
        "symptom": "Filter differential pressure slowly rising; finished-water turbidity climbing beyond 1.0 NTU.",
        "description": "The filter bed has passed its normal run and is blinding; backwash was never triggered.",
        "injected_fault": "Backwash trigger setpoint corrupted high so the sequence never initiates.",
        "operation_notes": "DP trend and turbidity correlate; this is a long-developing fault, not an instant one.",
        "expected_checks": [
            "read_dp_trend",
            "check_backwash_trigger",
            "check_backwash_runtime_count",
            "verify_filter_isolation_valves",
            "check_turbidity_reading",
            "review_backwash_log",
        ],
        "correct_diagnosis": "Backwash trigger setpoint set too high, so the blinding filter never initiated backwash.",
        "correct_diagnosis_keys": ["backwash trigger", "setpoint", "filter blinding"],
        "common_misdiagnoses": ["coagulant", "chlorine", "flowmeter"],
    },
    {
        "slug": "magflow-failed-low",
        "title": "Pump running on a failed magflow reading",
        "symptom": "Distribution pump 1 still running with no measured flow; clearwell level not falling as expected.",
        "description": "Magnetic flowmeter FT-001 reading collapsed to minimum while the pump continues.",
        "injected_fault": "Magflow excitation failure drives flow reading to ~0 with the pump unchanged.",
        "operation_notes": "A 4 mA or zeroed magflow with a running pump is a survey-then-diagnose case.",
        "expected_checks": [
            "confirm_flow_reading",
            "verify_flow_signal_loop",
            "check_pump_command",
            "check_pump_running_feedback",
            "compare_level_trend",
            "check_bypass_or_valve_position",
        ],
        "correct_diagnosis": "Magnetic flowmeter FT-001 failed (excitation), reading zero flow while the pump is delivering.",
        "correct_diagnosis_keys": ["flowmeter failed", "ft-001", "magflow"],
        "common_misdiagnoses": ["pump trip", "level transmitter", "command not sent"],
    },
    {
        "slug": "level-loop-open",
        "title": "Clearwell level stuck at 4 mA (open loop)",
        "symptom": "LT-001 reads exactly 0.00 m across several hours while the plant visibly has water; alarm behaviour is confusing.",
        "description": "The level transmitter loop is open, so the reading pins at 4.0 mA = 0 m.",
        "injected_fault": "Termination in the transmitter marshalling panel came loose; loop is open.",
        "operation_notes": "A flat reading pinned at scale minimum is classic open-loop behaviour on a live-zero loop.",
        "expected_checks": [
            "measure_loop_current",
            "check_transmitter_power",
            "verify_terminal_connection",
            "check_wiring_continuity",
            "compare_manual_level_reading",
            "check_plc_input_card_status",
        ],
        "correct_diagnosis": "Open circuit on the LT-001 4-20 mA loop pinning the reading at 4 mA (0 m).",
        "correct_diagnosis_keys": ["open loop", "4-20 open", "lt-001 open"],
        "common_misdiagnoses": ["level transmitter fault", "scale", "software"],
    },
    {
        "slug": "chlorine-airlock",
        "title": "Chlorine residual low from an air-locked dosing pump",
        "symptom": "Residual analyser AT-001 reads low; chlorine dosing pump command is at max but pump slips.",
        "description": "The chlorine dosing pump is running but delivering little; residual keeps dropping.",
        "injected_fault": "Air trapped in the dosing pump head reduces delivered volume per stroke.",
        "operation_notes": "A running pump with weak delivery points to priming/mechanical delivery, not electronics.",
        "expected_checks": [
            "check_pump_command",
            "check_pump_running",
            "verify_dosing_line_priming",
            "check_dosing_valve",
            "check_residual_analyser",
            "compare_dose_flow_actual",
        ],
        "correct_diagnosis": "Air lock in the chlorine dosing pump head reducing delivered chlorine.",
        "correct_diagnosis_keys": ["air lock", "dosing pump", "priming"],
        "common_misdiagnoses": ["analyser fault", "chlorine supply", "setpoint"],
    },
    {
        "slug": "pump-permissive-blocked",
        "title": "Duty pump will not start — permissive holding the command",
        "symptom": "Operator presses start on the HMI; Duty pump 1 never starts. No fault present; HMI shows the pump 'standby'.",
        "description": "A start command exists but the interlock page shows a permissive unsatisfied.",
        "injected_fault": "Clearwell low-level permissive switch stuck in a false (low) state.",
        "operation_notes": "The classic 'why won't it start' case — command present, output gated by an interlock.",
        "expected_checks": [
            "check_start_command",
            "check_interlock_page",
            "check_level_permissive",
            "check_esd_state",
            "check_plc_output_state",
            "check_starter_control_power",
        ],
        "correct_diagnosis": "Clearwell low-level permissive switch faulty, holding the pump start command blocked.",
        "correct_diagnosis_keys": ["permissive", "low level switch", "interlock"],
        "common_misdiagnoses": ["starter fault", "motor fault", "no command"],
    },
    {
        "slug": "backwash-valve-feedback",
        "title": "Backwash sequence stalls on valve feedback mismatch",
        "symptom": "Backwash sequence starts, then stalls at the filter isolation step with a 'valve position mismatch' alarm.",
        "description": "The backwash sequencer commanded a valve open but never saw the open-end feedback.",
        "injected_fault": "Valve feedback limit switch stuck, so the sequencer times out and halts.",
        "operation_notes": "A stalled sequence with a position-mismatch alarm points at feedback, not the valve drive.",
        "expected_checks": [
            "confirm_valve_open_command",
            "check_valve_feedback_switch",
            "check_actuator_power",
            "verify_sequence_step_timer",
            "check_valve_physically",
            "check_plc_input_feedback_card",
        ],
        "correct_diagnosis": "Backwash valve open-feedback limit switch stuck, halting the sequencer at isolation.",
        "correct_diagnosis_keys": ["limit switch", "feedback", "stuck switch"],
        "common_misdiagnoses": ["actuator", "sequencer", "timer"],
    },
    {
        "slug": "comms-loss-scada",
        "title": "Spurious alarms on PLC-to-SCADA communications loss",
        "symptom": "SCADA raises a storm of 'device offline' alarms for every tag and the trends freeze, though the plant runs normally.",
        "description": "The SCADA link to the PLC dropped; the PLC keeps controlling the plant fine.",
        "injected_fault": "Ethernet segment between PLC and SCADA switch failed.",
        "operation_notes": "Differentiate 'lost visibility' from 'lost control' before touching the plant.",
        "expected_checks": [
            "check_plc_scada_link",
            "check_network_switch",
            "check_plc_running_mode",
            "check_plant_values_local_hmi",
            "check_cable_segment",
            "verify_comms_watchdog",
        ],
        "correct_diagnosis": "Comms loss on the PLC-to-SCADA segment; the PLC is healthy and controlling normally.",
        "correct_diagnosis_keys": ["comms loss", "ethernet segment", "scada link"],
        "common_misdiagnoses": ["plc fault", "io fault", "power dip"],
    },
]


DISTRACTOR_CHECKS = [
    "check_motor_winding_resistance",
    "check_hmi_touchscreen",
    "restart_scada_server",
    "check_panel_cooling_fan",
    "replace_transmitter_blind",
    "check_unrelated_loop_signal",
    "check_earthing_continuity",
    "check_cabinet_lighting",
]


def _palette(expected: list[str], distractors: list[str] | None = None, extra: int = 3) -> list[str]:
    """Build the student-facing check palette: expected checks + plausible distractors."""
    return palette(expected, distractors=distractors, extra=extra)


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.query(Project).count() > 0:
            return
        _create_demo_user(db)
        _seed_water_project(db)
    finally:
        db.close()


def _create_demo_user(db: Session) -> None:
    from app.core.security import hash_password

    if db.query(User).filter(User.email == "demo@academy.local").first():
        return
    db.add(User(
        email="demo@academy.local",
        full_name="Demo Student",
        hashed_password=hash_password("demo1234"),
        institution="MSU",
    ))
    db.commit()


def _seed_water_project(db: Session) -> None:
    project = Project(
        slug="water-treatment-500",
        title="500 m\u00b3/h Municipal Water Treatment Plant",
        industry="water",
        description=(
            "Coagulation \u2192 flocculation \u2192 sedimentation \u2192 filtration \u2192 disinfection \u2192 "
            "distribution, with PID dosing, auto backwash sequencing, and pump alternation. "
            "The reason many engineers wish they'd done this project before industry."
        ),
        difficulty="advanced",
        hours=50,
        status="published",
    )
    db.add(project)
    db.flush()

    for i, section in enumerate(WATER_SECTIONS):
        db.add(ProjectSection(
            project_id=project.id,
            order=i,
            key=section["key"],
            title=section["title"],
            content=section["content"],
        ))

    for f in WATER_FAULTS:
        db.add(FaultScenario(
            project_id=project.id,
            slug=f["slug"],
            title=f["title"],
            description=f["description"],
            symptom=f["symptom"],
            injected_fault=f["injected_fault"],
            operation_notes=f["operation_notes"],
            available_checks=_palette(f["expected_checks"]),
            expected_checks=f["expected_checks"],
            correct_diagnosis=f["correct_diagnosis"],
            correct_diagnosis_keys=f["correct_diagnosis_keys"],
            common_misdiagnoses=f["common_misdiagnoses"],
            difficulty=2,
            is_published=True,
        ))

    db.commit()
    print(f"  [seed] created project '{project.slug}' with {len(WATER_SECTIONS)} sections, {len(WATER_FAULTS)} fault scenarios")


def seed_generated_variant(industry: str = "mining", title: str = "Thickener Underflow Control") -> Project:
    """Example of generating a new project from templates."""
    definition = ProjectDefinition(
        slug=f"{industry}-{title.lower().replace(' ', '-')}",
        title=title,
        industry=industry,
        difficulty="intermediate",
        hours=30,
        description="A mining vertical project generated from the base template.",
    )
    generator = ProjectGenerator(definition)
    faults = [
        {
            "title": "Underflow density drifting",
            "symptom": "Underflow density slowly climbs, torque rises.",
            "injected_fault": "Rake speed feedback failing.",
            "expected_checks": ["confirm_density", "check_torque", "check_rake_feedback", "check_pump_command"],
            "correct_diagnosis": "Rake speed feedback failing, allowing bed to compact.",
            "correct_diagnosis_keys": ["rake feedback", "compaction"],
            "common_misdiagnoses": ["pump", "density meter"],
        }
    ]
    db = SessionLocal()
    try:
        project = Project(slug=definition.slug, title=definition.title, industry=definition.industry,
                          difficulty=definition.difficulty, hours=definition.hours,
                          description=definition.description, status="published")
        db.add(project)
        db.flush()
        for i, section in enumerate(generator.build_sections(faults)):
            db.add(ProjectSection(project_id=project.id, order=i, key=section["key"], title=section["title"], content=section["content"]))
        for f in faults:
            db.add(FaultScenario(project_id=project.id, slug=f"{definition.slug}-{f['title'].lower().replace(' ', '-')}",
                                 title=f["title"], description=f.get("description", ""), symptom=f["symptom"],
                                 injected_fault=f["injected_fault"], available_checks=_palette(f["expected_checks"]),
                                 expected_checks=f["expected_checks"], correct_diagnosis=f["correct_diagnosis"],
                                 correct_diagnosis_keys=f["correct_diagnosis_keys"], common_misdiagnoses=f["common_misdiagnoses"]))
        db.commit()
    finally:
        db.close()
    return project