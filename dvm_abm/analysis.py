import pandas as pd
from .model import DVMConstructionModel
from .scenarios import get_default_scenarios

def run_simulation(scenario, run_id:int, seed:int, days:int=100, daily_shock_probability:float=.32):
    model=DVMConstructionModel(scenario=scenario, seed=seed, max_days=days, daily_shock_probability=daily_shock_probability)
    while model.running:
        model.step()
    df=model.get_model_dataframe(); df["run"]=run_id; df["scenario"]=scenario.name
    return df

def run_scenario_comparison(scenarios=None, runs:int=30, days:int=100, base_seed:int=20260609, daily_shock_probability:float=.32):
    scenarios=scenarios or get_default_scenarios(); frames=[]
    for sc in scenarios:
        for run in range(runs):
            frames.append(run_simulation(sc, run, base_seed+run, days, daily_shock_probability))
    return pd.concat(frames, ignore_index=True)

def final_rows_by_run(df):
    return df.sort_values(["scenario","run","day"]).groupby(["scenario","run"], observed=True).tail(1).reset_index(drop=True)

def summarize_final_runs(final_df):
    num=final_df.select_dtypes(include="number").columns
    return final_df.groupby("scenario", observed=True)[num].mean().reset_index().round(4)
