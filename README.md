# DVM-ABM v24.4 update

This update implements the modelling changes discussed after reviewing the PPC and supervisor workload charts.

## Main changes

### 1. Supervisor base workload
The supervisor now has worker-independent daily base workload:
- general administration
- reporting to management
- procurement/order administration
- invoice/order handling proxy
- authority/safety documentation
- meetings
- DVM reporting burden

This workload consumes capacity before proactive planning can happen.

### 2. Planning is no longer unlimited
Unused supervisor capacity is no longer automatically converted into planning time. The model now uses `planning_need_per_day`, so planning time is capped and planning shortfall is tracked.

### 3. Stronger PPC / ready work area mechanism
Weekly PPC now depends more strongly on:
- ready work area picture quality
- readiness visibility
- planning quality
- open schedule backlog
- supervisor backlog

Backlog now also reduces production progress, so plan failures can accumulate and delay the project.

### 4. Stronger supervisor load mechanism
Poor information quality, low ready work area visibility, centralised decision-making and backlog now create baseline coordination needs even when crews do not explicitly ask questions.

### 5. Updated scenario configuration
`config/scenarios.yaml` includes new supervisor workload parameters. Forced reporting DVM has the highest reporting/admin burden; ready work area and lean-autonomous DVM reduce some admin/manual coordination burden.

## Files to replace

- `app.py`
- `dvm_abm/model.py`
- `dvm_abm/agents.py`
- `dvm_abm/scenarios.py`
- `config/scenarios.yaml`

## Git commands

```bash
git add app.py dvm_abm/model.py dvm_abm/agents.py dvm_abm/scenarios.py config/scenarios.yaml
git commit -m "Add supervisor base workload and stronger PPC dynamics"
git push
```

Then in Streamlit Cloud:

`Manage app -> Clear cache -> Reboot`
