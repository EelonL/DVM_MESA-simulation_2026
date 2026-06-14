# DVM-ABM simulator

Agent-based simulation model for exploring how different forms of Digital Visual Management (DVM) may influence production reliability, weekly planning reliability, supervisor workload, making-do, disruption recovery and project completion in construction workface production.

The model is implemented in Python with Mesa-style agent-based modelling logic and a Streamlit user interface. It is intended for research, teaching and exploratory model-based reasoning. It is not a validated production-planning engine and should not be used to forecast a real project without calibration and validation.

## Current version

Current integrated model state:

```text
v25.8 — Supervisor visualization update
```

The latest state combines these major development steps:

| Version | Main change |
|---|---|
| v25.3 | Project-time aggregate metrics, improved idle-time units, dynamic supervisor capacity and sensitivity-harness timing. |
| v25.4 | Supervisor field-interaction logic added: supervision interpreted as site-based worker interaction and support time. |
| v25.5 | Supervisor time-allocation calibration corrected to avoid double-counting administrative/reporting load. |
| v25.6 | PPC and planned/actual duration alignment corrected. PPC is calculated over the observed project period during which tasks remain. |
| v25.7 | `field_interaction_demand_multiplier` added for targeted threshold tests of supervisor field-support bottlenecks. |
| v25.8 | Supervisor tab visualisation updated to show current time-allocation and field-support metrics instead of obsolete legacy workload charts. |

The Streamlit cache key in the current `app.py` is:

```python
APP_DATA_VERSION = "v25_8_supervisor_visualization_update"
```

After uploading changes to Streamlit Community Cloud, use:

```text
Manage app → Clear cache → Reboot
```

## Purpose of the model

The simulator compares alternative DVM and visual management configurations under the same simulated project workload, resource constraints and disruption environment.

The guiding research question is:

> Under what conditions does Digital Visual Management support or harm production reliability at the construction workface?

The model is especially suited for examining mechanisms such as:

- whether DVM improves workface situational awareness;
- whether crews can use information directly, or whether information is mainly visible to management;
- whether DVM reduces uncertainty and waiting, or becomes reporting and surveillance burden;
- how make-ready quality affects weekly commitments and PPC;
- how supervisor field-interaction capacity affects crew progress;
- how making-do and constraint debt may influence later disruption and rework;
- how alternative ready-work switching helps recovery from disruptions.

## Main scenarios

The default model compares five DVM / visual management configurations.

| Scenario key | Display name | Interpretation |
|---|---|---|
| `analog_vm` | Analog visual management | Traditional visual planning and coordination with limited digital support. |
| `management_dashboard` | Management dashboard | Information mainly supports management visibility; weaker direct support for crews. |
| `forced_reporting_dvm` | DVM as forced reporting | Digital system is used primarily for reporting, compliance and control. |
| `workface_dvm` | Ready work area DVM | DVM focuses on ready work areas, constraints, task status and crew usability. |
| `dvm_lean_autonomous` | Lean-autonomous DVM | DVM supports autonomous crew decisions, make-ready quality, learning and production flow. |

Scenario parameters are configured in:

```text
config/scenarios.yaml
```

The Python scenario structure is defined in:

```text
dvm_abm/scenarios.py
```

## Repository structure

Expected repository structure:

```text
DVM_MESA-simulation_2026-main/
    app.py
    requirements.txt
    config/
        scenarios.yaml
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
    sensitivity_harness_v8/
        sensitivity_harness/
            run_sensitivity.py
            sensitivity_config.yaml
            requirements_sensitivity.txt
            README_sensitivity.md
```

The exact repository may contain additional notebooks, output files or older update packages. The core Streamlit application requires `app.py`, `requirements.txt`, `config/` and `dvm_abm/`.

## Installation and local use

Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Run the Streamlit app locally:

```powershell
streamlit run app.py
```

## Streamlit Community Cloud deployment

The repository should include at least:

```text
app.py
requirements.txt
dvm_abm/
config/
```

After pushing changes to GitHub, reboot the deployed app:

```text
Manage app → Clear cache → Reboot
```

This is important because Streamlit can otherwise reuse old cached model objects, scenarios or result tables.

## User interface

The Streamlit app contains the following main tabs.

