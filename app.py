"""
DVM-ABM Streamlit UI
Interaktiivinen käyttöliittymä dvm_abm_mvp_v23.py -simulaatiolle.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dataclasses import replace
import sys
import os
import io
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from dvm_abm_mvp_v23 import (
    SCENARIOS, Scenario, run_simulation, summarize,
    final_rows_by_run, SimulationMetrics,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DVM-ABM Simulator",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colour palette per scenario ────────────────────────────────────────────────
SCENARIO_COLORS = {
    "analog_vm":            "#D85A30",
    "management_dashboard": "#888780",
    "forced_reporting_dvm": "#BA7517",
    "workface_dvm":         "#378ADD",
    "dvm_lean_autonomous":  "#1D9E75",
}

SCENARIO_LABELS = {
    "analog_vm":            "Analog VM",
    "management_dashboard": "Management Dashboard",
    "forced_reporting_dvm": "Forced Reporting DVM",
    "workface_dvm":         "Workface DVM",
    "dvm_lean_autonomous":  "DVM Lean Autonomous",
}

DISRUPTION_LABELS = {
    "material_shortage_count":    "Material shortage",
    "logistics_delay_count":      "Logistics delay",
    "lifting_delay_count":        "Lifting delay",
    "design_missing_count":       "Design missing",
    "equipment_unavailable_count":"Equipment unavail.",
    "weather_condition_count":    "Weather/site",
}

# ── Plotly shared theme ────────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", size=12, color="#444"),
    margin=dict(l=8, r=8, t=32, b=8),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)

# ── Excel export helpers ───────────────────────────────────────────────────────
def _sanitize_sheet_name(name: str) -> str:
    """Excel sheet names have a 31-character limit and cannot contain some chars."""
    invalid = ["\\", "/", "*", "?", ":", "[", "]"]
    for ch in invalid:
        name = name.replace(ch, "_")
    return name[:31]


def build_excel_download(sheets: dict[str, pd.DataFrame], metadata: dict | None = None) -> bytes:
    """Build an Excel workbook in memory for Streamlit download_button.

    Parameters
    ----------
    sheets:
        Dictionary where keys are sheet names and values are DataFrames.
    metadata:
        Optional metadata written to a separate sheet.

    Returns
    -------
    bytes:
        XLSX file content.
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if metadata:
            meta_df = pd.DataFrame(
                [{"parameter": key, "value": value} for key, value in metadata.items()]
            )
            meta_df.to_excel(writer, sheet_name="metadata", index=False)

        for sheet_name, df in sheets.items():
            safe_name = _sanitize_sheet_name(sheet_name)
            df.to_excel(writer, sheet_name=safe_name, index=False)

            # Basic usability formatting
            ws = writer.book[safe_name]
            ws.freeze_panes = "A2"
            for col_cells in ws.columns:
                max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col_cells)
                ws.column_dimensions[col_cells[0].column_letter].width = min(max(max_len + 2, 10), 40)

    output.seek(0)
    return output.getvalue()


def scenario_summary_from_final(df_final: pd.DataFrame) -> pd.DataFrame:
    """Create a compact one-scenario summary table from final run metrics."""
    numeric = df_final.select_dtypes(include="number")
    summary = numeric.mean().to_frame("mean").reset_index().rename(columns={"index": "metric"})
    summary["std"] = numeric.std().values
    summary["min"] = numeric.min().values
    summary["max"] = numeric.max().values
    return summary.round(4)


def compare_summary_from_final(df_all: pd.DataFrame) -> pd.DataFrame:
    """Create scenario-level mean summary for all-scenario comparison."""
    numeric_cols = df_all.select_dtypes(include="number").columns.tolist()
    keep = [
        "day", "ppc_proxy", "avg_sa", "planning_quality",
        "avg_recovery_time", "total_idle_time", "total_idle_time_external",
        "alternative_task_switches", "failed_task_switches",
        "supervisor_recovery_interventions", "firefighting_ratio",
        "supervisor_backlog", "trust_in_data", "avg_adoption",
    ]
    keep = [c for c in keep if c in numeric_cols]
    return df_all.groupby("scenario", observed=True)[keep].mean().reset_index().round(4)


