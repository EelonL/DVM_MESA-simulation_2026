# DVM-ABM Simulation

**Digital Visual Management Agent-Based Simulation for Construction Production Control**

This repository contains an exploratory **Mesa-based agent-based simulation model** and a **Streamlit user interface** for studying how Digital Visual Management (DVM) may influence construction production flow, workface situational awareness, supervisor coordination workload, planning quality, and recovery from external disruptions.

The current implementation is intended for **research discussion, scenario exploration, and model development**. It is not a calibrated forecasting tool.

---

## 1. What this model is about

The model explores how different forms of Digital Visual Management affect construction production systems.

The central idea is that DVM does not automatically improve production. Its effect depends on whether digital information becomes useful **workface-level situational awareness** for crews and supervisors.

The model examines questions such as:

- Does a management dashboard improve production if workface-level visibility remains weak?
- Does workface DVM help crews find alternative workfaces when disruptions occur?
- How does DVM affect the amount of reactive coordination required from supervisors?
- Does reduced reactive coordination free supervisor time for proactive planning?
- Does better planning quality improve future task readiness and disruption recovery?
- How resilient are different DVM implementation scenarios under the same external shock environment?

The model focuses especially on **recovery from disruptions**, not only on productivity.

---

## 2. Conceptual logic

The model is based on a three-layer interpretation of DVM:

```text
Physical World
    tasks, crews, locations, materials, equipment, disruptions

Abstract World
    data capture, data quality, data integration, situation picture, DVM views

Socio-Psychological World
    perception, comprehension, projection, trust, adoption, decision-making
```

The main causal logic is:

```text
Physical events
→ captured and integrated data
→ DVM situation picture
→ crew situational awareness
→ task selection / alternative workface switching / escalation
→ recovery time, supervisor workload and production flow
```

The model also includes a planning feedback loop:

```text
better crew situational awareness
→ fewer questions and escalations
→ less supervisor reactive coordination
→ more proactive planning time
→ higher planning quality
→ better future preconditions and faster recovery
→ improved production flow
```

The negative loop is also represented:

```text
weak workface situational awareness
→ more failed task switches and escalations
→ more supervisor recovery interventions
→ less planning time
→ lower planning quality
→ slower recovery from future disruptions
→ more idle time and weaker production flow
```

---

## 3. Current technical architecture

The current version uses:

- **Mesa** for the agent-based model structure
- **Streamlit** for the web user interface
- **Plotly** for interactive visualisations
- **Pandas** for tabular data handling
- **OpenPyXL** for Excel export

The model code is separated from the user interface.

```text
app.py                  Streamlit user interface

dvm_abm/
    model.py            Mesa model
    agents.py           Crew, task and supervisor agents
    scenarios.py        Scenario definitions and loading
    shocks.py           External shock generation
    analysis.py         Batch runs and aggregation
    export.py           Excel export helpers
    visualization.py    Plot helper functions
    utils.py            Small shared utilities

config/
    scenarios.yaml      Editable scenario parameters

scripts/
    run_batch.py        Command-line batch run

tests/
    test_model_runs.py  Minimal smoke test
```

---

## 4. Main agents

### `CrewAgent`

Represents a work crew.

Crews can:

- select tasks
- perform work
- experience disruptions
- ask questions
- escalate issues
- find alternative tasks or workfaces
- develop or lose DVM adoption
- accumulate idle time and external disruption idle time

### `TaskAgent`

Represents a construction task or work package.

Tasks have:

- trade
- location
- planned start
- planned duration
- priority
- complexity
- readiness state
- predecessor dependencies
- external blockage state

### `SupervisorAgent`

Represents a limited-capacity supervisor coordination resource.

The supervisor handles:

- crew questions
- escalations
- recovery interventions
- coordination needs
- reporting work
- proactive planning

The supervisor has a daily capacity. If the reactive workload is too high, backlog and response delay increase.

---

## 5. DVM implementation scenarios

The default model compares five scenarios.

| Scenario | Description |
|---|---|
| `analog_vm` | Traditional analogue visual management and supervisor-led coordination |
| `management_dashboard` | Digital dashboard mainly serving management, with limited workface usefulness |
| `forced_reporting_dvm` | Digitally enforced reporting with high reporting burden and low trust |
| `workface_dvm` | DVM information is available near the workface and supports crew decisions |
| `dvm_lean_autonomous` | Workface DVM combined with lean practices, autonomy, planning quality and better task recommendations |

The scenarios are defined in:

```text
config/scenarios.yaml
```

They can also be loaded from built-in defaults in `dvm_abm/scenarios.py`.

---

## 6. External shocks and disruption recovery

A key feature of the model is that all scenarios face the same external shock environment within the same run.

Examples of external shocks include:

- material shortage
- logistics delay
- lifting delay
- missing design information
- unavailable equipment
- weather or site condition problems

The model separates:

```text
external shock exposure
```

from:

```text
disruption recovery capability
```

This is important because DVM is not assumed to remove external variability. Instead, DVM may improve the system's ability to recover from disruptions.

When an external disruption occurs, a crew may:

1. find an alternative ready task or workface, or
2. fail to find one and escalate the issue to the supervisor.

The probability of finding an alternative task depends on:

