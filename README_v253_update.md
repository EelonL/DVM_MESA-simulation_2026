# DVM-ABM v25.3 update

This update contains two parts:

1. Simulation model updates
2. Local sensitivity harness v3

## Simulation model changes

Replace these files in your model repository:

```text
app.py
dvm_abm/model.py
dvm_abm/agents.py
```

Main model changes:

- Adds idle-time interpretation metrics in hours:
  - `idle_time_hours_per_day`
  - `idle_time_hours_per_active_crew_day`
  - `external_idle_time_hours_per_day`
  - `external_idle_time_hours_per_active_crew_day`
  - `idle_time_due_to_external_disruptions_hours_per_day`
  - `idle_time_due_to_external_disruptions_hours_per_active_crew_day`
- Adds cumulative active crew days.
- Adds a simplified dynamic supervisor staffing rule:
  - one trade supervisor per active discipline/trade;
  - one site manager above trade supervisors;
  - the existing SupervisorAgent is used as an aggregate capacity resource;
  - daily supervisor capacity = supervisor count × supervisor capacity per person.
- Adds reporting metrics:
  - `trade_supervisor_count_today`
  - `site_manager_count_today`
  - `supervisor_count_today`
  - `effective_supervisor_capacity_today`
  - `supervisor_capacity_per_person`
- Adds project-period aggregate metrics for sensitivity analysis:
  - `mean_open_schedule_backlog`
  - `max_open_schedule_backlog`
  - `mean_make_ready_score_over_project`
  - `min_make_ready_score_over_project`
  - `mean_supervisor_backlog`
  - `max_supervisor_backlog`
  - `mean_firefighting_ratio`
  - `max_firefighting_ratio`
- Makes making-do easier to activate in stress tests by allowing committed but not-yet-sound tasks to enter the risky task candidate set.
- Updates `APP_DATA_VERSION` to force Streamlit cache refresh.

## Sensitivity harness v3 changes

Run from:

```text
sensitivity_harness_v3/sensitivity_harness/run_sensitivity.py
```

Main harness changes:

- Prints estimated model-run count before execution.
- Asks for confirmation unless `--yes` is used.
- Supports `--estimate-only`.
- Records individual model-run start time, finish time and duration.
- Records whole batch start time, finish time and duration.
- Adds a `Run timing` sheet to Excel.
- Adds `extreme_making_do` sanity check.
- Avoids NumPy warnings when screening correlations have constant columns.
- Adds new idle-time and aggregate metrics to the default key metrics.

Recommended first run:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset smoke --estimate-only
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset smoke
```

Then:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset screening
```

Use larger presets only after reviewing runtime and smoke-test results.
