from __future__ import annotations

from enum import Enum
from mesa import Agent

from .utils import clamp


class TaskStatus(str, Enum):
    NOT_READY = "not_ready"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    INTERRUPTED = "interrupted"
    BLOCKED_EXTERNAL = "blocked_external"
    COMPLETED = "completed"


class MesaCompatAgent(Agent):
    """Small compatibility wrapper for different Mesa Agent constructors."""

    def __init__(self, model, unique_id=None):
        try:
            # Mesa 3 style
            super().__init__(model)
        except TypeError:
            # Older Mesa style
            super().__init__(unique_id, model)

        self.uid = unique_id if unique_id is not None else getattr(self, "unique_id", id(self))


class TaskAgent(MesaCompatAgent):
    """Construction task / work package agent."""

    def __init__(
        self,
        model,
        unique_id,
        trade,
        location,
        planned_start,
        planned_duration,
        priority,
        complexity,
        predecessor_ids=None,
    ):
        super().__init__(model, unique_id)

        self.id = unique_id
        self.trade = trade
        self.location = location
        self.planned_start = planned_start
        self.planned_duration = planned_duration
        self.priority = priority
        self.complexity = complexity
        self.predecessor_ids = predecessor_ids or []

        self.status = TaskStatus.NOT_READY
        self.remaining_duration = float(planned_duration)
        self.actual_start = None
        self.actual_finish = None

        self.interruptions = 0
        self.waiting_time = 0.0
        self.rework_time = 0.0

        self.material_ready = False
        self.location_ready = False
        self.improved_by_planning = False

        # LPS / make-ready constraints.
        self.constraints = {
            "design_ready": False,
            "material_ready": False,
            "crew_ready": False,
            "equipment_ready": False,
            "space_ready": False,
            "predecessor_ready": False,
            "approval_ready": False,
            "safety_quality_ready": False,
        }
        self.make_ready_score = 0.0

        # Weekly commitment and PPC tracking.
        self.committed_week = None
        self.commitment_day = None
        self.commitment_sound = False
        self.commitment_failed = False

        # Making-do tracking: starting work without all prerequisites.
        self.making_do_active = False
        self.making_do_started = False
        self.making_do_interruptions = 0
        self.rework_due_to_making_do = 0.0

        self.external_blockage_active = False
        self.external_blockage_type = None
        self.external_blockage_started = None
        self.external_blockage_remaining = 0.0
        self.external_blockage_resolved = None

    @property
    def is_done(self):
        return self.status == TaskStatus.COMPLETED


class CrewAgent(MesaCompatAgent):
    """Crew agent that works, waits, asks questions and switches tasks."""

    def __init__(
        self,
        model,
        unique_id,
        trade,
        location,
        experience,
        dvm_skill,
        productivity=1.0,
        adoption=0.5,
        compliance_use=0.0,
    ):
        super().__init__(model, unique_id)

        self.id = unique_id
        self.trade = trade
        self.location = location
        self.experience = experience
        self.dvm_skill = dvm_skill
        self.productivity = productivity

        self.adoption = adoption
        self.compliance_use = compliance_use
        self.current_task_id = None
        self.last_sa = 0.0

        self.working_time = 0
        self.idle_time = 0.0
        self.idle_time_external = 0.0
        self.movements = 0

        self.escalations = 0
        self.autonomous_resolutions = 0
        self.prevented_interruptions = 0
        self.questions_asked = 0

        self.alternative_task_switches = 0
        self.failed_task_switches = 0

    def effective_use(self):
        return clamp(max(self.adoption, self.compliance_use))

    def update_adoption(self, useful_event=False, bad_event=False):
        s = self.model.dvm_scenario
        delta = s.learning_rate * self.dvm_skill

        if useful_event:
            delta += s.adoption_sensitivity * (1 - 0.55 * s.reporting_burden)

        if bad_event:
            delta -= s.adoption_sensitivity * (
                0.45 * s.reporting_burden + 0.55 * s.perceived_surveillance
            )

        self.adoption = clamp(self.adoption + delta)

    def step(self):
        self.model.step_crew(self)


