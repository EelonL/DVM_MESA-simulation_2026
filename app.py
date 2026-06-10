"""
DVM-ABM Streamlit UI for the Mesa version

Main file for Streamlit Community Cloud.

Expected repository structure:
    app.py
    requirements.txt
    dvm_abm/
        __init__.py
        model.py
        agents.py
        scenarios.py
        shocks.py
        analysis.py
        export.py
        visualization.py
        utils.py
    config/
        scenarios.yaml

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import traceback

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from dvm_abm.analysis import (
    run_simulation,
    run_scenario_comparison,
    final_rows_by_run,
    summarize_final_runs,
)
from dvm_abm.export import build_excel_download, make_download_filename
from dvm_abm.scenarios import load_scenarios, Scenario


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DVM-ABM simulator",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Scenario labels and colours ────────────────────────────────────────────────
SCENARIO_COLORS = {
    "analog_vm": "#D85A30",
    "management_dashboard": "#888780",
    "forced_reporting_dvm": "#BA7517",
    "workface_dvm": "#378ADD",
    "dvm_lean_autonomous": "#1D9E75",
}

SCENARIO_LABELS = {
    "analog_vm": "Analog visual management",
    "management_dashboard": "Management dashboard",
    "forced_reporting_dvm": "DVM as forced reporting",
    "workface_dvm": "Ready work area DVM",
    "dvm_lean_autonomous": "Lean-autonomous DVM",
}

DISRUPTION_LABELS = {
    "material_shortage_count": "Material shortage",
    "logistics_delay_count": "Logistics delay",
    "lifting_delay_count": "Lifting delay",
    "design_missing_count": "Design missing",
    "equipment_unavailable_count": "Equipment unavailable",
    "weather_condition_count": "Weather/site condition",
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", size=12, color="#444"),
    margin=dict(l=8, r=8, t=92, b=16),
    title_x=0.0,
    title_y=0.98,
    title_xanchor="left",
    title_yanchor="top",
    title_pad=dict(t=2, b=24),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.12,
        xanchor="left",
        x=0,
        bgcolor="rgba(255,255,255,0.75)",
    ),
)

APP_DATA_VERSION = "v25_0_completion_promise_ppc"


# ── Helper functions ───────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def cached_load_scenarios(app_data_version: str = APP_DATA_VERSION) -> list[Scenario]:
    # app_data_version is intentionally part of the cache key.
    # It prevents Streamlit from reusing old cached Scenario objects after
    # the Scenario dataclass has changed.
    return load_scenarios("config/scenarios.yaml")


def scenario_summary_from_final(df_final: pd.DataFrame) -> pd.DataFrame:
    """Compact one-scenario summary table from final run metrics."""
    numeric = df_final.select_dtypes(include="number")
    summary = numeric.mean().to_frame("mean").reset_index().rename(columns={"index": "metric"})
    summary["std"] = numeric.std().values
    summary["min"] = numeric.min().values
    summary["max"] = numeric.max().values
    return summary.round(4)


def display_metric(df: pd.DataFrame, col: str, default: float = 0.0) -> float:
    if col not in df.columns or df.empty:
        return default
    return float(df[col].mean())

def display_percent(df: pd.DataFrame, col: str, default: float = 0.0) -> str:
    return f"{display_metric(df, col, default):.1%}"


def switch_success_rate(df: pd.DataFrame) -> float:
    if df.empty or "alternative_task_switches" not in df.columns or "failed_task_switches" not in df.columns:
        return 0.0
    total = df["alternative_task_switches"] + df["failed_task_switches"]
    rate = df["alternative_task_switches"] / total.replace(0, pd.NA)
    return float(rate.fillna(0).mean())


def scenario_color(name: str) -> str:
    return SCENARIO_COLORS.get(name, "#378ADD")


def scenario_label(name: str) -> str:
    name = str(name)
    return SCENARIO_LABELS.get(name, name)


V24_4_SCENARIO_DEFAULTS = {
    "supervisor_base_workload": 1.50,
    "management_reporting_load": 0.65,
    "procurement_admin_load": 0.55,
    "authority_reporting_load": 0.35,
    "meeting_load": 0.70,
    "admin_variability": 0.25,
    "planning_need_per_day": 2.20,
    "workload_shape": "balanced_beta",
    "workload_alpha": 2.4,
    "workload_beta": 2.3,
    "resource_shape": "under_resourced_peak",
    "resource_alpha": 2.2,
    "resource_beta": 2.2,
    "min_active_crews": 2,
    "max_active_crews": 8,
    "peak_underresource_factor": 0.80,
    "workload_pressure_sensitivity": 0.60,
    "constraint_screening_strength": 0.60,
    "make_ready_threshold": 0.72,
    "commitment_realism": 0.65,
    "overcommitment_tendency": 0.30,
    "making_do_tendency": 0.25,
    "making_do_interruption_rate": 0.22,
    "making_do_rework_factor": 0.25,
    "constraint_improvement_rate": 0.10,
    "commitment_capacity_factor": 1.0,
}


def ensure_scenario_v24_4_fields(scenario: Scenario) -> Scenario:
    """Rebuild Scenario if an old cached object is missing v24.4 fields."""
    missing = [field for field in V24_4_SCENARIO_DEFAULTS if not hasattr(scenario, field)]
    if not missing:
        return scenario

    data = {}
    for field in getattr(Scenario, "__dataclass_fields__", {}):
        if hasattr(scenario, field):
            data[field] = getattr(scenario, field)

    scenario_name = data.get("name", getattr(scenario, "name", "unknown"))
    scenario_defaults_by_name = {
        "analog_vm": {
            "supervisor_base_workload": 1.60,
            "management_reporting_load": 0.65,
            "procurement_admin_load": 0.65,
            "authority_reporting_load": 0.35,
            "meeting_load": 0.75,
            "admin_variability": 0.30,
            "planning_need_per_day": 2.20,
            "constraint_screening_strength": 0.35,
            "make_ready_threshold": 0.72,
            "commitment_realism": 0.55,
            "overcommitment_tendency": 0.45,
            "making_do_tendency": 0.45,
            "making_do_interruption_rate": 0.30,
            "making_do_rework_factor": 0.35,
            "constraint_improvement_rate": 0.07,
            "commitment_capacity_factor": 1.05,
        },
        "management_dashboard": {
            "supervisor_base_workload": 1.50,
            "management_reporting_load": 0.90,
            "procurement_admin_load": 0.55,
            "authority_reporting_load": 0.35,
            "meeting_load": 0.80,
            "admin_variability": 0.28,
            "planning_need_per_day": 2.25,
            "constraint_screening_strength": 0.55,
            "make_ready_threshold": 0.74,
            "commitment_realism": 0.62,
            "overcommitment_tendency": 0.35,
            "making_do_tendency": 0.32,
            "making_do_interruption_rate": 0.24,
            "making_do_rework_factor": 0.28,
            "constraint_improvement_rate": 0.09,
            "commitment_capacity_factor": 1.00,
        },
        "forced_reporting_dvm": {
            "supervisor_base_workload": 1.70,
            "management_reporting_load": 1.25,
            "procurement_admin_load": 0.65,
            "authority_reporting_load": 0.40,
            "meeting_load": 0.85,
            "admin_variability": 0.35,
            "planning_need_per_day": 2.30,
            "constraint_screening_strength": 0.45,
            "make_ready_threshold": 0.75,
            "commitment_realism": 0.50,
            "overcommitment_tendency": 0.55,
            "making_do_tendency": 0.50,
            "making_do_interruption_rate": 0.34,
            "making_do_rework_factor": 0.40,
            "constraint_improvement_rate": 0.06,
            "commitment_capacity_factor": 1.10,
        },
        "workface_dvm": {
            "supervisor_base_workload": 1.35,
            "management_reporting_load": 0.60,
            "procurement_admin_load": 0.48,
            "authority_reporting_load": 0.30,
            "meeting_load": 0.65,
            "admin_variability": 0.24,
            "planning_need_per_day": 2.20,
        },
        "dvm_lean_autonomous": {
            "supervisor_base_workload": 1.20,
            "management_reporting_load": 0.45,
            "procurement_admin_load": 0.40,
            "authority_reporting_load": 0.28,
            "meeting_load": 0.55,
            "admin_variability": 0.20,
            "planning_need_per_day": 2.10,
            "constraint_screening_strength": 0.88,
            "make_ready_threshold": 0.68,
            "commitment_realism": 0.86,
            "overcommitment_tendency": 0.12,
            "making_do_tendency": 0.10,
            "making_do_interruption_rate": 0.12,
            "making_do_rework_factor": 0.12,
            "constraint_improvement_rate": 0.15,
            "commitment_capacity_factor": 0.88,
        },
    }

    defaults = dict(V24_4_SCENARIO_DEFAULTS)
    defaults.update(scenario_defaults_by_name.get(str(scenario_name), {}))
    for field in missing:
        data[field] = defaults[field]

    return Scenario(**data)


def rgba_from_hex(hex_color: str, alpha: float = 0.15) -> str:
    """Return a Plotly-compatible rgba colour from a #RRGGBB colour."""
    try:
        if isinstance(hex_color, str) and hex_color.startswith("#") and len(hex_color) == 7:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            return f"rgba({r},{g},{b},{alpha})"
    except Exception:
        pass
    return f"rgba(55,138,221,{alpha})"


