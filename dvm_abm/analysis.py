from .model import DVMConstructionModel
import pandas as pd

def run_simulation(scenario, run, seed, days, daily_shock_probability=.32):
    """Run one simulation.

    In v24.7, days means planned project duration. The model itself continues
    beyond this value until all tasks are complete or a hard safety limit is reached.
    """
    model = DVMConstructionModel(
        scenario=scenario,
        seed=seed,
        max_days=days,
        daily_shock_probability=daily_shock_probability,
    )
    while model.running:
        model.step()
    df = model.get_model_dataframe()
    df["run"] = run
    return df

def run_scenario_comparison(scenarios, runs, days, base_seed, daily_shock_probability=.32):
    frames=[]
    for sc in scenarios:
        for run in range(runs):
            frames.append(run_simulation(sc, run, base_seed+run, days, daily_shock_probability))
    return pd.concat(frames, ignore_index=True)

def final_rows_by_run(df):
    return df.sort_values("day").groupby(["scenario","run"], as_index=False).tail(1)

def summarize_final_runs(df_final):
    numeric=df_final.select_dtypes("number").columns
    return df_final.groupby("scenario")[list(numeric)].mean().reset_index()
