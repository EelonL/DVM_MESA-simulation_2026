# v25.1 actual-completion-aligned PPC

Replace:
- app.py
- dvm_abm/model.py

Main correction:
- PPC is now calculated as total successful weekly completion promises / total weekly completion promises.
- Tasks that actually complete in week W are included in week W's completion promises.
- This prevents completed tasks from being left outside the PPC denominator and should make PPC consistent with project completion.
