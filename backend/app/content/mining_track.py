"""Mining & Minerals track (blueprint: Mining & Minerals vertical).

One authored advanced project walks the full 17-section lifecycle on a mine
crushing plant: gyratory crusher feed control, conveyor interlock logic, tramp
metal protection and chute clearing. install_mining_track() is idempotent —
only creates projects whose slug is absent — so it is safe to call at startup
and from the Admin UI alongside the foundations curriculum.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.fault.palette import palette
from app.models import FaultScenario, Project, ProjectSection

DIFFICULTY_LEVEL = {"basic": 1, "intermediate": 2, "advanced": 3, "expert": 4}

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

MINING_TRACK = {
    "name": "Mining & Minerals",
    "blurb": (
        "One authored advanced package on a real mine control problem: a primary "
        "crushing station with gyratory feed control, conveyor interlock logic, "
        "tramp-metal protection and chute clearing. Same 17-section lifecycle, "
        "higher heat."
    ),
    "levels": [
        {
            "level": 3,
            "label": "Industrial scale",
            "slug": "mining-primary-crushing",
            "competency": "Crusher feed regulation, start/stop conveyor sequencing, tramp-metal protection and plant-wide interlocking.",
        }
    ],
}

MINING_PROJECTS: list[dict] = [
    {
        "slug": "mining-primary-crushing",
        "title": "Primary Crushing Station — Gyratory Feed Control & Conveyor Interlocks",
        "industry": "mining",
        "difficulty": "advanced",
        "hours": 50,
        "description": (
            "1000 t/h primary crushing: ROM ore feeds a gyratory crusher through an apron feeder, "
            "discharges on a main conveyor with belt protection, and clears into the stockpile "
            "reclaim. Start/stop sequencing, crusher power -based feed control, metal detection "
            "and full plant interlocking. The project every mine-control engineer cuts their teeth on."
        ),
        "sections": [
            {
                "key": "project_brief",
                "title": "Project Brief",
                "content": """# Project Brief — 1000 t/h Primary Crushing Station

**Client:** Zambezi Copper Mine (surface)
**Duty:** Reduce ROM ore < 1200 mm to < 250 mm
**Train:** Apron feeder → gyratory crusher (1000 t/h) → discharge conveyor CV-01 → transfer chute → stockpile conveyor CV-02

## What the client actually asked for
"A crusher that cannot choke, a conveyor line that cannot run with a load on a stopped belt,
and a plant that starts in the right order and stops on any trip without burying anything."

## Key requirements
- Crusher start BEFORE the discharge conveyor; discharge conveyor before feed. Reverse order on stop.
- Control apron-feeder speed from crusher power draw so the gyratory never under-zooms into a choke.
- Tramp metal (bolts, drill steel) detected and rejected before the crusher, with a defined stop sequence.
- Belt protection: misalignment, slip, pull-cord and chute-block detection on CV-01/CV-02.
- Everything held in a cause-and-effect matrix implementable in a single PLC with two distributed I/O racks.

## Constraints
- Intermittent power — restart sequencing must be event-driven, not timer-guessed.
- Dusty environment: every sensor selected for IP65+ and rated for vibration near the crusher.