def make_download_filename(prefix: str, scenario_name: str | None = None) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if scenario_name:
        return f"{prefix}_{scenario_name}_{stamp}.xlsx"
    return f"{prefix}_{stamp}.xlsx"


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏗️ DVM-ABM Simulator")
    st.caption("v2.3 — mekanismitestausmalli")
    st.caption("Tulokset voi ladata Excelinä Tulokset- ja Skenaariovertailu-välilehdiltä.")
    st.divider()

    # Scenario selection
    st.markdown("**Skenaario**")
    selected_scenario_name = st.selectbox(
        "Valitse skenaario",
        options=[s.name for s in SCENARIOS],
        format_func=lambda n: SCENARIO_LABELS.get(n, n),
        label_visibility="collapsed",
    )
    active_scenario: Scenario = next(s for s in SCENARIOS if s.name == selected_scenario_name)

    st.divider()

    # Run settings
    st.markdown("**Simulointiasetukset**")
    runs = st.slider("Ajoja (runs)", 5, 100, 30, step=5)
    max_days = st.slider("Päiviä (max)", 50, 200, 100, step=10)
    base_seed = st.number_input("Base seed", value=20260609, step=1)

    st.divider()

    # Override: external disruptions
    st.markdown("**Ulkoiset häiriöt**")
    ext_rate = st.slider(
        "Häiriötodennäköisyys / pv",
        0.0, 1.0, float(active_scenario.external_disruption_rate), step=0.005,
    )
    ext_severity = st.slider(
        "Vakavuus (severity)",
        0.1, 2.0, float(active_scenario.external_disruption_severity), step=0.05,
    )

    st.divider()

    # Override: socio-psychological
    st.markdown("**Psykologiset tekijät**")
    autonomy = st.slider(
        "Autonomia",
        0.0, 1.0, float(active_scenario.autonomy_level), step=0.01,
    )
    surveillance = st.slider(
        "Valvontapaine",
        0.0, 1.0, float(active_scenario.perceived_surveillance), step=0.01,
    )
    reporting_burden = st.slider(
        "Raportointitaakka",
        0.0, 1.0, float(active_scenario.reporting_burden), step=0.01,
    )

    st.divider()

    # Override: supervisor
    st.markdown("**Työnjohtaja**")
    supervisor_capacity = st.slider(
        "Kapasiteetti (h/pv)",
        2.0, 16.0, float(active_scenario.supervisor_capacity), step=0.5,
    )

    run_btn = st.button("▶ Aja simulaatio", type="primary", use_container_width=True)

# ── Apply overrides ────────────────────────────────────────────────────────────
modified_scenario: Scenario = replace(
    active_scenario,
    external_disruption_rate=ext_rate,
    external_disruption_severity=ext_severity,
    autonomy_level=autonomy,
    perceived_surveillance=surveillance,
    reporting_burden=reporting_burden,
    supervisor_capacity=supervisor_capacity,
)

# ── Cache key: all params that affect output ───────────────────────────────────
cache_key = (
    selected_scenario_name, runs, max_days, int(base_seed),
    round(ext_rate, 4), round(ext_severity, 4),
    round(autonomy, 4), round(surveillance, 4),
    round(reporting_burden, 4), round(supervisor_capacity, 4),
)

