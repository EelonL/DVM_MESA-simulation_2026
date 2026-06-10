# DVM-ABM v2.4 update

This update adds a more realistic weekly PPC and delay/backlog logic.

## Replace these files

- `app.py`
- `dvm_abm/model.py`
- `dvm_abm/agents.py`

## Main changes

### Weekly PPC

PPC is now calculated as weekly plan reliability:

```text
weekly PPC = tasks planned to finish in a week and completed by week end / tasks planned to finish in that week
```

The old `ppc_proxy` column is retained as a backwards-compatible alias, but it now reports `avg_weekly_ppc` rather than final cumulative completion.

### Carryover and delay

The model now reports:

- `planned_tasks_this_week`
- `completed_on_plan_this_week`
- `weekly_ppc`
- `avg_weekly_ppc`
- `last_completed_weekly_ppc`
- `weekly_carryover`
- `open_schedule_backlog`
- `cumulative_plan_failures`
- `project_delay_days`
- `avg_lateness_days`
- `late_completed_tasks`

If PPC is below 100%, unfinished planned work remains open and competes with following weeks' tasks. No automatic catch-up capacity is added.

### Streamlit UI

The first tab is now `Overview` and focuses on:

- average weekly PPC
- open schedule backlog
- project delay
- recovery time
- firefighting ratio
- external idle time
- alternative workface switching

The old PPC histogram and `Crew SA vs PPC proxy` scatter have been removed from the overview because they were misleading.

## Deploy

```bash
git add app.py dvm_abm/model.py dvm_abm/agents.py
git commit -m "Add weekly PPC and schedule backlog logic"
git push
```

Then in Streamlit Cloud:

```text
Manage app -> Clear cache -> Reboot
```