## Deliverable
A complete 17-section engineering package the client's control team can commission and operate.""",
            },
            {
                "key": "process_description",
                "title": "Process Description",
                "content": """ROM dump trucks tip into the ROM bin. The apron feeder (AF-01) whraps ore onto a grizzly;
oversize falls into the gyratory crusher (CR-01), undersize bypasses via the grizzly bypass
chute. Crushed product discharges onto CV-01 (head chute), transfers to CV-02 and reports to
the coarse-ore stockpile.

## Normal operation
Start-up sequence: CV-02, then CV-01, then CR-01 lube + motor, then AF-01. The apron feeder
ramps under crusher power control (setpoint band 60-80% motor current). Shut-down reverses.

## Abnormal states
- High crusher power → feeder rap slows.
- Choke detect (power sustained > 95%, no feed) → feed off, lube run, mechanical clear.
- CV-01 stopped with AF-01 running = hangup / head-chute blockage is imminent.
- Tramp metal detected → belt stop after the metal passes the magnetic separator or is removed manually.""",
            },
            {
                "key": "p_and_id",
                "title": "P&ID",
                "content": """# P&ID — Crushing station control scope

| Tag | Service | Signal | Card | Range |
|-----|---------|--------|------|-------|
| PE-001 | Crusher power draw | AI 4-20 mA | IW0.0 | 0-100 % |
| SE-201 | CV-01 speed | AI 4-20 mA | IW0.2 | 0-4 m/s |
| ZS-110 | Tramp metal detector | DI | I1.0 | - |
| ZS-211 | CV-01 misalignment | DI | I1.1 | - |
| ZS-212 | CV-01 slip | DI | I1.2 | - |
| ZS-213 | CV-01 pull-cord | DI | I1.3 | - |
| ZS-214 | CV-01 head chute clear | DI | I1.4 | - |
| ZS-221 | CV-02 misalignment | DI | I1.5 | - |
| ZS-222 | CV-02 slip | DI | I1.6 | - |
| ZS-230 | Crusher lube pressure | DI | I1.7 | - |
| AF-01 RUN | Apron feeder running | DI | I2.0 | - |
| CR-01 RUN | Crusher running | DI | I2.1 | - |
| AF-01 CMD | Apron feeder drive cmd | DO | Q0.0 | - |
| CR-01 CMD | Crusher motor cmd | DO | Q0.1 | - |
| CV-01 CMD | Discharge belt cmd | DO | Q0.2 | - |
| CV-02 CMD | Stockpile belt cmd | DO | Q0.3 | - |
| ALM-HORN | Audible alarm / annunciator | DO | Q0.4 | - |

*The I/O in this table is the contract the PLC program and the HMI implement.*""",
            },
            {
                "key": "io_list",
                "title": "I/O List",
                "content": """# I/O List

| Module | Address | Tag | Description | Type | Range | Loop |
|--------|---------|-----|-------------|------|-------|------|
| AI | IW0.0 | PE-001 | Crusher motor % current | 4-20 mA | 0-100 % | crusher power |
| AI | IW0.2 | SE-201 | CV-01 belt speed | 4-20 mA | 0-4 m/s | belt drive |
| DI | I1.0 | ZS-110 | Tramp metal detector (NC=cool) | 24 V | - | tramp protection |
| DI | I1.1 | ZS-211 | CV-01 misalignment switch | 24 V | - | belt protection |
| DI | I1.2 | ZS-212 | CV-01 slip switch | 24 V | - | belt protection |
| DI | I1.3 | ZS-213 | CV-01 pull-cord (NC) | 24 V | - | personnel |
| DI | I1.4 | ZS-214 | CV-01 head chute blocked | 24 V | - | chute protection |
| DI | I1.5 | ZS-221 | CV-02 misalignment switch | 24 V | - | belt protection |
| DI | I1.6 | ZS-222 | CV-02 slip switch | 24 V | - | belt protection |
| DI | I1.7 | ZS-230 | Crusher lube oil pressure | 24 V | - | equip. protection |
| DI | I2.0 | AF-01 RUN | Apron feeder running feedback | 24 V | - | starter aux |
| DI | I2.1 | CR-01 RUN | Crusher motor running feedback | 24 V | - | starter aux |
| DO | Q0.0 | AF-01 CMD | Apron feeder drive command | relay | - | VFD/soft-start |
| DO | Q0.1 | CR-01 CMD | Crusher motor command | relay | - | HV starter |
| DO | Q0.2 | CV-01 CMD | Discharge belt command | relay | - | starter coil |
| DO | Q0.3 | CV-02 CMD | Stockpile belt command | relay | - | starter coil |
| DO | Q0.4 | ALM-HORN | Annunciator horn | relay | - | plant |

Every point is loop-checked against this list before FAT; the maintenance crew
commissions from this sheet.""",
            },
            {
                "key": "tag_list",
                "title": "Tag List",
                "content": """# Tag List

| Tag | Description | Data type | Units | Range | Alias |
|-----|-------------|-----------|-------|-------|-------|
| PE-001 | Crusher power draw | REAL | % | 0-100 | CR.POWER |
| SE-201 | CV-01 belt speed | REAL | m/s | 0-4 | CV1.SPEED |
| ZS-110 | Tramp metal detected | BOOL | - | - | TRAMP.DET |
| ZS-211 | CV-01 misalignment | BOOL | - | - | CV1.MISALIGN |
| ZS-212 | CV-01 slip | BOOL | - | - | CV1.SLIP |
| ZS-213 | CV-01 pull-cord | BOOL | - | - | CV1.PULLCORD |
| ZS-214 | CV-01 head chute blocked | BOOL | - | - | CV1.CHUTE.BLK |
| ZS-221 | CV-02 misalignment | BOOL | - | - | CV2.MISALIGN |
| ZS-222 | CV-02 slip | BOOL | - | - | CV2.SLIP |
| ZS-230 | Crusher lube pressure | BOOL | - | - | CR.LUBE.OK |
| AF-01 RUN | Apron feeder running | BOOL | - | - | AF.RUN |
| CR-01 RUN | Crusher running | BOOL | - | - | CR.RUN |
| AF-01 CMD | Apron feeder command | BOOL | - | - | AF.CMD |
| CR-01 CMD | Crusher motor command | BOOL | - | - | CR.CMD |
| CV-01 CMD | Discharge belt command | BOOL | - | - | CV1.CMD |
| CV-02 CMD | Stockpile belt command | BOOL | - | - | CV2.CMD |
| ALM-PLANT | Plant alarm aggregate | BOOL | - | - | ALM.ANY |

Convention: every HMI / SCADA / alarm tag appears here first with one alias.""",
            },
            {
                "key": "control_philosophy",
                "title": "Control Philosophy",
                "content": """## Modes
- AUTO: full sequencing — feeder trimmed by crusher power, interlocks live.
- MAN: operator commands through the HMI; interlocks still enforced.
- LOCAL: starter-cubicle control; PLC only monitors and alarms.

## Start / stop sequencing (the client's rule zero)
- START: CV-02 → CV-01 → CR-01 (lube verified) → AF-01. Each step requires the prior
  device 'running' before the next starts; 5 s time-out raises a sequence fault.
- STOP: reverse order, AF-01 first, belt fully cleared before CR-01 drops below speed.

## Crusher feed control
Apron feeder speed = feed-forward ramp + trim on crusher power (setpoint band 60-80%).
If power > 95% for 5 s → feeder speed capped to minimum; a power collapse with choke
symptom selects chute/crusher check, not continued feeding.

## Belt protection
Any of misalignment, slip, pull-cord, chute-block on a running belt stops that belt AND
upstream devices in the same train. Tramp metal detection stops CV-01 (and AF-01) with
the metal flagged for removal at the magnetic separator.

No output can be forced if its interlock group is unsatisfied — the same rule applies
in AUTO and MAN.""",
            },
            {
                "key": "plc_program",
                "title": "PLC Program",
                "content": """Standard: IEC 61131-3, Siemens TIA Portal reference (S7-1500, two ET200SP racks).

| OB/FC/FB | Purpose |
|----------|---------|
| OB1 | Main cycle, calls train blocks |
| FB_TrainSeq | Start/stop sequencer for CV-02/CV-01/CR-01/AF-01 |
| FB_FeedCtrl | Crusher-power based apron feeder trim |
| FB_BeltProt | Belt protection grouping per conveyor |
| FB_Tramp | Tramp metal detection + stop sequence |
| FB_PlantAlarms | Alarm aggregation + horn |

Skeleton of the start sequence (STL/SCL equivalent):

    // START order: CV2 -> CV1 -> CR1(lube) -> AF1
    SeqStep 1: if NOT CV2_RUN then CV2_CMD := 1
    SeqStep 2: when CV2_RUN, command CV1
    SeqStep 3: when CV1_RUN and LUBE_OK, command CR1
    SeqStep 4: when CR1_RUN, ramp AF1 under feed control

Rules: a device drops its command the instant any of its permissive inputs fall
(false), regardless of sequence position. Rung order is the safety contract.""",
            },
            {
                "key": "hmi",
                "title": "HMI",
                "content": """Screens (WinCC Unified on the plant station):

1. **Plant overview** — train mimic: bin, feeder, crusher, CV-01, transfer, CV-02.
   Live power %, speeds, run/stop lamps and the global alarm banner.
2. **Sequencer** — step indicator for start/stop, permissive reasons for each device.
3. **Crusher feed** — power trend, feeder speed setpoint/actual, choke status, manual override.
4. **Belt protection** — per-belt matrix of protective devices with reset logic.
5. **Tramp log** — every metal detection event with time, belt position and disposition.

Rules: interlock resets are permissioned and logged; the feed page allows MAN speed
only when the station is in MAN with all interlocks satisfied. No dead buttons.""",
            },
            {
                "key": "scada",
                "title": "SCADA",
                "content": """WinCC SCADA above the PLC:
- Historian tags mirror the Tag List: power, speeds, run-times, trip counters.
- Report pack for the client: tonnes moved proxy (belt speed x run time), trip causes
  with times, tramp-metal log, sequence stroke records.
- Remote viewing with full alarm surface; on comms loss the PLC holds the current safe
  state and SCADA raises 'comm fail' for every tag.

The critical control intelligence lives in the PLC — SCADA is read-heavy and
reports, exactly the offline-first discipline the rest of this platform teaches.""",
            },
            {
                "key": "alarms",
                "title": "Alarms",
                "content": """Rationalisation per ISA-18.2:

| Tag | Priority | Setpoint | Message | Operator action |
|-----|----------|----------|---------|-----------------|
| TRAMP.DET | Urgent | - | Tramp metal detected on CV-01 | Stop feed, remove metal, log, reset |
| CV1.CHUTE.BLK | High | - | CV-01 head chute blocked | Clear chute, verify, reset protection |
| CR.CHOKE | High | power>95% 5 s | Crusher choke developing | Reduce feed, check crusher, consider clear |
| CV1.MISALIGN | High | - | CV-01 misalignment trip | Inspect belt tracking, repair, reset |
| CV1.SLIP | High | - | CV-01 belt slip | Check drive / belt tension |
| CV1.PULLCORD | High | - | Pull-cord operated | Attend personnel, reset |
| CR.LUBE.LO | High | lube pressure lost | Crusher lube pressure low | Stop crusher, restore lube, check bearings |
| SEQ.FAULT | Medium | - | Sequence step timed out | Check device feedback, re-arm sequence |

No alarm without a consequence and a recovery. Horn for Urgent group only.""",
            },
            {
                "key": "interlocks",
                "title": "Interlocks",
                "content": """Cause-and-effect matrix (excerpt). Start commands are gated by their permissive group:

| Interlock | Effect | Type | Reset |
|-----------|--------|------|-------|
| ZS-230 lube low | Block CR-01 start; trip if running | Equipment | Restore pressure, manual reset |
| CV-02 not running | Block CV-01 + AF-01 | Sequence | Start CV-02 first |
| CV-01 not running | Block AF-01 | Sequence | Start CV-01 first |
| CV-01 slip/misalign/chute | Stop CV-01 AND AF-01 | Belt protection | Clear cause, manual reset |
| CV-02 slip/misalign | Stop CV-02 (and by sequence CF-01, AF-01) | Belt protection | Clear cause, manual reset |
| ZS-110 tramp (while running) | Stop CV-01 + AF-01, flag metal | Protection | Remove metal, manual reset |
| CR-01 running lost | Stop AF-01 immediately | Equipment | Diagnose, restore |

The HMI interlock page shows exactly which permissive holds each device — nobody
guesses why a belt will not start.""",
            },
            {
                "key": "networking",
                "title": "Networking",
                "content": """- Control network: PROFINET, PLC + two ET200SP racks + HMI on a dedicated VLAN (fixed IPs).
- Plant IT: SCADA/reporting on a firewalled VLAN 20; no process control rides the IT path.
- IP scheme: 10.40.x.x/24 control, 10.50.x.x/24 supervision.
- IP65/67 enclosures near the crusher; fibre to the control room; switch and IP schedule
  fixed and printed for the electricians.

Failure semantics: a lost IO device drives its tags failsafe; the SCADA link is watched by
a comm watchdog; the train holds defined safe state. This is a dusty, vibrating plant — 
cabinet zoning, spare cores and labelled spares are expected, not optional.""",
            },
            {
                "key": "testing",
                "title": "Testing / FAT & SAT",
                "content": """## Factory Acceptance Test (FAT)
- Loop check of every I/O point against the I/O list (signals, scaling, alarms).
- Sequence test: start CV-02→CV-01→CR-01→AF-01 with and without feedback time-outs.
- Interlock matrix: every cause-and-effect entry injected and observed.
- Belt protection drills: force each protective input; the correct train drops.
- Choke simulation: ramp crusher power in the simulator; feeder trim responds.

## Site Acceptance Test (SAT)
- Comms + power proving on site; tension/alignment of both belts verified by instrument.
- Live choke drill with an empty bin; tramp-metal drill with a test piece.
- 72 h soak under load; trip log and trend evidence compared to design.

No exemption without a written, client-signed deviation.""",
            },
            {
                "key": "fault_injection",
                "title": "Fault Injection",
                "content": """Four faults ship with this project — the ones mine control technicians actually face:

- **Belt trips on misalignment at high tonnage.** The tripping switch is serviceable but
  guided/tracking looks fine; find out what is really flipping the contact.
- **Crusher feed chokes with power draw climbing.** The feeder is obeying a bad measured
  signal; the loop looks healthy at every intermediate point.
- **Tramp metal stop keeps firing with no metal.** Someone has a quiet electrical fault
  that looks exactly like a real detection.
- **CV-01 starts but AF-01 never commands.** Trace why the feed permissive is missing.

Diagnose each with the full check palette, name the root cause with evidence, and state
what you would NOT touch during the diagnosis.""",
            },
            {
                "key": "troubleshooting",
                "title": "Troubleshooting",
                "content": """Sequence for a stopped mine plant, in order:

1. **Establish the last event** — the alarm/trip history, not the story. What tripped first?
2. **Belt protection half-split** — is the protective device itself true, or is the wiring/
   PLC input simulating it? Measure at the terminal, not at the HMI.
3. **Sequence state** — which device is holding the train? The HMI interlock page answers.
4. **Power path** — for a device that will not start, verify command present AND power at
   the starter before touching the drive.
5. **Feed loop** — when the crusher chokes, compare feeder command to power trend: is the
   loop sensing (signal) or actuating (drive) the problem?
6. **Diagnose with evidence, reset deliberately** — a reset without the cause cleared
   costs a belt load-up every time.

Keep a dated log: symptom, checks, measurements, root cause, reset. It is the client's
reliability record as much as the technician's.""",
            },
            {
                "key": "commissioning",
                "title": "Commissioning",
                "content": """Sequenced by area, in order:

1. Pre-commissioning: megger + continuity, instrument calibration (power transmitter,
   speed probes) with dated records.
2. Loop checks: every AI/DI reads correctly, every DO/DOA operates the correct device.
3. Dry runs with the plant isolated: sequence start/stop, interlocks, alarm setpoints.
4. First load: empty-bin start in precise sequence, then loaded start; feeder ramp observed.
5. Choke drill + tramp drill under supervision; protective resets proven.
6. 72 h soak, then handover pack: as-builts, FAT/SAT records, calibration certificates,
   alarm rationalisation, interlock matrix, O&M manual and operator training record.

Handover gate: signed SAT, deviation register empty or client-approved.""",
            },
            {
                "key": "final_documentation",
                "title": "Final Documentation",
                "content": """The handover pack, and the reason this folder is a genuine work sample:
- As-built P&ID and control schematics.
- Final I/O list and tag list (marked against FAT/SAT changes).
- FAT + SAT test certificates with sign-off records.
- Alarm rationalisation tables and the cause-and-effect matrix (as-built).
- O&M manual: start/stop, permissive reasons, chute clear procedure, tramp procedure.
- Operator training record and the spare parts list Hamilton would approve.

This is what you hand a client — and the single item on your CV that proves you can
sequence a mine plant, not just label a ladder diagram.""",
            },
        ],
        "faults": [
            {
                "slug": "belt-misalignment-at-tonnage",
                "title": "CV-01 trips on misalignment at high tonnage",
                "symptom": "CV-01 trips intermittently for 'misalignment' during loaded operation, but tracking looks correct on inspection and the switch is serviceable.",
                "description": "A protective circuit that trips a running belt. Something makes the input pulse only under load.",
                "injected_fault": "The CV-01 misalignment switch's wiring shares a thermocouple cable tray; vibration under load intermittently shorts the pair, spiking the protective input.",
                "operation_notes": "Correlate tripping with tonnage/vibration, not with belt alignment. A switch that tests fine on the bench can still be the victim in a faulted circuit.",
                "expected_checks": [
                    "confirm_misalignment_alarm",
                    "measure_switch_input_trip",
                    "check_switch_wiring_run",
                    "verify_switch_physically",
                    "correlate_trip_with_load",
                    "inspect_shared_cable_tray",
                ],
                "correct_diagnosis": "Wiring fault: the misalignment circuit shares a cable tray and intermittently shorts under crusher vibration.",
                "correct_diagnosis_keys": ["cable tray", "wire short", "intermittent short", "sharing"],
                "common_misdiagnoses": ["alignment", "switch fault", "plc input"],
            },
            {
                "slug": "crusher-feed-choke",
                "title": "Crusher feed chokes with power draw climbing",
                "symptom": "Crusher power slowly climbs toward the choke band while the apron feeder keeps ramping feed. The loop reads healthy at intermediate points.",
                "description": "The feeder acts on a false signal, so it feeds against the choke instead of backing off.",
                "injected_fault": "Crusher power transmitter PE-001 reads ~35% lower than true under load (attenuated mA span), so the feed controller keeps speeding the feeder up.",
                "operation_notes": "A scaling/signal fault beats the loop far better than the loop's own equals. Compare HMI power to a clamp-meter / calibrated load.",
                "expected_checks": [
                    "compare_hmi_power_reading",
                    "measure_loop_current",
                    "inject_reference_current",
                    "check_transmitter_span",
                    "verify_feeder_ramp_logic",
                    "check_crusher_actual_load",
                ],
                "correct_diagnosis": "PE-001 scaled low (span attenuation), so feed control keeps raising feeder speed toward a choke.",
                "correct_diagnosis_keys": ["pe-001", "power transmitter", "scaled low", "span"],
                "common_misdiagnoses": ["feeder drive", "choke", "crusher motor"],
            },
            {
                "slug": "tramp-metal-false-trip",
                "title": "Tramp-metal stop keeps firing with no metal present",
                "symptom": "The plant stops repeatedly on 'tramp metal detected' but no metal ever appears at the magnetic separator. Resets hold only until the next loaded run.",
                "description": "A detection circuit that behaves like a real metal event but has no metal. Looks identical from the operator's side.",
                "injected_fault": "Tramp metal detector ZS-110 supply rail sagging under feeder current draw; the detector's electronics trip its own healthy-check output.",
                "operation_notes": "Check the detector's own health signal and PSU, not the belt. A false 'tramp' that survives resets until load returns is a power/supply signature.",
                "expected_checks": [
                    "confirm_tramp_alarm",
                    "check_detector_self_health",
                    "measure_detector_supply",
                    "verify_reset_persistence",
                    "oversee_belt_unloaded",
                    "check_earthing_ground_loop",
                ],
                "correct_diagnosis": "Tramp detector power rail sags under feeder load, causing a false healthy-check trip on every loaded run.",
                "correct_diagnosis_keys": ["power rail", "detector supply", "false trip", "psu sag"],
                "common_misdiagnoses": ["tramp metal", "detector sensitivity", "faulty detector"],
            },
            {
                "slug": "feeder-never-commands",
                "title": "CV-01 starts but the apron feeder never commands",
                "symptom": "Discharge belt CV-01 runs, crusher is available, yet AF-01 stays off with no alarm. The sequencer appears stuck after the CV-01 step.",
                "description": "A sequence next-step permission that never arrives, holding the train from feeding.",
                "injected_fault": "Crusher lube pressure switch ZS-230 contact stuck open, so the CR-01 start step never becomes permissible and the feeder (last step) never commands.",
                "operation_notes": "The stuck step isn't the feeder — look at the step before it. Check the sequencer's permissive chain and the lube circuit.",
                "expected_checks": [
                    "check_sequence_step",
                    "check_lube_pressure_switch",
                    "check_crusher_ready",
                    "check_next_step_permissive",
                    "check_manual_feeder_cmd",
                    "verify_feedback_chain",
                ],
                "correct_diagnosis": "Crusher lube pressure switch stuck open, blocking the CR-01 step so the feeder (last sequence step) never commands.",
                "correct_diagnosis_keys": ["lube switch", "zs-230", "sequence step", "crusher ready"],
                "common_misdiagnoses": ["feeder drive", "vfds", "af-01 feedback"],
            },
        ],
    },
]


def install_mining_track(db: Session) -> list[str]:
    """Create any Mining & Minerals project whose slug is missing. Idempotent."""
    created: list[str] = []
    existing = {slug for (slug,) in db.query(Project.slug).all()}
    for definition in MINING_PROJECTS:
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