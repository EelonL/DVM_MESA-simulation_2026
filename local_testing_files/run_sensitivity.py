"""
Local sensitivity-test harness for the DVM-ABM model.

Version v8 adds targeted threshold tests for DVM support vs control, LPS commitment realism,
and supervisor field-interaction bottlenecks.

Usage examples, Windows PowerShell:
    py run_sensitivity.py        # asks model folder and run-size preset interactively
    py run_sensitivity.py --model-dir "C:\\path\\to\\dvm_mesa-simulation_2026"
    py run_sensitivity.py --model-dir "C:\\path\\to\\model" --mode sanity
    py run_sensitivity.py --model-dir "C:\\path\\to\\model" --mode ofat --config sensitivity_config.yaml

The script intentionally runs outside Streamlit. It imports the local ABM model
from the folder selected by the user, runs sensitivity experiments, and writes
an Excel workbook plus optional CSV files into a timestamped results folder.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import importlib
import inspect
import math
import os
from pathlib import Path
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import yaml
except ImportError as exc:
    raise SystemExit("Missing dependency: PyYAML. Install with: py -m pip install pyyaml") from exc

try:
    import pandas as pd
except ImportError as exc:
    raise SystemExit("Missing dependency: pandas. Install with: py -m pip install pandas openpyxl") from exc

try:
    import matplotlib.pyplot as plt
except Exception:  # matplotlib is optional for tables; charts are skipped if unavailable
    plt = None


DEFAULT_KEY_METRICS = [
    "project_delay_days",
    "actual_project_finish",
    "avg_weekly_ppc",
    "aggregate_ppc",
    "last_completed_weekly_ppc",
    "open_schedule_backlog",
    "mean_open_schedule_backlog",
    "max_open_schedule_backlog",
    "cumulative_plan_failures",
    "avg_make_ready_score",
    "mean_make_ready_score_over_project",
    "min_make_ready_score_over_project",
    "cumulative_making_do_starts",
    "cumulative_rework_due_to_making_do",
    "supervisor_reactive_time",
    "firefighting_ratio",
    "mean_firefighting_ratio",
    "max_firefighting_ratio",
    "supervisor_backlog",
    "mean_supervisor_backlog",
    "max_supervisor_backlog",
    "supervisor_count_today",
    "effective_supervisor_capacity_today",
    "field_interaction_capacity_hours_per_day",
    "field_interaction_demand_hours_per_day",
    "field_interaction_used_hours_per_day",
    "field_interaction_hours_per_supervisor_day",
    "field_interaction_hours_per_active_crew_day",
    "unresolved_field_support_hours_per_day",
    "unresolved_field_support_hours_per_active_crew_day",
    "field_support_utilization",
    "mean_field_support_utilization",
    "planning_hours_per_day",
    "planning_hours_per_supervisor_day",
    "admin_reporting_hours_per_day",
    "admin_reporting_hours_per_supervisor_day",
    "avg_sa",
    "trust_in_data",
    "trust_in_management",
    "avg_adoption",
    "idle_time_due_to_external_disruptions",
    "idle_time_due_to_external_disruptions_hours_per_day",
    "idle_time_due_to_external_disruptions_hours_per_active_crew_day",
    "idle_time_hours_per_day",
    "idle_time_hours_per_active_crew_day",
    "external_idle_time_hours_per_day",
    "external_idle_time_hours_per_active_crew_day",
    "alternative_task_switches",
]


DEFAULT_CONFIG: Dict[str, Any] = {
    "general": {
        "planned_project_duration": 100,
        "base_seed": 20260609,
        "runs_per_case": 10,
        "daily_shock_probability": 0.32,
        "scenario_filter": "all",
        "save_timeseries": False,
        "max_workers": 1,
    },
    "outputs": {
        "key_metrics": DEFAULT_KEY_METRICS,
        "export_raw_csv": True,
        "make_plots": True,
    },
    "parameter_ranges": {
        "crew_access": [0.10, 0.95],
        "management_access": [0.10, 0.95],
        "task_relevance": [0.10, 0.95],
        "visual_clarity": [0.10, 0.95],
        "capture_rate": [0.10, 0.95],
        "data_accuracy": [0.45, 0.98],
        "data_timeliness": [0.10, 0.95],
        "reporting_burden": [0.00, 0.95],
        "perceived_surveillance": [0.00, 0.95],
        "decision_centralization": [0.00, 0.95],
        "autonomy_level": [0.05, 0.95],
        "initial_trust_in_data": [0.10, 0.95],
        "initial_trust_in_management": [0.10, 0.95],
        "constraint_screening_strength": [0.10, 0.95],
        "make_ready_threshold": [0.45, 0.95],
        "commitment_realism": [0.10, 0.95],
        "overcommitment_tendency": [0.00, 0.95],
        "making_do_tendency": [0.00, 0.95],
        "making_do_interruption_rate": [0.00, 0.70],
        "making_do_rework_factor": [0.00, 0.80],
        "supervisor_capacity": [4.0, 10.0],
        "supervisor_base_workload": [0.3, 3.0],
        "planning_need_per_day": [0.5, 4.0],
        "peak_underresource_factor": [0.45, 1.05],
        "workload_pressure_sensitivity": [0.0, 1.5],
        "field_interaction_demand_multiplier": [0.50, 3.00],
        "field_interaction_capacity_multiplier": [0.50, 2.00],
    },
    "sanity_cases": [
        {
            "name": "baseline",
            "description": "Original scenario values.",
            "overrides": {},
        },
        {
            "name": "zero_shocks",
            "description": "No external daily shocks.",
            "daily_shock_probability": 0.0,
            "overrides": {},
        },
        {
            "name": "perfect_dvm",
            "description": "High information quality, worker access and autonomy.",
            "overrides": {
                "capture_rate": 0.95,
                "data_accuracy": 0.98,
                "data_timeliness": 0.95,
                "data_completeness": 0.95,
                "integration_level": 0.95,
                "crew_access": 0.95,
                "visual_clarity": 0.95,
                "task_relevance": 0.95,
                "readiness_visibility": 0.95,
                "task_recommendation_quality": 0.95,
                "autonomy_level": 0.95,
                "reporting_burden": 0.05,
                "perceived_surveillance": 0.05,
            },
        },
        {
            "name": "high_reporting_burden",
            "description": "DVM creates reporting load and surveillance experience.",
            "overrides": {
                "reporting_burden": 0.90,
                "perceived_surveillance": 0.90,
                "compliance_pressure": 0.90,
                "task_relevance": 0.35,
                "crew_access": 0.35,
            },
        },
        {
            "name": "management_only_dashboard",
            "description": "Management sees the situation, but crews do not get useful workface access.",
            "overrides": {
                "management_access": 0.95,
                "crew_access": 0.15,
                "task_relevance": 0.20,
                "visual_clarity": 0.35,
                "autonomy_level": 0.20,
                "decision_centralization": 0.85,
            },
        },
        {
            "name": "low_resource_fit",
            "description": "Resource peak is underdimensioned relative to workload.",
            "overrides": {
                "peak_underresource_factor": 0.50,
                "max_active_crews": 5,
                "workload_pressure_sensitivity": 1.20,
            },
        },
        {
            "name": "strict_make_ready",
            "description": "Only high-readiness tasks should be promised or started.",
            "overrides": {
                "make_ready_threshold": 0.90,
                "constraint_screening_strength": 0.90,
                "making_do_tendency": 0.05,
            },
        },
        {
            "name": "loose_make_ready_high_making_do",
            "description": "Tasks are started with weak readiness and high making-do tendency.",
            "overrides": {
                "make_ready_threshold": 0.50,
                "constraint_screening_strength": 0.25,
                "making_do_tendency": 0.85,
                "making_do_interruption_rate": 0.55,
                "making_do_rework_factor": 0.60,
            },
        },
        {
            "name": "extreme_making_do",
            "description": "Stress test: risky promises and very high making-do tendency should activate making-do metrics.",
            "overrides": {
                "make_ready_threshold": 0.95,
                "constraint_screening_strength": 0.05,
                "constraint_improvement_rate": 0.01,
                "commitment_realism": 0.20,
                "overcommitment_tendency": 0.90,
                "making_do_tendency": 0.95,
                "making_do_interruption_rate": 0.70,
                "making_do_rework_factor": 0.80,
            },
        },
    ],
    "ofat": {
        "enabled": False,
        "parameters": [
            "crew_access",
            "management_access",
            "task_relevance",
            "visual_clarity",
            "capture_rate",
            "data_accuracy",
            "data_timeliness",
            "reporting_burden",
            "perceived_surveillance",
            "decision_centralization",
            "autonomy_level",
            "initial_trust_in_data",
            "initial_trust_in_management",
            "constraint_screening_strength",
            "make_ready_threshold",
            "commitment_realism",
            "overcommitment_tendency",
            "making_do_tendency",
            "making_do_interruption_rate",
            "making_do_rework_factor",
            "supervisor_capacity",
            "supervisor_base_workload",
            "planning_need_per_day",
            "peak_underresource_factor",
            "workload_pressure_sensitivity",
        ],
        "relative_levels": [-0.30, -0.15, 0.0, 0.15, 0.30],
        "runs_per_case": 1,
    },
    "threshold_tests": {
        "enabled": False,
        "runs_per_case": 1,
        "grid_values_01": [0.10, 0.50, 0.90],
        "tests": [
            {"name": "crew_access_x_management_access", "x": "crew_access", "y": "management_access"},
            {"name": "reporting_burden_x_autonomy", "x": "reporting_burden", "y": "autonomy_level"},
            {"name": "task_relevance_x_data_accuracy", "x": "task_relevance", "y": "data_accuracy"},
            {"name": "surveillance_x_trust", "x": "perceived_surveillance", "y": "initial_trust_in_management"},
            {"name": "constraint_screening_x_making_do", "x": "constraint_screening_strength", "y": "making_do_tendency"},
        ],
    },
    "screening": {
        "enabled": True,
        "n_samples": 20,
        "runs_per_sample": 1,
        "parameters": [
            "crew_access",
            "management_access",
            "task_relevance",
            "capture_rate",
            "data_accuracy",
            "data_timeliness",
            "reporting_burden",
            "perceived_surveillance",
            "decision_centralization",
            "autonomy_level",
            "constraint_screening_strength",
            "commitment_realism",
            "overcommitment_tendency",
            "making_do_tendency",
            "supervisor_capacity",
            "peak_underresource_factor",
            "workload_pressure_sensitivity",
        ],
    },
}


# ---------------------------------------------------------------------------
# Basic utilities
# ---------------------------------------------------------------------------


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Return base recursively updated by override."""
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        print(f"Config not found at {path}. Creating a default config there.")
        path.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return copy.deepcopy(DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}
    return deep_merge(DEFAULT_CONFIG, user_cfg)


