# v25.5 supervisor-time calibration and larger screening guidance

This update corrects an overcorrection introduced in v25.4.

## Problem observed in v25.4

The v25.4 supervisor field-interaction model made the supervisor mechanism more realistic, but it also made some scenarios produce very low PPC and very long project delays again. The main reason was that role-based administration time was double-counted:

1. The role-based time allocation already reserved a large non-field, non-planning part of the day.
2. The old scenario-specific supervisor admin/reporting workload parameters were then added again at full scale.
3. This left little or no planning time, degraded planning quality, increased carryover and reduced PPC.

## Fixes in v25.5

### 1. Administration workload no longer double-counted

The role-based admin/reporting time is now the baseline. Legacy scenario admin-load parameters are treated only as smaller site-level adjustments. This should restore planning time and reduce unrealistic delay explosions.

### 2. Routine field-interaction demand reduced

The routine field-support demand per active crew was too high in v25.4. The formula was softened so that normal crew support does not automatically consume the entire field-interaction capacity every day.

### 3. Field support idle conversion checked

Unresolved field-support hours are converted to workday-equivalent idle units before being added to crew idle time.

### 4. App cache version updated

`APP_DATA_VERSION` was updated to:

```python
APP_DATA_VERSION = "v25_5_supervisor_time_calibration"
```

After uploading to Streamlit, clear cache and reboot the app.

## Recommended next tests

Run first:

```powershell
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset smoke --estimate-only
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset smoke
```

If the smoke run looks reasonable, run a larger screening:

```powershell
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset standard
```

The standard preset should use approximately:

```text
80 samples × 2 runs/sample × 5 scenarios = 800 screening runs
```

This is more appropriate for interpreting Spearman screening correlations than the smoke test with only 10 samples.

## What to inspect after the next smoke run

Check that:

- baseline PPC is no longer around 0.30 for all weaker scenarios;
- delays are not exploding to hundreds of days under normal baseline assumptions;
- `planning_hours_per_supervisor_day` is not systematically zero;
- `field_support_utilization` is informative but not always exactly 1.0;
- `supervisor_backlog` grows only when the field/support/admin/planning demand actually exceeds available capacity;
- `idle_time_hours_per_active_crew_day` is within a more plausible range.

