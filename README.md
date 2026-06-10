# DVM-ABM v24.6 update

This update adds the LPS core logic discussed in the chat:
make-ready constraints, weekly commitments, PPC based on commitments, and making-do.

## Main additions

### 1. LPS prerequisite constraints
Each task now has eight prerequisites:
- design_ready
- material_ready
- crew_ready
- equipment_ready
- space_ready
- predecessor_ready
- approval_ready
- safety_quality_ready

These form a `make_ready_score`.

### 2. Weekly commitments
At the beginning of each simulation week the model creates LPS weekly commitments.
PPC is now calculated as:

`completed committed tasks / weekly committed tasks`

Baseline adherence remains separate from PPC.

### 3. Making-do
In poorer scenarios, tasks may be started even when not all prerequisites are ready.
Making-do increases:
- interruptions
- rework
- supervisor coordination needs
- risk of PPC failure

### 4. Scenario differences
Scenarios now differ in:
- constraint screening strength
- make-ready threshold
- commitment realism
- overcommitment tendency
- making-do tendency
- making-do interruption and rework effects

## Files to replace

- `app.py`
- `dvm_abm/model.py`
- `dvm_abm/agents.py`
- `dvm_abm/scenarios.py`
- `config/scenarios.yaml`

## Git commands

```bash
git add app.py dvm_abm/model.py dvm_abm/agents.py dvm_abm/scenarios.py config/scenarios.yaml
git commit -m "Add LPS constraints weekly commitments and making-do"
git push
```

Then in Streamlit Cloud:
`Manage app -> Clear cache -> Reboot`
