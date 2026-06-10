# DVM-ABM simulator

Mesa- and Streamlit-based agent-based simulation model for exploring how different forms of Digital Visual Management (DVM) may influence production reliability, situational awareness, supervisor workload, making-do, recovery from disruptions and project completion in a construction setting.

The model is intended as a research and learning tool. It does not predict a real project directly. Instead, it helps compare alternative management and information-system scenarios under the same simulated workload and disruption environment.

## Purpose

The simulator asks a practical question:

> How do different visual management and digital visual management configurations affect the reliability of weekly planning, the accumulation of unfinished work, the workload of the supervisor, and the final completion time of a construction project?

The model combines ideas from:

- Last Planner System (LPS)
- Percent Plan Complete (PPC)
- make-ready planning
- making-do and rework
- situational awareness
- digital visual management
- supervisor firefighting and planning time
- external disruptions and recovery
- project workload and resource fit

The current model version is developed as an exploratory research prototype, not as a validated production-planning engine.

## Main scenarios

The default scenario set compares five forms of visual management or DVM use.

| Scenario key | Display name | Interpretation |
|---|---|---|
| `analog_vm` | Analog visual management | Traditional visual planning and coordination, limited digital support. |
| `management_dashboard` | Management dashboard | Information mainly supports managers; weaker direct support for crews. |
| `forced_reporting_dvm` | DVM as forced reporting | Digital system is used mainly for control, reporting and compliance. |
| `workface_dvm` | Ready work area DVM | Digital support is focused on ready work areas, constraints and crew usability. |
| `dvm_lean_autonomous` | Lean-autonomous DVM | DVM supports autonomous decision-making, make-ready quality and team learning. |

The scenario parameters are defined in:

```text
config/scenarios.yaml
```

The Python dataclass structure is defined in:

```text
dvm_abm/scenarios.py
```

## Repository structure

Expected repository structure:

```text
app.py
requirements.txt
dvm_abm/
    __init__.py
    model.py
    agents.py
    scenarios.py
    shocks.py
    analysis.py
    export.py
    visualization.py
    utils.py
config/
    scenarios.yaml
```

The Streamlit application entry point is:

```bash
streamlit run app.py
```

## Installation

Create and activate a virtual environment:

```bash
py -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
py -m pip install -r requirements.txt
```

Run locally:

```bash
streamlit run app.py
```

If using Streamlit Community Cloud, the repository should include at least:

```text
app.py
requirements.txt
dvm_abm/
config/
```

After larger model updates, clear the Streamlit cache and reboot the app:

```text
Manage app → Clear cache → Reboot
```

This is important because Streamlit may otherwise reuse old cached model objects or scenario objects.

## User interface

The Streamlit app contains six main tabs:

| Tab | Purpose |
|---|---|
| Overview | Key scenario results, PPC, make-ready, backlog, delay and main charts. |
| Time series | Time-dependent development of selected metrics. |
| Disruptions | External disruption, recovery and alternative task switching metrics. |
| Supervisor | Supervisor workload, planning time, reactive work and firefighting. |
| Scenario comparison | Runs all scenarios under the same settings for comparison. |
| Data | Shows and downloads the underlying result tables. |

The app supports Excel export for both single-scenario runs and scenario comparison runs.

## Main simulation settings

The most important user-controlled inputs are:

| Setting | Meaning |
|---|---|
| Runs | Number of stochastic replications. |
| Planned project duration, days | Planned target duration of the project. The simulation may continue beyond this until all tasks are complete. |
| Base seed | Random seed for reproducibility. |
| Daily external shock probability | Probability of external disruptions. |
| Capture rate | How well the DVM system captures relevant site information. |
| Data accuracy | Accuracy of captured data. |
| Data timeliness | How fresh the information is. |
| Crew access | How well crews can access and use the information. |
| Management access | How well management can access the information. |
| Autonomy | Degree to which crews can act autonomously based on DVM. |
| Perceived surveillance | Degree to which DVM feels like monitoring/control. |
| Reporting burden | Extra administrative burden caused by the system. |
| Supervisor capacity | Available supervisor working capacity per day. |
| Initial planning quality | Initial level of planning reliability. |
| Maximum active crews | Maximum resource level near the project peak. |
| Peak resource fit | How well resources match peak workload. |

## Core model logic

### Project baseline

The project consists of a fixed number of tasks. The planned completion of tasks is distributed over the user-defined planned project duration.

This is important:

