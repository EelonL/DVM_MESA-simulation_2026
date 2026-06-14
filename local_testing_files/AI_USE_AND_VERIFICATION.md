# AI Use and Human Verification Protocol

This document describes how generative AI was used in the development of the DVM-ABM research model, how AI-assisted outputs were reviewed, and how human verification was carried out. The purpose of this document is to support transparency, reproducibility, and responsible research practice.

This document is not a raw transcript of AI interactions. Instead, it provides a structured account of the role of AI assistance, the human review process, and the verification steps used before AI-assisted outputs were accepted into the research workflow.

## 1. Scope of AI use

Generative AI was used as a research support tool during the development of an agent-based simulation model of Digital Visual Management (DVM) in construction workface operations.

AI assistance was used in the following areas:

- drafting and debugging Python code;
- designing and revising the agent-based model structure;
- documenting model parameters and their practical interpretation;
- preparing README and methodological documentation;
- designing causal loop and stock-and-flow sketches;
- planning the sensitivity testing programme;
- creating a local sensitivity testing harness;
- drafting preliminary methodological text;
- translating and refining research questions, titles, and explanatory text.

AI assistance was not used as an autonomous source of research findings. AI-generated outputs were treated as provisional suggestions requiring human review, modification, and testing.

## 2. AI tools used

The primary AI tool used in this work was ChatGPT. The tool was used interactively to support coding, conceptual modelling, documentation, and writing.

Where relevant, the exact AI tool and model version should be recorded in the project log, for example:

| Field | Entry |
|---|---|
| AI tool | ChatGPT |
| Model | GPT-5.5 Thinking |
| Main use | Code support, debugging, documentation, sensitivity testing design, writing support |
| Period of use | To be completed by the author |
| Responsible human researcher | To be completed by the author |

If other tools are later used, they should be added to this section.

## 3. Research tasks supported by AI

### 3.1 Code development

AI was used to draft and revise Python code for the agent-based model and related tooling. This included:

- model logic for task agents, crew agents, and supervisor behaviour;
- scenario parameter structures;
- Streamlit user interface elements;
- Excel exports;
- visualisation scripts;
- local sensitivity testing code;
- debugging assistance based on error messages and observed outputs.

AI-generated code was not accepted solely on the basis of plausibility. Code suggestions were reviewed, modified, executed, and compared against expected model behaviour.

### 3.2 Conceptual model development

AI was used to support the conceptual structuring of the model, including:

- identification of causal mechanisms linking DVM, situation awareness, make-ready quality, PPC, carryover, making-do, supervisor workload, and project completion;
- drafting causal loop diagram logic;
- drafting a stock-and-flow representation of the model;
- identifying potentially DVM-favourable assumptions;
- proposing DVM-friendly, neutral, and DVM-sceptical scenario interpretations.

These conceptual suggestions were treated as modelling hypotheses and were revised by the researcher.

### 3.3 Parameter documentation

AI was used to create a parameter table describing:

- parameter names;
- scenario values;
- target agent or model process;
- interpretation;
- expected effect on the model;
- practical examples of parameter values;
- implications of increasing or decreasing parameter values.

The parameter table is intended to support expert review and calibration. The examples are not empirical estimates unless separately documented as such.

### 3.4 Sensitivity testing

AI was used to design a sensitivity testing strategy and to draft a local testing harness. The testing design includes:

- sanity checks;
- one-factor-at-a-time testing;
- threshold tests;
- Latin Hypercube style screening;
- Excel export of results;
- recording of model version, settings, seeds, parameter ranges, and outputs.

The purpose of the sensitivity testing framework is to evaluate whether the model’s findings are robust or dependent on narrow parameter assumptions.

### 3.5 Writing and documentation

AI was used to draft preliminary versions of:

- research questions;
- article title alternatives;
- methodological text;
- AI use disclosure;
- README documentation;
- explanations of ODD, sensitivity testing, and model evaluation.

All writing suggestions were reviewed and edited by the author. AI-generated text was not treated as final scholarly argumentation.

## 4. Human review and verification protocol

AI-assisted outputs were subjected to human review before being incorporated into the research workflow. The verification process followed these principles:

1. **Conceptual review**  
   The researcher evaluated whether the AI-suggested modelling logic was consistent with the research question, construction production theory, Last Planner System logic, DVM assumptions, and the intended level of abstraction.

2. **Code review**  
   AI-generated or AI-modified code was inspected before use. Particular attention was paid to task state transitions, PPC calculation, scenario parameter use, random seeds, export logic, and compatibility with the existing model structure.

3. **Execution testing**  
   Code was run locally. Errors, crashes, unexpected results, and implausible outputs were used to refine the code.

4. **Output plausibility checks**  
   Simulation outputs were compared against expected directional behaviour. For example, a near-on-time project should not systematically produce very low PPC, and a DVM configuration with no worker access should not strongly improve worker-level situation awareness.

5. **Version comparison**  
   Model revisions were compared across versions. When changes produced unexpected or unchanged results, the model logic, cache behaviour, parameter use, and output metrics were inspected.

6. **Sensitivity testing**  
   A dedicated local sensitivity testing harness was created to test whether results are robust across parameter values, random seeds, and scenario assumptions.

7. **Human responsibility**  
   The researcher retained responsibility for all final decisions, including model structure, parameter choices, code acceptance, interpretation of outputs, and written claims.

## 5. Code verification process

The following checks were used or are planned for AI-assisted code:

