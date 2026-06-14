# Local sensitivity-test harness for DVM-ABM

This package adds a command-line sensitivity-test harness for the DVM-ABM model. It is meant to be run locally, outside Streamlit.

## Files

```text
run_sensitivity.py        # standalone local runner
sensitivity_config.yaml   # editable test design
requirements_sensitivity.txt
```

## Install dependencies

From your normal model environment:

```powershell
py -m pip install pandas openpyxl pyyaml matplotlib
```

If the model itself needs Mesa and Streamlit dependencies, install them as usual from the main project `requirements.txt`.

## First run

Place these files anywhere, for example in a separate folder called `sensitivity_tools`.

Then run:

```powershell
py run_sensitivity.py
```

The script asks for the folder that contains the ABM model, for example:

```text
C:\Users\...\dvm_mesa-simulation_2026
```

That folder should contain:

```text
app.py
dvm_abm/
config/scenarios.yaml
```

## Run with command-line arguments

```powershell
py run_sensitivity.py --model-dir "C:\path\to\dvm_mesa-simulation_2026"
```

Run only one test mode:

```powershell
py run_sensitivity.py --model-dir "C:\path\to\model" --mode sanity
py run_sensitivity.py --model-dir "C:\path\to\model" --mode ofat
py run_sensitivity.py --model-dir "C:\path\to\model" --mode threshold
py run_sensitivity.py --model-dir "C:\path\to\model" --mode screening
```

## Outputs

The script creates a timestamped folder inside the selected model folder:

```text
sensitivity_results/YYYYMMDD_HHMMSS/
```

The main output is:

```text
dvm_abm_sensitivity_results_YYYYMMDD_HHMMSS.xlsx
```

The workbook includes:

```text
README
Run settings
Summary
Sanity flags
OFAT effects
Screening corr
Final run metrics
Parameter ranges
Config YAML
```

Raw CSV files and PNG plots are also saved if enabled in `sensitivity_config.yaml`.

## Recommended workflow

1. Change model code or `scenarios.yaml`.
2. Run `py run_sensitivity.py --model-dir "..." --mode sanity`.
3. If sanity checks look reasonable, run `--mode ofat`.
4. If the model is stable, run `--mode threshold` or `--mode screening`.
5. Save the resulting folder with the model version or Git commit hash.

## Notes

The harness imports the model from the folder selected at runtime. This makes it possible to test different model versions simply by pointing the runner to different folders.

The script currently uses:

- sanity checks
- one-factor-at-a-time testing
- two-parameter threshold grids
- Latin Hypercube screening with rank correlations

It is intentionally a first robust version, not a full Sobol/Morris implementation. Sobol or Morris can be added later after the model has stabilised and the most important parameters have been screened.
