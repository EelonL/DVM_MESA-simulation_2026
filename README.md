# DVM-ABM v24.5 update

This update adds project workload and resource curves.

## Main additions

### 1. Beta-distributed planned workload
Task planned starts are no longer uniformly distributed. The planned task timing is sampled from a beta distribution, producing a more realistic project workload curve:
- low workload during mobilisation
- peak workload in the middle
- reduced workload during close-out

### 2. Variable active crew resources
The model creates a larger potential crew pool, but each day only part of it is active according to a resource curve. This creates realistic differences between:
- planned workload
- available crew capacity
- workload pressure

### 3. Workload pressure
A new metric `workload_pressure` compares planned weekly work against active crew capacity. It affects:
- ready work area availability
- production progress
- crew questions
- supervisor coordination needs
- recovery from disruptions

### 4. Streamlit visualisation
The Overview tab now includes:
- `Planned workload and active crew resources`
- new metrics for workload pressure and active crews
- sidebar controls for maximum active crews and peak resource fit

## Files to replace

- `app.py`
- `dvm_abm/model.py`
- `dvm_abm/scenarios.py`
- `config/scenarios.yaml`

`dvm_abm/agents.py` is included for completeness but is unchanged from v24.4.

## Git commands

```bash
git add app.py dvm_abm/model.py dvm_abm/scenarios.py config/scenarios.yaml
git commit -m "Add project workload and variable crew resource curves"
git push
```

Then in Streamlit Cloud:

`Manage app -> Clear cache -> Reboot`
