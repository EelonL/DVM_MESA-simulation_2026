# DVM-ABM v25.4 update: supervisor field interaction and planning time allocation

This update changes the supervisor logic from a generic capacity bottleneck into a role-based time allocation model.

## Files to replace in the model repository

Copy these files into the root of the DVM-ABM repository:

```text
app.py
dvm_abm/model.py
dvm_abm/agents.py
```

## Main conceptual change

Supervisor time is now split into three practical time budgets:

1. **Field interaction / worker support**: time spent with crews on site, including instructions, workface checks, local coordination, quality/safety checks and resolving practical problems.
2. **Proactive planning**: time used for make-ready planning, preparation, schedule control and future constraint removal.
3. **Admin, meetings and reporting**: time consumed away from direct crew support or proactive planning.

The model still uses one aggregate `SupervisorAgent`, but its daily capacity is built from a role rule:

```text
one trade supervisor per active trade
+ one site manager
```

The role-based time shares use empirical anchors from site-management time-use studies:

```text
trade supervisor / foreman:
  field interaction / supervision = 40%
  planning = 14%

site manager / general superintendent:
  field interaction / supervision = 25%
  planning = 16%
```

## New same-day crew support mechanism

The active crews create field-interaction demand through routine supervision, questions, escalations, coordination needs, recovery interventions and making-do consequences.

If demand exceeds available field-interaction capacity, the unresolved support is converted into additional crew waiting time on the same day. It also increases supervisor backlog and response delay, and can reduce future planning quality.

This creates two separate but connected mechanisms:

```text
same-day production flow:
field interaction capacity -> worker support -> crew progress / idle time

future production reliability:
planning time -> planning quality -> make-ready -> PPC / carryover
```

## New output metrics

The model now reports, among others:

```text
field_interaction_capacity_hours_per_day
field_interaction_demand_hours_per_day
baseline_field_interaction_demand_hours_per_day
field_interaction_used_hours_per_day
field_interaction_hours_per_supervisor_day
field_interaction_hours_per_active_crew_day
unresolved_field_support_hours_per_day
unresolved_field_support_hours_per_active_crew_day
field_support_utilization
mean_field_support_utilization
planning_hours_per_day
planning_hours_per_supervisor_day
admin_reporting_hours_per_day
admin_reporting_hours_per_supervisor_day
mean_supervisor_count_over_project
max_supervisor_count_over_project
```

## Streamlit

`APP_DATA_VERSION` has been updated to force cache refresh:

```python
APP_DATA_VERSION = "v25_4_field_interaction_supervisor_time"
```

After copying the files to Streamlit Cloud, clear cache and reboot the app.

## Sensitivity harness

The sensitivity harness has been updated to include the new supervisor field-support metrics in the default key metrics and plots.

Use:

```powershell
cd sensitivity_harness_v4\sensitivity_harness
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset smoke --estimate-only
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset smoke
```

Then, if the smoke run looks reasonable:

```powershell
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset screening
```