def prompt_for_model_dir(default: Optional[Path] = None) -> Path:
    """Ask the user for a model directory. Try Tk folder dialog if available."""
    print("\nSelect the folder that contains app.py, dvm_abm/ and config/.")
    print("You can paste the path manually. Press Enter to try a folder dialog.")
    if default:
        print(f"Default: {default}")
    raw = input("Model folder path: ").strip().strip('"')
    if raw:
        return Path(raw).expanduser().resolve()
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(title="Select DVM-ABM model folder")
        root.destroy()
        if selected:
            return Path(selected).expanduser().resolve()
    except Exception:
        pass
    if default:
        return default.resolve()
    raise SystemExit("No model directory selected.")


def prepare_imports(model_dir: Path):
    if not model_dir.exists():
        raise SystemExit(f"Model directory does not exist: {model_dir}")
    if not (model_dir / "dvm_abm").exists():
        raise SystemExit(f"Folder does not contain dvm_abm/: {model_dir}")
    sys.path.insert(0, str(model_dir))
    os.chdir(model_dir)
    importlib.invalidate_caches()


def get_scenario_name(sc: Any) -> str:
    return str(getattr(sc, "name", getattr(sc, "key", "scenario")))


def scenario_fields(sc: Any) -> set:
    if dataclasses.is_dataclass(sc):
        return {f.name for f in dataclasses.fields(sc)}
    return set(vars(sc).keys())


VIRTUAL_SCENARIO_FIELDS = {"field_interaction_demand_multiplier", "field_interaction_capacity_multiplier"}


def override_scenario(sc: Any, overrides: Dict[str, Any]) -> Any:
    """Create a modified scenario object, ignoring unknown fields."""
    overrides = overrides or {}
    valid = scenario_fields(sc)
    virtual = {k: v for k, v in overrides.items() if k in VIRTUAL_SCENARIO_FIELDS}
    clean = {k: v for k, v in overrides.items() if k in valid}
    unknown = sorted(set(overrides) - valid - set(virtual))
    if unknown:
        print(f"  Note: ignored unknown Scenario fields for {get_scenario_name(sc)}: {unknown}")
    if dataclasses.is_dataclass(sc):
        new_sc = dataclasses.replace(sc, **clean)
    else:
        new_sc = copy.deepcopy(sc)
        for k, v in clean.items():
            setattr(new_sc, k, v)

    # v8: allow sensitivity-only virtual parameters without changing scenarios.py.
    # This is used for field_interaction_demand_multiplier and field_interaction_capacity_multiplier. They are read by model.py
    # if the v25.7 field-demand patch has been applied. If not, the value is still
    # recorded in the final output but has no model effect.
    for k, v in virtual.items():
        try:
            setattr(new_sc, k, v)
        except Exception:
            try:
                object.__setattr__(new_sc, k, v)
            except Exception:
                print(f"  Warning: could not attach virtual Scenario field {k}={v} to {get_scenario_name(sc)}")
    return new_sc


def clamp_to_range(parameter: str, value: float, ranges: Dict[str, Any]) -> float:
    if parameter in ranges:
        lo, hi = ranges[parameter]
        return max(float(lo), min(float(hi), float(value)))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 0.0 <= float(value) <= 1.0:
            return max(0.0, min(1.0, float(value)))
    return float(value)


def choose_scenarios(all_scenarios: Sequence[Any], scenario_filter: Any) -> List[Any]:
    if scenario_filter in (None, "all", ["all"]):
        return list(all_scenarios)
    wanted = set(scenario_filter if isinstance(scenario_filter, list) else [scenario_filter])
    selected = [sc for sc in all_scenarios if get_scenario_name(sc) in wanted]
    if not selected:
        raise SystemExit(f"No scenarios matched scenario_filter={scenario_filter}")
    return selected


# ---------------------------------------------------------------------------
# Model integration
# ---------------------------------------------------------------------------


def load_model_api(model_dir: Path):
    prepare_imports(model_dir)
    scenarios_mod = importlib.import_module("dvm_abm.scenarios")
    analysis_mod = importlib.import_module("dvm_abm.analysis")

    scenarios_path = model_dir / "config" / "scenarios.yaml"
    if not scenarios_path.exists():
        raise SystemExit(f"Scenario YAML not found: {scenarios_path}")

    if hasattr(scenarios_mod, "load_scenarios"):
        scenarios = scenarios_mod.load_scenarios(str(scenarios_path))
    elif hasattr(scenarios_mod, "get_default_scenarios"):
        scenarios = scenarios_mod.get_default_scenarios()
    else:
        raise SystemExit("Could not find load_scenarios() or get_default_scenarios() in dvm_abm.scenarios")

    if not hasattr(analysis_mod, "run_simulation"):
        raise SystemExit("Could not find run_simulation() in dvm_abm.analysis")

    return scenarios, analysis_mod


