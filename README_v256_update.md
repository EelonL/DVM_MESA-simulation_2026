# DVM-ABM v25.6 update: planned/actual duration alignment and weekly PPC

This update corrects the interpretation of planned project duration, actual completion, and PPC.

## Main modelling changes

1. Planned task completions are now stretched to the full planned project duration.
   - If the planned project duration is 100 days, the baseline task distribution reaches day 100.
   - This prevents the baseline from accidentally ending early because of random workload sampling.

2. PPC is now calculated only over observed active project weeks.
   - If all tasks finish before the planned project finish, PPC stops at the actual completion week.
   - If the project is late, PPC continues until all tasks are completed.
   - Future planned weeks are not added to the PPC denominator after the project has already finished.

3. `avg_weekly_ppc` is now the average of weekly PPC values.
   - This matches the interpretation of PPC as a weekly plan reliability measure.
   - The previous aggregate ratio is retained as `aggregate_ppc` for diagnostics.

4. `total_ppc_promises` and `total_ppc_successes` are still exported.
   - They are now calculated over the observed project period, not automatically until the planned project duration.

## Files to replace

Replace these files in the model repository:

```text
app.py
dvm_abm/model.py
dvm_abm/agents.py
```

The `agents.py` file is unchanged from v25.5 but is included for a complete replacement package.

## Streamlit cache

The Streamlit cache version has been updated to:

```python
APP_DATA_VERSION = "v25_6_ppc_observed_duration_alignment"
```

After deployment, clear cache and reboot the app.

## Sensitivity harness

The sensitivity harness is included as:

```text
sensitivity_harness_v6/sensitivity_harness/
```

Changes:

- `aggregate_ppc` added to output metrics.
- `screening` preset increased to 80 samples × 2 runs per sample.
- `standard` preset increased to 150 samples × 2 runs per sample.
- The static YAML config now includes the supervisor field-interaction metrics and `aggregate_ppc`.

Suggested next tests:

```powershell
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset smoke --estimate-only
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset smoke
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset screening
```

Use `--preset standard` only after smoke and screening outputs look plausible.