def build_single_excel(
    df_ts: pd.DataFrame,
    df_final: pd.DataFrame,
    metadata: dict,
) -> bytes:
    return build_excel_download(
        sheets={
            "summary": scenario_summary_from_final(df_final),
            "final_run_metrics": df_final,
            "timeseries": df_ts,
        },
        metadata=metadata,
    )


def build_compare_excel(
    df_all_ts: pd.DataFrame,
    df_all_final: pd.DataFrame,
    metadata: dict,
) -> bytes:
    return build_excel_download(
        sheets={
            "scenario_summary": summarize_final_runs(df_all_final),
            "final_run_metrics": df_all_final,
            "timeseries": df_all_ts,
        },
        metadata=metadata,
    )


@st.cache_data(show_spinner=False)
def cached_run_single(
    app_data_version: str,
    scenario_name: str,
    runs: int,
    max_days: int,
    base_seed: int,
    daily_shock_probability: float,
    capture_rate: float,
    data_accuracy: float,
    data_timeliness: float,
    crew_access: float,
    management_access: float,
    autonomy_level: float,
    perceived_surveillance: float,
    reporting_burden: float,
    supervisor_capacity: float,
    initial_planning_quality: float,
    supervisor_base_workload: float,
    max_active_crews: int,
    peak_underresource_factor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run one scenario multiple times and return timeseries + final runs."""
    scenarios = cached_load_scenarios(APP_DATA_VERSION)
    base_scenario = next(s for s in scenarios if s.name == scenario_name)
    base_scenario = ensure_scenario_v24_4_fields(base_scenario)

    scenario = replace(
        base_scenario,
        capture_rate=capture_rate,
        data_accuracy=data_accuracy,
        data_timeliness=data_timeliness,
        crew_access=crew_access,
        management_access=management_access,
        autonomy_level=autonomy_level,
        perceived_surveillance=perceived_surveillance,
        reporting_burden=reporting_burden,
        supervisor_capacity=supervisor_capacity,
        initial_planning_quality=initial_planning_quality,
        supervisor_base_workload=supervisor_base_workload,
        max_active_crews=max_active_crews,
        peak_underresource_factor=peak_underresource_factor,
    )

    frames = []
    for run_id in range(runs):
        frames.append(
            run_simulation(
                scenario=scenario,
                run_id=run_id,
                seed=base_seed + run_id,
                days=max_days,
                daily_shock_probability=daily_shock_probability,
            )
        )

    df_ts = pd.concat(frames, ignore_index=True)
    df_final = final_rows_by_run(df_ts)
    return df_ts, df_final


@st.cache_data(show_spinner=False)
def cached_run_all_scenarios(
    app_data_version: str,
    runs: int,
    max_days: int,
    base_seed: int,
    daily_shock_probability: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run all scenarios with default parameters."""
    scenarios = cached_load_scenarios(app_data_version)
    scenarios = [ensure_scenario_v24_4_fields(s) for s in scenarios]
    df_all_ts = run_scenario_comparison(
        scenarios=scenarios,
        runs=runs,
        days=max_days,
        base_seed=base_seed,
        daily_shock_probability=daily_shock_probability,
    )
    df_all_final = final_rows_by_run(df_all_ts)
    df_summary = summarize_final_runs(df_all_final)
    return df_all_ts, df_all_final, df_summary


FRIENDLY_METRIC_NAMES = {
    "avg_weekly_ppc": "Average weekly PPC",
    "weekly_ppc": "Weekly PPC",
    "last_completed_weekly_ppc": "Last completed weekly PPC",
    "open_schedule_backlog": "Open schedule backlog",
    "cumulative_plan_failures": "Accumulated plan failures",
    "project_delay_days": "Realized project delay, days",
    "avg_lateness_days": "Average lateness, days",
    "late_completed_tasks": "Late completed tasks",
    "avg_sa": "Crew situation awareness",
    "avg_recovery_time": "Average recovery time, days",
    "total_idle_time": "Total waiting time, days",
    "total_idle_time_external": "External waiting time, days",
    "idle_time_due_to_external_disruptions": "External waiting time, days",
    "firefighting_ratio": "Firefighting ratio",
    "planning_quality": "Planning quality",
    "trust_in_data": "Trust in data",
    "trust_in_management": "Trust in management",
    "avg_adoption": "Average adoption",
    "avg_effective_use": "Average effective DVM use",
    "supervisor_utilization": "Supervisor utilization",
    "planned_workload_today": "Planned tasks due today",
    "active_crews_today": "Active crews",
    "available_crew_capacity_today": "Available crew capacity",
    "workload_pressure": "Workload pressure",
    "baseline_adherence": "Baseline adherence",
    "weekly_committed_tasks": "Weekly committed tasks",
    "weekly_task_capacity": "Weekly task capacity",
    "cumulative_schedule_adherence": "Cumulative schedule adherence",
    "ppc_schedule_score": "PPC schedule score",
    "ppc_schedule_consistency_gap": "PPC-schedule consistency gap",
    "completed_committed_tasks": "Completed committed tasks",
    "avg_make_ready_score": "Average make-ready score",
    "sound_commitment_share": "Sound commitment share",
    "constraints_ready_count": "Constraints ready",
    "constraints_missing_count": "Constraints missing",
    "cumulative_making_do_starts": "Cumulative making-do starts",
    "cumulative_making_do_interruptions": "Cumulative making-do interruptions",
    "cumulative_rework_due_to_making_do": "Cumulative rework due to making-do",
    "supervisor_base_workload": "Supervisor base workload",
    "supervisor_total_workload": "Supervisor total workload",
    "supervisor_planning_shortfall": "Supervisor planning shortfall",
    "cumulative_base_workload": "Cumulative base workload",
    "cumulative_planning_shortfall": "Cumulative planning shortfall",
    "supervisor_backlog": "Supervisor backlog",
    "cumulative_reactive_time": "Cumulative reactive supervisor time",
    "cumulative_planning_time": "Cumulative planning time",
    "alternative_task_switches": "Successful alternative ready work area switches",
    "failed_task_switches": "Failed alternative task switches",
    "supervisor_recovery_interventions": "Supervisor recovery interventions",
    "active_external_blockages": "Active external blockages",
    "day": "Final day",
}


def friendly_metric_name(metric: str) -> str:
    return FRIENDLY_METRIC_NAMES.get(metric, str(metric).replace("_", " ").capitalize())


def line_mean_by_day(
    df: pd.DataFrame,
    metric: str,
    title: str,
    color: str,
    y_title: str | None = None,
) -> go.Figure:
    fig = go.Figure()
    if df.empty or "day" not in df.columns or metric not in df.columns:
        fig.update_layout(
            title=title,
            xaxis_title="Day",
            yaxis_title=y_title or metric,
            **PLOTLY_LAYOUT,
        )
        fig.add_annotation(
            text=f"Metric not available in the current simulation data: {metric}",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        )
        return fig

    agg = df.groupby("day", observed=True)[metric].agg(["mean", "std"]).reset_index()
    agg["std"] = agg["std"].fillna(0)

    fig.add_trace(
        go.Scatter(
            x=pd.concat([agg["day"], agg["day"][::-1]]),
            y=pd.concat([agg["mean"] + agg["std"], (agg["mean"] - agg["std"])[::-1]]),
            fill="toself",
            fillcolor=rgba_from_hex(color),
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False,
            name="±1 SD",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=agg["day"],
            y=agg["mean"],
            mode="lines",
            line=dict(color=color, width=2),
            name="Mean",
            showlegend=False,
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Day",
        yaxis_title=y_title or metric,
        **PLOTLY_LAYOUT,
    )
    return fig


def line_compare_by_scenario(df: pd.DataFrame, metric: str, title: str, y_title: str | None = None) -> go.Figure:
    fig = go.Figure()
    if df.empty or "day" not in df.columns or "scenario" not in df.columns or metric not in df.columns:
        fig.update_layout(
            title=title,
            xaxis_title="Day",
            yaxis_title=y_title or friendly_metric_name(metric),
            **PLOTLY_LAYOUT,
        )
        fig.add_annotation(
            text=f"Metric not available in the current simulation data: {metric}",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        )
        return fig

    for scenario_name, g in df.groupby("scenario", observed=True):
        ts = g.groupby("day", observed=True)[metric].mean()
        fig.add_trace(
            go.Scatter(
                x=ts.index,
                y=ts.values,
                name=scenario_label(str(scenario_name)),
                mode="lines",
                line=dict(color=scenario_color(str(scenario_name)), width=2),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Day",
        yaxis_title=y_title or friendly_metric_name(metric),
        **PLOTLY_LAYOUT,
    )
    return fig


def minmax(series: pd.Series, invert: bool = False) -> pd.Series:
    s = series.astype(float)
    denom = s.max() - s.min()
    if denom == 0:
        out = pd.Series([0.5] * len(s), index=s.index)
    else:
        out = (s - s.min()) / denom
    return 1 - out if invert else out



def ensure_v24_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add safe fallback columns so old cached/partial simulation data does not crash the UI."""
    if df is None or df.empty:
        return df
    df = df.copy()

    if "avg_weekly_ppc" not in df.columns:
        if "weekly_ppc" in df.columns:
            df["avg_weekly_ppc"] = df["weekly_ppc"]
        elif "ppc_proxy" in df.columns:
            df["avg_weekly_ppc"] = df["ppc_proxy"]
        else:
            df["avg_weekly_ppc"] = 0.0

    if "weekly_ppc" not in df.columns:
        df["weekly_ppc"] = df["avg_weekly_ppc"]

    fallback_zero_cols = [
        "last_completed_weekly_ppc",
        "planned_tasks_this_week",
        "completed_on_plan_this_week",
        "weekly_carryover",
        "open_schedule_backlog",
        "cumulative_plan_failures",
        "project_delay_days",
        "avg_lateness_days",
        "late_completed_tasks",
        "supervisor_base_workload",
        "supervisor_total_workload",
        "supervisor_planning_need",
        "supervisor_planning_shortfall",
        "supervisor_available_planning_capacity",
        "cumulative_base_workload",
        "cumulative_planning_shortfall",
        "planned_workload_today",
        "active_crews_today",
        "available_crew_capacity_today",
        "workload_pressure",
        "baseline_adherence",
        "weekly_committed_tasks",
        "completed_committed_tasks",
        "weekly_task_capacity",
        "cumulative_schedule_adherence",
        "ppc_schedule_score",
        "ppc_schedule_consistency_gap",
        "avg_make_ready_score",
        "sound_commitment_share",
        "constraints_ready_count",
        "constraints_missing_count",
        "making_do_starts",
        "cumulative_making_do_starts",
        "making_do_interruptions",
        "cumulative_making_do_interruptions",
        "rework_due_to_making_do",
        "cumulative_rework_due_to_making_do",
        "hard_limit_reached",
        "incomplete_at_hard_limit",
    ]
    for col in fallback_zero_cols:
        if col not in df.columns:
            df[col] = 0.0

    return df

# ── Load scenarios ─────────────────────────────────────────────────────────────
try:
    SCENARIOS = [ensure_scenario_v24_4_fields(s) for s in cached_load_scenarios(APP_DATA_VERSION)]
except Exception as exc:
    st.error("Scenario configuration could not be loaded.")
    st.exception(exc)
    st.stop()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏗️ DVM-ABM simulator")
    st.caption("Mesa-based simulation model")
    st.caption("Results can be downloaded as Excel files.")
    st.divider()

    st.markdown("**Scenario**")

    # Build a robust scenario lookup. This avoids StopIteration if Streamlit
    # has stale widget state after a code/config update.
    scenario_names = [s.name for s in SCENARIOS]
    scenario_by_name = {s.name: s for s in SCENARIOS}

    if not scenario_names:
        st.error(
            "No scenarios were loaded. Check that config/scenarios.yaml exists "
            "and contains a top-level 'scenarios:' section."
        )
        st.stop()

    previous_selection = st.session_state.get("selected_scenario_name", scenario_names[0])
    if previous_selection not in scenario_by_name:
        previous_selection = scenario_names[0]
        st.session_state["selected_scenario_name"] = previous_selection

    selected_scenario_name = st.selectbox(
        "Choose scenario",
        options=scenario_names,
        index=scenario_names.index(previous_selection),
        format_func=scenario_label,
        label_visibility="collapsed",
        key="selected_scenario_name",
    )

    active_scenario = ensure_scenario_v24_4_fields(
        scenario_by_name.get(selected_scenario_name, SCENARIOS[0])
    )

    st.divider()

    st.markdown("**Simulation settings**")
    runs = st.slider("Runs", 5, 100, 30, step=5)
    max_days = st.slider("Planned project duration, days", 50, 200, 100, step=10)
    base_seed = st.number_input("Base seed", value=20260609, step=1)

    st.divider()

    st.markdown("**External shock environment**")
    daily_shock_probability = st.slider(
        "Daily external shock probability",
        0.00,
        0.80,
        0.32,
        step=0.01,
        help="This controls the shared external shock schedule. In comparison mode, all scenarios face the same shock environment for each run.",
    )

    st.divider()

    st.markdown("**DVM / information quality**")
    capture_rate = st.slider("Capture rate", 0.0, 1.0, float(active_scenario.capture_rate), step=0.01)
    data_accuracy = st.slider("Data accuracy", 0.0, 1.0, float(active_scenario.data_accuracy), step=0.01)
    data_timeliness = st.slider("Data timeliness", 0.0, 1.0, float(active_scenario.data_timeliness), step=0.01)
    crew_access = st.slider("Crew access", 0.0, 1.0, float(active_scenario.crew_access), step=0.01)
    management_access = st.slider("Management access", 0.0, 1.0, float(active_scenario.management_access), step=0.01)

    st.divider()

    st.markdown("**Socio-psychological factors**")
    autonomy_level = st.slider("Autonomy", 0.0, 1.0, float(active_scenario.autonomy_level), step=0.01)
    perceived_surveillance = st.slider("Perceived surveillance", 0.0, 1.0, float(active_scenario.perceived_surveillance), step=0.01)
    reporting_burden = st.slider("Reporting burden", 0.0, 1.0, float(active_scenario.reporting_burden), step=0.01)

    st.divider()

    st.markdown("**Supervisor and planning**")
    supervisor_capacity = st.slider("Supervisor capacity (h/day)", 2.0, 16.0, float(active_scenario.supervisor_capacity), step=0.5)
    initial_planning_quality = st.slider(
        "Initial planning quality",
        0.0,
        1.0,
        float(active_scenario.initial_planning_quality),
        step=0.01,
    )
    supervisor_base_workload = st.slider(
        "Supervisor base workload (h/day)",
        0.0,
        7.0,
        float(getattr(active_scenario, "supervisor_base_workload", 1.5)),
        step=0.1,
        help="Worker-independent daily supervisor workload such as administration, reporting, orders, invoices, authority documentation and meetings.",
    )

    st.divider()
    st.markdown("**Project workload and resources**")
    max_active_crews = st.slider(
        "Maximum active crews",
        3,
        12,
        int(getattr(active_scenario, "max_active_crews", 8)),
        step=1,
        help="Maximum number of crews available near the resource peak.",
    )
    peak_underresource_factor = st.slider(
        "Peak resource fit",
        0.40,
        1.10,
        float(getattr(active_scenario, "peak_underresource_factor", 0.80)),
        step=0.01,
        help="How closely resources follow peak workload. Lower values mean under-resourcing during the peak.",
    )

    run_btn = st.button("▶ Run simulation", type="primary", use_container_width=True)


# ── Session state and simulation run ───────────────────────────────────────────
cache_key = (
    APP_DATA_VERSION,
    selected_scenario_name,
    runs,
    max_days,
    int(base_seed),
    round(daily_shock_probability, 4),
    round(capture_rate, 4),
    round(data_accuracy, 4),
    round(data_timeliness, 4),
    round(crew_access, 4),
    round(management_access, 4),
    round(autonomy_level, 4),
    round(perceived_surveillance, 4),
    round(reporting_burden, 4),
    round(supervisor_capacity, 4),
    round(initial_planning_quality, 4),
    round(supervisor_base_workload, 4),
    int(max_active_crews),
    round(peak_underresource_factor, 4),
)

if "single_cache_key" not in st.session_state:
    st.session_state["single_cache_key"] = None
    st.session_state["single_result"] = None

if run_btn or st.session_state["single_cache_key"] != cache_key:
    try:
        with st.spinner("Running simulation…"):
            df_ts, df_final = cached_run_single(*cache_key)
        st.session_state["single_cache_key"] = cache_key
        st.session_state["single_result"] = (df_ts, df_final)
    except Exception as exc:
        st.error("Simulation failed.")
        st.code(traceback.format_exc())
        st.stop()

if st.session_state["single_result"] is None:
    st.info("Press **▶ Run simulation** to start.")
    st.stop()

df_ts, df_final = st.session_state["single_result"]
df_ts = ensure_v24_columns(df_ts)
df_final = ensure_v24_columns(df_final)

color = scenario_color(selected_scenario_name)
label = scenario_label(selected_scenario_name)


# ── Excel for current single scenario ──────────────────────────────────────────
single_metadata = {
    "model": "DVM-ABM Mesa",
    "selected_scenario": selected_scenario_name,
    "scenario_label": label,
    "runs": runs,
    "max_days": max_days,
    "base_seed": int(base_seed),
    "daily_shock_probability": daily_shock_probability,
    "capture_rate": capture_rate,
    "data_accuracy": data_accuracy,
    "data_timeliness": data_timeliness,
    "crew_access": crew_access,
    "management_access": management_access,
    "autonomy_level": autonomy_level,
    "perceived_surveillance": perceived_surveillance,
    "reporting_burden": reporting_burden,
    "supervisor_capacity": supervisor_capacity,
    "initial_planning_quality": initial_planning_quality,
    "supervisor_base_workload": supervisor_base_workload,
    "max_active_crews": max_active_crews,
    "peak_underresource_factor": peak_underresource_factor,
    "created_at": datetime.now().isoformat(timespec="seconds"),
}
single_excel_bytes = build_single_excel(df_ts, df_final, single_metadata)


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_results, tab_timeseries, tab_disruptions, tab_supervisor, tab_compare, tab_data = st.tabs(
    [
        "📊 Overview",
        "📈 Time series",
        "⚡ Disruptions",
        "👷 Supervisor",
        "🔀 Scenario comparison",
        "📄 Data",
    ]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Results / Overview
# ═══════════════════════════════════════════════════════════════════════════════
with tab_results:
    st.markdown(f"### {label} — overview across {runs} runs")
    st.caption(
        "This page shows the resilience logic of the model: weekly plan reliability, "
        "schedule backlog, recovery from disruptions and supervisor firefighting."
    )

    dcol1, dcol2 = st.columns([1, 3])
    with dcol1:
        st.download_button(
            label="⬇️ Download Excel",
            data=single_excel_bytes,
            file_name=make_download_filename("dvm_abm_single_run", selected_scenario_name),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with dcol2:
        st.caption("Workbook contains metadata, summary, final_run_metrics and timeseries sheets.")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Final day", f"{display_metric(df_final, 'day'):.0f}")
    k2.metric("Average weekly PPC", display_percent(df_final, "avg_weekly_ppc"))
    k3.metric("Make-ready score", display_percent(df_final, "avg_make_ready_score"))
    k4.metric("Making-do starts", f"{display_metric(df_final, 'cumulative_making_do_starts'):.1f}")
    k5.metric("Open backlog", f"{display_metric(df_final, 'open_schedule_backlog'):.1f} tasks")
    k6.metric("Project delay", f"{display_metric(df_final, 'project_delay_days'):.1f} d")

    st.divider()

    workload_agg = df_ts.groupby("day", observed=True)[
        ["planned_workload_today", "active_crews_today", "workload_pressure"]
    ].mean().reset_index()
    fig_load = go.Figure()
    fig_load.add_trace(
        go.Bar(
            x=workload_agg["day"],
            y=workload_agg["planned_workload_today"],
            name="Planned tasks due",
            marker_color="#BA7517",
            opacity=0.55,
            yaxis="y",
        )
    )
    fig_load.add_trace(
        go.Scatter(
            x=workload_agg["day"],
            y=workload_agg["active_crews_today"],
            name="Active crews",
            mode="lines",
            line=dict(color="#1D9E75", width=3),
            yaxis="y2",
        )
    )
    fig_load.update_layout(
        title="Planned workload and active crew resources",
        xaxis_title="Day",
        yaxis=dict(title="Planned tasks due"),
        yaxis2=dict(title="Active crews", overlaying="y", side="right"),
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_load, use_container_width=True)

    lps_agg = df_ts.groupby("day", observed=True)[
        ["avg_weekly_ppc", "baseline_adherence", "avg_make_ready_score", "sound_commitment_share"]
    ].mean().reset_index()
    fig_lps = go.Figure()
    for metric, name, colour in [
        ("avg_weekly_ppc", "PPC from weekly commitments", "#1D9E75"),
        ("baseline_adherence", "Baseline adherence", "#888780"),
        ("avg_make_ready_score", "Make-ready score", "#378ADD"),
        ("sound_commitment_share", "Sound commitment share", "#BA7517"),
    ]:
        if metric in lps_agg.columns:
            fig_lps.add_trace(go.Scatter(
                x=lps_agg["day"], y=lps_agg[metric],
                name=name, mode="lines", line=dict(color=colour, width=2)
            ))
    fig_lps.update_layout(
        title="LPS make-ready and commitment reliability",
        xaxis_title="Day",
        yaxis_title="Share",
        **PLOTLY_LAYOUT,
    )
    fig_lps.update_yaxes(range=[0,1], tickformat=".0%")
    st.plotly_chart(fig_lps, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        fig_ppc = line_mean_by_day(
            df_ts,
            metric="avg_weekly_ppc",
            title="Weekly plan reliability over time",
            color=color,
            y_title="Average weekly PPC",
        )
        fig_ppc.update_yaxes(range=[0, 1], tickformat=".0%")
        fig_ppc.add_hline(
            y=0.85,
            line_dash="dash",
            line_color="#888780",
            annotation_text="85% reference",
            annotation_position="bottom right",
        )
        st.plotly_chart(fig_ppc, use_container_width=True)

    with col_b:
        fig_backlog = line_mean_by_day(
            df_ts,
            metric="open_schedule_backlog",
            title="Open schedule backlog over time",
            color="#D85A30",
            y_title="Open delayed tasks",
        )
        st.plotly_chart(fig_backlog, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        fig_idle = go.Figure()
        if "total_idle_time_external" in df_final.columns:
            fig_idle.add_trace(
                go.Box(
                    y=df_final["total_idle_time_external"],
                    name="External waiting",
                    marker_color="#D85A30",
                    boxmean=True,
                )
            )
        fig_idle.add_trace(
            go.Box(
                y=df_final["total_idle_time"],
                name="Total waiting",
                marker_color=color,
                boxmean=True,
            )
        )
        fig_idle.update_layout(
            title="Waiting time across runs",
            yaxis_title="Days",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_idle, use_container_width=True)

    with col_d:
        fig_recovery = px.scatter(
            df_final,
            x="avg_sa",
            y="avg_recovery_time",
            color_discrete_sequence=[color],
            opacity=0.65,
            labels={
                "avg_sa": "Crew situation awareness, 0–1",
                "avg_recovery_time": "Average recovery time from disruptions, days",
            },
            title="Do crews with better situation awareness recover faster?",
            trendline="ols" if len(df_final) >= 3 else None,
        )
        fig_recovery.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig_recovery, use_container_width=True)

    col_e, col_f = st.columns(2)

    with col_e:
        if "alternative_task_switches" in df_final.columns and "total_idle_time_external" in df_final.columns:
            fig_switch = px.scatter(
                df_final,
                x="alternative_task_switches",
                y="total_idle_time_external",
                color_discrete_sequence=["#1D9E75"],
                opacity=0.65,
                labels={
                    "alternative_task_switches": "Successful alternative ready work area switches",
                    "total_idle_time_external": "External waiting time, days",
                },
                title="Do alternative ready work areas reduce external waiting time?",
                trendline="ols" if len(df_final) >= 3 else None,
            )
            fig_switch.update_layout(**PLOTLY_LAYOUT)
            st.plotly_chart(fig_switch, use_container_width=True)

    with col_f:
        fig_delay = go.Figure()
        fig_delay.add_trace(
            go.Box(
                y=df_final["project_delay_days"],
                name="Project delay",
                marker_color="#BA7517",
                boxmean=True,
            )
        )
        fig_delay.add_trace(
            go.Box(
                y=df_final["cumulative_plan_failures"],
                name="Plan failures",
                marker_color="#888780",
                boxmean=True,
            )
        )
        fig_delay.update_layout(
            title="Project delay and accumulated plan failures",
            yaxis_title="Days / tasks",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_delay, use_container_width=True)

    st.markdown("#### Making-do effects")
    md_cols = ["cumulative_making_do_starts", "cumulative_making_do_interruptions", "cumulative_rework_due_to_making_do"]
    if all(col in df_ts.columns for col in md_cols):
        md_agg = df_ts.groupby("day", observed=True)[md_cols].mean().reset_index()
        fig_md = go.Figure()
        fig_md.add_trace(go.Scatter(x=md_agg["day"], y=md_agg["cumulative_making_do_starts"], name="Making-do starts", mode="lines", line=dict(color="#D85A30", width=2)))
        fig_md.add_trace(go.Scatter(x=md_agg["day"], y=md_agg["cumulative_making_do_interruptions"], name="Making-do interruptions", mode="lines", line=dict(color="#BA7517", width=2)))
        fig_md.add_trace(go.Scatter(x=md_agg["day"], y=md_agg["cumulative_rework_due_to_making_do"], name="Rework due to making-do", mode="lines", line=dict(color="#888780", width=2)))
        fig_md.update_layout(title="Making-do consequences over time", xaxis_title="Day", yaxis_title="Count / days", **PLOTLY_LAYOUT)
        st.plotly_chart(fig_md, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Time series
# ═══════════════════════════════════════════════════════════════════════════════
with tab_timeseries:
    st.markdown(f"### {label} — daily averages")

    metric_options = [
        "avg_sa",
        "avg_weekly_ppc",
        "weekly_ppc",
        "open_schedule_backlog",
        "cumulative_plan_failures",
        "project_delay_days",
        "workload_pressure",
        "baseline_adherence",
        "cumulative_schedule_adherence",
        "ppc_schedule_score",
        "ppc_schedule_consistency_gap",
        "weekly_task_capacity",
        "avg_make_ready_score",
        "sound_commitment_share",
        "cumulative_making_do_starts",
        "cumulative_making_do_interruptions",
        "cumulative_rework_due_to_making_do",
        "planning_quality",
        "trust_in_data",
        "trust_in_management",
        "avg_adoption",
        "avg_effective_use",
        "supervisor_utilization",
        "supervisor_base_workload",
        "supervisor_planning_shortfall",
        "firefighting_ratio",
        "total_idle_time",
        "total_idle_time_external",
        "avg_recovery_time",
        "external_disruptions",
        "alternative_task_switches",
        "failed_task_switches",
    ]
    metric_options = [m for m in metric_options if m in df_ts.columns]

    ts_metric = st.selectbox(
        "Metric",
        options=metric_options,
        format_func=friendly_metric_name,
    )

    fig_ts = line_mean_by_day(
        df_ts,
        metric=ts_metric,
        title=f"{ts_metric.replace('_', ' ')} — mean ± SD",
        color=color,
        y_title=ts_metric,
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    show_runs = st.checkbox("Show individual runs (max 20)")
    if show_runs:
        fig_ind = go.Figure()
        for run_id in sorted(df_ts["run"].unique())[:20]:
            run_df = df_ts[df_ts["run"] == run_id]
            fig_ind.add_trace(
                go.Scatter(
                    x=run_df["day"],
                    y=run_df[ts_metric],
                    mode="lines",
                    line=dict(color=color, width=0.8),
                    opacity=0.35,
                    showlegend=False,
                )
            )
        fig_ind.update_layout(
            title="Individual runs",
            xaxis_title="Day",
            yaxis_title=ts_metric,
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_ind, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Disruptions
# ═══════════════════════════════════════════════════════════════════════════════
with tab_disruptions:
    st.markdown(f"### {label} — external disruption and recovery analysis")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("External disruptions", f"{display_metric(df_final, 'external_disruptions'):.1f}")
    c2.metric("Avg recovery time", f"{display_metric(df_final, 'avg_recovery_time'):.2f} d")
    c3.metric("Alternative ready work area switches", f"{display_metric(df_final, 'alternative_task_switches'):.1f}")
    c4.metric("External waiting time", f"{display_metric(df_final, 'idle_time_due_to_external_disruptions'):.1f} d")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        disrupt_means = {
            label_: df_final[col].mean()
            for col, label_ in DISRUPTION_LABELS.items()
            if col in df_final.columns
        }
        fig_d = go.Figure(
            go.Bar(
                x=list(disrupt_means.values()),
                y=list(disrupt_means.keys()),
                orientation="h",
                marker_color=color,
                opacity=0.85,
            )
        )
        fig_d.update_layout(
            title="External disruption types",
            xaxis_title="Average count per run",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_d, use_container_width=True)

    with col_b:
        fig_r = go.Figure()
        fig_r.add_trace(
            go.Histogram(
                x=df_final["avg_recovery_time"],
                nbinsx=15,
                marker_color=color,
                opacity=0.85,
            )
        )
        fig_r.update_layout(
            title="Average recovery time across runs",
            xaxis_title="Days",
            yaxis_title="Runs",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_r, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        total_sw = df_final["alternative_task_switches"] + df_final["failed_task_switches"]
        success_rate = (df_final["alternative_task_switches"] / total_sw.replace(0, 1)).mean()
        fig_sw = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=round(success_rate * 100, 1),
                number={"suffix": "%"},
                title={"text": "Alternative ready work area success rate"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": color},
                    "steps": [
                        {"range": [0, 40], "color": "#fcebeb"},
                        {"range": [40, 70], "color": "#faeeda"},
                        {"range": [70, 100], "color": "#eaf3de"},
                    ],
                },
            )
        )
        fig_sw.update_layout(**PLOTLY_LAYOUT, height=280)
        st.plotly_chart(fig_sw, use_container_width=True)

    with col_d:
        fig_bl = line_mean_by_day(
            df_ts,
            metric="active_external_blockages",
            title="Active external blockages over time",
            color=color,
            y_title="Active blockages",
        )
        st.plotly_chart(fig_bl, use_container_width=True)

    st.markdown("#### Recovery mechanisms")
    fig_rec = go.Figure()
    fig_rec.add_trace(
        go.Box(
            y=df_final["alternative_task_switches"],
            name="Alternative ready work area switches",
            marker_color="#1D9E75",
            boxmean=True,
        )
    )
    fig_rec.add_trace(
        go.Box(
            y=df_final["failed_task_switches"],
            name="Failed switches",
            marker_color="#D85A30",
            boxmean=True,
        )
    )
    fig_rec.add_trace(
        go.Box(
            y=df_final["supervisor_recovery_interventions"],
            name="Supervisor interventions",
            marker_color="#888780",
            boxmean=True,
        )
    )
    fig_rec.update_layout(
        title="Recovery mechanisms across runs",
        yaxis_title="Count",
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_rec, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Supervisor
# ═══════════════════════════════════════════════════════════════════════════════
with tab_supervisor:
    st.markdown(f"### {label} — supervisor workload")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Firefighting ratio", f"{display_metric(df_final, 'firefighting_ratio'):.1%}")
    c2.metric("Supervisor utilization", f"{display_metric(df_final, 'supervisor_utilization'):.1%}")
    c3.metric("Base workload", f"{display_metric(df_final, 'supervisor_base_workload'):.1f} h/d")
    c4.metric("Planning shortfall", f"{display_metric(df_final, 'cumulative_planning_shortfall'):.1f} h")
    c5.metric("Backlog", f"{display_metric(df_final, 'supervisor_backlog'):.2f} h")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        supervisor_time_cols = [
            "cumulative_base_workload",
            "cumulative_reactive_time",
            "cumulative_planning_time",
            "cumulative_planning_shortfall",
        ]
        available_time_cols = [c for c in supervisor_time_cols if c in df_ts.columns]
        sup_agg = df_ts.groupby("day", observed=True)[available_time_cols].mean().reset_index()
        fig_sup = go.Figure()
        if "cumulative_base_workload" in sup_agg.columns:
            fig_sup.add_trace(
                go.Scatter(
                    x=sup_agg["day"],
                    y=sup_agg["cumulative_base_workload"],
                    name="Base workload",
                    mode="lines",
                    line=dict(color="#888780", width=2),
                )
            )
        if "cumulative_reactive_time" in sup_agg.columns:
            fig_sup.add_trace(
                go.Scatter(
                    x=sup_agg["day"],
                    y=sup_agg["cumulative_reactive_time"],
                    name="Reactive time",
                    mode="lines",
                    line=dict(color="#D85A30", width=2),
                )
            )
        if "cumulative_planning_time" in sup_agg.columns:
            fig_sup.add_trace(
                go.Scatter(
                    x=sup_agg["day"],
                    y=sup_agg["cumulative_planning_time"],
                    name="Planning time",
                    mode="lines",
                    line=dict(color="#1D9E75", width=2),
                )
            )
        if "cumulative_planning_shortfall" in sup_agg.columns:
            fig_sup.add_trace(
                go.Scatter(
                    x=sup_agg["day"],
                    y=sup_agg["cumulative_planning_shortfall"],
                    name="Planning shortfall",
                    mode="lines",
                    line=dict(color="#BA7517", width=2, dash="dash"),
                )
            )
        fig_sup.update_layout(
            title="Cumulative supervisor workload",
            xaxis_title="Day",
            yaxis_title="Hours",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_sup, use_container_width=True)

    with col_b:
        fig_ff = line_mean_by_day(
            df_ts,
            metric="firefighting_ratio",
            title="Firefighting ratio over time",
            color="#D85A30",
            y_title="Ratio",
        )
        fig_ff.add_hline(
            y=0.5,
            line_dash="dash",
            line_color="#888780",
            annotation_text="50% threshold",
            annotation_position="top right",
        )
        fig_ff.update_yaxes(range=[0, 1])
        st.plotly_chart(fig_ff, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        fig_planning = line_mean_by_day(
            df_ts,
            metric="planning_quality",
            title="Planning quality over time",
            color=color,
            y_title="Planning quality",
        )
        fig_planning.update_yaxes(range=[0, 1])
        st.plotly_chart(fig_planning, use_container_width=True)

    with col_d:
        fig_backlog = line_mean_by_day(
            df_ts,
            metric="supervisor_backlog",
            title="Supervisor backlog over time",
            color=color,
            y_title="Backlog",
        )
        st.plotly_chart(fig_backlog, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Scenario comparison
# ═══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown("### All-scenario comparison")
    st.caption(
        "All scenarios are run with default scenario parameters. The shared external shock "
        "probability, run count, days and base seed come from the sidebar."
    )

    if st.button("🔄 Run all scenarios", type="secondary"):
        try:
            with st.spinner("Running all scenarios…"):
                df_all_ts, df_all_final, df_summary = cached_run_all_scenarios(
                    APP_DATA_VERSION,
                    runs=runs,
                    max_days=max_days,
                    base_seed=int(base_seed),
                    daily_shock_probability=daily_shock_probability,
                )
            st.session_state["all_result"] = (df_all_ts, df_all_final, df_summary)
        except Exception as exc:
            st.error("Scenario comparison failed.")
            st.code(traceback.format_exc())

    all_result = st.session_state.get("all_result", None)

    if all_result is None:
        st.info("Press **🔄 Run all scenarios** to see the comparison.")
    else:
        df_all_ts, df_all_final, df_summary = all_result
        df_all_ts = ensure_v24_columns(df_all_ts)
        df_all_final = ensure_v24_columns(df_all_final)

        compare_metadata = {
            "model": "DVM-ABM Mesa",
            "mode": "all_scenarios_comparison",
            "runs_per_scenario": runs,
            "max_days": max_days,
            "base_seed": int(base_seed),
            "daily_shock_probability": daily_shock_probability,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "note": "Scenario-specific sidebar overrides are not applied in this comparison tab.",
        }
        compare_excel_bytes = build_compare_excel(df_all_ts, df_all_final, compare_metadata)

        st.download_button(
            label="⬇️ Download scenario comparison Excel",
            data=compare_excel_bytes,
            file_name=make_download_filename("dvm_abm_scenario_comparison"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        preferred_compare_metrics = [
            "avg_weekly_ppc",
            "last_completed_weekly_ppc",
            "open_schedule_backlog",
            "cumulative_plan_failures",
            "project_delay_days",
            "avg_sa",
            "day",
            "avg_recovery_time",
            "total_idle_time",
            "total_idle_time_external",
            "firefighting_ratio",
            "planning_quality",
            "trust_in_data",
            "avg_adoption",
            "alternative_task_switches",
            "failed_task_switches",
            "supervisor_recovery_interventions",
        ]
        available_compare_metrics = [m for m in preferred_compare_metrics if m in df_all_final.columns]
        compare_metric = st.selectbox(
            "Comparison metric",
            options=available_compare_metrics,
            format_func=friendly_metric_name,
        )

        fig_cmp = go.Figure()
        for sc in SCENARIOS:
            sc_df = df_all_final[df_all_final["scenario"] == sc.name]
            fig_cmp.add_trace(
                go.Box(
                    y=sc_df[compare_metric],
                    name=scenario_label(sc.name),
                    marker_color=scenario_color(sc.name),
                    boxmean=True,
                )
            )
        fig_cmp.update_layout(
            title=f"{friendly_metric_name(compare_metric)} — all scenarios",
            yaxis_title=friendly_metric_name(compare_metric),
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

        st.markdown("#### Daily development")
        ts_col = st.selectbox(
            "Time-series metric",
            options=[
                "avg_sa",
                "avg_weekly_ppc",
                "open_schedule_backlog",
                "cumulative_plan_failures",
                "project_delay_days",
                "planning_quality",
                "trust_in_data",
                "firefighting_ratio",
                "active_external_blockages",
                "avg_recovery_time",
                "idle_time_due_to_external_disruptions",
            ],
            format_func=friendly_metric_name,
            key="ts_cmp",
        )
        st.plotly_chart(
            line_compare_by_scenario(df_all_ts, ts_col, f"{ts_col.replace('_', ' ')} — scenario comparison"),
            use_container_width=True,
        )

        st.markdown("#### Summary table")
        selected_cols = [
            "scenario",
            "avg_weekly_ppc",
            "last_completed_weekly_ppc",
            "open_schedule_backlog",
            "cumulative_plan_failures",
            "project_delay_days",
            "avg_sa",
            "day",
            "avg_recovery_time",
            "total_idle_time",
            "total_idle_time_external",
            "firefighting_ratio",
            "planning_quality",
            "trust_in_data",
            "avg_adoption",
            "alternative_task_switches",
            "failed_task_switches",
            "supervisor_recovery_interventions",
        ]
        selected_cols = [c for c in selected_cols if c in df_summary.columns]
        table = df_summary[selected_cols].copy()
        table["scenario"] = table["scenario"].map(lambda x: scenario_label(str(x)))
        st.dataframe(table, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Data
# ═══════════════════════════════════════════════════════════════════════════════
with tab_data:
    st.markdown("### Data tables")

    st.markdown("#### Final run metrics")
    st.dataframe(df_final, use_container_width=True)

    st.markdown("#### Time series")
    st.dataframe(df_ts, use_container_width=True)

    st.download_button(
        label="⬇️ Download current scenario Excel",
        data=single_excel_bytes,
        file_name=make_download_filename("dvm_abm_single_run", selected_scenario_name),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