| Tab | Purpose |
|---|---|
| Overview | Key result metrics, PPC, project completion, make-ready, backlog and main charts. |
| Time series | Time-dependent development of selected production and DVM metrics. |
| Disruptions | External disruptions, recovery time, alternative task switching and external idle time. |
| Supervisor | Supervisor time allocation, field support utilisation, unresolved support and diagnostics. |
| Scenario comparison | Runs all scenarios under the same input settings for comparison. |
| Data | Shows and downloads result tables. |

The app supports Excel export for both single-scenario runs and scenario comparison runs.

## Main user inputs

The Streamlit sidebar controls the most important run settings.

| Setting | Meaning |
|---|---|
| Runs | Number of stochastic replications. |
| Planned project duration, days | Planned target duration of the project. This is not a hard stop. |
| Base seed | Random seed for reproducibility. |
| Daily external shock probability | Probability of external disruption on a given day. |
| Capture rate | How much relevant site information the DVM system captures. |
| Data accuracy | Accuracy of captured information. |
| Data timeliness | Freshness of information. |
| Data completeness | Coverage of relevant information. |
| Integration level | Degree of integration across information sources. |
| Crew access | How well crews can access and use DVM information. |
| Management access | How well management can access DVM information. |
| Visual clarity | How clearly information is represented. |
| Task relevance | How relevant the information is for actual workface decisions. |
| Autonomy | Degree to which crews can act independently based on DVM. |
| Decision centralization | Degree to which decisions remain management-centred. |
| Perceived surveillance | Degree to which DVM is experienced as monitoring/control. |
| Reporting burden | Additional administrative work caused by DVM. |
| Supervisor capacity | Supervisor working capacity parameter used in support and planning logic. |
| Initial planning quality | Initial reliability of make-ready and production planning. |
| Maximum active crews | Peak active crew capacity in the project. |
| Peak resource fit | How well available resources match peak workload. |

## Core model logic

### 1. Planned duration and actual duration

The input `Planned project duration, days` is the planned target duration. It is not a simulation stop.

The simulation continues until:

```text
all tasks are complete
```

or until a technical safety limit is reached.

Project delay is calculated as:

```text
project_delay_days = max(0, actual_project_finish - planned_project_duration)
```

If the project finishes before the planned completion day, the project finishes early. The model does not force the simulation to continue just because the planned duration has not yet ended.

### 2. Baseline task plan

The model creates a baseline task plan over the planned project duration. If planned duration is 100 days, planned task completions are distributed over approximately those 100 days.

This avoids the earlier artefact where the baseline plan ended before the planned project duration and made otherwise reasonable project completion appear late in PPC terms.

### 3. Task states

Tasks move through simplified production states, for example:

```text
NOT_READY
READY
IN_PROGRESS
INTERRUPTED
COMPLETED
```

Each task has a planned finish and actual progress. The model tracks whether tasks are ready, started, interrupted, completed, late or carried over.

### 4. Make-ready and constraints

Each task has make-ready prerequisites such as:

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

The share of satisfied prerequisites forms a make-ready score. A task is considered sound when its make-ready score meets the scenario threshold and its predecessor logic is valid.

### 5. Weekly commitments and PPC

The model uses Last Planner style weekly commitments.

A weekly commitment means:

```text
A task is promised to be completed during the week.
```

PPC is calculated as the average of weekly PPC values over the observed project period:

```text
weekly_ppc = completed promised weekly tasks / promised weekly tasks
avg_weekly_ppc = average of weekly PPC values
```

The PPC horizon follows the actual project observation period:

- if the project finishes early, PPC is calculated until the week when the last task is completed;
- if the project finishes late, PPC continues until all tasks are completed;
- future weeks after actual project completion are not added to the PPC denominator.

The model also reports:

```text
aggregate_ppc = total successful weekly promises / total weekly promises
```

`avg_weekly_ppc` is the primary PPC metric. `aggregate_ppc` is a diagnostic comparator.

### 6. Carryover and backlog

If a promised task is not completed in its committed week, it can become carryover. Carryover tasks may be recommitted in later weeks, but the model limits repeated denominator inflation from the same delayed task.

Key outputs include:

```text
open_schedule_backlog
mean_open_schedule_backlog
max_open_schedule_backlog
cumulative_plan_failures
late_completed_tasks
avg_lateness_days
```

### 7. DVM information, situational awareness and trust

