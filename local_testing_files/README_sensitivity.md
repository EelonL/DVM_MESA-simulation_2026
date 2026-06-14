# DVM-ABM sensitivity harness v3

This version is optimised for local model testing and avoids accidental long runs.

Key changes compared with v2:

- prints an estimated number of individual model runs before execution;
- asks for confirmation before running unless `--yes` is used;
- records run start time, finish time and duration for each individual model run;
- records batch start time, finish time and total duration in the Excel README sheet;
- includes a separate `Run timing` sheet in the Excel output;
- adds an `extreme_making_do` sanity check;
- handles constant columns in screening correlations without NumPy warnings;
- includes new idle-time and dynamic aggregate metrics when the model provides them.

Recommended first checks:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset smoke --estimate-only
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset smoke
```

A useful next screening run:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\DVM_MESA-simulation_2026-main" --preset screening
```

Use `--yes` only when you already accept the estimated run count.