# ── Run simulation (cached per unique params) ──────────────────────────────────
@st.cache_data(show_spinner=False)
def cached_run(scenario_key, runs, max_days, seed, ext_rate, ext_severity,
               autonomy, surveillance, reporting_burden, supervisor_capacity):
    scenario = next(s for s in SCENARIOS if s.name == scenario_key)
    scenario = replace(
        scenario,
        external_disruption_rate=ext_rate,
        external_disruption_severity=ext_severity,
        autonomy_level=autonomy,
        perceived_surveillance=surveillance,
        reporting_burden=reporting_burden,
        supervisor_capacity=supervisor_capacity,
    )
    all_rows = []
    for run_id in range(runs):
        all_rows.extend(run_simulation(scenario, run_id, seed + run_id, days=max_days))
    return all_rows


@st.cache_data(show_spinner=False)
def cached_all_scenarios(runs, max_days, seed):
    """Run all 5 scenarios with default params for comparison tab."""
    all_rows = []
    for scenario in SCENARIOS:
        for run_id in range(runs):
            all_rows.extend(run_simulation(scenario, run_id, seed + run_id, days=max_days))
    return all_rows


# Trigger on button press or first load
if "sim_rows" not in st.session_state:
    st.session_state["sim_rows"] = None
    st.session_state["cache_key"] = None

if run_btn or st.session_state["cache_key"] != cache_key:
    with st.spinner("Ajetaan simulaatio…"):
        rows = cached_run(*cache_key)
        st.session_state["sim_rows"] = rows
        st.session_state["cache_key"] = cache_key

rows = st.session_state["sim_rows"]

if rows is None:
    st.info("Paina **▶ Aja simulaatio** käynnistääksesi.")
    st.stop()

# ── Helpers ────────────────────────────────────────────────────────────────────
df_ts = pd.DataFrame([r.__dict__ for r in rows])
df_final = pd.DataFrame([r.__dict__ for r in final_rows_by_run(rows)])

df_summary_single = scenario_summary_from_final(df_final)

single_metadata = {
    "model_version": "v2.3",
    "selected_scenario": selected_scenario_name,
    "scenario_label": SCENARIO_LABELS.get(selected_scenario_name, selected_scenario_name),
    "runs": runs,
    "max_days": max_days,
    "base_seed": int(base_seed),
    "external_disruption_rate": ext_rate,
    "external_disruption_severity": ext_severity,
    "autonomy_level": autonomy,
    "perceived_surveillance": surveillance,
    "reporting_burden": reporting_burden,
    "supervisor_capacity": supervisor_capacity,
    "created_at": datetime.now().isoformat(timespec="seconds"),
}

single_excel_bytes = build_excel_download(
    sheets={
        "summary": df_summary_single,
        "final_run_metrics": df_final,
        "timeseries": df_ts,
    },
    metadata=single_metadata,
)

def mean_col(col):
    return df_final[col].mean() if col in df_final.columns else 0.0

def delta_vs_analog(col):
    """Return delta string vs analog_vm default for the same col."""
    return None  # Only meaningful in compare mode; omit here to keep it simple

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_results, tab_timeseries, tab_disruptions, tab_supervisor, tab_compare = st.tabs([
    "📊 Tulokset",
    "📈 Aikasarjat",
    "⚡ Häiriöt",
    "👷 Työnjohtaja",
    "🔀 Skenaariovertailu",
])