- crew situational awareness
- workface picture quality
- planning quality
- task recommendation quality
- crew autonomy
- decision centralisation

---

## 7. Key output metrics

### Production flow

```text
completed_tasks
ppc_proxy
total_idle_time
total_working_time
total_interruptions
prevented_interruptions
```

### Situational awareness and DVM use

```text
avg_sa
sa_std
avg_adoption
avg_effective_use
trust_in_data
trust_in_management
workface_picture_quality
management_picture_quality
workface_gap
```

### Supervisor workload

```text
supervisor_reactive_time
supervisor_planning_time
supervisor_reporting_time
supervisor_utilization
supervisor_backlog
supervisor_response_delay
firefighting_ratio
cumulative_crew_questions
cumulative_unresolved_questions
```

### External disruption and recovery

```text
external_disruptions
active_external_blockages
avg_recovery_time
avg_blockage_resolution_time
total_recovery_time
alternative_task_switches
failed_task_switches
supervisor_recovery_interventions
idle_time_due_to_external_disruptions
```

### Planning feedback

```text
planning_quality
preconditions_improved_by_planning
```

---

## 8. Streamlit application

The Streamlit app is started from:

```text
app.py
```

The UI includes tabs for:

- Results
- Time series
- Disruptions
- Supervisor
- Scenario comparison
- Data

The sidebar allows the user to adjust:

- selected scenario
- number of runs
- maximum simulation days
- random seed
- external shock probability
- DVM information quality
- crew and management access
- autonomy
- perceived surveillance
- reporting burden
- supervisor capacity
- initial planning quality

The app also supports Excel downloads.

---

## 9. Excel export

The Streamlit UI allows users to download simulation results as Excel workbooks.

For a single scenario run, the workbook includes:

```text
metadata
summary
final_run_metrics
timeseries
```

For all-scenario comparison, the workbook includes:

```text
metadata
scenario_summary
final_run_metrics
timeseries
```

This makes it possible to run the model in Streamlit Community Cloud and download the results for local analysis in Excel.

---

## 10. Installation

Create and activate a virtual environment if desired.

Install requirements:

```bash
pip install -r requirements.txt
```

The expected `requirements.txt` contains at least:

```text
streamlit
mesa
pandas
numpy
matplotlib
plotly
pyyaml
openpyxl
statsmodels
```

---

## 11. Run locally

Run the Streamlit app:

```bash
streamlit run app.py
```

Or run the batch script:

```bash
python scripts/run_batch.py
```

The batch script writes CSV outputs to:

```text
outputs/csv/
```

---

## 12. Streamlit Community Cloud deployment

To deploy on Streamlit Community Cloud:

1. Push the repository to GitHub.
2. Go to Streamlit Community Cloud.
3. Create a new app.
4. Select the repository.
5. Set the main file path to:

```text
app.py
```

6. Make sure `requirements.txt` is in the repository root.
7. Deploy.

The app does not require secrets for the current version.

---

## 13. Suggested repository structure

```text
dvm-abm-simulation/
│
├── README.md
├── requirements.txt
├── app.py
│
├── config/
│   └── scenarios.yaml
│
├── dvm_abm/
│   ├── __init__.py
│   ├── agents.py
│   ├── analysis.py
│   ├── export.py
│   ├── model.py
│   ├── scenarios.py
│   ├── shocks.py
│   ├── utils.py
│   └── visualization.py
│
├── docs/
│   └── figures/
│
├── outputs/
│   ├── csv/
│   └── figures/
│
├── scripts/
│   └── run_batch.py
│
└── tests/
    └── test_model_runs.py
```

---

## 14. Important limitations

This model is exploratory.

Important limitations:

- Parameter values are scenario assumptions, not calibrated empirical values.
- The model has not yet been validated against real project data.
- Spatial modelling is simplified.
- Crew behaviour is represented through utility and probability rules.
- Situational awareness is represented indirectly through synthetic variables.
- External shocks are stylised.
- The model should not be used for project forecasting without calibration and validation.

The intended use is:

```text
conceptual exploration
research discussion
scenario comparison
sensitivity testing
method development
```

Not intended use:

```text
project forecasting
commercial decision-making without calibration
claims of generalisable performance improvement
```

---

## 15. Next development steps

Possible next steps:

- add sensitivity analysis
- add calibration from empirical disruption and recovery data
- separate scheduled external shocks and encountered disruptions more explicitly in the UI
- add a spatial workface layer
- add more realistic crew and location constraints
- add parameter editing through YAML or UI
- add validation workshops with construction managers and crews
- improve automated tests
- improve documentation of scenario assumptions
- add publication-ready figures

---

## 16. Research interpretation

A possible interpretation of the model is:

> DVM does not remove external variability from construction production. Its value lies in improving workface-level situational awareness, reducing unnecessary supervisor intervention, supporting alternative workface switching, and strengthening the planning capacity loop that enables faster recovery from disruptions.

The model is therefore best understood as a computational formalisation of a possible mechanism:

```text
DVM → situational awareness → recovery capability → supervisor capacity → planning quality → production resilience
```

---

## 17. Status

Current status:

```text
Prototype / research model
```

Current implementation:

```text
Mesa-based ABM with Streamlit UI
```

