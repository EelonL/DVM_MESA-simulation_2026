# DVM ABM v25.8 — Supervisor visualization update

This update changes only the Streamlit visualization code (`app.py`).

## Purpose

The Supervisor tab has been updated to match the current supervisor time-allocation logic:

- replaces the obsolete **Cumulative supervisor workload** chart
- keeps legacy supervisor backlog and firefighting ratio as diagnostics in an expander
- adds a main chart for daily supervisor time allocation:
  - field interaction used, h/day
  - planning, h/day
  - admin/reporting, h/day
  - field support capacity, h/day
  - field support demand, h/day
- adds a main chart for field support utilization over time
- replaces the main backlog chart with unresolved field support hours over time

## Files to replace

Replace this file in your Streamlit app repository:

```text
app.py
```

No model logic changes are included in this patch.

## Streamlit Cloud

After uploading the new `app.py`, use:

```text
Clear cache -> Reboot
```

The cache key in `app.py` is now:

```python
APP_DATA_VERSION = "v25_8_supervisor_visualization_update"
```
