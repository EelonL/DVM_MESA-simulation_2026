from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import yaml

@dataclass(frozen=True)
class Scenario:
    name: str
    crew_access: float
    management_access: float
    reporting_burden: float
    perceived_surveillance: float
    autonomy_level: float
    decision_centralization: float
    initial_planning_quality: float
    initial_trust_in_data: float
    initial_trust_in_management: float
    capture_rate: float
    data_accuracy: float
    data_timeliness: float
    data_completeness: float
    integration_level: float
    readiness_visibility: float
    material_visibility: float
    congestion_visibility: float
    priority_visibility: float
    task_recommendation_quality: float
    visual_clarity: float
    task_relevance: float
    compliance_pressure: float
    disturbance_probability: float
    initial_plan_reliability: float
    learning_rate: float
    trust_sensitivity: float
    adoption_sensitivity: float
    supervisor_capacity: float
    question_handling_time: float
    escalation_handling_time: float
    reporting_time_base: float
    coordination_task_time: float
    proactive_planning_effect: float
    overload_delay_effect: float
    planning_decay: float
    def with_overrides(self, **kwargs):
        return replace(self, **{k:v for k,v in kwargs.items() if v is not None})

_DEFAULTS = {
"analog_vm": dict(crew_access=.22, management_access=.35, reporting_burden=.18, perceived_surveillance=.20, autonomy_level=.25, decision_centralization=.80, initial_planning_quality=.48, initial_trust_in_data=.60, initial_trust_in_management=.55, capture_rate=.22, data_accuracy=.65, data_timeliness=.28, data_completeness=.38, integration_level=.18, readiness_visibility=.18, material_visibility=.18, congestion_visibility=.08, priority_visibility=.38, task_recommendation_quality=.05, visual_clarity=.45, task_relevance=.35, compliance_pressure=.10, disturbance_probability=.24, initial_plan_reliability=.50, learning_rate=.005, trust_sensitivity=.010, adoption_sensitivity=.010, supervisor_capacity=8.0, question_handling_time=.30, escalation_handling_time=.90, reporting_time_base=.60, coordination_task_time=.50, proactive_planning_effect=.006, overload_delay_effect=.12, planning_decay=.007),
"management_dashboard": dict(crew_access=.25, management_access=.92, reporting_burden=.68, perceived_surveillance=.56, autonomy_level=.22, decision_centralization=.88, initial_planning_quality=.52, initial_trust_in_data=.56, initial_trust_in_management=.47, capture_rate=.64, data_accuracy=.79, data_timeliness=.70, data_completeness=.74, integration_level=.72, readiness_visibility=.56, material_visibility=.52, congestion_visibility=.45, priority_visibility=.84, task_recommendation_quality=.46, visual_clarity=.62, task_relevance=.45, compliance_pressure=.75, disturbance_probability=.24, initial_plan_reliability=.55, learning_rate=.005, trust_sensitivity=.018, adoption_sensitivity=.018, supervisor_capacity=8.0, question_handling_time=.32, escalation_handling_time=1.0, reporting_time_base=1.25, coordination_task_time=.50, proactive_planning_effect=.005, overload_delay_effect=.16, planning_decay=.008),
"forced_reporting_dvm": dict(crew_access=.23, management_access=.88, reporting_burden=.88, perceived_surveillance=.82, autonomy_level=.18, decision_centralization=.92, initial_planning_quality=.46, initial_trust_in_data=.45, initial_trust_in_management=.36, capture_rate=.64, data_accuracy=.75, data_timeliness=.58, data_completeness=.68, integration_level=.60, readiness_visibility=.58, material_visibility=.52, congestion_visibility=.48, priority_visibility=.75, task_recommendation_quality=.42, visual_clarity=.52, task_relevance=.42, compliance_pressure=.95, disturbance_probability=.25, initial_plan_reliability=.55, learning_rate=.002, trust_sensitivity=.024, adoption_sensitivity=.026, supervisor_capacity=8.0, question_handling_time=.35, escalation_handling_time=1.10, reporting_time_base=1.60, coordination_task_time=.55, proactive_planning_effect=.004, overload_delay_effect=.20, planning_decay=.010),
"workface_dvm": dict(crew_access=.78, management_access=.70, reporting_burden=.38, perceived_surveillance=.30, autonomy_level=.58, decision_centralization=.45, initial_planning_quality=.58, initial_trust_in_data=.66, initial_trust_in_management=.62, capture_rate=.72, data_accuracy=.82, data_timeliness=.78, data_completeness=.78, integration_level=.72, readiness_visibility=.86, material_visibility=.80, congestion_visibility=.78, priority_visibility=.68, task_recommendation_quality=.76, visual_clarity=.73, task_relevance=.80, compliance_pressure=.35, disturbance_probability=.22, initial_plan_reliability=.60, learning_rate=.012, trust_sensitivity=.014, adoption_sensitivity=.028, supervisor_capacity=8.0, question_handling_time=.28, escalation_handling_time=.85, reporting_time_base=.80, coordination_task_time=.45, proactive_planning_effect=.007, overload_delay_effect=.12, planning_decay=.006),
"dvm_lean_autonomous": dict(crew_access=.88, management_access=.82, reporting_burden=.28, perceived_surveillance=.18, autonomy_level=.74, decision_centralization=.32, initial_planning_quality=.65, initial_trust_in_data=.78, initial_trust_in_management=.75, capture_rate=.84, data_accuracy=.90, data_timeliness=.88, data_completeness=.87, integration_level=.88, readiness_visibility=.93, material_visibility=.88, congestion_visibility=.88, priority_visibility=.82, task_recommendation_quality=.88, visual_clarity=.84, task_relevance=.88, compliance_pressure=.30, disturbance_probability=.19, initial_plan_reliability=.65, learning_rate=.018, trust_sensitivity=.012, adoption_sensitivity=.038, supervisor_capacity=8.0, question_handling_time=.25, escalation_handling_time=.75, reporting_time_base=.65, coordination_task_time=.40, proactive_planning_effect=.008, overload_delay_effect=.10, planning_decay=.005),
}

def get_default_scenarios():
    return [Scenario(name=k, **v) for k,v in _DEFAULTS.items()]

def load_scenarios(path="config/scenarios.yaml"):
    p = Path(path)
    if not p.exists():
        return get_default_scenarios()
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data = data.get("scenarios", data)
    return [Scenario(name=k, **v) for k,v in data.items()]