- local execution without Streamlit;
- Streamlit execution for interactive inspection;
- comparison of exported Excel outputs across model versions;
- inspection of key output metrics such as PPC, project delay, backlog, making-do, supervisor workload, and situation awareness;
- checking that new parameters are actually used in model logic rather than only appearing in configuration files;
- checking that fallback values in the user interface do not hide missing model outputs;
- checking that cached Streamlit objects do not cause outdated model versions to be used;
- running the local sensitivity testing harness after major model changes.

Any code included in a public repository should be linked to a commit hash or release tag so that the exact version used in the study can be recovered.

## 6. Model testing and sensitivity testing

Sensitivity testing is used as a central part of the model evaluation strategy. The testing programme includes:

- **sanity checks**, to verify logical behaviour in extreme or simplified cases;
- **local sensitivity tests**, to identify parameters with clear direct effects;
- **global screening**, to detect influential parameters and interactions;
- **threshold tests**, to identify conditions under which DVM changes from beneficial to neutral or harmful;
- **scenario robustness checks**, to assess how often each DVM configuration performs better or worse under alternative assumptions.

The sensitivity testing results should be archived with:

- the tested model version;
- the configuration file;
- parameter ranges;
- random seeds;
- run counts;
- raw run outputs;
- summary statistics;
- generated figures;
- interpretation notes.

## 7. Non-use and exclusions

AI was not used to replace human responsibility for the research. In particular:

- AI was not treated as an author;
- AI was not used as an independent validator of the model;
- AI-generated references were not accepted without checking;
- AI-generated code was not accepted without execution testing;
- AI-generated interpretations were not treated as findings without comparison to model outputs;
- confidential or sensitive project data should not be entered into AI tools unless approved by the relevant organisation and ethical/data protection requirements.

## 8. Data protection and confidentiality

The research process should avoid entering confidential, personal, contractual, or commercially sensitive data into generative AI tools unless there is a clear legal and organisational basis for doing so.

For this model, the main AI-assisted work concerned synthetic model logic, code structure, generic parameter values, public or non-confidential methodological discussion, and research text drafting.

If empirical project data are later used for calibration or validation, a separate data protection assessment should be completed before using AI tools with those data.

## 9. Public archiving strategy

The following public documentation structure is recommended:

```text
repository/
    README.md
    AI_USE_AND_VERIFICATION.md
    AI_USE_LOG.csv
    CHANGELOG.md
    config/
        scenarios.yaml
    dvm_abm/
        model.py
        agents.py
        scenarios.py
        analysis.py
    sensitivity_harness/
        run_sensitivity.py
        sensitivity_config.yaml
        README_sensitivity.md
    results/
        selected_sensitivity_outputs/
```

The repository should be archived through a persistent research archive such as Zenodo or OSF when the study is submitted or published. A release tag should be created for the exact model version used in the manuscript.

## 10. Suggested AI use log

A separate `AI_USE_LOG.csv` file can be used to record AI assistance at the task level. The following columns are recommended:

| Column | Description |
|---|---|
| date | Date of AI-assisted task |
| research_phase | Model development, debugging, documentation, sensitivity testing, writing, etc. |
| ai_tool | Tool used |
| model_version | AI model, if known |
| purpose | Purpose of the interaction |
| input_type | Code excerpt, error message, conceptual question, text draft, etc. |
| output_type | Code patch, explanation, table, documentation, figure idea, etc. |
| human_review | How the output was reviewed |
| verification_action | Test run, code review, comparison, rejected, modified, etc. |
| accepted_status | Accepted, partly accepted, rejected |
| linked_file_or_commit | File name, commit hash, release tag, or issue |
| notes | Additional notes |

Example entries:

| date | research_phase | purpose | human_review | verification_action | accepted_status |
|---|---|---|---|---|---|
| 2026-06-10 | Debugging | PPC calculation produced implausibly low values | Reviewed model logic and exported Excel results | Modified PPC calculation and reran scenario comparison | Partly accepted |
| 2026-06-14 | Documentation | Draft parameter documentation | Checked parameter names against scenario configuration | Created Excel parameter table for team review | Accepted with edits |
| 2026-06-14 | Sensitivity testing | Design local test harness | Reviewed expected tests and output structure | Ran local harness and inspected Excel output | Accepted with testing |

## 11. Reporting statement for manuscript

A concise disclosure statement for the manuscript may read as follows:

> Generative AI tools were used as research support during the study, particularly for drafting and debugging Python code, documenting model parameters, designing visualisations, structuring the sensitivity testing workflow, and preparing preliminary text drafts. All AI-generated suggestions were reviewed, modified, and verified by the author. The author remains fully responsible for the model design, methodological choices, analysis, interpretation of results, and final manuscript.

A more detailed description of AI use, human review, and verification is provided in this document and in the associated repository files.

## 12. Known limitations of AI assistance

The use of AI assistance creates several limitations that should be acknowledged:

- AI suggestions may be plausible but incorrect;
- AI may overlook hidden assumptions in code or parameter logic;
- AI can generate overconfident methodological language;
- AI-assisted code may contain subtle bugs;
- AI may suggest references or practices that require independent checking;
- AI-generated explanations may simplify modelling choices too much.

These limitations were addressed through human review, code execution, output inspection, version comparison, and sensitivity testing.

## 13. Responsibility statement

The author is responsible for the final research design, simulation model, code, parameter choices, testing strategy, interpretation of outputs, manuscript text, and any errors that remain.

AI assistance was used to support the research process, but it did not replace scholarly judgement, domain expertise, or methodological responsibility.
