# Automation Technician Foundations — Curriculum

The first authored curriculum for the AI-Powered Industrial Academy: four projects
that take a learner from "I can push a button" to "I can own a dosing skid", each a
complete 17-section engineering package with graded fault scenarios.

The curriculum installs itself into the platform. On first boot it seeds four
projects (idempotent — existing databases only gain the missing ones), and its
offline bundles are built automatically. An admin can re-sync at any time from
**Admin → Learning content → Sync curriculum**.

## Recommended order

| # | Project | Level | Industry | Hours | You will learn |
| --- | --- | --- | --- | --- | --- |
| 1 | [Motor Starter — Start, Stop, and a Safe Hold](#1-motor-starter) | Foundations (basic) | manufacturing | 12 | Start/stop circuits, seal-in logic, e-stop chains, permissives, discrepancy monitoring, FAT discipline |
| 2 | [4-20 mA Loop & I/O Checkout](#2-instrument-loop-checkout) | Foundations (basic) | water | 14 | Loop sheets, live-zero signals, scaling, fail-safe behaviour, calibration |
| 3 | [Conveyor Sorter Cell](#3-conveyor-sorter-cell) | Core systems (intermediate) | manufacturing | 30 | State machines, zone interlocks, sensor integrity, counters, reject memory |
| 4 | [Chlorine Dosing Skid](#4-chlorine-dosing-skid) | Core systems (intermediate) | water | 28 | Duty/standby, demand pacing + PID trim, drum & leak safety, changeover |

After project 4, a learner is ready for the seeded **500 m³/h Water Plant**
(advanced) and the admin-generated industry variants.

## The 17-section lifecycle

Every project delivers the same engineering package a real service team hands to a
client, in the same order:

`project_brief → process_description → p_and_id → io_list → tag_list →
control_philosophy → plc_program → hmi → scada → alarms → interlocks →
networking → testing → fault_injection → troubleshooting → commissioning →
final_documentation`

Each section is authored for the project's specific machinery — the chlorine skid's
interlock matrix is its own, and the sorter cell's counters have their own naming
rules. Content is not template fill-in.

## Fault scenario coverage

Each project hides realistic faults in the Fault Injection phase, graded against the
check palette:

- **Motor Starter** — won't start (door interlock in the healthy header), runs on
  after Stop (welded contactor tips), e-stop bypassed (jumper in the safety mirror).
- **Instrument Loop** — pinned 4 mA (open loop), pinned 20 mA (fail-high), 10x
  scaling error at the HMI layer.
- **Sorter Cell** — never diverts (air supply isolated), spurious rejects (noise in
  the cable route), false jam (fogged photocell lens), counter drift (input debounce
  merging parts).
- **Dosing Skid** — no alternation (retained MANUAL mode), drum-low disagreement
  (false-high level transmitter vs true switch), leak detector crying wolf
  (washdown wetting the probe).

The correct diagnosis in each case calls for evidence, and the temptation-check
(distractor) teaches what NOT to change while isolating a live fault.

## Tooling alignment

The projects mirror the hardware the platform already integrates with:

- The **sorter cell** exercises the same sensing/actuation pattern as the
  FACTORY I/O conveyor station on Modbus TCP (`/api/integrations`).
- The **motor starter** and **skid** follow Siemens-style naming used in the
  TIA Portal project work and the WinCC/SCADA screens reference the same tags.
- Every project's network section documents the Profinet/VLAN layout that the S7 and
  OPC UA links assume.

## Content structure in the repo

- `backend/app/content/curriculum.py` — authored projects, faults, track map, and
  the idempotent `install_curriculum()` loader.
- `backend/app/api/routes_curriculum.py` — `GET /api/curriculum` (index, auth) and
  `POST /api/curriculum/install` (admin sync), which also refreshes offline bundles.
- `backend/tests/curriculum_test.py` — suite verifying lifecycle order, published
  faults, bundles, diagnosis grading and install idempotency.

To author the next project: add a dict to `CURRICULUM_PROJECTS` (same shape as the
existing four), restart, and hit **Sync curriculum** — no schema or UI changes
needed.