def run_one_case(
    analysis_mod: Any,
    scenario: Any,
    test_mode: str,
    test_case: str,
    run_index: int,
    seed: int,
    planned_project_duration: int,
    daily_shock_probability: float,
    parameter: Optional[str] = None,
    parameter_value: Optional[Any] = None,
    level: Optional[Any] = None,
    sample_id: Optional[int] = None,
    save_timeseries: bool = False,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Run the model once and return final row plus optional time series."""
    kwargs = dict(
        scenario=scenario,
        run=run_index,
        seed=seed,
        days=planned_project_duration,
        daily_shock_probability=daily_shock_probability,
    )

    # Compatibility for older/newer run_simulation signatures.
    sig = inspect.signature(analysis_mod.run_simulation)
    if "run" not in sig.parameters and "run_id" in sig.parameters:
        kwargs["run_id"] = kwargs.pop("run")
    if "days" not in sig.parameters and "max_days" in sig.parameters:
        kwargs["max_days"] = kwargs.pop("days")

    run_started_at = datetime.now()
    perf_start = time.perf_counter()
    df = analysis_mod.run_simulation(**kwargs)
    run_duration_sec = time.perf_counter() - perf_start
    run_finished_at = datetime.now()
    if not isinstance(df, pd.DataFrame):
        raise RuntimeError("run_simulation() did not return a pandas DataFrame")

    if "scenario" not in df.columns:
        df["scenario"] = get_scenario_name(scenario)
    if "run" not in df.columns:
        df["run"] = run_index

    df = df.copy()
    df["test_mode"] = test_mode
    df["test_case"] = test_case
    df["parameter"] = parameter or ""
    df["parameter_value"] = "" if parameter_value is None else parameter_value
    df["level"] = "" if level is None else level
    df["sample_id"] = "" if sample_id is None else sample_id
    df["seed"] = seed
    df["run_started_at"] = run_started_at.isoformat(timespec="seconds")
    df["run_finished_at"] = run_finished_at.isoformat(timespec="seconds")
    df["run_duration_sec"] = run_duration_sec

    sort_cols = [c for c in ["day"] if c in df.columns]
    if sort_cols:
        final = df.sort_values(sort_cols).tail(1).copy()
    else:
        final = df.tail(1).copy()
    return final, df if save_timeseries else None


def run_case_replicates(
    analysis_mod: Any,
    scenario: Any,
    test_mode: str,
    test_case: str,
    runs: int,
    base_seed: int,
    planned_project_duration: int,
    daily_shock_probability: float,
    parameter: Optional[str] = None,
    parameter_value: Optional[Any] = None,
    level: Optional[Any] = None,
    sample_id: Optional[int] = None,
    save_timeseries: bool = False,
) -> Tuple[List[pd.DataFrame], List[pd.DataFrame]]:
    finals: List[pd.DataFrame] = []
    timeseries: List[pd.DataFrame] = []
    for run_index in range(int(runs)):
        seed = int(base_seed) + run_index
        final, ts = run_one_case(
            analysis_mod=analysis_mod,
            scenario=scenario,
            test_mode=test_mode,
            test_case=test_case,
            run_index=run_index,
            seed=seed,
            planned_project_duration=int(planned_project_duration),
            daily_shock_probability=float(daily_shock_probability),
            parameter=parameter,
            parameter_value=parameter_value,
            level=level,
            sample_id=sample_id,
            save_timeseries=save_timeseries,
        )
        finals.append(final)
        if ts is not None:
            timeseries.append(ts)
    return finals, timeseries


# ---------------------------------------------------------------------------
# Experiment designs
# ---------------------------------------------------------------------------


def run_sanity(cfg: Dict[str, Any], scenarios: Sequence[Any], analysis_mod: Any) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    general = cfg["general"]
    finals: List[pd.DataFrame] = []
    series: List[pd.DataFrame] = []
    for case in cfg.get("sanity_cases", []):
        case_name = case.get("name", "case")
        case_shock = case.get("daily_shock_probability", general["daily_shock_probability"])
        overrides = case.get("overrides", {})
        print(f"\n[SANITY] {case_name}")
        for sc in scenarios:
            sc_mod = override_scenario(sc, overrides)
            print(f"  scenario={get_scenario_name(sc)} runs={general['runs_per_case']}")
            f, ts = run_case_replicates(
                analysis_mod=analysis_mod,
                scenario=sc_mod,
                test_mode="sanity",
                test_case=case_name,
                runs=general["runs_per_case"],
                base_seed=general["base_seed"],
                planned_project_duration=general["planned_project_duration"],
                daily_shock_probability=case_shock,
                save_timeseries=general.get("save_timeseries", False),
            )
            finals.extend(f)
            series.extend(ts)
    return pd.concat(finals, ignore_index=True), pd.concat(series, ignore_index=True) if series else None


def run_ofat(cfg: Dict[str, Any], scenarios: Sequence[Any], analysis_mod: Any) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    general = cfg["general"]
    ofat = cfg.get("ofat", {})
    ranges = cfg.get("parameter_ranges", {})
    levels = ofat.get("relative_levels", [-0.3, -0.15, 0, 0.15, 0.3])
    runs = int(ofat.get("runs_per_case", general["runs_per_case"]))
    finals: List[pd.DataFrame] = []
    series: List[pd.DataFrame] = []
    for p in ofat.get("parameters", []):
        print(f"\n[OFAT] parameter={p}")
        for sc in scenarios:
            if not hasattr(sc, p):
                print(f"  skipping {p} for {get_scenario_name(sc)}: not in Scenario")
                continue
            base_value = getattr(sc, p)
            if not isinstance(base_value, (int, float)) or isinstance(base_value, bool):
                print(f"  skipping non-numeric parameter {p}={base_value}")
                continue
            for rel in levels:
                value = clamp_to_range(p, float(base_value) * (1.0 + float(rel)), ranges)
                sc_mod = override_scenario(sc, {p: value})
                case_name = f"{p}_{rel:+.2f}"
                print(f"  scenario={get_scenario_name(sc)} level={rel:+.2f} value={value:.4g}")
                f, ts = run_case_replicates(
                    analysis_mod=analysis_mod,
                    scenario=sc_mod,
                    test_mode="ofat",
                    test_case=case_name,
                    runs=runs,
                    base_seed=general["base_seed"],
                    planned_project_duration=general["planned_project_duration"],
                    daily_shock_probability=general["daily_shock_probability"],
                    parameter=p,
                    parameter_value=value,
                    level=rel,
                    save_timeseries=general.get("save_timeseries", False),
                )
                finals.extend(f)
                series.extend(ts)
    return pd.concat(finals, ignore_index=True), pd.concat(series, ignore_index=True) if series else None


def scale_grid_value(parameter: str, raw: float, ranges: Dict[str, Any]) -> float:
    lo, hi = ranges.get(parameter, [0.0, 1.0])
    return float(lo) + float(raw) * (float(hi) - float(lo))


def threshold_values_for(test: Dict[str, Any], axis: str, parameter: str, default_grid_01: Sequence[float], ranges: Dict[str, Any]) -> List[float]:
    """Return explicit threshold values for x/y or map normalized 0..1 grid values to parameter ranges."""
    key = f"{axis}_values"
    if key in test and test[key] is not None:
        return [float(v) for v in test[key]]
    return [scale_grid_value(parameter, float(raw), ranges) for raw in default_grid_01]


def run_thresholds(cfg: Dict[str, Any], scenarios: Sequence[Any], analysis_mod: Any) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    general = cfg["general"]
    threshold = cfg.get("threshold_tests", {})
    ranges = cfg.get("parameter_ranges", {})
    runs = int(threshold.get("runs_per_case", general["runs_per_case"]))
    grid_values = threshold.get("grid_values_01", [0.1, 0.3, 0.5, 0.7, 0.9])
    finals: List[pd.DataFrame] = []
    series: List[pd.DataFrame] = []
    for test in threshold.get("tests", []):
        test_name = test.get("name") or f"{test['x']}_x_{test['y']}"
        x_param, y_param = test["x"], test["y"]
        print(f"\n[THRESHOLD] {test_name}: {x_param} x {y_param}")
        x_values = threshold_values_for(test, "x", x_param, grid_values, ranges)
        y_values = threshold_values_for(test, "y", y_param, grid_values, ranges)
        for sc in scenarios:
            for x_val in x_values:
                for y_val in y_values:
                    sc_mod = override_scenario(sc, {x_param: x_val, y_param: y_val})
                    case_name = f"{test_name}_{x_val:.3g}_{y_val:.3g}"
                    f, ts = run_case_replicates(
                        analysis_mod=analysis_mod,
                        scenario=sc_mod,
                        test_mode="threshold",
                        test_case=case_name,
                        runs=runs,
                        base_seed=general["base_seed"],
                        planned_project_duration=general["planned_project_duration"],
                        daily_shock_probability=general["daily_shock_probability"],
                        parameter=f"{x_param}|{y_param}",
                        parameter_value=f"{x_val:.6g}|{y_val:.6g}",
                        level=f"{x_val:.6g}|{y_val:.6g}",
                        save_timeseries=general.get("save_timeseries", False),
                    )
                    for frame in f:
                        frame["x_parameter"] = x_param
                        frame["y_parameter"] = y_param
                        frame["x_value"] = x_val
                        frame["y_value"] = y_val
                    if ts:
                        for frame in ts:
                            frame["x_parameter"] = x_param
                            frame["y_parameter"] = y_param
                            frame["x_value"] = x_val
                            frame["y_value"] = y_val
                    finals.extend(f)
                    series.extend(ts)
            print(f"  scenario={get_scenario_name(sc)} done")
    return pd.concat(finals, ignore_index=True), pd.concat(series, ignore_index=True) if series else None


def latin_hypercube(n: int, parameters: Sequence[str], ranges: Dict[str, Any], seed: int) -> List[Dict[str, float]]:
    rng = random.Random(seed)
    columns: Dict[str, List[float]] = {}
    for p in parameters:
        lo, hi = ranges[p]
        bins = []
        for i in range(n):
            u = (i + rng.random()) / n
            bins.append(float(lo) + u * (float(hi) - float(lo)))
        rng.shuffle(bins)
        columns[p] = bins
    return [{p: columns[p][i] for p in parameters} for i in range(n)]


def run_screening(cfg: Dict[str, Any], scenarios: Sequence[Any], analysis_mod: Any) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    general = cfg["general"]
    screening = cfg.get("screening", {})
    ranges = cfg.get("parameter_ranges", {})
    params = [p for p in screening.get("parameters", []) if p in ranges]
    n_samples = int(screening.get("n_samples", 150))
    runs = int(screening.get("runs_per_sample", 3))
    samples = latin_hypercube(n_samples, params, ranges, seed=int(general["base_seed"]))
    finals: List[pd.DataFrame] = []
    series: List[pd.DataFrame] = []
    print(f"\n[SCREENING] samples={n_samples} parameters={len(params)} runs_per_sample={runs}")
    for sample_id, overrides in enumerate(samples):
        if sample_id % max(1, n_samples // 10) == 0:
            print(f"  sample {sample_id+1}/{n_samples}")
        for sc in scenarios:
            sc_mod = override_scenario(sc, overrides)
            f, ts = run_case_replicates(
                analysis_mod=analysis_mod,
                scenario=sc_mod,
                test_mode="screening",
                test_case="lhs_screening",
                runs=runs,
                base_seed=int(general["base_seed"]) + 100000 + sample_id * 100,
                planned_project_duration=general["planned_project_duration"],
                daily_shock_probability=general["daily_shock_probability"],
                parameter="|".join(params),
                parameter_value="lhs",
                level="lhs",
                sample_id=sample_id,
                save_timeseries=general.get("save_timeseries", False),
            )
            for frame in f:
                for p, v in overrides.items():
                    frame[p] = v
            if ts:
                for frame in ts:
                    for p, v in overrides.items():
                        frame[p] = v
            finals.extend(f)
            series.extend(ts)
    return pd.concat(finals, ignore_index=True), pd.concat(series, ignore_index=True) if series else None


# ---------------------------------------------------------------------------
# Analysis and export
# ---------------------------------------------------------------------------


def numeric_summary(df: pd.DataFrame, key_metrics: Sequence[str]) -> pd.DataFrame:
    metrics = [m for m in key_metrics if m in df.columns]
    group_cols = [c for c in ["test_mode", "test_case", "scenario", "parameter", "parameter_value", "level", "sample_id"] if c in df.columns]
    if not metrics:
        return pd.DataFrame()
    grouped = df.groupby(group_cols, dropna=False)[metrics]
    summary = grouped.agg(["mean", "std", "min", "max", "median"]).reset_index()
    summary.columns = ["_".join([str(x) for x in col if str(x) != ""]).strip("_") if isinstance(col, tuple) else str(col) for col in summary.columns]
    return summary


def ofat_effects(df: pd.DataFrame, key_metrics: Sequence[str]) -> pd.DataFrame:
    if df.empty or "ofat" not in set(df.get("test_mode", [])):
        return pd.DataFrame()
    odf = df[df["test_mode"] == "ofat"].copy()
    metrics = [m for m in key_metrics if m in odf.columns]
    rows = []
    for (scenario, parameter), sub in odf.groupby(["scenario", "parameter"]):
        if not parameter:
            continue
        try:
            baseline = sub[sub["level"].astype(str).isin(["0.0", "0", "0.00"])]
        except Exception:
            baseline = pd.DataFrame()
        for metric in metrics:
            means = sub.groupby("level")[metric].mean()
            if means.empty:
                continue
            baseline_value = float(baseline[metric].mean()) if not baseline.empty and metric in baseline else float(sub[metric].mean())
            rows.append({
                "scenario": scenario,
                "parameter": parameter,
                "metric": metric,
                "min_mean": means.min(),
                "max_mean": means.max(),
                "range_effect": means.max() - means.min(),
                "baseline_mean": baseline_value,
                "relative_range_effect": (means.max() - means.min()) / (abs(baseline_value) + 1e-9),
            })
    return pd.DataFrame(rows).sort_values(["metric", "relative_range_effect"], ascending=[True, False]) if rows else pd.DataFrame()


def screening_correlations(df: pd.DataFrame, cfg: Dict[str, Any], key_metrics: Sequence[str]) -> pd.DataFrame:
    if df.empty or "screening" not in set(df.get("test_mode", [])):
        return pd.DataFrame()
    params = cfg.get("screening", {}).get("parameters", [])
    sdf = df[df["test_mode"] == "screening"].copy()
    metrics = [m for m in key_metrics if m in sdf.columns]
    rows = []
    # Average runs by sample/scenario first, then use rank correlations as screening proxy.
    group_cols = ["scenario", "sample_id"]
    keep_cols = [p for p in params if p in sdf.columns] + metrics
    sample_df = sdf[group_cols + keep_cols].copy()
    numeric_cols = [c for c in keep_cols if c in sample_df.columns]
    sample_df[numeric_cols] = sample_df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    sample_mean = sample_df.groupby(group_cols, dropna=False)[numeric_cols].mean().reset_index()
    for scenario, sub in sample_mean.groupby("scenario"):
        for p in params:
            if p not in sub.columns:
                continue
            for m in metrics:
                if m not in sub.columns:
                    continue
                x = sub[p].rank()
                y = sub[m].rank()
                if x.nunique(dropna=True) < 2 or y.nunique(dropna=True) < 2:
                    corr = math.nan
                    note = "constant_parameter_or_metric"
                else:
                    corr = x.corr(y)
                    note = ""
                rows.append({"scenario": scenario, "parameter": p, "metric": m, "spearman_rank_corr": corr, "abs_corr": abs(corr) if pd.notna(corr) else math.nan, "note": note})
    return pd.DataFrame(rows).sort_values(["metric", "abs_corr"], ascending=[True, False]) if rows else pd.DataFrame()


def threshold_summary(df: pd.DataFrame, key_metrics: Sequence[str]) -> pd.DataFrame:
    """Aggregate threshold-grid runs by test/scenario/x/y for heatmap-ready analysis."""
    if df.empty or "threshold" not in set(df.get("test_mode", [])):
        return pd.DataFrame()
    tdf = df[df["test_mode"] == "threshold"].copy()
    if "x_value" not in tdf.columns or "y_value" not in tdf.columns:
        return pd.DataFrame()
    metrics = [m for m in key_metrics if m in tdf.columns]
    if not metrics:
        return pd.DataFrame()
    group_cols = ["test_case", "scenario", "x_parameter", "y_parameter", "x_value", "y_value"]
    for c in ["x_value", "y_value"] + metrics:
        if c in tdf.columns:
            tdf[c] = pd.to_numeric(tdf[c], errors="coerce")
    grouped = tdf.groupby(group_cols, dropna=False)[metrics]
    out = grouped.agg(["mean", "std", "min", "max"]).reset_index()
    out.columns = ["_".join([str(x) for x in col if str(x) != ""]).strip("_") if isinstance(col, tuple) else str(col) for col in out.columns]
    return out


def add_sanity_flags(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    rows = []
    # Lightweight, non-prescriptive checks. They flag candidates for inspection rather than failing the model.
    for _, r in summary.iterrows():
        case = str(r.get("test_case", ""))
        scenario = r.get("scenario", "")
        flags = []
        if case == "zero_shocks":
            col = "idle_time_due_to_external_disruptions_mean"
            if col in summary.columns and pd.notna(r.get(col)) and float(r.get(col)) > 0.1:
                flags.append("External idle time remains above 0.1 despite zero_shocks.")
        if case == "perfect_dvm":
            col = "avg_weekly_ppc_mean"
            if col in summary.columns and pd.notna(r.get(col)) and float(r.get(col)) < 0.50:
                flags.append("PPC remains below 50% in perfect_dvm case; inspect PPC or capacity assumptions.")
        if case == "management_only_dashboard":
            col = "avg_sa_mean"
            if col in summary.columns and pd.notna(r.get(col)) and float(r.get(col)) > 0.75:
                flags.append("Worker SA is high despite low crew access; inspect access mechanism.")
        if flags:
            rows.append({"test_case": case, "scenario": scenario, "flags": " | ".join(flags)})
    return pd.DataFrame(rows)


def safe_sheet_name(name: str) -> str:
    return str(name)[:31].replace("/", "_").replace("\\", "_").replace("?", "_").replace("*", "_").replace("[", "(").replace("]", ")")


def export_excel(
    out_path: Path,
    cfg: Dict[str, Any],
    final_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    ofat_df: pd.DataFrame,
    screening_df: pd.DataFrame,
    threshold_df: pd.DataFrame,
    flags_df: pd.DataFrame,
    timeseries_df: Optional[pd.DataFrame],
    batch_started_at: Optional[datetime] = None,
    batch_finished_at: Optional[datetime] = None,
    batch_duration_sec: Optional[float] = None,
):
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        readme = pd.DataFrame([
            ["Created", datetime.now().isoformat(timespec="seconds")],
            ["Batch started", "" if batch_started_at is None else batch_started_at.isoformat(timespec="seconds")],
            ["Batch finished", "" if batch_finished_at is None else batch_finished_at.isoformat(timespec="seconds")],
            ["Batch duration seconds", "" if batch_duration_sec is None else round(float(batch_duration_sec), 3)],
            ["Batch duration minutes", "" if batch_duration_sec is None else round(float(batch_duration_sec)/60.0, 3)],
            ["Mean model run duration seconds", "" if "run_duration_sec" not in final_df.columns else round(float(final_df["run_duration_sec"].mean()), 4)],
            ["Purpose", "Local sensitivity test results for DVM-ABM."],
            ["Interpretation", "Exploratory robustness analysis; not calibration or empirical validation by itself."],
            ["Rows in final_run_metrics", len(final_df)],
            ["Rows in timeseries", 0 if timeseries_df is None else len(timeseries_df)],
        ], columns=["Item", "Value"])
        readme.to_excel(writer, sheet_name="README", index=False)
        pd.DataFrame([cfg.get("general", {})]).to_excel(writer, sheet_name="Run settings", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        flags_df.to_excel(writer, sheet_name="Sanity flags", index=False)
        ofat_df.to_excel(writer, sheet_name="OFAT effects", index=False)
        screening_df.to_excel(writer, sheet_name="Screening corr", index=False)
        threshold_df.to_excel(writer, sheet_name="Threshold summary", index=False)
        final_df.to_excel(writer, sheet_name="Final run metrics", index=False)
        timing_cols=[c for c in ["test_mode","test_case","scenario","run","sample_id","seed","run_started_at","run_finished_at","run_duration_sec"] if c in final_df.columns]
        if timing_cols:
            final_df[timing_cols].to_excel(writer, sheet_name="Run timing", index=False)
        # Keep Excel reasonable: if large timeseries, save CSV instead.
        if timeseries_df is not None and len(timeseries_df) <= 500000:
            timeseries_df.to_excel(writer, sheet_name="Timeseries", index=False)
        # Parameter ranges
        ranges = cfg.get("parameter_ranges", {})
        pd.DataFrame([{"parameter": k, "low": v[0], "high": v[1]} for k, v in ranges.items()]).to_excel(writer, sheet_name="Parameter ranges", index=False)
        # Config dump
        cfg_text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True).splitlines()
        pd.DataFrame({"sensitivity_config_yaml": cfg_text}).to_excel(writer, sheet_name="Config YAML", index=False)

        # Basic formatting
        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            for cell in ws[1]:
                cell.style = "Headline 4"
            for column_cells in ws.columns:
                max_len = 0
                col_letter = column_cells[0].column_letter
                for cell in column_cells[:200]:
                    try:
                        max_len = max(max_len, len(str(cell.value)) if cell.value is not None else 0)
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = max(10, min(45, max_len + 2))


def plot_outputs(out_dir: Path, summary_df: pd.DataFrame, ofat_df: pd.DataFrame, screening_df: pd.DataFrame, threshold_df: pd.DataFrame, key_metrics: Sequence[str]):
    if plt is None:
        print("matplotlib not available; skipping plots.")
        return
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(exist_ok=True)

    # OFAT tornado-like bar charts for selected metrics.
    if not ofat_df.empty:
        for metric in [m for m in ["project_delay_days", "avg_weekly_ppc", "firefighting_ratio", "cumulative_making_do_starts", "unresolved_field_support_hours_per_day", "field_support_utilization"] if m in key_metrics]:
            sub = ofat_df[ofat_df["metric"] == metric].copy().sort_values("relative_range_effect", ascending=False).head(20)
            if sub.empty:
                continue
            labels = sub["parameter"].astype(str) + " | " + sub["scenario"].astype(str)
            fig, ax = plt.subplots(figsize=(10, max(4, len(sub)*0.35)))
            ax.barh(labels[::-1], sub["relative_range_effect"][::-1])
            ax.set_xlabel("Relative range effect")
            ax.set_title(f"OFAT sensitivity: {metric}")
            fig.tight_layout()
            fig.savefig(plot_dir / f"ofat_{metric}.png", dpi=180)
            plt.close(fig)

    # Screening rank correlation charts.
    if not screening_df.empty:
        for metric in [m for m in ["project_delay_days", "avg_weekly_ppc", "firefighting_ratio", "cumulative_making_do_starts", "unresolved_field_support_hours_per_day", "field_support_utilization"] if m in key_metrics]:
            sub = screening_df[screening_df["metric"] == metric].copy().sort_values("abs_corr", ascending=False).head(20)
            if sub.empty:
                continue
            labels = sub["parameter"].astype(str) + " | " + sub["scenario"].astype(str)
            fig, ax = plt.subplots(figsize=(10, max(4, len(sub)*0.35)))
            ax.barh(labels[::-1], sub["spearman_rank_corr"][::-1])
            ax.axvline(0, linewidth=0.8)
            ax.set_xlabel("Spearman rank correlation")
            ax.set_title(f"Screening correlation: {metric}")
            fig.tight_layout()
            fig.savefig(plot_dir / f"screening_corr_{metric}.png", dpi=180)
            plt.close(fig)

    # Targeted threshold heatmaps for selected metrics.
    if threshold_df is not None and not threshold_df.empty:
        heatmap_metrics = [m for m in [
            "avg_weekly_ppc",
            "project_delay_days",
            "field_support_utilization",
            "unresolved_field_support_hours_per_day",
            "admin_reporting_hours_per_supervisor_day",
            "cumulative_making_do_starts",
        ] if f"{m}_mean" in threshold_df.columns]
        for metric in heatmap_metrics:
            col = f"{metric}_mean"
            for (case, scenario), sub in threshold_df.groupby(["test_case", "scenario"]):
                pivot = sub.pivot_table(index="y_value", columns="x_value", values=col, aggfunc="mean")
                if pivot.empty:
                    continue
                fig, ax = plt.subplots(figsize=(7, 5))
                im = ax.imshow(pivot.values, aspect="auto", origin="lower")
                ax.set_xticks(range(len(pivot.columns)))
                ax.set_xticklabels([f"{v:.2g}" for v in pivot.columns], rotation=45, ha="right")
                ax.set_yticks(range(len(pivot.index)))
                ax.set_yticklabels([f"{v:.2g}" for v in pivot.index])
                xlab = str(sub["x_parameter"].iloc[0]) if "x_parameter" in sub else "x"
                ylab = str(sub["y_parameter"].iloc[0]) if "y_parameter" in sub else "y"
                ax.set_xlabel(xlab)
                ax.set_ylabel(ylab)
                ax.set_title(f"{metric}: {case} | {scenario}")
                fig.colorbar(im, ax=ax)
                fig.tight_layout()
                safe = safe_sheet_name(f"{case}_{scenario}_{metric}").replace(" ", "_")
                fig.savefig(plot_dir / f"threshold_{safe}.png", dpi=180)
                plt.close(fig)


def write_csv_outputs(out_dir: Path, final_df: pd.DataFrame, summary_df: pd.DataFrame, ofat_df: pd.DataFrame, screening_df: pd.DataFrame, threshold_df: pd.DataFrame, timeseries_df: Optional[pd.DataFrame]):
    final_df.to_csv(out_dir / "final_run_metrics.csv", index=False, encoding="utf-8-sig")
    summary_df.to_csv(out_dir / "summary.csv", index=False, encoding="utf-8-sig")
    if not ofat_df.empty:
        ofat_df.to_csv(out_dir / "ofat_effects.csv", index=False, encoding="utf-8-sig")
    if not screening_df.empty:
        screening_df.to_csv(out_dir / "screening_correlations.csv", index=False, encoding="utf-8-sig")
    if not threshold_df.empty:
        threshold_df.to_csv(out_dir / "threshold_summary.csv", index=False, encoding="utf-8-sig")
    if timeseries_df is not None:
        timeseries_df.to_csv(out_dir / "timeseries.csv", index=False, encoding="utf-8-sig")




# ---------------------------------------------------------------------------
# Run-size presets and estimates
# ---------------------------------------------------------------------------

KEY_SCREENING_PARAMETERS = [
    "crew_access",
    "management_access",
    "task_relevance",
    "capture_rate",
    "data_accuracy",
    "data_timeliness",
    "reporting_burden",
    "perceived_surveillance",
    "decision_centralization",
    "autonomy_level",
    "constraint_screening_strength",
    "commitment_realism",
    "overcommitment_tendency",
    "making_do_tendency",
    "supervisor_capacity",
    "field_interaction_capacity_multiplier",
    "peak_underresource_factor",
    "workload_pressure_sensitivity",
]

CORE_SCREENING_PARAMETERS = [
    "crew_access",
    "management_access",
    "task_relevance",
    "reporting_burden",
    "perceived_surveillance",
    "autonomy_level",
    "constraint_screening_strength",
    "commitment_realism",
    "making_do_tendency",
    "supervisor_capacity",
]

THRESHOLD_CORE_TESTS = [
    {"name": "reporting_burden_x_autonomy", "x": "reporting_burden", "y": "autonomy_level"},
    {"name": "overcommitment_x_commitment_realism", "x": "overcommitment_tendency", "y": "commitment_realism"},
]

TARGETED_THRESHOLD_TESTS = [
    {
        "name": "reporting_burden_x_autonomy",
        "x": "reporting_burden",
        "y": "autonomy_level",
        "x_values": [0.05, 0.25, 0.45, 0.65, 0.85, 0.95],
        "y_values": [0.05, 0.25, 0.45, 0.65, 0.85, 0.95],
    },
    {
        "name": "overcommitment_x_commitment_realism",
        "x": "overcommitment_tendency",
        "y": "commitment_realism",
        "x_values": [0.00, 0.20, 0.40, 0.60, 0.80, 0.95],
        "y_values": [0.10, 0.30, 0.50, 0.70, 0.90, 0.95],
    },
    {
        "name": "field_capacity_x_field_demand",
        "x": "field_interaction_capacity_multiplier",
        "y": "field_interaction_demand_multiplier",
        "x_values": [0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00],
        "y_values": [0.50, 1.00, 1.50, 2.00, 2.50, 3.00],
    },
]


def apply_preset(cfg: Dict[str, Any], preset: str) -> Dict[str, Any]:
    """Apply a run-size preset. Use preset='config' to keep the YAML unchanged."""
    preset = (preset or "smoke").lower()
    out = copy.deepcopy(cfg)
    if preset == "config":
        return out

    out.setdefault("general", {})["save_timeseries"] = False
    out.setdefault("outputs", {})["make_plots"] = True

    if preset == "smoke":
        out["general"]["runs_per_case"] = 1
        out.setdefault("ofat", {})["enabled"] = False
        out.setdefault("threshold_tests", {})["enabled"] = False
        out.setdefault("screening", {})["enabled"] = True
        out["screening"]["n_samples"] = 10
        out["screening"]["runs_per_sample"] = 1
        out["screening"]["parameters"] = CORE_SCREENING_PARAMETERS

    elif preset == "light":
        out["general"]["runs_per_case"] = 2
        out.setdefault("ofat", {})["enabled"] = True
        out["ofat"]["runs_per_case"] = 1
        out["ofat"]["relative_levels"] = [-0.30, 0.0, 0.30]
        out["ofat"]["parameters"] = CORE_SCREENING_PARAMETERS
        out.setdefault("threshold_tests", {})["enabled"] = False
        out.setdefault("screening", {})["enabled"] = True
        out["screening"]["n_samples"] = 40
        out["screening"]["runs_per_sample"] = 1
        out["screening"]["parameters"] = KEY_SCREENING_PARAMETERS

    elif preset == "screening":
        # v25.6: local tests showed runs are fast enough to make the default
        # screening preset more useful than a smoke-level sample.
        out["general"]["runs_per_case"] = 1
        out.setdefault("ofat", {})["enabled"] = False
        out.setdefault("threshold_tests", {})["enabled"] = False
        out.setdefault("screening", {})["enabled"] = True
        out["screening"]["n_samples"] = 80
        out["screening"]["runs_per_sample"] = 2
        out["screening"]["parameters"] = KEY_SCREENING_PARAMETERS

    elif preset == "threshold_focus":
        # v8: targeted 2D tests for the three mechanisms identified after screening.
        # Intended as interactive option 4.
        out["general"]["runs_per_case"] = 1
        out.setdefault("ofat", {})["enabled"] = False
        out.setdefault("screening", {})["enabled"] = False
        out.setdefault("threshold_tests", {})["enabled"] = True
        out["threshold_tests"]["runs_per_case"] = 3
        out["threshold_tests"]["grid_values_01"] = [0.10, 0.30, 0.50, 0.70, 0.90]
        out["threshold_tests"]["tests"] = TARGETED_THRESHOLD_TESTS

    elif preset == "screening_large":
        out["general"]["runs_per_case"] = 1
        out.setdefault("ofat", {})["enabled"] = False
        out.setdefault("threshold_tests", {})["enabled"] = False
        out.setdefault("screening", {})["enabled"] = True
        out["screening"]["n_samples"] = 150
        out["screening"]["runs_per_sample"] = 3
        out["screening"]["parameters"] = KEY_SCREENING_PARAMETERS

    elif preset == "threshold":
        out["general"]["runs_per_case"] = 1
        out.setdefault("ofat", {})["enabled"] = False
        out.setdefault("screening", {})["enabled"] = False
        out.setdefault("threshold_tests", {})["enabled"] = True
        out["threshold_tests"]["runs_per_case"] = 3
        out["threshold_tests"]["grid_values_01"] = [0.10, 0.30, 0.50, 0.70, 0.90]
        out["threshold_tests"]["tests"] = THRESHOLD_CORE_TESTS

    elif preset == "standard":
        out["general"]["runs_per_case"] = 5
        out.setdefault("ofat", {})["enabled"] = True
        out["ofat"]["runs_per_case"] = 3
        out["ofat"]["relative_levels"] = [-0.30, -0.15, 0.0, 0.15, 0.30]
        out["ofat"]["parameters"] = KEY_SCREENING_PARAMETERS
        out.setdefault("threshold_tests", {})["enabled"] = True
        out["threshold_tests"]["runs_per_case"] = 3
        out["threshold_tests"]["grid_values_01"] = [0.10, 0.30, 0.50, 0.70, 0.90]
        out["threshold_tests"]["tests"] = THRESHOLD_CORE_TESTS
        out.setdefault("screening", {})["enabled"] = True
        out["screening"]["n_samples"] = 150
        out["screening"]["runs_per_sample"] = 2
        out["screening"]["parameters"] = KEY_SCREENING_PARAMETERS

    elif preset == "full":
        out["general"]["runs_per_case"] = 10
        out.setdefault("ofat", {})["enabled"] = True
        out["ofat"]["runs_per_case"] = 10
        out["ofat"]["relative_levels"] = [-0.30, -0.15, 0.0, 0.15, 0.30]
        out["ofat"]["parameters"] = list(out.get("parameter_ranges", {}).keys())
        out.setdefault("threshold_tests", {})["enabled"] = True
        out["threshold_tests"]["runs_per_case"] = 5
        out["threshold_tests"]["grid_values_01"] = [0.10, 0.30, 0.50, 0.70, 0.90]
        out["threshold_tests"]["tests"] = [
            {"name": "crew_access_x_management_access", "x": "crew_access", "y": "management_access"},
            {"name": "reporting_burden_x_autonomy", "x": "reporting_burden", "y": "autonomy_level"},
            {"name": "task_relevance_x_data_accuracy", "x": "task_relevance", "y": "data_accuracy"},
            {"name": "surveillance_x_trust", "x": "perceived_surveillance", "y": "initial_trust_in_management"},
            {"name": "constraint_screening_x_making_do", "x": "constraint_screening_strength", "y": "making_do_tendency"},
        ]
        out.setdefault("screening", {})["enabled"] = True
        out["screening"]["n_samples"] = 150
        out["screening"]["runs_per_sample"] = 3
        out["screening"]["parameters"] = KEY_SCREENING_PARAMETERS

    else:
        raise SystemExit(f"Unknown preset: {preset}. Use config, smoke, light, screening, threshold_focus, screening_large, threshold, standard, or full.")
    return out


def estimate_run_count(cfg: Dict[str, Any], scenarios: Sequence[Any], modes: Sequence[str]) -> Dict[str, int]:
    """Estimate number of individual model runs before execution."""
    n_scenarios = len(scenarios)
    general = cfg.get("general", {})
    estimates: Dict[str, int] = {}

    if "sanity" in modes:
        estimates["sanity"] = len(cfg.get("sanity_cases", [])) * int(general.get("runs_per_case", 1)) * n_scenarios

    if "ofat" in modes and cfg.get("ofat", {}).get("enabled", True):
        ofat = cfg.get("ofat", {})
        levels = ofat.get("relative_levels", [-0.3, -0.15, 0, 0.15, 0.3])
        runs = int(ofat.get("runs_per_case", general.get("runs_per_case", 1)))
        count = 0
        for sc in scenarios:
            for p in ofat.get("parameters", []):
                if hasattr(sc, p):
                    base_value = getattr(sc, p)
                    if isinstance(base_value, (int, float)) and not isinstance(base_value, bool):
                        count += len(levels) * runs
        estimates["ofat"] = count

    if "threshold" in modes and cfg.get("threshold_tests", {}).get("enabled", True):
        threshold = cfg.get("threshold_tests", {})
        grid = threshold.get("grid_values_01", [0.1, 0.3, 0.5, 0.7, 0.9])
        runs = int(threshold.get("runs_per_case", general.get("runs_per_case", 1)))
        estimates["threshold"] = len(threshold.get("tests", [])) * (len(grid) ** 2) * runs * n_scenarios

    if "screening" in modes and cfg.get("screening", {}).get("enabled", True):
        screening = cfg.get("screening", {})
        estimates["screening"] = int(screening.get("n_samples", 0)) * int(screening.get("runs_per_sample", 1)) * n_scenarios

    estimates["total"] = sum(estimates.values())
    return estimates


def print_run_estimate(estimates: Dict[str, int]) -> None:
    total = estimates.get("total", 0)
    print("\nEstimated individual model runs:")
    for k, v in estimates.items():
        if k != "total":
            print(f"  {k:10s}: {v:,}")
    print(f"  {'total':10s}: {total:,}")
    if total:
        print("\nRough runtime if one model run takes:")
        for sec in [0.2, 1.0, 3.0, 5.0]:
            minutes = total * sec / 60.0
            if minutes < 60:
                txt = f"{minutes:.1f} min"
            else:
                txt = f"{minutes/60.0:.1f} h"
            print(f"  {sec:>3.1f} s/run -> {txt}")


def confirm_before_run(total_runs: int, yes: bool) -> None:
    if yes:
        return
    print("\nThe estimate above is approximate but useful for avoiding accidental long runs.")
    answer = input("Continue? [y/N]: ").strip().lower()
    if answer not in {"y", "yes", "k", "kylla", "kyllä"}:
        raise SystemExit("Run cancelled by user.")


def preset_label(preset: str) -> str:
    labels = {
        "smoke": "Smoke: very quick technical check",
        "light": "Light: small first sensitivity run",
        "screening": "Screening: broader LHS-style screening",
        "threshold_focus": "Targeted thresholds: DVM support/control, PPC commitments, and field-support capacity-demand bottleneck",
        "screening_large": "Large screening: stronger LHS screening, no threshold grids",
        "threshold": "Threshold: selected 2D parameter-pair heatmaps",
        "standard": "Standard: sanity + OFAT + threshold + screening",
        "full": "Full: heavy run for final robustness checks",
        "config": "Config: use sensitivity_config.yaml exactly as written",
    }
    return labels.get(preset, preset)


def choose_preset_interactively(cfg: Dict[str, Any], scenarios: Sequence[Any], mode: str) -> str:
    """Ask the user which run-size preset to use and show estimated run counts."""
    presets = ["smoke", "light", "screening", "threshold_focus", "screening_large", "threshold", "standard", "full", "config"]
    modes = ["sanity", "ofat", "threshold", "screening"] if mode == "all" else [mode]

    print("\nChoose sensitivity run size / preset:")
    print("  Recommendation: after screening, use option 4 'threshold_focus' for targeted tests.\n")
    for idx, preset in enumerate(presets, start=1):
        test_cfg = apply_preset(cfg, preset)
        est = estimate_run_count(test_cfg, scenarios, modes)
        total = est.get("total", 0)
        approx_min = total * 0.5 / 60.0  # based on recent observed local run time ~0.5 s/run
        if approx_min < 60:
            time_txt = f"~{approx_min:.1f} min at 0.5 s/run"
        else:
            time_txt = f"~{approx_min/60.0:.1f} h at 0.5 s/run"
        print(f"  {idx}. {preset:15s} {total:>7,} model runs   {time_txt:>20s}   - {preset_label(preset)}")

    print("\nYou can type a number or preset name. Press Enter for 'screening'.")
    while True:
        answer = input("Preset: ").strip().lower()
        if not answer:
            return "screening"
        if answer.isdigit():
            i = int(answer)
            if 1 <= i <= len(presets):
                return presets[i-1]
        if answer in presets:
            return answer
        print("Unknown selection. Please type a number or one of: " + ", ".join(presets))

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local sensitivity tests for DVM-ABM.")
    parser.add_argument("--model-dir", type=str, default=None, help="Folder containing app.py, dvm_abm/ and config/.")
    parser.add_argument("--config", type=str, default="sensitivity_config.yaml", help="Sensitivity YAML config path.")
    parser.add_argument("--mode", type=str, default="all", choices=["all", "sanity", "ofat", "threshold", "screening"], help="Which test mode to run.")
    parser.add_argument("--preset", type=str, default=None, choices=["config", "smoke", "light", "screening", "threshold_focus", "screening_large", "threshold", "standard", "full"], help="Run-size preset. If omitted, the script asks interactively. Use --preset config to use YAML unchanged.")
    parser.add_argument("--yes", action="store_true", help="Skip the run-count confirmation prompt.")
    parser.add_argument("--estimate-only", action="store_true", help="Print estimated run count and exit without running simulations.")
    parser.add_argument("--out-dir", type=str, default=None, help="Output folder. Default: <model-dir>/sensitivity_results/<timestamp>.")
    parser.add_argument("--init-config", action="store_true", help="Write default config and exit.")
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    if args.init_config:
        if config_path.exists():
            raise SystemExit(f"Config already exists: {config_path}")
        config_path.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"Wrote default config: {config_path}")
        return

    cfg = load_config(config_path)

    model_dir = Path(args.model_dir).expanduser().resolve() if args.model_dir else prompt_for_model_dir(Path.cwd())
    scenarios, analysis_mod = load_model_api(model_dir)
    selected_scenarios = choose_scenarios(scenarios, cfg.get("general", {}).get("scenario_filter", "all"))

    selected_preset = args.preset or choose_preset_interactively(cfg, selected_scenarios, args.mode)
    cfg = apply_preset(cfg, selected_preset)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else model_dir / "sensitivity_results" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save the resolved config for reproducibility.
    (out_dir / "resolved_sensitivity_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")

    all_final_frames: List[pd.DataFrame] = []
    all_ts_frames: List[pd.DataFrame] = []

    modes = ["sanity", "ofat", "threshold", "screening"] if args.mode == "all" else [args.mode]
    print(f"\nModel folder: {model_dir}")
    print(f"Output folder: {out_dir}")
    print(f"Preset: {selected_preset}")
    print(f"Scenarios: {[get_scenario_name(s) for s in selected_scenarios]}")
    print(f"Modes: {modes}")

    estimates = estimate_run_count(cfg, selected_scenarios, modes)
    print_run_estimate(estimates)
    if args.estimate_only:
        print("\nEstimate only: no simulations executed.")
        return
    confirm_before_run(estimates.get("total", 0), args.yes)

    batch_started_at = datetime.now()
    batch_perf_start = time.perf_counter()

    for mode in modes:
        if mode == "sanity":
            final, ts = run_sanity(cfg, selected_scenarios, analysis_mod)
        elif mode == "ofat":
            if not cfg.get("ofat", {}).get("enabled", True):
                print("OFAT disabled in config; skipping.")
                continue
            final, ts = run_ofat(cfg, selected_scenarios, analysis_mod)
        elif mode == "threshold":
            if not cfg.get("threshold_tests", {}).get("enabled", True):
                print("Threshold tests disabled in config; skipping.")
                continue
            final, ts = run_thresholds(cfg, selected_scenarios, analysis_mod)
        elif mode == "screening":
            if not cfg.get("screening", {}).get("enabled", True):
                print("Screening disabled in config; skipping.")
                continue
            final, ts = run_screening(cfg, selected_scenarios, analysis_mod)
        else:
            raise ValueError(mode)
        all_final_frames.append(final)
        if ts is not None:
            all_ts_frames.append(ts)

    if not all_final_frames:
        raise SystemExit("No runs were executed.")

    final_df = pd.concat(all_final_frames, ignore_index=True)
    timeseries_df = pd.concat(all_ts_frames, ignore_index=True) if all_ts_frames else None
    key_metrics = cfg.get("outputs", {}).get("key_metrics", DEFAULT_KEY_METRICS)
    summary_df = numeric_summary(final_df, key_metrics)
    ofat_df = ofat_effects(final_df, key_metrics)
    screening_df = screening_correlations(final_df, cfg, key_metrics)
    threshold_df = threshold_summary(final_df, key_metrics)
    flags_df = add_sanity_flags(summary_df)

    batch_duration_sec = time.perf_counter() - batch_perf_start
    batch_finished_at = datetime.now()

    excel_path = out_dir / f"dvm_abm_sensitivity_results_{timestamp}.xlsx"
    export_excel(excel_path, cfg, final_df, summary_df, ofat_df, screening_df, threshold_df, flags_df, timeseries_df, batch_started_at, batch_finished_at, batch_duration_sec)

    if cfg.get("outputs", {}).get("export_raw_csv", True):
        write_csv_outputs(out_dir, final_df, summary_df, ofat_df, screening_df, threshold_df, timeseries_df)
    if cfg.get("outputs", {}).get("make_plots", True):
        plot_outputs(out_dir, summary_df, ofat_df, screening_df, threshold_df, key_metrics)

    print("\nSensitivity test completed.")
    print(f"Excel report: {excel_path}")
    print(f"Output folder: {out_dir}")


if __name__ == "__main__":
    main()
