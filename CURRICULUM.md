# ASAPA — Curriculum & Learning Tracks

Two authored tracks install into the platform: the **Automation Technician
Foundations** curriculum (four water/manufacturing projects) and the
**Mining & Minerals** track (flagship primary-crushing plant). The curriculum
installs itself on first boot (idempotent — existing databases only gain the
missing projects), and its offline bundles are built automatically. An admin can
re-sync at any time from **Admin → Learning content → Sync curriculum**.

## Track 1 — Automation Technician Foundations

Four projects that take a learner from "I can push a button" to "I can own a
dosing skid", each a complete 17-section engineering package with graded fault
scenarios.

## Recommended order (Foundations)

| # | Project | Level | Industry | Hours | You will learn |
| --- | --- | --- | --- | --- | --- |
| 1 | [Motor Starter — Start, Stop, and a Safe Hold](#1-motor-starter) | Foundations (basic) | manufacturing | 12 | Start/stop circuits, seal-in logic, e-stop chains, permissives, discrepancy monitoring, FAT discipline |
| 2 | [4-20 mA Loop & I/O Checkout](#2-instrument-loop-checkout) | Foundations (basic) | water | 14 | Loop sheets, live-zero signals, scaling, fail-safe behaviour, calibration |
| 3 | [Conveyor Sorter Cell](#3-conveyor-sorter-cell) | Core systems (intermediate) | manufacturing | 30 | State machines, zone interlocks, sensor integrity, counters, reject memory |
| 4 | [Chlorine Dosing Skid](#4-chlorine-dosing-skid) | Core systems (intermediate) | water | 28 | Duty/standby, demand pacing + PID trim, drum & leak safety, changeover |

After project 4, a learner is ready for the seeded **500 m³/h Water Plant**
(advanced) and the admin-generated industry variants.

## Track 2 — Mining & Minerals

| # | Project | Level | Industry | Hours | You will learn |
| --- | --- | --- | --- | --- | --- |
| 1 | [Primary Crushing Plant](#1-primary-crushing-plant) | Advanced | mining | 50 | Coarse ore handling, crusher feed control, tramp-metal detection & false-trip diagnosis, belt protection at tonnage, feeder sequencing, WEG/IP55 site practice |

The Mining track is authored in `backend/app/content/mining_track.py` and installs
as its own track (slug `mining-track`). It is **not** part of the Foundations
index: `GET /api/curriculum` returns only the four foundations, while
`GET /api/curriculum/tracks` lists both tracks and `GET /api/curriculum/mining`
serves the minerals catalog. Projects in both tracks carry the same 17-section
lifecycle and fault-injection grading.

### Primary Crushing Plant

A 50-hour advanced project (`mining-primary-crushing`) for a 400 t/h primary
crushing plant fed by a vibratory feeder and dump hopper. The 17 sections cover
grizzly/nibble screening, apron-feeder-vs-crusher rate balancing, belt weigh
feeders with coarse-air separation, tramp metal detectors (TDK-style), WEG
starter duty, and site dust/operator protection. Four hidden faults are graded
against the check palette:

- `belt-misalignment-at-tonnage` — belt wander under load with a healthy
  alignment-window fault in routine-op and an answering deviation trip.
- `crusher-feed-choke` — feed-rate climb acts normal but crusher amps climb while
  level echo is stale; interlock matrix trips that froze the wrong pair.
- `tramp-metal-false-trip` — TDK trips on frames/couplers rather than ore; healthy
  cable re-route in the fix.
- `feeder-never-commands` — commander stuck with the run permissive chain healthy;
  `WEIGH` steady at idle while `SPEED` roams.

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

- `backend/app/content/curriculum.py` — authored Foundations projects, faults, track map, and
  the idempotent `install_curriculum()` loader.
- `backend/app/content/mining_track.py` — authored Mining & Minerals track (`install_mining_track()`).
- `backend/app/api/routes_curriculum.py` — `GET /api/curriculum` (Foundations index, auth),
  `GET /api/curriculum/tracks`, `GET /api/curriculum/mining`,
  `POST /api/curriculum/install` (admin sync), which also refreshes offline bundles.
- `backend/tests/curriculum_test.py` — Foundations suite (lifecycle order, published faults,
  bundles, diagnosis grading, install idempotency).
- `backend/tests/blueprint_test.py` — Mining track, TIA bridge, schematic viewer and fields the
  portfolio-publish coverage.

To author the next project: add a dict to `CURRICULUM_PROJECTS` (same shape as the
existing four) or to `MINING_PROJECTS` for the minerals track, restart, and hit
**Sync curriculum** — no schema or UI changes needed.