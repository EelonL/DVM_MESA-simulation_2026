from dvm_abm.scenarios import get_default_scenarios
from dvm_abm.analysis import run_simulation

def test_one_scenario_runs():
    df=run_simulation(get_default_scenarios()[0], run_id=0, seed=123, days=5)
    assert not df.empty
    assert "completed_tasks" in df.columns
