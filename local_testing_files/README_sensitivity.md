# DVM-ABM sensitivity harness v8 — targeted thresholds

This version adds an interactive targeted threshold preset for the three mechanism tests selected after the v25.6 screening run:

1. `reporting_burden × autonomy_level`
   - tests when DVM becomes administrative/control burden instead of workface support.
2. `overcommitment_tendency × commitment_realism`
   - tests when Last Planner commitments collapse PPC.
3. `field_interaction_capacity_multiplier × field_interaction_demand_multiplier`
   - tests when supervisor field support becomes a bottleneck.

## Important

The third test requires the v25.7 `model.py` patch because `field_interaction_demand_multiplier` is a new virtual sensitivity parameter. The default value is `1.0`, so normal v25.6 behaviour is unchanged unless the sensitivity harness overrides it.

## Recommended run

From this folder:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main"
```

In the interactive menu, choose:

```text
4
```

This runs `threshold_focus`.

You can also run it directly:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset threshold_focus
```

## Outputs

In addition to the previous files, v8 writes:

- `threshold_summary.csv`
- Excel sheet `Threshold summary`
- threshold heatmap PNGs in `plots/`

Key metrics to inspect:

- `avg_weekly_ppc`
- `project_delay_days`
- `field_support_utilization`
- `unresolved_field_support_hours_per_day`
- `admin_reporting_hours_per_supervisor_day`
- `cumulative_making_do_starts`
