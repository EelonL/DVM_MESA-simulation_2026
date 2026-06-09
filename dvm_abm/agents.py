from __future__ import annotations
from enum import Enum
from mesa import Agent
from .utils import clamp

class TaskStatus(str, Enum):
    NOT_READY="not_ready"; READY="ready"; IN_PROGRESS="in_progress"; INTERRUPTED="interrupted"; BLOCKED_EXTERNAL="blocked_external"; COMPLETED="completed"

class MesaCompatAgent(Agent):
    def __init__(self, model, unique_id=None):
        try:
            super().__init__(model)
        except TypeError:
            super().__init__(unique_id, model)
        self.uid = unique_id if unique_id is not None else getattr(self, "unique_id", id(self))

class TaskAgent(MesaCompatAgent):
    def __init__(self, model, unique_id, trade, location, planned_start, planned_duration, priority, complexity, predecessor_ids=None):
        super().__init__(model, unique_id)
        self.id=unique_id; self.trade=trade; self.location=location; self.planned_start=planned_start; self.planned_duration=planned_duration
        self.priority=priority; self.complexity=complexity; self.predecessor_ids=predecessor_ids or []
        self.status=TaskStatus.NOT_READY; self.remaining_duration=float(planned_duration); self.actual_start=None; self.actual_finish=None
        self.interruptions=0; self.waiting_time=0.0; self.material_ready=False; self.location_ready=False
        self.external_blockage_active=False; self.external_blockage_type=None; self.external_blockage_started=None; self.external_blockage_remaining=0.0
    @property
    def is_done(self): return self.status == TaskStatus.COMPLETED

class CrewAgent(MesaCompatAgent):
    def __init__(self, model, unique_id, trade, location, experience, dvm_skill, productivity=1.0, adoption=0.5, compliance_use=0.0):
        super().__init__(model, unique_id)
        self.id=unique_id; self.trade=trade; self.location=location; self.experience=experience; self.dvm_skill=dvm_skill; self.productivity=productivity
        self.adoption=adoption; self.compliance_use=compliance_use; self.current_task_id=None; self.last_sa=0.0
        self.working_time=0; self.idle_time=0.0; self.idle_time_external=0.0; self.movements=0; self.escalations=0; self.autonomous_resolutions=0; self.prevented_interruptions=0
        self.questions_asked=0; self.alternative_task_switches=0; self.failed_task_switches=0
    def effective_use(self): return clamp(max(self.adoption, self.compliance_use))
    def update_adoption(self, useful_event=False, bad_event=False):
        s=self.model.scenario; delta=s.learning_rate*self.dvm_skill
        if useful_event: delta += s.adoption_sensitivity*(1-.55*s.reporting_burden)
        if bad_event: delta -= s.adoption_sensitivity*(.45*s.reporting_burden+.55*s.perceived_surveillance)
        self.adoption=clamp(self.adoption+delta)
    def step(self): self.model.step_crew(self)

class SupervisorAgent(MesaCompatAgent):
    def __init__(self, model, unique_id, capacity_per_day, question_handling_time, escalation_handling_time, reporting_time_base, coordination_task_time):
        super().__init__(model, unique_id)
        self.capacity_per_day=capacity_per_day; self.question_handling_time=question_handling_time; self.escalation_handling_time=escalation_handling_time
        self.reporting_time_base=reporting_time_base; self.coordination_task_time=coordination_task_time; self.recovery_intervention_time=.75
        self.backlog=0.0; self.cumulative_reactive_time=0.0; self.cumulative_planning_time=0.0; self.cumulative_questions=0; self.cumulative_unresolved_questions=0.0
        self.last_reactive_time=0.0; self.last_planning_time=0.0; self.last_reporting_time=0.0; self.last_utilization=0.0; self.last_response_delay=0.0; self.last_firefighting_ratio=0.0
    def process_day(self, questions, escalations, coordination_needs, recovery_interventions, external_pressure):
        s=self.model.scenario; m=self.model
        reactive=questions*self.question_handling_time + escalations*self.escalation_handling_time + coordination_needs*self.coordination_task_time + recovery_interventions*self.recovery_intervention_time + s.reporting_burden*self.reporting_time_base
        total=reactive+min(self.backlog,self.capacity_per_day*.5)
        planning=max(0.0,self.capacity_per_day-total); overload=max(0.0,total-self.capacity_per_day)
        unresolved=overload/max(self.question_handling_time,.01)
        self.backlog=max(0.0,self.backlog+overload-max(0.0,self.capacity_per_day-reactive)*.25)
        self.last_reactive_time=reactive; self.last_planning_time=planning; self.last_reporting_time=s.reporting_burden*self.reporting_time_base; self.last_utilization=total/self.capacity_per_day
        self.last_response_delay=.15+s.overload_delay_effect*self.backlog+.25*max(0,self.last_utilization-1); self.last_firefighting_ratio=reactive/max(reactive+planning,.01)
        self.cumulative_reactive_time+=reactive; self.cumulative_planning_time+=planning; self.cumulative_questions+=questions; self.cumulative_unresolved_questions+=unresolved
        gain=s.proactive_planning_effect*planning*(1-m.planning_quality); loss=.014*overload+.006*self.backlog+.010*external_pressure+.004*s.reporting_burden*(1-m.trust_in_management)+s.planning_decay
        m.planning_quality=clamp(m.planning_quality+gain-loss)