color = SCENARIO_COLORS.get(selected_scenario_name, "#378ADD")
label = SCENARIO_LABELS.get(selected_scenario_name, selected_scenario_name)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Tulokset
# ══════════════════════════════════════════════════════════════════════════════
with tab_results:
    st.markdown(f"### {label} — {runs} ajoa")

    dcol1, dcol2 = st.columns([1, 3])
    with dcol1:
        st.download_button(
            label="⬇️ Lataa tämän ajon Excel",
            data=single_excel_bytes,
            file_name=make_download_filename("dvm_abm_single_run", selected_scenario_name),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with dcol2:
        st.caption("Excel sisältää metadata-, summary-, final_run_metrics- ja timeseries-välilehdet.")

    # KPI row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Lopetuspäivä (ka)", f"{mean_col('day'):.0f} pv")
    c2.metric("PPC-proxy (ka)", f"{mean_col('ppc_proxy'):.3f}")
    c3.metric("SA-taso (ka)", f"{mean_col('avg_sa'):.3f}")
    c4.metric("Recovery-aika (ka)", f"{mean_col('avg_recovery_time'):.2f} pv")
    c5.metric("Firefighting-ratio", f"{mean_col('firefighting_ratio'):.2%}")

    st.divider()

    col_a, col_b = st.columns(2)

    # Distribution: final PPC-proxy across runs
    with col_a:
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=df_final["ppc_proxy"],
            nbinsx=20,
            marker_color=color,
            opacity=0.85,
            name="PPC-proxy",
        ))
        fig.update_layout(
            title="PPC-proxy — jakauma (runs)",
            xaxis_title="PPC-proxy",
            yaxis_title="Ajot",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Box: idle time breakdown
    with col_b:
        fig2 = go.Figure()
        fig2.add_trace(go.Box(
            y=df_final["total_idle_time"],
            name="Idle (kaikki)",
            marker_color=color,
            boxmean=True,
        ))
        fig2.add_trace(go.Box(
            y=df_final["total_idle_time_external"],
            name="Idle (ext. häiriöt)",
            marker_color="#D85A30",
            boxmean=True,
        ))
        fig2.update_layout(
            title="Idle-aika per ajo (pv)",
            yaxis_title="Päivää",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Scatter: SA vs PPC-proxy
    col_c, col_d = st.columns(2)
    with col_c:
        fig3 = px.scatter(
            df_final,
            x="avg_sa", y="ppc_proxy",
            color_discrete_sequence=[color],
            opacity=0.6,
            labels={"avg_sa": "SA-taso (ka)", "ppc_proxy": "PPC-proxy"},
            title="SA-taso vs PPC-proxy",
            trendline="ols",
        )
        fig3.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        fig4 = px.scatter(
            df_final,
            x="trust_in_data", y="avg_adoption",
            color_discrete_sequence=[color],
            opacity=0.6,
            labels={"trust_in_data": "Luottamus dataan", "avg_adoption": "Adoptio (ka)"},
            title="Luottamus vs DVM-adoptio",
            trendline="ols",
        )
        fig4.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig4, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Aikasarjat
# ══════════════════════════════════════════════════════════════════════════════
with tab_timeseries:
    st.markdown(f"### {label} — päiväkohtaiset keskiarvot")

    ts_metric = st.selectbox("Metriikka", options=[
        "avg_sa", "ppc_proxy", "planning_quality",
        "trust_in_data", "trust_in_management",
        "avg_adoption", "avg_effective_use",
        "supervisor_utilization", "firefighting_ratio",
        "total_idle_time", "total_idle_time_external",
        "avg_recovery_time",
    ], format_func=lambda x: x.replace("_", " "))

    # Mean + std band per day
    agg = df_ts.groupby("day")[ts_metric].agg(["mean", "std"]).reset_index()
    agg["std"] = agg["std"].fillna(0)

    fig_ts = go.Figure()
    fig_ts.add_trace(go.Scatter(
        x=pd.concat([agg["day"], agg["day"][::-1]]),
        y=pd.concat([agg["mean"] + agg["std"], (agg["mean"] - agg["std"])[::-1]]),
        fill="toself",
        fillcolor=color.replace(")", ", 0.15)").replace("rgb", "rgba") if color.startswith("rgb") else color + "26",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False,
        name="±1 SD",
    ))
    fig_ts.add_trace(go.Scatter(
        x=agg["day"], y=agg["mean"],
        mode="lines",
        line=dict(color=color, width=2),
        name="Keskiarvo",
    ))
    fig_ts.update_layout(
        title=f"{ts_metric.replace('_', ' ')} — päivittäinen ka ± SD",
        xaxis_title="Päivä",
        yaxis_title=ts_metric,
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    # Individual runs (togglable)
    show_runs = st.checkbox("Näytä yksittäiset ajot (max 20)")
    if show_runs:
        fig_ind = go.Figure()
        for run_id in df_ts["run"].unique()[:20]:
            run_df = df_ts[df_ts["run"] == run_id]
            fig_ind.add_trace(go.Scatter(
                x=run_df["day"], y=run_df[ts_metric],
                mode="lines",
                line=dict(color=color, width=0.8),
                opacity=0.35,
                showlegend=False,
            ))
        fig_ind.update_layout(
            title="Yksittäiset ajot",
            xaxis_title="Päivä",
            yaxis_title=ts_metric,
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_ind, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Häiriöt
# ══════════════════════════════════════════════════════════════════════════════
with tab_disruptions:
    st.markdown(f"### {label} — häiriöanalyysi")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Häiriöitä yhteensä (ka/ajo)", f"{mean_col('external_disruptions'):.1f}")
    c2.metric("Avg recovery-aika", f"{mean_col('avg_recovery_time'):.2f} pv")
    c3.metric("Vaihtomesta-kytkennät (ka)", f"{mean_col('alternative_task_switches'):.1f}")
    c4.metric("Idle (ext. häiriöt) ka", f"{mean_col('idle_time_due_to_external_disruptions'):.1f} pv")

    st.divider()

    col_a, col_b = st.columns(2)

    # Disruption type breakdown
    with col_a:
        disrupt_cols = list(DISRUPTION_LABELS.keys())
        disrupt_means = {DISRUPTION_LABELS[c]: df_final[c].mean() for c in disrupt_cols if c in df_final.columns}
        fig_d = go.Figure(go.Bar(
            x=list(disrupt_means.values()),
            y=list(disrupt_means.keys()),
            orientation="h",
            marker_color=color,
            opacity=0.85,
        ))
        fig_d.update_layout(
            title="Häiriötyyppijakauma (ka/ajo)",
            xaxis_title="Kpl",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_d, use_container_width=True)

    # Recovery time distribution
    with col_b:
        fig_r = go.Figure()
        fig_r.add_trace(go.Histogram(
            x=df_final["avg_recovery_time"],
            nbinsx=15,
            marker_color=color,
            opacity=0.85,
            name="Recovery-aika",
        ))
        fig_r.update_layout(
            title="Avg recovery-aika per ajo",
            xaxis_title="Päivää",
            yaxis_title="Ajot",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_r, use_container_width=True)

    # Alternative task switch success rate
    col_c, col_d = st.columns(2)
    with col_c:
        total_sw = df_final["alternative_task_switches"] + df_final["failed_task_switches"]
        success_rate = (df_final["alternative_task_switches"] / total_sw.replace(0, 1)).mean()
        fig_sw = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(success_rate * 100, 1),
            number={"suffix": "%"},
            title={"text": "Vaihtomesta-onnistumisprosentti"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 40], "color": "#fcebeb"},
                    {"range": [40, 70], "color": "#faeeda"},
                    {"range": [70, 100], "color": "#eaf3de"},
                ],
            },
        ))
        fig_sw.update_layout(**PLOTLY_LAYOUT, height=260)
        st.plotly_chart(fig_sw, use_container_width=True)

    with col_d:
        fig_bl = go.Figure()
        fig_bl.add_trace(go.Scatter(
            x=df_ts.groupby("day")["active_external_blockages"].mean().index,
            y=df_ts.groupby("day")["active_external_blockages"].mean().values,
            mode="lines",
            fill="tozeroy",
            line=dict(color=color, width=1.5),
            fillcolor=color + "33",
            name="Aktiiviset blockaget",
        ))
        fig_bl.update_layout(
            title="Aktiiviset ulkoiset blockaget / päivä (ka)",
            xaxis_title="Päivä",
            yaxis_title="Kpl",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_bl, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Työnjohtaja
# ══════════════════════════════════════════════════════════════════════════════
with tab_supervisor:
    st.markdown(f"### {label} — työnjohtajan kuormitus")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Firefighting-ratio (ka)", f"{mean_col('firefighting_ratio'):.2%}")
    c2.metric("Supervisor utilization (ka)", f"{mean_col('supervisor_utilization'):.2%}")
    c3.metric("Unresolved questions (ka)", f"{mean_col('cumulative_unresolved_questions'):.1f}")
    c4.metric("Backlog (ka lopussa)", f"{mean_col('supervisor_backlog'):.2f} h")

    st.divider()
    col_a, col_b = st.columns(2)

    # Reactive vs planning time timeseries
    with col_a:
        sup_agg = df_ts.groupby("day")[
            ["cumulative_reactive_time", "cumulative_planning_time"]
        ].mean().reset_index()
        fig_sup = go.Figure()
        fig_sup.add_trace(go.Scatter(
            x=sup_agg["day"], y=sup_agg["cumulative_reactive_time"],
            name="Reaktiivinen aika", mode="lines",
            line=dict(color="#D85A30", width=2),
        ))
        fig_sup.add_trace(go.Scatter(
            x=sup_agg["day"], y=sup_agg["cumulative_planning_time"],
            name="Suunnitteluaika", mode="lines",
            line=dict(color="#1D9E75", width=2),
        ))
        fig_sup.update_layout(
            title="Kumulatiivinen aika (ka, pv)",
            xaxis_title="Päivä",
            yaxis_title="Tuntia",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_sup, use_container_width=True)

    # Firefighting ratio over time
    with col_b:
        ff_agg = df_ts.groupby("day")["firefighting_ratio"].agg(["mean", "std"]).reset_index()
        fig_ff = go.Figure()
        fig_ff.add_trace(go.Scatter(
            x=ff_agg["day"], y=ff_agg["mean"],
            mode="lines", line=dict(color="#D85A30", width=2),
            name="Firefighting-ratio",
        ))
        fig_ff.add_hline(y=0.5, line_dash="dash", line_color="#888780",
                         annotation_text="50% kynnys", annotation_position="top right")
        fig_ff.update_layout(
            title="Firefighting-ratio / päivä (ka)",
            xaxis_title="Päivä",
            yaxis_title="Ratio",
            yaxis=dict(range=[0, 1]),
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_ff, use_container_width=True)

    # Supervisor backlog over time
    col_c, col_d = st.columns(2)
    with col_c:
        bl_agg = df_ts.groupby("day")["supervisor_backlog"].mean()
        fig_bl2 = go.Figure()
        fig_bl2.add_trace(go.Scatter(
            x=bl_agg.index, y=bl_agg.values,
            fill="tozeroy", mode="lines",
            line=dict(color=color, width=1.5),
            fillcolor=color + "33",
            name="Backlog",
        ))
        fig_bl2.update_layout(
            title="Työnjohtajan backlog / päivä (ka, h)",
            xaxis_title="Päivä",
            yaxis_title="Tuntia",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_bl2, use_container_width=True)

    with col_d:
        fig_rd = go.Figure()
        fig_rd.add_trace(go.Histogram(
            x=df_final["supervisor_response_delay"],
            nbinsx=15,
            marker_color=color,
            opacity=0.85,
        ))
        fig_rd.update_layout(
            title="Response delay -jakauma (lopputila, runs)",
            xaxis_title="Viive",
            yaxis_title="Ajot",
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_rd, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Skenaariovertailu
# ══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.markdown("### Kaikkien skenaarioiden vertailu")
    st.caption("Kaikki skenaariot ajetaan oletusparametreilla (sivupalkin overridet eivät vaikuta tähän).")

    if st.button("🔄 Aja kaikki skenaariot", type="secondary"):
        with st.spinner("Ajetaan kaikki 5 skenaariota…"):
            all_rows = cached_all_scenarios(runs, max_days, int(base_seed))
            st.session_state["all_rows"] = all_rows

    all_rows = st.session_state.get("all_rows", None)

    if all_rows is None:
        st.info("Paina **🔄 Aja kaikki skenaariot** nähdäksesi vertailun.")
    else:
        df_all = pd.DataFrame([r.__dict__ for r in final_rows_by_run(all_rows)])
        df_all_ts = pd.DataFrame([r.__dict__ for r in all_rows])

        compare_summary_df = compare_summary_from_final(df_all)
        compare_metadata = {
            "model_version": "v2.3",
            "mode": "all_scenarios_comparison",
            "runs_per_scenario": runs,
            "max_days": max_days,
            "base_seed": int(base_seed),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "note": "Sidebar parameter overrides do not affect this comparison tab in the current UI.",
        }
        compare_excel_bytes = build_excel_download(
            sheets={
                "scenario_summary": compare_summary_df,
                "final_run_metrics": df_all,
                "timeseries": df_all_ts,
            },
            metadata=compare_metadata,
        )

        st.download_button(
            label="⬇️ Lataa skenaariovertailu Excelinä",
            data=compare_excel_bytes,
            file_name=make_download_filename("dvm_abm_scenario_comparison"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        compare_metric = st.selectbox("Vertailtava metriikka", options=[
            "ppc_proxy", "avg_sa", "day", "avg_recovery_time",
            "total_idle_time", "total_idle_time_external",
            "firefighting_ratio", "planning_quality",
            "trust_in_data", "avg_adoption",
        ], format_func=lambda x: x.replace("_", " "))

        # Box plot per scenario
        fig_cmp = go.Figure()
        for sc in SCENARIOS:
            sc_df = df_all[df_all["scenario"] == sc.name]
            fig_cmp.add_trace(go.Box(
                y=sc_df[compare_metric],
                name=SCENARIO_LABELS[sc.name],
                marker_color=SCENARIO_COLORS[sc.name],
                boxmean=True,
            ))
        fig_cmp.update_layout(
            title=f"{compare_metric.replace('_', ' ')} — kaikki skenaariot",
            yaxis_title=compare_metric,
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

        # Timeseries comparison
        st.markdown("#### Päiväkohtainen kehitys")
        ts_col = st.selectbox("Aikasarjametriikka", options=[
            "avg_sa", "ppc_proxy", "planning_quality",
            "trust_in_data", "firefighting_ratio",
            "active_external_blockages",
        ], format_func=lambda x: x.replace("_", " "), key="ts_cmp")

        fig_ts_cmp = go.Figure()
        for sc in SCENARIOS:
            sc_ts = df_all_ts[df_all_ts["scenario"] == sc.name].groupby("day")[ts_col].mean()
            fig_ts_cmp.add_trace(go.Scatter(
                x=sc_ts.index, y=sc_ts.values,
                name=SCENARIO_LABELS[sc.name],
                mode="lines",
                line=dict(color=SCENARIO_COLORS[sc.name], width=2),
            ))
        fig_ts_cmp.update_layout(
            title=f"{ts_col.replace('_', ' ')} — skenaariovertailu (ka)",
            xaxis_title="Päivä",
            yaxis_title=ts_col,
            **PLOTLY_LAYOUT,
        )
        st.plotly_chart(fig_ts_cmp, use_container_width=True)

        # Summary table
        st.markdown("#### Yhteenvetotaulukko")
        summary_cols = [
            "scenario", "ppc_proxy", "avg_sa", "day",
            "avg_recovery_time", "total_idle_time",
            "firefighting_ratio", "planning_quality",
            "trust_in_data", "avg_adoption",
            "alternative_task_switches",
        ]
        summary_df = df_all[[c for c in summary_cols if c in df_all.columns]].groupby("scenario").mean().round(3)
        summary_df.index = [SCENARIO_LABELS.get(i, i) for i in summary_df.index]
        st.dataframe(summary_df.style.background_gradient(cmap="RdYlGn", axis=0), use_container_width=True)
