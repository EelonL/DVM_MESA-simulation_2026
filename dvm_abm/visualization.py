import plotly.graph_objects as go
SCENARIO_COLORS={"analog_vm":"#D85A30","management_dashboard":"#888780","forced_reporting_dvm":"#BA7517","workface_dvm":"#378ADD","dvm_lean_autonomous":"#1D9E75"}
SCENARIO_LABELS={"analog_vm":"Analog VM","management_dashboard":"Management Dashboard","forced_reporting_dvm":"Forced Reporting DVM","workface_dvm":"Workface DVM","dvm_lean_autonomous":"DVM Lean Autonomous"}
PLOTLY_LAYOUT=dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(family="sans-serif",size=12,color="#444"),margin=dict(l=8,r=8,t=32,b=8),legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="left",x=0))
def line_by_scenario(df, metric, title):
    fig=go.Figure()
    for sc,g in df.groupby("scenario", observed=True):
        ts=g.groupby("day")[metric].mean()
        fig.add_trace(go.Scatter(x=ts.index,y=ts.values,name=SCENARIO_LABELS.get(str(sc),str(sc)),mode="lines",line=dict(color=SCENARIO_COLORS.get(str(sc),"#378ADD"),width=2)))
    fig.update_layout(title=title,xaxis_title="Day",yaxis_title=metric,**PLOTLY_LAYOUT)
    return fig