DVM quality is represented through information capture, accuracy, timeliness, completeness, integration, visibility, access and user fit.

Simplified causal chain:

```text
DVM scenario
→ information quality and access
→ crew and management picture quality
→ situational awareness
→ make-ready quality
→ weekly commitments
→ PPC and project completion
```

DVM can also have negative effects through:

```text
reporting burden
perceived surveillance
decision centralization
low task relevance
low visual clarity
```

### 8. Supervisor time allocation

The current model treats supervision as limited site-based worker interaction and support time, not passive inspection.

Supervisor time is divided into:

```text
field interaction / worker support
planning
admin and reporting
reactive problem handling
```

The model uses two stylised supervisor roles:

| Role | Interpretation |
|---|---|
| Trade supervisor | One supervisor per active trade / discipline. |
| Site manager | One site manager coordinating the whole site. |

Empirical anchoring is based on construction site management time-allocation studies. In the model, field interaction limits how much worker support, coordination, problem solving and immediate guidance can be provided during a day.

Important supervisor metrics:

```text
supervisor_count_today
trade_supervisor_count_today
site_manager_count_today
effective_supervisor_capacity_today
field_interaction_capacity_hours_per_day
field_interaction_demand_hours_per_day
baseline_field_interaction_demand_hours_per_day
field_interaction_used_hours_per_day
field_interaction_hours_per_supervisor_day
field_interaction_hours_per_active_crew_day
field_support_utilization
unresolved_field_support_hours_per_day
planning_hours_per_day
planning_hours_per_supervisor_day
admin_reporting_hours_per_day
admin_reporting_hours_per_supervisor_day
supervisor_utilization
```

If field-interaction demand exceeds capacity, unresolved field support may increase crew waiting, slow progress and increase the risk of making-do or carryover.

### 9. Making-do and rework

A task may be started before all prerequisites are properly ready. This is treated as making-do.

Making-do can cause:

```text
interruptions
additional coordination demand
rework
lost productivity
future instability
```

Relevant outputs:

```text
making_do_starts
cumulative_making_do_starts
making_do_interruptions
cumulative_making_do_interruptions
rework_due_to_making_do
cumulative_rework_due_to_making_do
```

The current model activates making-do, but its long-term consequences are still exploratory and should be interpreted cautiously unless further calibrated.

### 10. External disruptions and recovery

The model includes external disruptions such as material shortages, logistics delays, lifting delays, missing design information, unavailable equipment and weather-related disruptions.

DVM may support recovery by improving:

```text
constraint visibility
alternative ready-work visibility
crew situational awareness
supervisor coordination
```

Relevant outputs include:

```text
external_disruptions
active_external_blockages
avg_recovery_time
alternative_task_switches
failed_task_switches
external_idle_time_hours_per_day
external_idle_time_hours_per_active_crew_day
supervisor_recovery_interventions
```

## Main output metrics

### Production and schedule

| Metric | Meaning |
|---|---|
| `completed_tasks` | Number of completed tasks. |
| `remaining_tasks` | Number of unfinished tasks. |
| `actual_project_finish` | Actual final completion day when all tasks are complete. |
| `project_delay_days` | Delay relative to planned project duration. |
| `avg_weekly_ppc` | Average of weekly PPC values over the observed project period. |
| `aggregate_ppc` | Total successful weekly promises divided by total weekly promises. |
| `avg_lateness_days` | Average lateness of completed tasks. |
| `late_completed_tasks` | Number of tasks completed after planned finish. |
| `open_schedule_backlog` | Current number of tasks behind planned finish. |
| `mean_open_schedule_backlog` | Mean open backlog over project time. |
| `max_open_schedule_backlog` | Maximum open backlog over project time. |

### Workface and DVM

| Metric | Meaning |
|---|---|
| `avg_sa` | Average crew situational awareness. |
| `workface_picture_quality` | Quality of workface-level picture. |
| `management_picture_quality` | Quality of management-level picture. |
| `workface_gap` | Difference between management and workface visibility. |
| `trust_in_data` | Trust in DVM data. |
| `trust_in_management` | Trust in management. |
| `avg_adoption` | Average adoption of DVM. |
| `avg_effective_use` | Effective use of DVM. |
| `avg_make_ready_score` | Current average make-ready score. |
| `mean_make_ready_score_over_project` | Project-time average make-ready score. |
| `min_make_ready_score_over_project` | Lowest make-ready score during project. |

