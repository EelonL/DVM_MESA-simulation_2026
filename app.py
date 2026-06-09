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
    page_title="DVM-ABM Simulator",
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
    "analog_vm": "Analog VM",
    "management_dashboard": "Management Dashboard",
    "forced_reporting_dvm": "Forced Reporting DVM",
    "workface_dvm": "Workface DVM",
    "dvm_lean_autonomous": "DVM Lean Autonomous",
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
    margin=dict(l=8, r=8, t=36, b=8),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)


# ── Helper functions ───────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def cached_load_scenarios() -> list[Scenario]:
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


def scenario_color(name: str) -> str:
    return SCENARIO_COLORS.get(name, "#378ADD")


def scenario_label(name: str) -> str:
    name = str(name)
    return SCENARIO_LABELS.get(name, name)


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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run one scenario multiple times and return timeseries + final runs."""
    scenarios = cached_load_scenarios()
    base_scenario = next(s for s in scenarios if s.name == scenario_name)

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
    runs: int,
    max_days: int,
    base_seed: int,
    daily_shock_probability: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run all scenarios with default parameters."""
    scenarios = cached_load_scenarios()
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


def line_mean_by_day(
    df: pd.DataFrame,
    metric: str,
    title: str,
    color: str,
    y_title: str | None = None,
) -> go.Figure:
    agg = df.groupby("day", observed=True)[metric].agg(["mean", "std"]).reset_index()
    agg["std"] = agg["std"].fillna(0)

    fig = go.Figure()
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
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Day",
        yaxis_title=y_title or metric,
        **PLOTLY_LAYOUT,
    )
    return fig


def line_compare_by_scenario(df: pd.DataFrame, metric: str, title: str) -> go.Figure:
    fig = go.Figure()
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
    fig.update_layout(title=title, xaxis_title="Day", yaxis_title=metric, **PLOTLY_LAYOUT)
    return fig


def minmax(series: pd.Series, invert: bool = False) -> pd.Series:
    s = series.astype(float)
    denom = s.max() - s.min()
    if denom == 0:
        out = pd.Series([0.5] * len(s), index=s.index)
    else:
        out = (s - s.min()) / denom
    return 1 - out if invert else out


# ── Load scenarios ─────────────────────────────────────────────────────────────
try:
    SCENARIOS = cached_load_scenarios()
except Exception as exc:
    st.error("Scenario configuration could not be loaded.")
    st.exception(exc)
    st.stop()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏗️ DVM-ABM Simulator")
    st.caption("Mesa version — Streamlit UI")
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

    active_scenario = scenario_by_name.get(selected_scenario_name, SCENARIOS[0])

    st.divider()

    st.markdown("**Simulation settings**")
    runs = st.slider("Runs", 5, 100, 30, step=5)
    max_days = st.slider("Max days", 50, 200, 100, step=10)
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

    run_btn = st.button("▶ Run simulation", type="primary", use_container_width=True)