> If the user sets the planned project duration to 100 days, the baseline task completions are distributed across that 100-day plan.

The simulation then shows whether the project finishes early, on time or late.

### Task states

Tasks may move through states such as:

```text
NOT_READY
READY
IN_PROGRESS
INTERRUPTED
COMPLETED
```

The model tracks both planned and actual task timing.

### LPS constraints

Each task has make-ready prerequisites, such as:

```text
design_ready
material_ready
crew_ready
equipment_ready
space_ready
predecessor_ready
approval_ready
safety_quality_ready
```

These constraints form a make-ready score. A task is sound when enough prerequisites are satisfied and predecessor logic is valid.

### Weekly commitments and PPC

The model uses a Last Planner style weekly planning logic.

A weekly commitment means:

> A task is promised to be completed during the week.

The model assumes that LPS tasks are already sized so that they can be completed within a week. Longer work packages should be split into smaller weekly tasks before PPC is calculated.

PPC is calculated as:

```text
PPC = successful weekly completion promises / all weekly completion promises
```

The model aligns PPC with actual weekly task completions so that completed work does not fall outside the PPC denominator.

Important PPC-related outputs include:

| Metric | Meaning |
|---|---|
| `weekly_ppc` | PPC for the current week. |
| `avg_weekly_ppc` | Aggregate PPC over observed promises. |
| `last_completed_weekly_ppc` | PPC of the latest completed week. |
| `weekly_committed_tasks` | Number of tasks promised for the current week. |
| `completed_committed_tasks` | Number of promised tasks completed by week end. |
| `total_ppc_promises` | Total number of PPC promises counted. |
| `total_ppc_successes` | Total number of successful PPC promises. |
| `ppc_schedule_score` | Schedule-based diagnostic score. |
| `ppc_schedule_consistency_gap` | Diagnostic gap between schedule performance and PPC. |

### Carryover

If a task is not completed during its planned week, it may become carryover. Carryover can be re-committed, but the model includes limits so that one repeatedly delayed task does not inflate the PPC denominator indefinitely.

### Making-do

If a task is started without enough prerequisites, the model may treat this as making-do. Making-do can cause:

- interruptions
- rework
- escalation
- additional coordination demand
- lost productivity

Relevant metrics include:

```text
making_do_starts
cumulative_making_do_starts
making_do_interruptions
cumulative_making_do_interruptions
rework_due_to_making_do
cumulative_rework_due_to_making_do
```

### Active crew selection

The model does not simply activate the first N crews in a fixed list. Active crews are selected based on current trade-specific demand.

The selection considers:

- in-progress work
- weekly commitments
- ready tasks
- overdue tasks
- task priority
- remaining trade-specific backlog

This avoids a late-project artefact where the wrong trades remain active while the remaining tasks belong to other trades.

### Project completion

The input `Planned project duration, days` is the planned target duration, not a hard simulation stop.

The model continues until:

```text
all tasks are complete
```

or until a technical hard safety limit is reached.

Project delay is calculated as:

```text
project_delay_days = actual_project_finish - planned_project_duration
```

with zero as the minimum value.

## Main outputs

### Production and schedule metrics

| Metric | Meaning |
|---|---|
| `completed_tasks` | Number of completed tasks. |
| `remaining_tasks` | Number of unfinished tasks. |
| `actual_project_finish` | Actual final completion day if all tasks are complete. |
| `project_delay_days` | Delay relative to planned project duration. |
| `avg_lateness_days` | Average lateness of tasks. |
| `late_completed_tasks` | Number of tasks completed after their planned week. |
| `open_schedule_backlog` | Number of tasks currently behind their planned finish. |
| `cumulative_plan_failures` | Failed weekly commitments. |
| `baseline_adherence` | Current week baseline adherence. |
| `cumulative_schedule_adherence` | Cumulative schedule adherence up to current week. |

### Situational awareness and DVM metrics

| Metric | Meaning |
|---|---|
| `avg_sa` | Average crew situational awareness. |
| `workface_picture_quality` | Ready work area / workface picture quality. |
| `management_picture_quality` | Management-level picture quality. |
| `workface_gap` | Difference between management and crew/workface picture quality. |
| `trust_in_data` | Trust in data. |
| `trust_in_management` | Trust in management. |
| `avg_adoption` | Average DVM adoption. |
| `avg_effective_use` | Effective DVM use. |

### Supervisor metrics

