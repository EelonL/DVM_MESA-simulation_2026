# v25.9 role-calibrated field-support capacity update

This update refines the supervisor time-allocation logic and targeted threshold tests.

## Main changes

1. Site manager supervision time is no longer treated as full direct crew-facing field support.
   - Trade supervisor direct field interaction share: 40% of the workday.
   - Site manager direct crew-facing field interaction share: 15% of the workday.
   - Site manager supervisor/site-management coordination share: 10% of the workday.
   - Site manager planning share remains 16%.

2. The empirical time-allocation anchor is preserved. The site manager's earlier 25% supervision share is split into 15% direct crew support and 10% coordination with trade supervisors.

3. A new virtual sensitivity parameter was added:

```text
field_interaction_capacity_multiplier
```

Default: 1.0. Normal Streamlit/baseline behaviour is unchanged except for the site-manager role calibration. Threshold tests can vary this parameter to test when field-support capacity becomes a bottleneck.

4. The third threshold_focus test is changed from:

```text
supervisor_capacity × field_interaction_demand_multiplier
```

to:

```text
field_interaction_capacity_multiplier × field_interaction_demand_multiplier
```

This directly tests field-support capacity versus field-support demand.

## Files to replace

Replace these in the model repository:

```text
app.py
dvm_abm/model.py
dvm_abm/agents.py
```

Use `sensitivity_harness_v9/sensitivity_harness` for the updated threshold tests.

## Streamlit Cloud

After pushing to GitHub, use:

```text
Clear cache → Reboot
```

The Streamlit cache key is now:

```python
APP_DATA_VERSION = "v25_9_role_calibrated_field_capacity"
```

## Suggested next run

```powershell
py run_sensitivity.py --model-dir "C:\...\DVM_MESA-simulation_2026-main" --preset threshold_focus
```

Or run interactively and choose option 4.