# ── Session state and simulation run ───────────────────────────────────────────
cache_key = (
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
    "created_at": datetime.now().isoformat(timespec="seconds"),
}
single_excel_bytes = build_single_excel(df_ts, df_final, single_metadata)


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_results, tab_timeseries, tab_disruptions, tab_supervisor, tab_compare, tab_data = st.tabs(
    [
        "📊 Results",
        "📈 Time series",
        "⚡ Disruptions",
        "👷 Supervisor",
        "🔀 Scenario comparison",
        "📄 Data",
    ]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Results
# ═══════════════════════════════════════════════════════════════════════════════
with tab_results:
    st.markdown(f"### {label} — {runs} runs")

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

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Final day (avg)", f"{display_metric(df_final, 'day'):.0f}")
    c2.metric("PPC proxy", f"{display_metric(df_final, 'ppc_proxy'):.3f}")
    c3.metric("Crew SA", f"{display_metric(df_final, 'avg_sa'):.3f}")
    c4.metric("Recovery time", f"{display_metric(df_final, 'avg_recovery_time'):.2f} d")
    c5.metric("Firefighting ratio", f"{display_metric(df_final, 'firefighting_ratio'):.1%}")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        fig = go.Figure()
        fig.add_trace(
            go.Histogram(
                x=df_final["ppc_proxy"],
                nbinsx=20,
                marker_color=color,
                opacity=0.85,
                name="PPC proxy",
            )
        )
        fig.update_layout(
            title="PPC proxy distribution across runs",
            xaxis_title="PPC proxy",
            yaxis_title="Runs",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        fig2 = go.Figure()
        fig2.add_trace(
            go.Box(
                y=df_final["total_idle_time"],
                name="Idle total",
                marker_color=color,
                boxmean=True,
            )
        )
        if "total_idle_time_external" in df_final.columns:
            fig2.add_trace(
                go.Box(
                    y=df_final["total_idle_time_external"],
                    name="Idle external",
                    marker_color="#D85A30",
                    boxmean=True,
                )
            )
        fig2.update_layout(
            title="Idle time per run",
            yaxis_title="Days",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        fig3 = px.scatter(
            df_final,
            x="avg_sa",
            y="ppc_proxy",
            color_discrete_sequence=[color],
            opacity=0.65,
            labels={"avg_sa": "Crew SA", "ppc_proxy": "PPC proxy"},
            title="Crew situational awareness vs PPC proxy",
            trendline="ols" if len(df_final) >= 3 else None,
        )
        fig3.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        fig4 = px.scatter(
            df_final,
            x="avg_sa",
            y="avg_recovery_time",
            color_discrete_sequence=[color],
            opacity=0.65,
            labels={"avg_sa": "Crew SA", "avg_recovery_time": "Average recovery time"},
            title="Crew situational awareness vs recovery time",
            trendline="ols" if len(df_final) >= 3 else None,
        )
        fig4.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig4, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Time series
# ═══════════════════════════════════════════════════════════════════════════════
with tab_timeseries:
    st.markdown(f"### {label} — daily averages")

    metric_options = [
        "avg_sa",
        "ppc_proxy",
        "planning_quality",
        "trust_in_data",
        "trust_in_management",
        "avg_adoption",
        "avg_effective_use",
        "supervisor_utilization",
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
        format_func=lambda x: x.replace("_", " "),
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
    c3.metric("Alternative switches", f"{display_metric(df_final, 'alternative_task_switches'):.1f}")
    c4.metric("External idle time", f"{display_metric(df_final, 'idle_time_due_to_external_disruptions'):.1f} d")

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
            title="Disruption type distribution",
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
            title="Average recovery time per run",
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
                title={"text": "Alternative workface success rate"},
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

    st.markdown("#### Recovery mechanism")
    fig_rec = go.Figure()
    fig_rec.add_trace(
        go.Box(
            y=df_final["alternative_task_switches"],
            name="Alternative switches",
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Firefighting ratio", f"{display_metric(df_final, 'firefighting_ratio'):.1%}")
    c2.metric("Supervisor utilization", f"{display_metric(df_final, 'supervisor_utilization'):.1%}")
    c3.metric("Unresolved questions", f"{display_metric(df_final, 'cumulative_unresolved_questions'):.1f}")
    c4.metric("Backlog", f"{display_metric(df_final, 'supervisor_backlog'):.2f} h")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        sup_agg = df_ts.groupby("day", observed=True)[
            ["cumulative_reactive_time", "cumulative_planning_time"]
        ].mean().reset_index()
        fig_sup = go.Figure()
        fig_sup.add_trace(
            go.Scatter(
                x=sup_agg["day"],
                y=sup_agg["cumulative_reactive_time"],
                name="Reactive time",
                mode="lines",
                line=dict(color="#D85A30", width=2),
            )
        )
        fig_sup.add_trace(
            go.Scatter(
                x=sup_agg["day"],
                y=sup_agg["cumulative_planning_time"],
                name="Planning time",
                mode="lines",
                line=dict(color="#1D9E75", width=2),
            )
        )
        fig_sup.update_layout(
            title="Cumulative supervisor time",
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

        compare_metric = st.selectbox(
            "Comparison metric",
            options=[
                "ppc_proxy",
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
            ],
            format_func=lambda x: x.replace("_", " "),
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
            title=f"{compare_metric.replace('_', ' ')} — all scenarios",
            yaxis_title=compare_metric,
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

        st.markdown("#### Daily development")
        ts_col = st.selectbox(
            "Time-series metric",
            options=[
                "avg_sa",
                "ppc_proxy",
                "planning_quality",
                "trust_in_data",
                "firefighting_ratio",
                "active_external_blockages",
                "avg_recovery_time",
                "idle_time_due_to_external_disruptions",
            ],
            format_func=lambda x: x.replace("_", " "),
            key="ts_cmp",
        )
        st.plotly_chart(
            line_compare_by_scenario(df_all_ts, ts_col, f"{ts_col.replace('_', ' ')} — scenario comparison"),
            use_container_width=True,
        )

        st.markdown("#### Summary table")
        selected_cols = [
            "scenario",
            "ppc_proxy",
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