| Metric | Meaning |
|---|---|
| `supervisor_total_workload` | Total supervisor workload. |
| `supervisor_base_workload` | Worker-independent administrative workload. |
| `supervisor_planning_time` | Time available/used for planning. |
| `supervisor_reactive_time` | Time used for reactive problem handling. |
| `firefighting_ratio` | Share of supervisor effort spent in reactive work. |
| `supervisor_backlog` | Accumulated unresolved supervisor workload. |
| `cumulative_planning_time` | Cumulative planning time. |
| `cumulative_reactive_time` | Cumulative reactive time. |

### Disruption and recovery metrics

| Metric | Meaning |
|---|---|
| `external_disruptions` | Number of external disruptions. |
| `active_external_blockages` | Currently active external blockages. |
| `avg_recovery_time` | Average recovery time. |
| `alternative_task_switches` | Successful switches to alternative ready work. |
| `failed_task_switches` | Failed alternative switches. |
| `idle_time_due_to_external_disruptions` | Waiting caused by external disruptions. |
| `supervisor_recovery_interventions` | Supervisor interventions for recovery. |

## Excel exports

The app exports Excel workbooks with three main sheets:

| Sheet | Content |
|---|---|
| `metadata` | Run settings and timestamp. |
| `summary` or `scenario_summary` | Aggregated final metrics. |
| `final_run_metrics` | One final row per run. |
| `timeseries` | Full time series of all runs. |

For scenario comparison, the workbook contains all scenarios in the same file.

## Development notes

### Versioning

The app uses an internal cache version string:

```python
APP_DATA_VERSION = "..."
```

After model or scenario changes, update this string. Otherwise Streamlit may reuse cached data from an older model version.

### Streamlit cache

The app uses cached functions for loading scenarios and running simulations. After changing dataclass fields, scenario fields, model reporters or output columns, clear cache and reboot in Streamlit Cloud.

### Scenario compatibility

The app contains fallback logic to rebuild older cached `Scenario` objects if fields are missing. This prevents crashes after scenario dataclass updates.

### UI fallback columns

The app also contains fallback column creation to prevent crashes when older cached result tables lack newer metrics. This is useful during development, but it can hide whether a new model reporter is actually producing values. If a new metric stays exactly zero in all runs, check whether it is produced by the model or added later by UI fallback logic.

## Model limitations

This is an exploratory model. Important limitations include:

- Parameters are illustrative and require calibration.
- The model is not validated against a specific real project.
- Tasks are simplified weekly-sized work packages.
- Trade logic is stylized.
- Human behaviour is represented through simplified parameterized rules.
- PPC, make-ready, situational awareness and trust are model constructs, not direct empirical measurements.
- Results should be interpreted comparatively, not as exact forecasts.

## Suggested interpretation

Use the model to compare patterns rather than single numbers.

Useful questions include:

- Does a scenario reduce carryover and backlog?
- Does DVM improve make-ready quality?
- Does it reduce supervisor firefighting?
- Does it increase crew situational awareness?
- Does it support alternative task switching after disruptions?
- Does it reduce project delay?
- Does PPC move consistently with project completion?

The most useful result is usually the relative difference between scenarios under the same assumptions.

## Typical workflow

1. Select a scenario.
2. Set planned project duration and number of runs.
3. Adjust DVM, autonomy, reporting burden and resource parameters if needed.
4. Run the simulation.
5. Inspect overview and time series.
6. Download Excel.
7. Run scenario comparison.
8. Compare PPC, delay, backlog, supervisor workload and recovery metrics.
9. Calibrate parameters if needed.
10. Document assumptions before interpreting results.

## Updating the model

A typical update workflow:

```bash
git status
git add app.py dvm_abm/model.py dvm_abm/scenarios.py config/scenarios.yaml
git commit -m "Describe model update"
git push
```

Then in Streamlit Community Cloud:

```text
Manage app → Clear cache → Reboot
```

## Research use

When using results in research, report at least:

- model version
- scenario parameter values
- number of runs
- planned project duration
- random seed
- disruption probability
- main assumptions about task sizing and PPC
- whether results are exploratory or calibrated

Avoid presenting the model output as validated prediction unless it has been calibrated and tested against empirical project data.

## Current conceptual status

The current model structure represents:

```text
DVM scenario
→ information quality and access
→ situational awareness
→ make-ready quality
→ weekly completion promises
→ PPC
→ backlog and carryover
→ supervisor workload and firefighting
→ disruption recovery
→ actual project completion
```

This causal chain is intentionally simplified, but it provides a basis for experimenting with how digital visual management may influence construction production reliability.