class SupervisorAgent(MesaCompatAgent):
    """Limited-capacity supervisor coordination resource."""

    def __init__(
        self,
        model,
        unique_id,
        capacity_per_day,
        question_handling_time,
        escalation_handling_time,
        reporting_time_base,
        coordination_task_time,
        base_admin_load=0.0,
        management_reporting_load=0.0,
        procurement_admin_load=0.0,
        authority_reporting_load=0.0,
        meeting_load=0.0,
        admin_variability=0.0,
        planning_need_per_day=2.0,
    ):
        super().__init__(model, unique_id)

        self.id = unique_id
        self.capacity_per_day = capacity_per_day
        self.question_handling_time = question_handling_time
        self.escalation_handling_time = escalation_handling_time
        self.reporting_time_base = reporting_time_base
        self.coordination_task_time = coordination_task_time
        self.base_admin_load = base_admin_load
        self.management_reporting_load = management_reporting_load
        self.procurement_admin_load = procurement_admin_load
        self.authority_reporting_load = authority_reporting_load
        self.meeting_load = meeting_load
        self.admin_variability = admin_variability
        self.planning_need_per_day = planning_need_per_day
        self.recovery_intervention_time = 0.75

        # Accumulated supervisor state
        self.backlog = 0.0
        self.cumulative_reactive_time = 0.0
        self.cumulative_planning_time = 0.0
        self.cumulative_reporting_time = 0.0
        self.cumulative_base_workload = 0.0
        self.cumulative_planning_shortfall = 0.0
        self.cumulative_questions = 0
        self.cumulative_escalations = 0
        self.cumulative_recovery_interventions = 0
        self.cumulative_unresolved_questions = 0.0

        # Last-day metrics used by DataCollector.
        # These must exist before the first DataCollector.collect().
        self.last_reactive_time = 0.0
        self.last_planning_time = 0.0
        self.last_reporting_time = 0.0
        self.last_base_workload = 0.0
        self.last_planning_need = 0.0
        self.last_planning_shortfall = 0.0
        self.last_available_planning_capacity = 0.0
        self.last_total_workload = 0.0
        self.last_utilization = 0.0
        self.last_response_delay = 0.0
        self.last_firefighting_ratio = 0.0
        self.last_questions = 0
        self.last_escalations = 0
        self.last_recovery_interventions = 0
        self.last_unresolved_questions = 0.0

    def process_day(
        self,
        questions,
        escalations,
        coordination_needs,
        recovery_interventions,
        external_pressure,
    ):
        s = self.model.dvm_scenario
        m = self.model
        r = getattr(m, "py_random", None)

        # Worker-independent supervisor base workload:
        # reporting to management, invoice/order handling, authority documentation,
        # meetings and other administrative duties.
        variability = 0.0
        if r is not None and self.admin_variability > 0:
            variability = r.normalvariate(0.0, self.admin_variability)

        dvm_reporting_time = s.reporting_burden * self.reporting_time_base
        base_workload = max(
            0.0,
            self.base_admin_load
            + self.management_reporting_load
            + self.procurement_admin_load
            + self.authority_reporting_load
            + self.meeting_load
            + dvm_reporting_time
            + variability,
        )

        reactive = (
            questions * self.question_handling_time
            + escalations * self.escalation_handling_time
            + coordination_needs * self.coordination_task_time
            + recovery_interventions * self.recovery_intervention_time
        )

        backlog_work = min(self.backlog, self.capacity_per_day * 0.35)
        planning_need = self.planning_need_per_day

        available_after_base_and_reactive = max(
            0.0,
            self.capacity_per_day - base_workload - reactive - backlog_work,
        )
        planning = min(planning_need, available_after_base_and_reactive)
        planning_shortfall = max(0.0, planning_need - planning)

        total_actual_work = base_workload + reactive + backlog_work + planning
        overload = max(0.0, base_workload + reactive + backlog_work - self.capacity_per_day)
        unresolved = overload / max(self.question_handling_time, 0.01)

        # Backlog grows from true overload and from uncompleted planning work,
        # but only true overload creates unresolved crew questions.
        spare_after_required = max(
            0.0,
            self.capacity_per_day - base_workload - reactive - planning,
        )
        backlog_reduction = spare_after_required * 0.20
        self.backlog = max(
            0.0,
            self.backlog + overload + 0.35 * planning_shortfall - backlog_reduction,
        )

        self.last_reactive_time = reactive
        self.last_planning_time = planning
        self.last_reporting_time = dvm_reporting_time
        self.last_base_workload = base_workload
        self.last_planning_need = planning_need
        self.last_planning_shortfall = planning_shortfall
        self.last_available_planning_capacity = available_after_base_and_reactive
        self.last_total_workload = total_actual_work
        self.last_utilization = total_actual_work / max(self.capacity_per_day, 0.01)
        self.last_response_delay = (
            0.15
            + s.overload_delay_effect * self.backlog
            + 0.30 * max(0.0, self.last_utilization - 1)
            + 0.08 * planning_shortfall
        )
        # Firefighting ratio is the share of production-management time that is reactive.
        # Base administration is reported separately.
        self.last_firefighting_ratio = reactive / max(reactive + planning, 0.01)
        self.last_questions = questions
        self.last_escalations = escalations
        self.last_recovery_interventions = recovery_interventions
        self.last_unresolved_questions = unresolved

        self.cumulative_reactive_time += reactive
        self.cumulative_planning_time += planning
        self.cumulative_reporting_time += dvm_reporting_time
        self.cumulative_base_workload += base_workload
        self.cumulative_planning_shortfall += planning_shortfall
        self.cumulative_questions += questions
        self.cumulative_escalations += escalations
        self.cumulative_recovery_interventions += recovery_interventions
        self.cumulative_unresolved_questions += unresolved

        planning_gain = s.proactive_planning_effect * planning * (1 - m.planning_quality)
        planning_loss = (
            0.018 * overload
            + 0.012 * planning_shortfall
            + 0.008 * self.backlog
            + 0.010 * external_pressure
            + 0.004 * s.reporting_burden * (1 - m.trust_in_management)
            + s.planning_decay
        )

        m.planning_quality = clamp(m.planning_quality + planning_gain - planning_loss)
