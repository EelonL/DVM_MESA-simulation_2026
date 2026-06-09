from pathlib import Path
from dvm_abm.scenarios import load_scenarios
from dvm_abm.analysis import run_scenario_comparison, final_rows_by_run, summarize_final_runs

def main():
    scenarios=load_scenarios(); df=run_scenario_comparison(scenarios, runs=10, days=100)
    final=final_rows_by_run(df); summary=summarize_final_runs(final)
    out=Path("outputs/csv"); out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out/"mesa_timeseries.csv", index=False); final.to_csv(out/"mesa_final_run_metrics.csv", index=False); summary.to_csv(out/"mesa_summary.csv", index=False)
    print(summary)
if __name__=="__main__": main()