### Supervisor

| Metric | Meaning |
|---|---|
| `field_support_utilization` | Share of field-support capacity used. |
| `field_interaction_capacity_hours_per_day` | Available supervisor field-interaction capacity per day. |
| `field_interaction_demand_hours_per_day` | Demand for supervisor field interaction per day. |
| `field_interaction_used_hours_per_day` | Actual field-interaction time used. |
| `unresolved_field_support_hours_per_day` | Unresolved worker-support demand after available capacity. |
| `planning_hours_per_supervisor_day` | Planning hours per supervisor day. |
| `admin_reporting_hours_per_supervisor_day` | Admin/reporting hours per supervisor day. |
| `supervisor_utilization` | Overall supervisor utilisation. |
| `supervisor_backlog` | Legacy diagnostic backlog metric. |
| `firefighting_ratio` | Legacy diagnostic ratio for reactive effort. |

### Idle time and disruptions

| Metric | Meaning |
|---|---|
| `idle_time_hours_per_day` | Total idle time per project day. |
| `idle_time_hours_per_active_crew_day` | Idle hours per active crew day. |
| `external_idle_time_hours_per_day` | Idle time caused by external disruptions per day. |
| `external_idle_time_hours_per_active_crew_day` | External disruption idle time per active crew day. |
| `avg_recovery_time` | Average time to recover from external disruptions. |
| `alternative_task_switches` | Successful switches to alternative ready work. |
| `failed_task_switches` | Failed switches to alternative ready work. |

## Scenario comparison

The Scenario comparison tab runs all default scenarios under the same user inputs. This is the recommended mode for comparing DVM configurations because the scenarios are exposed to the same general simulation conditions.

Recommended interpretation:

```text
Compare relative differences between scenarios, not single absolute values.
```

Useful comparison metrics:

```text
actual_project_finish
project_delay_days
avg_weekly_ppc
idle_time_hours_per_active_crew_day
external_idle_time_hours_per_active_crew_day
field_support_utilization
admin_reporting_hours_per_supervisor_day
cumulative_making_do_starts
mean_open_schedule_backlog
```

## Excel exports

The app exports Excel workbooks with sheets such as:

| Sheet | Content |
|---|---|
| `metadata` | Run settings and timestamp. |
| `summary` or `scenario_summary` | Aggregated final metrics. |
| `final_run_metrics` | One final row per run. |
| `timeseries` | Full time series for each run. |

Sensitivity harness exports include additional sheets, for example:

```text
Run timing
Screening correlations
Threshold summary
```

## Sensitivity harness

The repository may include the standalone sensitivity test harness:

```text
sensitivity_harness_v8/sensitivity_harness/
```

The harness runs model batches outside Streamlit and writes CSV, Excel and PNG outputs.

Go to the harness folder:

```powershell
cd "C:\path\to\sensitivity_harness_v8\sensitivity_harness"
```

Run interactively:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main"
```

Run a preset directly:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset screening
```

Useful presets:

| Preset | Purpose |
|---|---|
| `smoke` | Quick sanity test. |
| `screening` | Broader screening run for parameter influence. |
| `screening_large` | Larger screening run. |
| `threshold_focus` | Targeted 2D threshold tests. |
| `standard` | Larger combined test package. |
| `full` | Extensive test package. |
| `config` | Use settings from the YAML config file. |

### Targeted threshold tests

The current v8 harness includes these mechanism-focused threshold tests:

| Test | Purpose |
|---|---|
| `reporting_burden × autonomy_level` | Identifies when DVM shifts from support to administrative/control burden. |
| `overcommitment_tendency × commitment_realism` | Tests when unrealistic weekly commitments collapse PPC. |
| `supervisor_capacity × field_interaction_demand_multiplier` | Tests when supervisor field support becomes a bottleneck. |

The third test requires the v25.7 model patch because it uses:

```text
field_interaction_demand_multiplier
```

Default value is `1.0`, so normal behaviour is unchanged unless the sensitivity harness overrides the parameter.

## Typical research workflow

