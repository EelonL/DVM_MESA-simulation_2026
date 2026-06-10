# DVM-ABM v24.7 update

This update changes the meaning of the user-defined project duration.

## Main change

`Planned project duration, days` is now the planned completion target of the project, not the simulation cutoff.

The simulation continues until:
1. all tasks are complete, or
2. a safety hard limit is reached: `max(planned_duration * 4, planned_duration + 200)`.

## Consequences

- `project_delay_days` is now realized delay when the project completes:
  `actual_project_finish - planned_project_duration`
- Scenario delay comparisons should now show real differences between scenarios.
- A project planned for 100 days may finish at day 105, 130, 180, etc.
- `remaining_tasks` and `actual_project_finish` are included in outputs.

## Files to replace

- `app.py`
- `dvm_abm/model.py`
- `dvm_abm/analysis.py`

The other files are included for consistency.

## Git commands

```bash
git add app.py dvm_abm/model.py dvm_abm/analysis.py
git commit -m "Run simulation until all tasks are complete"
git push
```

Then in Streamlit Cloud:
`Manage app -> Clear cache -> Reboot`
