# v25.2 planned baseline alignment

Replace:
- app.py
- dvm_abm/model.py

Main correction:
- Planned task finishes are distributed over the full planned project duration.
- Earlier versions compressed planned task starts into about 82% of the planned duration, which made near-on-time projects look late in PPC/task-level metrics.
- Carryover recommitment is moderated so the same unsound task does not inflate the PPC denominator indefinitely.

Expected effect:
- Near-on-time scenarios should show higher PPC.
- Low-PPC scenarios can still show pushed/colliding tasks and delayed project finish.