1. Run the Streamlit app locally or in Streamlit Cloud.
2. Inspect one scenario in the Overview, Time series, Disruptions and Supervisor tabs.
3. Run Scenario comparison with the same project settings.
4. Download Excel results.
5. Run a `smoke` sensitivity test to verify that the local model works.
6. Run `screening` or `screening_large` to identify influential parameters.
7. Run `threshold_focus` to inspect selected mechanism thresholds.
8. Interpret relative scenario differences and mechanism behaviour.
9. Document model version, parameter values, random seed, number of runs and planned project duration.
10. Avoid interpreting the model as a validated forecast unless empirical calibration has been performed.

## Model interpretation

The model should be used to reason about patterns such as:

- whether crew-facing DVM improves PPC and reduces project delay;
- whether management-only dashboards improve visibility without improving workface reliability;
- whether forced reporting increases administrative workload and supervisor utilisation;
- whether autonomy and task relevance reduce unnecessary supervisor field-support demand;
- whether overcommitment undermines PPC;
- whether resource fit dominates project duration;
- whether making-do activates under poor make-ready conditions;
- whether external disruption idle time can be reduced through alternative ready-work switching.

The most credible outputs are comparative and directional, not exact forecasts.

## Development notes

### Cache versioning

After any structural change to model reporters, scenario fields, dataclasses or result columns, update:

```python
APP_DATA_VERSION = "..."
```

Then clear Streamlit cache.

### Scenario compatibility

The app contains fallback logic for older cached scenario objects and missing result columns. This prevents UI crashes during development but may hide whether a metric is produced by the model or added later as a fallback. If a new metric stays zero in all runs, check the model reporters and not only the UI.

### Updating files

Typical Git workflow:

```powershell
git status
git add app.py dvm_abm/model.py dvm_abm/agents.py dvm_abm/scenarios.py config/scenarios.yaml
git commit -m "Update DVM ABM model"
git push
```

Then in Streamlit Cloud:

```text
Manage app → Clear cache → Reboot
```

## Limitations

This is an exploratory simulation model.

Important limitations:

- Parameters are stylised and require calibration.
- The model is not validated against a specific real project.
- Tasks are simplified weekly-sized work packages.
- Trade and crew behaviour are simplified.
- Human behaviour, trust, autonomy and surveillance are represented through parameterised rules.
- PPC and make-ready are model constructs rather than direct empirical observations.
- Supervisor time allocation is empirically anchored but not project-specifically measured.
- Making-do consequences are still exploratory and may require stronger calibration.
- Results should be reported as simulated patterns, not as measured construction productivity effects.

## AI use and verification

If the repository includes an AI-use disclosure file, it can be placed at:

```text
AI_USE_AND_VERIFICATION.md
```

Recommended disclosure:

```text
Generative AI tools were used as research support during the study, particularly for drafting and debugging Python code, documenting model parameters, designing visualisations, structuring the sensitivity testing workflow, and preparing preliminary text drafts. All AI-generated suggestions were reviewed, modified, and verified by the author. The author remains fully responsible for the model design, methodological choices, analysis, interpretation of results, and final manuscript.
```

## References for model assumptions

The model draws conceptually on the following research streams:

- Last Planner System and Percent Plan Complete.
- Lean construction, make-ready planning and production reliability.
- Making-do and constraint management.
- Construction site management and supervisor time allocation.
- Situational awareness and visual management.
- Agent-based modelling and sensitivity analysis.

Suggested project-specific references include:

- Lappalainen et al. (2023): Planned Percentage Completed in Construction — a quantitative review of literature.
- Marjasalo, Koskenvesa, Tolonen & Koskela: Time allocation of site management.
- Shohet & Laufer (1991): What does the construction foreman do?
- Grimm et al.: ODD protocol and agent-based model documentation.
- Saltelli et al.: Sensitivity analysis.
- Ligmann-Zielinska et al. and Borgonovo et al.: sensitivity analysis in agent-based modelling.

## Current conceptual chain

The simplified causal logic of the current model is:

```text
DVM configuration
→ information quality, access and task relevance
→ crew situational awareness and trust
→ make-ready quality and sound commitments
→ weekly PPC
→ carryover, backlog and idle time
→ supervisor field support and planning capacity
→ disruption recovery and alternative task switching
→ actual project completion
```

A central modelling assumption is that DVM is not inherently beneficial. Its effect depends on whether it supports workface decisions and make-ready reliability or instead adds reporting burden, surveillance pressure and management-centred visibility without improving crew actionability.
