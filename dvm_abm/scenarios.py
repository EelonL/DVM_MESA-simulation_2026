"""Scenario definitions and configuration loading for DVM-ABM.

This module must stay in sync with config/scenarios.yaml.

The Scenario dataclass contains the full parameter set used by the current
Mesa/Streamlit implementation. The loader accepts a YAML file with either:

    scenarios:
      analog_vm:
        capture_rate: 0.22
        ...

or directly:

    analog_vm:
      capture_rate: 0.22
      ...

Extra YAML keys are ignored only if they are not Scenario fields.
Missing required Scenario fields raise a clear error.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Scenario:
    name: str

    # Abstract world: data capture and DVM quality
    capture_rate: float
    data_accuracy: float
    data_timeliness: float
    data_completeness: float
    integration_level: float

    # DVM contents visible to users
    readiness_visibility: float
    material_visibility: float
    congestion_visibility: float
    priority_visibility: float
    task_recommendation_quality: float

    # Access and user fit
    crew_access: float
    management_access: float
    visual_clarity: float
    task_relevance: float

    # Socio-psychological layer
    initial_trust_in_data: float
    initial_trust_in_management: float
    autonomy_level: float
    decision_centralization: float
    reporting_burden: float
    perceived_surveillance: float
    compliance_pressure: float

    # Production environment
    disturbance_probability: float
    initial_plan_reliability: float

    # External variability parameters.
    # In the v2.3 model, the base shock schedule is controlled per run.
    # These fields are still retained for compatibility and future experiments.
    external_disruption_rate: float
    external_disruption_severity: float
    material_shortage_share: float
    logistics_delay_share: float
    lifting_delay_share: float
    design_missing_share: float
    equipment_unavailable_share: float
    weather_condition_share: float

    # Dynamics
    learning_rate: float
    trust_sensitivity: float
    adoption_sensitivity: float

    # Supervisor / planning feedback loop
    supervisor_capacity: float
    question_handling_time: float
    escalation_handling_time: float
    reporting_time_base: float
    coordination_task_time: float

    # Worker-independent supervisor base workload.
    # These represent daily management/admin work such as invoicing,
    # ordering, reporting to management, authority documentation and meetings.
    supervisor_base_workload: float
    management_reporting_load: float
    procurement_admin_load: float
    authority_reporting_load: float
    meeting_load: float
    admin_variability: float
    planning_need_per_day: float

    proactive_planning_effect: float
    overload_delay_effect: float
    planning_decay: float
    initial_planning_quality: float

    def with_overrides(self, **kwargs: Any) -> "Scenario":
        """Return a copy of the scenario with selected values replaced."""
        valid_fields = {f.name for f in fields(Scenario)}
        clean = {k: v for k, v in kwargs.items() if k in valid_fields and v is not None}
        return replace(self, **clean)


def _scenario_field_names() -> set[str]:
    return {f.name for f in fields(Scenario)}


def _make_scenario(name: str, params: dict[str, Any]) -> Scenario:
    """Create Scenario from dict and provide clear errors."""
    valid_fields = _scenario_field_names()
    clean = {k: v for k, v in params.items() if k in valid_fields and k != "name"}

    required = valid_fields - {"name"}
    missing = sorted(required - set(clean.keys()))
    if missing:
        raise ValueError(
            f"Scenario '{name}' is missing required parameters: {', '.join(missing)}"
        )

    return Scenario(name=name, **clean)


def load_scenarios(path: str | Path = "config/scenarios.yaml") -> list[Scenario]:
    """Load scenarios from YAML.

    Expected format:

        scenarios:
          analog_vm:
            capture_rate: 0.22
            ...

    The function also accepts a direct mapping without the top-level
    'scenarios' key.
    """
    path = Path(path)

    if not path.exists():
        return get_default_scenarios()

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if raw is None:
        raise ValueError(f"{path} is empty.")

    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a YAML mapping.")

    data = raw.get("scenarios", raw)

    if not isinstance(data, dict):
        raise ValueError(
            f"{path} must contain a mapping under the top-level 'scenarios:' key."
        )

    scenarios: list[Scenario] = []
    for name, params in data.items():
        if not isinstance(params, dict):
            raise ValueError(f"Scenario '{name}' must be a mapping of parameters.")
        scenarios.append(_make_scenario(str(name), params))

    if not scenarios:
        raise ValueError(f"No scenarios found in {path}.")

    return scenarios


def get_default_scenarios() -> list[Scenario]:
    """Return built-in fallback scenarios.

    These defaults mirror the current config/scenarios.yaml values. They are
    used only if config/scenarios.yaml is not found.
    """
    defaults: dict[str, dict[str, float]] = {
        "analog_vm": {
            "capture_rate": 0.22,
            "data_accuracy": 0.65,
            "data_timeliness": 0.28,
            "data_completeness": 0.38,
            "integration_level": 0.18,
            "readiness_visibility": 0.18,
            "material_visibility": 0.18,
            "congestion_visibility": 0.08,
            "priority_visibility": 0.38,
            "task_recommendation_quality": 0.05,
            "crew_access": 0.22,
            "management_access": 0.35,
            "visual_clarity": 0.45,
            "task_relevance": 0.35,
            "initial_trust_in_data": 0.60,
            "initial_trust_in_management": 0.55,
            "autonomy_level": 0.25,
            "decision_centralization": 0.80,
            "reporting_burden": 0.18,
            "perceived_surveillance": 0.20,
            "compliance_pressure": 0.10,
            "disturbance_probability": 0.24,
            "initial_plan_reliability": 0.50,
            "external_disruption_rate": 0.045,
            "external_disruption_severity": 1.00,
            "material_shortage_share": 0.30,
            "logistics_delay_share": 0.22,
            "lifting_delay_share": 0.16,
            "design_missing_share": 0.14,
            "equipment_unavailable_share": 0.10,
            "weather_condition_share": 0.08,
            "learning_rate": 0.005,
            "trust_sensitivity": 0.010,
            "adoption_sensitivity": 0.010,
            "supervisor_capacity": 8.0,
            "question_handling_time": 0.30,
            "escalation_handling_time": 0.90,
            "reporting_time_base": 0.60,
            "coordination_task_time": 0.50,
            "proactive_planning_effect": 0.006,
            "overload_delay_effect": 0.12,
            "planning_decay": 0.007,
            "initial_planning_quality": 0.48,
        },
        "management_dashboard": {
            "capture_rate": 0.64,
            "data_accuracy": 0.79,
            "data_timeliness": 0.70,
            "data_completeness": 0.74,
            "integration_level": 0.72,
            "readiness_visibility": 0.56,
            "material_visibility": 0.52,
            "congestion_visibility": 0.45,
            "priority_visibility": 0.84,
            "task_recommendation_quality": 0.46,
            "crew_access": 0.25,
            "management_access": 0.92,
            "visual_clarity": 0.62,
            "task_relevance": 0.45,
            "initial_trust_in_data": 0.56,
            "initial_trust_in_management": 0.47,
            "autonomy_level": 0.22,
            "decision_centralization": 0.88,
            "reporting_burden": 0.68,
            "perceived_surveillance": 0.56,
            "compliance_pressure": 0.75,
            "disturbance_probability": 0.24,
            "initial_plan_reliability": 0.55,
            "external_disruption_rate": 0.045,
            "external_disruption_severity": 1.00,
            "material_shortage_share": 0.30,
            "logistics_delay_share": 0.22,
            "lifting_delay_share": 0.16,
            "design_missing_share": 0.14,
            "equipment_unavailable_share": 0.10,
            "weather_condition_share": 0.08,
            "learning_rate": 0.005,
            "trust_sensitivity": 0.018,
            "adoption_sensitivity": 0.018,
            "supervisor_capacity": 8.0,
            "question_handling_time": 0.32,
            "escalation_handling_time": 1.00,
            "reporting_time_base": 1.25,
            "coordination_task_time": 0.50,
            "proactive_planning_effect": 0.005,
            "overload_delay_effect": 0.16,
            "planning_decay": 0.008,
            "initial_planning_quality": 0.52,
        },
        "forced_reporting_dvm": {
            "capture_rate": 0.64,
            "data_accuracy": 0.75,
            "data_timeliness": 0.58,
            "data_completeness": 0.68,
            "integration_level": 0.60,
            "readiness_visibility": 0.58,
            "material_visibility": 0.52,
            "congestion_visibility": 0.48,
            "priority_visibility": 0.75,
            "task_recommendation_quality": 0.42,
            "crew_access": 0.23,
            "management_access": 0.88,
            "visual_clarity": 0.52,
            "task_relevance": 0.42,
            "initial_trust_in_data": 0.45,
            "initial_trust_in_management": 0.36,
            "autonomy_level": 0.18,
            "decision_centralization": 0.92,
            "reporting_burden": 0.88,
            "perceived_surveillance": 0.82,
            "compliance_pressure": 0.95,
            "disturbance_probability": 0.25,
            "initial_plan_reliability": 0.55,
            "external_disruption_rate": 0.045,
            "external_disruption_severity": 1.00,
            "material_shortage_share": 0.30,
            "logistics_delay_share": 0.22,
            "lifting_delay_share": 0.16,
            "design_missing_share": 0.14,
            "equipment_unavailable_share": 0.10,
            "weather_condition_share": 0.08,
            "learning_rate": 0.002,
            "trust_sensitivity": 0.024,
            "adoption_sensitivity": 0.026,
            "supervisor_capacity": 8.0,
            "question_handling_time": 0.35,
            "escalation_handling_time": 1.10,
            "reporting_time_base": 1.60,
            "coordination_task_time": 0.55,
            "proactive_planning_effect": 0.004,
            "overload_delay_effect": 0.20,
            "planning_decay": 0.010,
            "initial_planning_quality": 0.46,
        },
        "workface_dvm": {
            "capture_rate": 0.72,
            "data_accuracy": 0.82,
            "data_timeliness": 0.78,
            "data_completeness": 0.78,
            "integration_level": 0.72,
            "readiness_visibility": 0.86,
            "material_visibility": 0.80,
            "congestion_visibility": 0.78,
            "priority_visibility": 0.68,
            "task_recommendation_quality": 0.76,
            "crew_access": 0.78,
            "management_access": 0.70,
            "visual_clarity": 0.73,
            "task_relevance": 0.80,
            "initial_trust_in_data": 0.66,
            "initial_trust_in_management": 0.62,
            "autonomy_level": 0.58,
            "decision_centralization": 0.45,
            "reporting_burden": 0.38,
            "perceived_surveillance": 0.30,
            "compliance_pressure": 0.35,
            "disturbance_probability": 0.22,
            "initial_plan_reliability": 0.60,
            "external_disruption_rate": 0.045,
            "external_disruption_severity": 1.00,
            "material_shortage_share": 0.30,
            "logistics_delay_share": 0.22,
            "lifting_delay_share": 0.16,
            "design_missing_share": 0.14,
            "equipment_unavailable_share": 0.10,
            "weather_condition_share": 0.08,
            "learning_rate": 0.012,
            "trust_sensitivity": 0.014,
            "adoption_sensitivity": 0.028,
            "supervisor_capacity": 8.0,
            "question_handling_time": 0.28,
            "escalation_handling_time": 0.85,
            "reporting_time_base": 0.80,
            "coordination_task_time": 0.45,
            "proactive_planning_effect": 0.007,
            "overload_delay_effect": 0.12,
            "planning_decay": 0.006,
            "initial_planning_quality": 0.58,
        },
        "dvm_lean_autonomous": {
            "capture_rate": 0.84,
            "data_accuracy": 0.90,
            "data_timeliness": 0.88,
            "data_completeness": 0.87,
            "integration_level": 0.88,
            "readiness_visibility": 0.93,
            "material_visibility": 0.88,
            "congestion_visibility": 0.88,
            "priority_visibility": 0.82,
            "task_recommendation_quality": 0.88,
            "crew_access": 0.88,
            "management_access": 0.82,
            "visual_clarity": 0.84,
            "task_relevance": 0.88,
            "initial_trust_in_data": 0.78,
            "initial_trust_in_management": 0.75,
            "autonomy_level": 0.74,
            "decision_centralization": 0.32,
            "reporting_burden": 0.28,
            "perceived_surveillance": 0.18,
            "compliance_pressure": 0.30,
            "disturbance_probability": 0.19,
            "initial_plan_reliability": 0.65,
            "external_disruption_rate": 0.045,
            "external_disruption_severity": 1.00,
            "material_shortage_share": 0.30,
            "logistics_delay_share": 0.22,
            "lifting_delay_share": 0.16,
            "design_missing_share": 0.14,
            "equipment_unavailable_share": 0.10,
            "weather_condition_share": 0.08,
            "learning_rate": 0.018,
            "trust_sensitivity": 0.012,
            "adoption_sensitivity": 0.038,
            "supervisor_capacity": 8.0,
            "question_handling_time": 0.25,
            "escalation_handling_time": 0.75,
            "reporting_time_base": 0.65,
            "coordination_task_time": 0.40,
            "proactive_planning_effect": 0.008,
            "overload_delay_effect": 0.10,
            "planning_decay": 0.005,
            "initial_planning_quality": 0.65,
        },
    }

    return [_make_scenario(name, params) for name, params in defaults.items()]
