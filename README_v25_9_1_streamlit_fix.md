# v25.9.1 Streamlit frozen Scenario fix

This patch fixes a Streamlit Cloud runtime error caused by assigning a virtual
scenario parameter to a frozen dataclass instance:

`dataclasses.FrozenInstanceError: cannot assign to field 'field_interaction_capacity_multiplier'`

The model logic is unchanged. The Streamlit app now attaches
`field_interaction_capacity_multiplier` using `object.__setattr__`, which is the
same idea already used safely in the sensitivity harness for virtual scenario
parameters.

## Files to replace

- `app.py`

The package also includes the unchanged v25.9 versions of:

- `dvm_abm/model.py`
- `dvm_abm/agents.py`
- `sensitivity_harness_v9/`

## Streamlit Cloud

After replacing `app.py`, commit and push to GitHub, then in Streamlit Cloud run:

- Clear cache
- Reboot

Cache version:

`APP_DATA_VERSION = "v25_9_1_streamlit_frozen_scenario_fix"`
