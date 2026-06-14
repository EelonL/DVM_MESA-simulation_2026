from __future__ import annotations
from dataclasses import dataclass
import random
import math
from statistics import pstdev
from mesa import Model, DataCollector
from .agents import CrewAgent, SupervisorAgent, TaskAgent, TaskStatus
from .scenarios import Scenario, get_default_scenarios
from .shocks import generate_external_shock_schedule
from .utils import clamp, clamp_range, safe_mean

@dataclass
class SituationPicture:
    workface_quality: float; management_quality: float; recommendation_quality: float; readiness_quality: float; material_quality: float; congestion_quality: float; priority_quality: float
    @property
    def workface_gap(self): return self.management_quality-self.workface_quality

@dataclass
class AgentSA:
    perception: float; comprehension: float; projection: float
    @property
    def total(self): return .4*self.perception+.35*self.comprehension+.25*self.projection

LPS_CONSTRAINTS = [
    "design_ready",
    "material_ready",
    "crew_ready",
    "equipment_ready",
    "space_ready",
    "predecessor_ready",
    "approval_ready",
    "safety_quality_ready",
]


class DVMConstructionModel(Model):
    def __init__(self, scenario: Scenario|None=None, seed:int=20260609, max_days:int=100, number_of_tasks:int=72, daily_shock_probability:float=.32):
        try: super().__init__(seed=seed)
        except TypeError: super().__init__()
        object.__setattr__(self, "dvm_scenario", scenario or get_default_scenarios()[0]); self.seed=seed
        # In v24.7 max_days means planned project duration, not simulation cutoff.
        self.planned_project_duration=max_days
        self.max_days=max_days
        self.simulation_hard_limit=max(max_days*4, max_days+200)
        self.day=0; self.running=True; self.py_random=random.Random(seed)
        self.trust_in_data=self.dvm_scenario.initial_trust_in_data; self.trust_in_management=self.dvm_scenario.initial_trust_in_management; self.planning_quality=self.dvm_scenario.initial_planning_quality; self.data_quality_modifier=1.0
        self.useful_dvm_events=0; self.harmful_events=0; self.external_disruptions=0; self.external_disruptions_by_type={}; self.recovery_times=[]; self.blockage_resolution_times=[]
        self.total_recovery_time=0.0; self.alternative_task_switches=0; self.failed_task_switches=0; self.supervisor_recovery_interventions=0; self.idle_time_due_to_external_disruptions=0.0
        self.daily_questions=0; self.daily_escalations=0; self.daily_coordination_needs=0; self.daily_recovery_interventions=0; self.daily_external_pressure=0; self.daily_useful=0; self.daily_harmful=0
        self.daily_making_do_starts=0; self.daily_making_do_interruptions=0; self.daily_rework_due_to_making_do=0.0
        self.weekly_commitments={}; self.current_committed_task_ids=set()
        # v25.1: track actual completion promises so PPC cannot miss tasks that
        # are truly completed during a week.
        self.weekly_actual_completion_promises={}
        self.task_commitment_counts={}
        self.commitment_history={}
        self.week_length=5; self.current_picture=SituationPicture(0,0,0,0,0,0,0); self.trades=["drywall","mep","finishes","carpentry"]
        self.shock_schedule=generate_external_shock_schedule(seed,self.trades,self.simulation_hard_limit+40,daily_shock_probability)
        self.planned_workload_by_day=[0 for _ in range(self.simulation_hard_limit+1)]
        self.resource_capacity_by_day=[0.0 for _ in range(self.simulation_hard_limit+1)]
        self.active_crews_today=0
        self.available_crew_capacity_today=0.0
        self.planned_workload_today=0.0
        self.workload_pressure=0.0
        self.active_crews=[]
        self.active_crew_trades_today=""
        # v25.3: interpretation and aggregation helpers for sensitivity testing.
        # One model time unit is treated as one workday; crew idle-time counters
        # are therefore converted to hours with workday_hours.
        self.workday_hours=8.0
        self.daily_idle_time=0.0
        self.daily_idle_time_external=0.0
        self.cumulative_active_crew_days=0.0
        self.trade_supervisor_count_today=0
        self.site_manager_count_today=1
        self.supervisor_count_today=1
        self.supervisor_capacity_per_person=float(getattr(self.dvm_scenario,"supervisor_capacity",8.0))
        self.effective_supervisor_capacity_today=self.supervisor_capacity_per_person
        # v25.4: role-based foreman/site-manager time allocation.
        # These shares are interpreted as field worker-interaction time and proactive
        # planning time, not as passive observation. They provide empirical anchors
        # for the supervisor resource using foreman time-allocation literature.
        self.trade_supervisor_day_hours=8.0
        self.site_manager_day_hours=8.2
        self.trade_supervisor_field_share=0.40
        self.trade_supervisor_planning_share=0.14
        self.site_manager_field_share=0.25
        self.site_manager_planning_share=0.16
        self.field_interaction_capacity_hours_today=0.0
        self.field_interaction_demand_hours_today=0.0
        self.baseline_field_interaction_demand_hours_today=0.0
        self.unresolved_field_support_hours_today=0.0
        self.planning_target_hours_today=float(getattr(self.dvm_scenario,"planning_need_per_day",2.0))
        self.admin_reporting_nominal_hours_today=0.0
        self.supervisor_field_support_idle_added_today=0.0
        self.cumulative_unresolved_field_support_hours=0.0
        self.max_unresolved_field_support_hours=0.0
        self.cumulative_field_interaction_demand_hours=0.0
        self.cumulative_field_interaction_used_hours=0.0
        self.cumulative_field_support_utilization=0.0
        self.cumulative_planning_hours_per_supervisor_day=0.0
        self.cumulative_field_interaction_hours_per_supervisor_day=0.0
        self.cumulative_admin_reporting_hours_per_supervisor_day=0.0
        self.cumulative_supervisor_count=0.0
        self.max_supervisor_count=0.0
        self.cumulative_open_schedule_backlog=0.0
        self.max_open_schedule_backlog=0.0
        self.cumulative_make_ready_score=0.0
        self.min_make_ready_score=1.0
        self.cumulative_supervisor_backlog=0.0
        self.max_supervisor_backlog=0.0
        self.cumulative_firefighting_ratio=0.0
        self.max_firefighting_ratio=0.0
        self.hard_limit_reached=False
        self.tasks=[]; self.crews=[]; self._create_project(number_of_tasks)
        self._build_workload_and_resource_curves()
        self.planned_project_finish=float(self.planned_project_duration)
        self.baseline_last_planned_task_finish=max((self._planned_finish(t) for t in self.tasks), default=0.0)
        self.min_make_ready_score=self.avg_make_ready_score if self.tasks else 0.0
        self.datacollector=DataCollector(model_reporters=self._reporters()); self.datacollector.collect(self)
    def _sample_workload_ratio(self):
        """Sample a planned task timing ratio in [0, 1] from the workload curve."""
        s=self.dvm_scenario; r=self.py_random
        shape=getattr(s,"workload_shape","balanced_beta")
        if shape=="front_loaded":
            return r.betavariate(1.8,3.4)
        if shape=="back_loaded":
            return r.betavariate(3.4,1.8)
        return r.betavariate(max(.2,getattr(s,"workload_alpha",2.4)),max(.2,getattr(s,"workload_beta",2.3)))

    def _beta_shape_value(self,x,alpha,beta):
        """Unnormalised beta-like curve value. Avoids SciPy dependency."""
        x=clamp_range(float(x),.001,.999)
        return (x**(alpha-1))*((1-x)**(beta-1))

    def _curve_values(self,days,alpha,beta):
        raw=[self._beta_shape_value((d+.5)/max(1,days),alpha,beta) for d in range(days)]
        mx=max(raw) if raw else 1.0
        return [v/mx for v in raw]

    def _build_workload_and_resource_curves(self):
        """Build planned workload and daily active crew resource curves."""
        s=self.dvm_scenario
        planned_days=max(1,self.planned_project_duration)
        days=max(1,self.simulation_hard_limit)
        self.planned_workload_by_day=[0 for _ in range(days+1)]
        for t in self.tasks:
            pf=int(clamp_range(self._planned_finish(t),0,planned_days))
            self.planned_workload_by_day[pf]+=1

        shape=getattr(s,"resource_shape","under_resourced_peak")
        min_crews=max(1,int(getattr(s,"min_active_crews",2)))
        max_crews=max(min_crews,int(getattr(s,"max_active_crews",len(self.crews))))
        under=clamp_range(float(getattr(s,"peak_underresource_factor",.8)),.2,1.2)
        alpha=max(.2,float(getattr(s,"resource_alpha",2.2)))
        beta=max(.2,float(getattr(s,"resource_beta",2.2)))
        curve=self._curve_values(planned_days,alpha,beta)

        # Scale curve to crew counts. Under-resourced peak means the resource peak
        # intentionally stays below the workload peak.
        resource=[]
        for d,v in enumerate(curve):
            if shape=="constant_crews":
                crews=max_crews
            elif shape=="follows_workload":
                crews=round(min_crews+(max_crews-min_crews)*clamp_range(v*under,.0,1.0))
            else:
                crews=round(min_crews+(max_crews-min_crews)*clamp_range(v*under,.0,1.0))
            resource.append(clamp_range(crews,min_crews,max_crews))
        if resource:
            tail=[max(min_crews, min(max_crews, int(round(min_crews)))) for _ in range(max(0, days-len(resource)+1))]
            self.resource_capacity_by_day=resource+tail
        else:
            self.resource_capacity_by_day=[min_crews for _ in range(days+1)]

    def _update_daily_load_state(self):
        day_index=int(clamp_range(self.day,0,len(self.resource_capacity_by_day)-1))
        self.active_crews_today=int(self.resource_capacity_by_day[day_index])
        # If the project is late, keep a small completion crew mobilised, but do
        # not assume all original trades stay on site. The selection of actual
        # crews is done by _active_crews_for_today().
        if self.day > self.planned_project_duration and any(not t.is_done for t in self.tasks):
            remaining_trades={t.trade for t in self.tasks if not t.is_done}
            self.active_crews_today=max(self.active_crews_today, min(len(remaining_trades), int(getattr(self.dvm_scenario, "max_active_crews", len(self.crews)))))
        self.available_crew_capacity_today=float(self.active_crews_today)
        self.planned_workload_today=float(self.planned_workload_by_day[day_index]) if day_index<len(self.planned_workload_by_day) else 0.0
        weekly_due=len(self._planned_in_week(self.current_week))
        weekly_capacity=max(1.0,self.active_crews_today*self.week_length)
        self.workload_pressure=clamp_range((weekly_due/weekly_capacity)-1.0,0.0,2.0)

    def _create_project(self,n):
        r=self.py_random
        for i in range(n):
            pred=[r.randrange(max(1,i-10),i)] if i>6 and r.random()<.6 else []
            # v25.2: distribute planned task finishes over the full planned
            # project duration. Earlier versions compressed task finishes into
            # about 82% of the project duration, which made near-on-time projects
            # look late at task/PPC level.
            start_ratio=self._sample_workload_ratio()
            planned_duration=r.randint(1,5)
            planned_finish=int(clamp_range(round(start_ratio*self.planned_project_duration), planned_duration, self.planned_project_duration))
            planned_start=max(0, planned_finish-planned_duration)
            t=TaskAgent(self,i,r.choice(self.trades),r.randrange(12),planned_start,planned_duration,r.uniform(.2,1),r.uniform(.35,1),pred); self.tasks.append(t)
        # Create the maximum potential crew pool. Daily resource curve decides how many are active.
        crew_pool=[]
        max_crews=max(1,int(getattr(self.dvm_scenario,"max_active_crews",8)))
        while len(crew_pool)<max_crews:
            crew_pool.extend(["drywall","mep","finishes","carpentry"])
        for i,tr in enumerate(crew_pool[:max_crews]):
            ad=clamp(.35+.48*self.dvm_scenario.crew_access-.18*self.dvm_scenario.reporting_burden+r.normalvariate(0,.08)); comp=clamp(self.dvm_scenario.compliance_pressure*(.45+.45*self.dvm_scenario.management_access))
            self.crews.append(CrewAgent(self,1000+i,tr,(2*i)%12,clamp(r.normalvariate(.6,.15)),clamp(r.normalvariate(.5+.25*self.dvm_scenario.crew_access,.15)),clamp_range(r.normalvariate(1,.1),.75,1.25),ad,comp))
        self.supervisor=SupervisorAgent(
            self,
            9000,
            self.dvm_scenario.supervisor_capacity,
            self.dvm_scenario.question_handling_time,
            self.dvm_scenario.escalation_handling_time,
            self.dvm_scenario.reporting_time_base,
            self.dvm_scenario.coordination_task_time,
            self.dvm_scenario.supervisor_base_workload,
            self.dvm_scenario.management_reporting_load,
            self.dvm_scenario.procurement_admin_load,
            self.dvm_scenario.authority_reporting_load,
            self.dvm_scenario.meeting_load,
            self.dvm_scenario.admin_variability,
            self.dvm_scenario.planning_need_per_day,
        )
    def _reporters(self):
        return {
            "scenario": lambda m: m.dvm_scenario.name,
            "day": "day",
            "week": lambda m: m.current_week,
            "planned_project_duration": lambda m: m.planned_project_duration,
            "baseline_last_planned_task_finish": lambda m: m.baseline_last_planned_task_finish,
            "simulation_hard_limit": lambda m: m.simulation_hard_limit,
            "completed_tasks": lambda m: sum(t.is_done for t in m.tasks),
            "remaining_tasks": lambda m: sum(not t.is_done for t in m.tasks),
            "total_tasks": lambda m: len(m.tasks),
            "actual_project_finish": lambda m: m.actual_project_finish,
            "hard_limit_reached": lambda m: int(m.hard_limit_reached),
            "incomplete_at_hard_limit": lambda m: int(m.hard_limit_reached and not all(t.is_done for t in m.tasks)),
            "active_crew_trades_today": lambda m: m.active_crew_trades_today,
            "planned_workload_today": lambda m: m.planned_workload_today,
            "active_crews_today": lambda m: m.active_crews_today,
            "cumulative_active_crew_days": lambda m: m.cumulative_active_crew_days,
            "available_crew_capacity_today": lambda m: m.available_crew_capacity_today,
            "trade_supervisor_count_today": lambda m: m.trade_supervisor_count_today,
            "site_manager_count_today": lambda m: m.site_manager_count_today,
            "supervisor_count_today": lambda m: m.supervisor_count_today,
            "effective_supervisor_capacity_today": lambda m: m.effective_supervisor_capacity_today,
            "supervisor_capacity_per_person": lambda m: m.supervisor_capacity_per_person,
            "field_interaction_capacity_hours_per_day": lambda m: m.field_interaction_capacity_hours_today,
            "field_interaction_demand_hours_per_day": lambda m: m.field_interaction_demand_hours_today,
            "baseline_field_interaction_demand_hours_per_day": lambda m: m.baseline_field_interaction_demand_hours_today,
            "field_interaction_used_hours_per_day": lambda m: m.supervisor.last_field_interaction_used,
            "field_interaction_hours_per_supervisor_day": lambda m: m.supervisor.last_field_interaction_hours_per_supervisor_day,
            "field_interaction_hours_per_active_crew_day": lambda m: m.supervisor.last_field_interaction_used/max(1.0,len(getattr(m,"active_crews",[]))),
            "unresolved_field_support_hours_per_day": lambda m: m.unresolved_field_support_hours_today,
            "unresolved_field_support_hours_per_active_crew_day": lambda m: m.unresolved_field_support_hours_today/max(1.0,len(getattr(m,"active_crews",[]))),
            "field_support_utilization": lambda m: m.supervisor.last_field_support_utilization,
            "mean_field_support_utilization": lambda m: m.cumulative_field_support_utilization/m._elapsed_days_for_rates(),
            "planning_hours_per_day": lambda m: m.supervisor.last_planning_time,
            "planning_hours_per_supervisor_day": lambda m: m.supervisor.last_planning_hours_per_supervisor_day,
            "admin_reporting_hours_per_day": lambda m: m.supervisor.last_base_workload,
            "admin_reporting_hours_per_supervisor_day": lambda m: m.supervisor.last_admin_reporting_hours_per_supervisor_day,
            "mean_supervisor_count_over_project": lambda m: m.cumulative_supervisor_count/m._elapsed_days_for_rates(),
            "max_supervisor_count_over_project": lambda m: m.max_supervisor_count,
            "workload_pressure": lambda m: m.workload_pressure,
            "baseline_due_tasks_this_week": lambda m: m.planned_tasks_this_week,
            "weekly_committed_tasks": lambda m: m.weekly_committed_tasks,
            "completed_committed_tasks": lambda m: m.completed_committed_tasks,
            "weekly_task_capacity": lambda m: m.weekly_task_capacity,
            "cumulative_schedule_adherence": lambda m: m.cumulative_schedule_adherence,
            "ppc_schedule_score": lambda m: m.ppc_schedule_score,
            "ppc_schedule_consistency_gap": lambda m: m.ppc_schedule_consistency_gap,
            "total_ppc_promises": lambda m: m.total_ppc_promises,
            "total_ppc_successes": lambda m: m.total_ppc_successes,
            "planned_tasks_this_week": lambda m: m.planned_tasks_this_week,
            "completed_on_plan_this_week": lambda m: m.completed_on_plan_this_week,
            "baseline_adherence": lambda m: m.baseline_adherence,
            "avg_make_ready_score": lambda m: m.avg_make_ready_score,
            "sound_commitment_share": lambda m: m.sound_commitment_share,
            "constraints_ready_count": lambda m: m.constraints_ready_count,
            "constraints_missing_count": lambda m: m.constraints_missing_count,
            "making_do_starts": "daily_making_do_starts",
            "cumulative_making_do_starts": lambda m: sum(t.making_do_started for t in m.tasks),
            "making_do_interruptions": "daily_making_do_interruptions",
            "cumulative_making_do_interruptions": lambda m: sum(t.making_do_interruptions for t in m.tasks),
            "rework_due_to_making_do": "daily_rework_due_to_making_do",
            "cumulative_rework_due_to_making_do": lambda m: sum(t.rework_due_to_making_do for t in m.tasks),
            "weekly_ppc": lambda m: m.weekly_ppc,
            "avg_weekly_ppc": lambda m: m.avg_weekly_ppc,
            "last_completed_weekly_ppc": lambda m: m.last_completed_weekly_ppc,
            "weekly_carryover": lambda m: m.weekly_carryover,
            "open_schedule_backlog": lambda m: m.open_schedule_backlog,
            "mean_open_schedule_backlog": lambda m: m.cumulative_open_schedule_backlog/m._elapsed_days_for_rates(),
            "max_open_schedule_backlog": lambda m: m.max_open_schedule_backlog,
            "mean_make_ready_score_over_project": lambda m: m.cumulative_make_ready_score/m._elapsed_days_for_rates(),
            "min_make_ready_score_over_project": lambda m: m.min_make_ready_score,
            "cumulative_plan_failures": lambda m: m.cumulative_plan_failures,
            "project_delay_days": lambda m: m.project_delay_days,
            "avg_lateness_days": lambda m: m.avg_lateness_days,
            "late_completed_tasks": lambda m: m.late_completed_tasks,
            "ppc_proxy": lambda m: m.ppc_proxy,
            "avg_sa": lambda m: safe_mean([c.last_sa for c in m.crews]),
            "sa_std": lambda m: pstdev([c.last_sa for c in m.crews]) if len(m.crews) > 1 else 0.0,
            "avg_decision_delay_proxy": lambda m: safe_mean([
                clamp_range(
                    3.0*m.dvm_scenario.decision_centralization*(1.0-c.last_sa)
                    + 1.2*m.dvm_scenario.reporting_burden*(1.0-m.trust_in_management)
                    + m.dvm_scenario.overload_delay_effect*m.supervisor.backlog,
                    0.05, 6.5
                ) for c in m.crews
            ]),
            "planning_quality": "planning_quality",
            "trust_in_data": "trust_in_data",
            "trust_in_management": "trust_in_management",
            "data_quality_modifier": "data_quality_modifier",
            "avg_adoption": lambda m: safe_mean([c.adoption for c in m.crews]),
            "avg_effective_use": lambda m: safe_mean([c.effective_use() for c in m.crews]),
            "workface_picture_quality": lambda m: m.current_picture.workface_quality,
            "ready_work_area_picture_quality": lambda m: m.current_picture.workface_quality,
            "management_picture_quality": lambda m: m.current_picture.management_quality,
            "workface_gap": lambda m: m.current_picture.workface_gap,
            "ready_work_area_gap": lambda m: m.current_picture.workface_gap,
            "total_idle_time": lambda m: sum(c.idle_time for c in m.crews),
            "total_idle_time_external": lambda m: sum(c.idle_time_external for c in m.crews),
            "daily_idle_time": lambda m: m.daily_idle_time,
            "daily_idle_time_external": lambda m: m.daily_idle_time_external,
            "total_idle_time_hours": lambda m: sum(c.idle_time for c in m.crews)*m.workday_hours,
            "total_idle_time_external_hours": lambda m: sum(c.idle_time_external for c in m.crews)*m.workday_hours,
            "idle_time_hours_per_day": lambda m: (sum(c.idle_time for c in m.crews)*m.workday_hours)/m._elapsed_days_for_rates(),
            "external_idle_time_hours_per_day": lambda m: (sum(c.idle_time_external for c in m.crews)*m.workday_hours)/m._elapsed_days_for_rates(),
            "idle_time_hours_per_active_crew_day": lambda m: (sum(c.idle_time for c in m.crews)*m.workday_hours)/max(1.0,m.cumulative_active_crew_days),
            "external_idle_time_hours_per_active_crew_day": lambda m: (sum(c.idle_time_external for c in m.crews)*m.workday_hours)/max(1.0,m.cumulative_active_crew_days),
            "daily_idle_time_hours": lambda m: m.daily_idle_time*m.workday_hours,
            "daily_external_idle_time_hours": lambda m: m.daily_idle_time_external*m.workday_hours,
            "total_working_time": lambda m: sum(c.working_time for c in m.crews),
            "total_interruptions": lambda m: sum(t.interruptions for t in m.tasks),
            "prevented_interruptions": lambda m: sum(c.prevented_interruptions for c in m.crews),
            "total_movements": lambda m: sum(c.movements for c in m.crews),
            "autonomous_resolutions": lambda m: sum(c.autonomous_resolutions for c in m.crews),
            "escalations": lambda m: sum(c.escalations for c in m.crews),
            "alternative_task_switches": "alternative_task_switches",
            "failed_task_switches": "failed_task_switches",
            "supervisor_recovery_interventions": "supervisor_recovery_interventions",
            "external_disruptions": "external_disruptions",
            "avg_recovery_time": lambda m: safe_mean(m.recovery_times),
            "avg_blockage_resolution_time": lambda m: safe_mean(m.blockage_resolution_times),
            "total_recovery_time": "total_recovery_time",
            "idle_time_due_to_external_disruptions": "idle_time_due_to_external_disruptions",
            "idle_time_due_to_external_disruptions_hours": lambda m: m.idle_time_due_to_external_disruptions*m.workday_hours,
            "idle_time_due_to_external_disruptions_hours_per_day": lambda m: (m.idle_time_due_to_external_disruptions*m.workday_hours)/m._elapsed_days_for_rates(),
            "idle_time_due_to_external_disruptions_hours_per_active_crew_day": lambda m: (m.idle_time_due_to_external_disruptions*m.workday_hours)/max(1.0,m.cumulative_active_crew_days),
            "supervisor_reactive_time": lambda m: m.supervisor.last_reactive_time,
            "supervisor_reactive_hours_per_supervisor_day": lambda m: m.supervisor.last_reactive_hours_per_supervisor_day,
            "supervisor_planning_time": lambda m: m.supervisor.last_planning_time,
            "supervisor_reporting_time": lambda m: m.supervisor.last_reporting_time,
            "supervisor_base_workload": lambda m: m.supervisor.last_base_workload,
            "supervisor_total_workload": lambda m: m.supervisor.last_total_workload,
            "supervisor_planning_need": lambda m: m.supervisor.last_planning_need,
            "supervisor_planning_shortfall": lambda m: m.supervisor.last_planning_shortfall,
            "supervisor_available_planning_capacity": lambda m: m.supervisor.last_available_planning_capacity,
            "cumulative_base_workload": lambda m: m.supervisor.cumulative_base_workload,
            "cumulative_planning_shortfall": lambda m: m.supervisor.cumulative_planning_shortfall,
            "supervisor_utilization": lambda m: m.supervisor.last_utilization,
            "supervisor_backlog": lambda m: m.supervisor.backlog,
            "mean_supervisor_backlog": lambda m: m.cumulative_supervisor_backlog/m._elapsed_days_for_rates(),
            "max_supervisor_backlog": lambda m: m.max_supervisor_backlog,
            "supervisor_response_delay": lambda m: m.supervisor.last_response_delay,
            "firefighting_ratio": lambda m: m.supervisor.last_firefighting_ratio,
            "mean_firefighting_ratio": lambda m: m.cumulative_firefighting_ratio/m._elapsed_days_for_rates(),
            "max_firefighting_ratio": lambda m: m.max_firefighting_ratio,
            "crew_questions": "daily_questions",
            "cumulative_crew_questions": lambda m: m.supervisor.cumulative_questions,
            "unresolved_questions": lambda m: m.supervisor.last_unresolved_questions,
            "cumulative_unresolved_questions": lambda m: m.supervisor.cumulative_unresolved_questions,
            "cumulative_planning_time": lambda m: m.supervisor.cumulative_planning_time,
            "cumulative_reactive_time": lambda m: m.supervisor.cumulative_reactive_time,
            "active_external_blockages": lambda m: sum(t.external_blockage_active for t in m.tasks),
            "dvm_usefulness_events": "useful_dvm_events",
            "harmful_events": "harmful_events",
            "material_shortage_count": lambda m: m.external_disruptions_by_type.get("material_shortage", 0),
            "logistics_delay_count": lambda m: m.external_disruptions_by_type.get("logistics_delay", 0),
            "lifting_delay_count": lambda m: m.external_disruptions_by_type.get("lifting_delay", 0),
            "design_missing_count": lambda m: m.external_disruptions_by_type.get("design_information_missing", 0),
            "equipment_unavailable_count": lambda m: m.external_disruptions_by_type.get("equipment_unavailable", 0),
            "weather_condition_count": lambda m: m.external_disruptions_by_type.get("weather_or_site_condition", 0),
        }

    def _planned_finish(self, task):
        return float(task.planned_start + task.planned_duration)

    def _week_for_day(self, day_value):
        return int(day_value // self.week_length) + 1

    @property
    def current_week(self):
        return self._week_for_day(self.day)

    def _week_bounds(self, week):
        start = (int(week) - 1) * self.week_length
        end = start + self.week_length - 1
        return start, end

    def _planned_in_week(self, week):
        start, end = self._week_bounds(week)
        return [t for t in self.tasks if start <= self._planned_finish(t) <= end]

    def _actual_completion_promises_in_week(self, week):
        """Tasks actually completed during this week.

        v25.2 interpretation:
        If a task is completed in week W, it should be counted as a promised
        completion of week W unless it was already explicitly promised in another
        commitment set. This aligns PPC with actual weekly completion promises
        and prevents completed tasks from falling outside the PPC denominator.
        """
        start, end = self._week_bounds(week)
        return [
            t for t in self.tasks
            if t.actual_finish is not None and start <= t.actual_finish <= end
        ]

    def _committed_in_week(self, week):
        # v25.1: weekly commitment means promised completion.
        # Combine explicit LPS commitments, baseline completion promises and
        # tasks actually completed during the week. The latter prevents finished
        # work from disappearing from PPC simply because it was already in progress
        # when commitments were generated.
        ids = set(self.weekly_commitments.get(int(week), set()))
        ids.update(t.id for t in self._planned_in_week(week))
        ids.update(t.id for t in self._actual_completion_promises_in_week(week))
        return [t for t in self.tasks if t.id in ids]

    def _completed_committed_in_week(self, week):
        _, end = self._week_bounds(week)
        return [
            t for t in self._committed_in_week(week)
            if t.actual_finish is not None and t.actual_finish <= end
        ]

    def _completed_on_plan_in_week(self, week):
        return self._completed_committed_in_week(week)

    def _weekly_ppc_value(self, week):
        committed = self._committed_in_week(week)
        if not committed:
            return None
        return len(self._completed_committed_in_week(week)) / len(committed)

    @property
    def total_ppc_promises(self):
        # Aggregate promised completions across the whole observed project.
        # This is more stable than averaging small weekly percentages.
        weeks = range(1, max(self.current_week, self._week_for_day(self.planned_project_duration)) + 1)
        ids_by_week = {w: {t.id for t in self._committed_in_week(w)} for w in weeks}
        return sum(len(ids) for ids in ids_by_week.values())

    @property
    def total_ppc_successes(self):
        weeks = range(1, max(self.current_week, self._week_for_day(self.planned_project_duration)) + 1)
        successes = 0
        for w in weeks:
            successes += len(self._completed_committed_in_week(w))
        return successes

    @property
    def weekly_task_capacity(self):
        # In v24.9 one LPS task is assumed to be a weekly-sized package.
        # Therefore capacity is roughly active crews per week, not active crews * 5 days.
        s = self.dvm_scenario
        return max(1, int(round(
            self.active_crews_today
            * s.commitment_capacity_factor
            * (0.90 + 0.35 * s.commitment_realism + 0.12 * s.autonomy_level)
        )))

    @property
    def cumulative_schedule_adherence(self):
        # Cumulative planned-completion reliability up to the current week.
        _, end = self._week_bounds(self.current_week)
        due = [t for t in self.tasks if self._planned_finish(t) <= end]
        if not due:
            return 0.0
        done = [t for t in due if t.actual_finish is not None and t.actual_finish <= end]
        return len(done) / len(due)

    @property
    def planned_tasks_this_week(self):
        # Baseline due tasks, not LPS commitments.
        return len(self._planned_in_week(self.current_week))

    @property
    def weekly_committed_tasks(self):
        return len(self._committed_in_week(self.current_week))

    @property
    def completed_committed_tasks(self):
        return len(self._completed_committed_in_week(self.current_week))

    @property
    def completed_on_plan_this_week(self):
        return self.completed_committed_tasks

    @property
    def baseline_adherence(self):
        planned = self._planned_in_week(self.current_week)
        if not planned:
            return 0.0
        _, end = self._week_bounds(self.current_week)
        done = [t for t in planned if t.actual_finish is not None and t.actual_finish <= end]
        return len(done) / len(planned)

    @property
    def weekly_ppc(self):
        value = self._weekly_ppc_value(self.current_week)
        return 0.0 if value is None else value

    @property
    def last_completed_weekly_ppc(self):
        completed_weeks = [w for w in range(1, self.current_week + 1) if self.day >= self._week_bounds(w)[1]]
        values = [(w, self._weekly_ppc_value(w)) for w in completed_weeks]
        values = [(w, v) for w, v in values if v is not None]
        if not values:
            return self.weekly_ppc or 0.0
        return values[-1][1]

    @property
    def avg_weekly_ppc(self):
        # v25.1: use aggregate PPC over all observed weekly promises:
        # total successful promises / total promises. This avoids small empty or
        # partial weeks distorting PPC and keeps it consistent with project completion.
        promises = self.total_ppc_promises
        if promises <= 0:
            return self.weekly_ppc or 0.0
        return self.total_ppc_successes / promises

    @property
    def sound_commitment_share(self):
        committed=self._committed_in_week(self.current_week)
        if not committed:
            return 0.0
        return sum(t.commitment_sound for t in committed) / len(committed)

    @property
    def avg_make_ready_score(self):
        open_tasks=[t for t in self.tasks if not t.is_done]
        if not open_tasks:
            return 1.0
        return safe_mean([t.make_ready_score for t in open_tasks])

    @property
    def constraints_ready_count(self):
        return sum(sum(1 for v in t.constraints.values() if v) for t in self.tasks if not t.is_done)

    @property
    def constraints_missing_count(self):
        return sum(sum(1 for v in t.constraints.values() if not v) for t in self.tasks if not t.is_done)

    @property
    def weekly_carryover(self):
        _, end = self._week_bounds(self.current_week)
        if self.day < end:
            return 0
        return max(0, self.weekly_committed_tasks - self.completed_committed_tasks)

    @property
    def open_schedule_backlog(self):
        return sum((not t.is_done) and self._planned_finish(t) < self.day for t in self.tasks)

    @property
    def cumulative_plan_failures(self):
        # Count failed weekly commitments. Late completion does not erase PPC failure.
        failures = 0
        for week, ids in self.weekly_commitments.items():
            _, week_end = self._week_bounds(week)
            if self.day >= week_end:
                for t in self.tasks:
                    if t.id in ids and (t.actual_finish is None or t.actual_finish > week_end):
                        failures += 1
        return failures

    @property
    def late_completed_tasks(self):
        return sum(
            t.actual_finish is not None
            and t.actual_finish > self._week_bounds(self._week_for_day(self._planned_finish(t)))[1]
            for t in self.tasks
        )

    @property
    def actual_project_finish(self):
        if not self.tasks or not all(t.is_done for t in self.tasks):
            return None
        return max((t.actual_finish or 0) for t in self.tasks)

    @property
    def project_delay_days(self):
        # In v24.7 this is realized delay whenever all tasks are complete.
        # During an unfinished run it is a provisional delay-to-date, but normal
        # simulation should continue until completion.
        actual_finish = self.actual_project_finish
        if actual_finish is not None:
            return max(0.0, actual_finish - self.planned_project_finish)
        return max(0.0, self.day - self.planned_project_finish)

    @property
    def avg_lateness_days(self):
        lateness = []
        for t in self.tasks:
            planned_finish = self._planned_finish(t)
            if t.actual_finish is not None:
                lateness.append(max(0.0, t.actual_finish - planned_finish))
            elif self.day > planned_finish:
                lateness.append(self.day - planned_finish)
        return safe_mean(lateness)

    @property
    def ppc_schedule_consistency_gap(self):
        # Diagnostic: a near-on-time project with very low PPC is suspicious.
        # Schedule score is 1.0 at or before planned duration and declines with delay.
        delay = self.project_delay_days
        schedule_score = clamp_range(1.0 - delay / max(1.0, float(self.planned_project_duration)), 0.0, 1.0)
        return max(0.0, schedule_score - self.avg_weekly_ppc)

    @property
    def ppc_schedule_score(self):
        delay = self.project_delay_days
        return clamp_range(1.0 - delay / max(1.0, float(self.planned_project_duration)), 0.0, 1.0)

    @property
    def ppc_proxy(self):
        return self.avg_weekly_ppc

    def _trade_demand_scores(self):
        """Estimate which trades are needed today.

        This avoids the earlier error where the first N crews in the static list
        stayed active while remaining tasks in other trades had no crew.
        """
        scores={tr:0.0 for tr in self.trades}
        for t in self.tasks:
            if t.is_done or t.external_blockage_active:
                continue
            score=0.0
            if t.status==TaskStatus.IN_PROGRESS:
                score+=12.0
            if t.id in self.current_committed_task_ids:
                score+=8.0
            if t.status==TaskStatus.READY:
                score+=5.0
            if t.planned_start <= self.day:
                score+=3.0
            if self._planned_finish(t) < self.day:
                score+=4.0
            score+=max(0.0, t.priority)
            scores[t.trade]=scores.get(t.trade,0.0)+score
        return scores

    def _active_crews_for_today(self):
        """Choose active crews according to remaining trade-specific work demand."""
        if not self.crews:
            self.active_crew_trades_today=""
            return []

        n=max(1, min(int(self.active_crews_today), len(self.crews)))
        demand=self._trade_demand_scores()

        # Keep crews that already have in-progress work, but only while there is a slot.
        selected=[]
        selected_ids=set()
        in_progress=sorted(
            [c for c in self.crews if c.current_task_id is not None],
            key=lambda c: demand.get(c.trade,0.0),
            reverse=True,
        )
        for c in in_progress:
            if len(selected)>=n:
                break
            selected.append(c); selected_ids.add(c.id)

        # Then choose crews from the trades with highest current demand.
        trade_order=sorted(self.trades, key=lambda tr: (demand.get(tr,0.0), -self.trades.index(tr)), reverse=True)
        # Rotate tie-breaking slightly so a low-capacity tail does not always pick the same trades.
        if trade_order:
            shift=self.day % len(trade_order)
            trade_order=trade_order[shift:]+trade_order[:shift]

        for tr in trade_order:
            if len(selected)>=n:
                break
            if demand.get(tr,0.0)<=0:
                continue
            candidates=[c for c in self.crews if c.trade==tr and c.id not in selected_ids]
            if not candidates:
                continue
            # Prefer closer and more productive crews.
            c=max(candidates, key=lambda c: c.productivity + .05*c.experience - .01*abs(c.location))
            selected.append(c); selected_ids.add(c.id)

        # Fill any remaining slots with generally useful crews, so the model can still recover.
        if len(selected)<n:
            rest=[c for c in self.crews if c.id not in selected_ids]
            rest=sorted(rest, key=lambda c: (demand.get(c.trade,0.0), c.productivity), reverse=True)
            for c in rest:
                selected.append(c); selected_ids.add(c.id)
                if len(selected)>=n:
                    break

        self.active_crew_trades_today=",".join(c.trade for c in selected)
        return selected

    def _elapsed_days_for_rates(self):
        # DataCollector collects before self.day is incremented, so day+1 is a
        # practical elapsed-days denominator for cumulative h/day indicators.
        return max(1.0, float(self.day+1))

    def _update_supervisor_staffing(self):
        """Aggregate supervisor staffing and role-based time budgets.

        v25.4 interpretation:
        - each active discipline/trade has one trade supervisor;
        - one site manager is available above trade supervisors;
        - trade supervisors and site manager have different time-allocation profiles;
        - field interaction means time spent with crews on site: instructions,
          workface checks, small problem solving, coordination and supervision.

        The model still uses one aggregate SupervisorAgent, but its daily capacity
        and time budgets are built from these role counts.
        """
        active_trades={c.trade for c in getattr(self,"active_crews",[]) if c is not None}
        self.trade_supervisor_count_today=len(active_trades)
        self.site_manager_count_today=1 if (self.trade_supervisor_count_today>0 or any(not t.is_done for t in self.tasks)) else 0
        self.supervisor_count_today=self.trade_supervisor_count_today+self.site_manager_count_today

        trade_hours=self.trade_supervisor_count_today*self.trade_supervisor_day_hours
        site_hours=self.site_manager_count_today*self.site_manager_day_hours
        self.effective_supervisor_capacity_today=trade_hours+site_hours
        self.supervisor_capacity_per_person=(self.effective_supervisor_capacity_today/max(1,self.supervisor_count_today)) if self.supervisor_count_today else 0.0

        self.field_interaction_capacity_hours_today=(
            trade_hours*self.trade_supervisor_field_share
            + site_hours*self.site_manager_field_share
        )
        self.planning_target_hours_today=max(
            float(getattr(self.dvm_scenario,"planning_need_per_day",2.0)),
            trade_hours*self.trade_supervisor_planning_share
            + site_hours*self.site_manager_planning_share,
        )
        # Role-based other/admin/reporting budget. Scenario-level reporting burden
        # is added on top in SupervisorAgent.process_day.
        self.admin_reporting_nominal_hours_today=max(
            0.0,
            self.effective_supervisor_capacity_today
            - self.field_interaction_capacity_hours_today
            - self.planning_target_hours_today,
        )
        # Routine field interaction demand: the more active crews and the more
        # uncertain the workface, the more same-day crew interaction is needed.
        uncertainty=(
            .40*(1-self.current_picture.workface_quality)
            + .30*(1-self.current_picture.readiness_quality)
            + .20*(1-self.planning_quality)
            + .10*self.workload_pressure
        )
        dvm_self_service=max(0.0,
            .20*self.dvm_scenario.crew_access
            + .20*self.dvm_scenario.task_relevance
            + .15*self.dvm_scenario.autonomy_level
            - .10*self.dvm_scenario.decision_centralization
        )
        demand_per_active_crew=clamp_range(1.15 + 1.10*uncertainty - .55*dvm_self_service, .45, 2.60)
        self.baseline_field_interaction_demand_hours_today=len(getattr(self,"active_crews",[]))*demand_per_active_crew
        self.field_interaction_demand_hours_today=self.baseline_field_interaction_demand_hours_today
        self.unresolved_field_support_hours_today=0.0
        self.supervisor_field_support_idle_added_today=0.0
        if hasattr(self,"supervisor"):
            self.supervisor.capacity_per_day=self.effective_supervisor_capacity_today
    def _update_period_metrics(self):
        elapsed=self._elapsed_days_for_rates()
        backlog=float(self.open_schedule_backlog)
        self.cumulative_open_schedule_backlog+=backlog
        self.max_open_schedule_backlog=max(self.max_open_schedule_backlog,backlog)
        mr=float(self.avg_make_ready_score)
        self.cumulative_make_ready_score+=mr
        self.min_make_ready_score=min(self.min_make_ready_score,mr)
        sb=float(getattr(self.supervisor,"backlog",0.0))
        self.cumulative_supervisor_backlog+=sb
        self.max_supervisor_backlog=max(self.max_supervisor_backlog,sb)
        ff=float(getattr(self.supervisor,"last_firefighting_ratio",0.0))
        self.cumulative_firefighting_ratio+=ff
        self.max_firefighting_ratio=max(self.max_firefighting_ratio,ff)
        self.cumulative_supervisor_count+=self.supervisor_count_today
        self.max_supervisor_count=max(self.max_supervisor_count,self.supervisor_count_today)
        ufs=float(getattr(self.supervisor,"last_unresolved_field_support_hours",0.0))
        self.unresolved_field_support_hours_today=ufs
        self.cumulative_unresolved_field_support_hours+=ufs
        self.max_unresolved_field_support_hours=max(self.max_unresolved_field_support_hours,ufs)
        self.cumulative_field_interaction_demand_hours+=float(getattr(self.supervisor,"last_field_interaction_demand",0.0))
        self.cumulative_field_interaction_used_hours+=float(getattr(self.supervisor,"last_field_interaction_used",0.0))
        self.cumulative_field_support_utilization+=float(getattr(self.supervisor,"last_field_support_utilization",0.0))
        self.cumulative_planning_hours_per_supervisor_day+=float(getattr(self.supervisor,"last_planning_hours_per_supervisor_day",0.0))
        self.cumulative_field_interaction_hours_per_supervisor_day+=float(getattr(self.supervisor,"last_field_interaction_hours_per_supervisor_day",0.0))
        self.cumulative_admin_reporting_hours_per_supervisor_day+=float(getattr(self.supervisor,"last_admin_reporting_hours_per_supervisor_day",0.0))

    def step(self):
        self.daily_questions=self.daily_escalations=self.daily_coordination_needs=self.daily_recovery_interventions=0; self.daily_external_pressure=0; self.daily_useful=0; self.daily_harmful=0
        self.daily_making_do_starts=0; self.daily_making_do_interruptions=0; self.daily_rework_due_to_making_do=0.0
        prev_idle=sum(c.idle_time for c in self.crews)
        prev_idle_external=sum(c.idle_time_external for c in self.crews)
        self._update_daily_load_state()
        self._update_blockages(); self.current_picture=self._picture(); self._update_constraints()
        if self.day % self.week_length == 0:
            self._make_weekly_commitments()
        self._update_readiness()
        self.active_crews=self._active_crews_for_today()
        self.cumulative_active_crew_days+=len(self.active_crews)
        self._update_supervisor_staffing()
        for c in list(self.active_crews): c.step()
        self.daily_coordination_needs += self._baseline_coordination_needs()
        self.supervisor.process_day(self.daily_questions,self.daily_escalations,self.daily_coordination_needs,self.daily_recovery_interventions,self.daily_external_pressure)
        # If field support demand exceeds the available worker-interaction budget,
        # part of the unresolved support demand appears immediately as crew waiting.
        unresolved_support=float(getattr(self.supervisor,"last_unresolved_field_support_hours",0.0))
        self.field_interaction_demand_hours_today=float(getattr(self.supervisor,"last_field_interaction_demand",self.baseline_field_interaction_demand_hours_today))
        self.unresolved_field_support_hours_today=unresolved_support
        if unresolved_support>0 and self.active_crews:
            idle_units=(unresolved_support/self.workday_hours)/len(self.active_crews)
            for c in self.active_crews:
                c.idle_time+=idle_units
            self.supervisor_field_support_idle_added_today=unresolved_support
        self.daily_idle_time=max(0.0,sum(c.idle_time for c in self.crews)-prev_idle)
        self.daily_idle_time_external=max(0.0,sum(c.idle_time_external for c in self.crews)-prev_idle_external)
        self._update_period_metrics()
        self._update_trust(); self.datacollector.collect(self); self.day+=1
        if sum(t.is_done for t in self.tasks)==len(self.tasks): self.running=False
        if self.day>=self.simulation_hard_limit:
            self.hard_limit_reached=True
            self.running=False
    def _baseline_coordination_needs(self):
        """Daily production coordination load not directly caused by crew questions.

        Poor ready work area visibility, centralized decision-making and schedule
        backlog create more coordination demand for the supervisor.
        """
        s = self.dvm_scenario
        backlog_pressure = clamp(self.open_schedule_backlog / max(len(self.tasks), 1))
        visibility_gap = 1.0 - self.current_picture.readiness_quality
        info_gap = 1.0 - self.current_picture.workface_quality
        return max(
            0.0,
            0.30
            + 1.10 * visibility_gap
            + 0.70 * info_gap
            + 0.85 * s.decision_centralization
            + 0.65 * backlog_pressure
            + getattr(s,"workload_pressure_sensitivity",.6)*self.workload_pressure
            + .40*s.making_do_tendency*(1-self.avg_make_ready_score)
            - 0.55 * s.autonomy_level
            - 0.35 * self.planning_quality,
        )

    def _picture(self):
        s=self.dvm_scenario; r=self.py_random; base=.22*r.triangular(0,1,s.capture_rate)+.22*r.triangular(0,1,s.data_accuracy)+.2*r.triangular(0,1,s.data_timeliness)+.18*s.data_completeness+.18*s.integration_level
        adj=clamp(base*self.data_quality_modifier+.05*self.planning_quality-.1*s.reporting_burden); wf=clamp(adj*(.45*s.crew_access+.25*s.visual_clarity+.30*s.task_relevance)); mg=clamp(adj*(.60*s.management_access+.2*s.visual_clarity+.2*s.integration_level))
        return SituationPicture(wf,mg,wf*s.task_recommendation_quality,wf*s.readiness_visibility,wf*s.material_visibility,wf*s.congestion_visibility,wf*s.priority_visibility)
    def _update_blockages(self):
        for t in self.tasks:
            if t.external_blockage_active:
                t.external_blockage_remaining-=1
                if t.external_blockage_remaining<=0: t.external_blockage_active=False; t.status=TaskStatus.READY; self.blockage_resolution_times.append(self.day-(t.external_blockage_started or self.day))
    def _update_constraints(self):
        """Update LPS prerequisites for each task."""
        s=self.dvm_scenario; r=self.py_random
        done={t.id for t in self.tasks if t.is_done}
        visibility=clamp(.35*s.constraint_screening_strength+.25*self.current_picture.readiness_quality+.20*self.current_picture.workface_quality+.20*self.planning_quality)
        for t in self.tasks:
            if t.is_done:
                t.make_ready_score=1.0
                continue
            # predecessor is deterministic; other constraints are progressively made ready.
            t.constraints["predecessor_ready"]=all(p in done for p in t.predecessor_ids)
            if self.day < t.planned_start-10:
                early_factor=.25
            elif self.day < t.planned_start:
                early_factor=.65
            else:
                early_factor=1.0
            base=clamp(
                .08
                + .36*s.initial_plan_reliability
                + .22*visibility
                + .18*self.planning_quality
                + .14*s.constraint_improvement_rate
                - .08*self.workload_pressure
                - .06*clamp(self.supervisor.backlog/max(self.supervisor.capacity_per_day,.01)),
                .02,.96
            )*early_factor
            probs={
                "design_ready": base*(.80+.35*s.readiness_visibility),
                "material_ready": base*(.75+.45*s.material_visibility),
                "crew_ready": clamp(.55+.10*self.active_crews_today-.08*self.workload_pressure),
                "equipment_ready": base*(.72+.25*s.integration_level),
                "space_ready": base*(.70+.40*s.congestion_visibility),
                "approval_ready": base*(.68+.18*s.management_access),
                "safety_quality_ready": base*(.78+.22*s.visual_clarity),
            }
            for key, prob in probs.items():
                if not t.constraints[key] and r.random()<clamp(prob):
                    t.constraints[key]=True
            t.material_ready=t.constraints["material_ready"]
            t.location_ready=t.constraints["space_ready"]
            t.make_ready_score=sum(1 for v in t.constraints.values() if v)/len(t.constraints)

    def _is_sound_task(self,t):
        return t.make_ready_score >= self.dvm_scenario.make_ready_threshold and t.constraints.get("predecessor_ready",False)

    def _make_weekly_commitments(self):
        """Create LPS weekly completion promises.

        v25.2 modelling assumption:
        - LPS tasks are weekly-sized packages.
        - The weekly plan promises completions, not merely starts.
        - Tasks planned to finish this week form the baseline promise set.
        - Already in-progress tasks can also be promised for completion this week.
        """
        s = self.dvm_scenario
        r = self.py_random
        week = self.current_week
        start, end = self._week_bounds(week)

        for t in self.tasks:
            if t.committed_week == week:
                t.committed_week = None
                t.commitment_day = None
                t.commitment_sound = False
        self.current_committed_task_ids = set()

        open_tasks = [
            t for t in self.tasks
            if not t.is_done and not t.external_blockage_active
            and t.status in (TaskStatus.NOT_READY, TaskStatus.READY, TaskStatus.INTERRUPTED, TaskStatus.IN_PROGRESS)
        ]

        planned_this_week = [
            t for t in open_tasks
            if start <= self._planned_finish(t) <= end
        ]

        in_progress_promises = [
            t for t in open_tasks
            if t.status == TaskStatus.IN_PROGRESS
            and t not in planned_this_week
            and self._planned_finish(t) <= end + self.week_length
        ]

        carryover = [
            t for t in open_tasks
            if self._planned_finish(t) < start
            and t not in in_progress_promises
            # v25.2: avoid endless recommitment of the same unsound task.
            # A repeatedly failed carryover task needs to be in progress or sound
            # before it is promised again.
            and (
                self.task_commitment_counts.get(t.id, 0) < 2
                or t.status == TaskStatus.IN_PROGRESS
                or self._is_sound_task(t)
            )
        ]

        lookahead = [
            t for t in open_tasks
            if end < self._planned_finish(t) <= end + self.week_length
            and t not in in_progress_promises
        ]

        capacity = self.weekly_task_capacity

        # The planned-this-week set is the core weekly promise. Capacity affects
        # how much additional carryover/lookahead the team dares to promise.
        overcommit_multiplier = 1.0 + 0.35 * s.overcommitment_tendency - 0.18 * s.commitment_realism
        target = max(len(planned_this_week), int(round(capacity * overcommit_multiplier)))
        target = max(1, target)

        candidates = []
        candidates.extend(in_progress_promises)
        candidates.extend(carryover)
        candidates.extend(planned_this_week)
        if len(candidates) < target:
            candidates.extend(lookahead)

        seen = set()
        unique = []
        for t in candidates:
            if t.id not in seen:
                unique.append(t)
                seen.add(t.id)

        if not unique:
            self.weekly_commitments[week] = set()
            return

        def commit_score(t):
            planned_urgency = 3.0 if start <= self._planned_finish(t) <= end else 0.0
            in_progress_bonus = 3.0 if t.status == TaskStatus.IN_PROGRESS else 0.0
            carryover_urgency = 2.8 if self._planned_finish(t) < start else 0.0
            sound_bonus = 2.0 if self._is_sound_task(t) else 0.0
            return (
                in_progress_bonus
                + carryover_urgency
                + planned_urgency
                + sound_bonus
                + 1.2 * t.make_ready_score
                + t.priority
                + 0.05 * max(0, self.day - self._planned_finish(t))
            )

        unique.sort(key=commit_score, reverse=True)

        committed = []
        for t in unique:
            sound = self._is_sound_task(t) or t.status == TaskStatus.IN_PROGRESS
            # Planned-this-week and in-progress tasks are normally completion promises.
            is_core_promise = (start <= self._planned_finish(t) <= end) or (t.status == TaskStatus.IN_PROGRESS)
            risky_commit_prob = clamp(
                (1 - s.constraint_screening_strength)
                * s.overcommitment_tendency
                * (1 + 0.35 * self.workload_pressure)
            )
            if is_core_promise or sound or r.random() < risky_commit_prob:
                t.committed_week = week
                t.commitment_day = self.day
                t.commitment_sound = bool(sound)
                committed.append(t)
            if len(committed) >= target:
                break

        ids = {t.id for t in committed}
        for t in committed:
            self.task_commitment_counts[t.id]=self.task_commitment_counts.get(t.id,0)+1
        self.current_committed_task_ids = ids
        self.weekly_commitments[week] = ids
        self.commitment_history[week] = {
            "committed": len(committed),
            "sound": sum(t.commitment_sound for t in committed),
            "capacity": capacity,
            "target": target,
            "planned_this_week": len(planned_this_week),
            "in_progress_promises": len(in_progress_promises),
        }

    def _update_readiness(self):
        done={t.id for t in self.tasks if t.is_done}
        for t in self.tasks:
            if t.is_done or t.external_blockage_active:
                continue
            sound=self._is_sound_task(t)
            # READY means sound enough for normal execution.
            if sound and t.status==TaskStatus.NOT_READY:
                t.status=TaskStatus.READY
            # Risky commitments may also become visible to crews, but are not truly sound.
            if t.committed_week==self.current_week and t.status==TaskStatus.NOT_READY:
                t.status=TaskStatus.READY
            # If predecessors fail, keep task from normal sound execution.
            if not all(p in done for p in t.predecessor_ids) and not t.making_do_active and t.status==TaskStatus.READY:
                t.status=TaskStatus.NOT_READY

    def step_crew(self,c):
        sa=self._sa(c); c.last_sa=sa.total; cur=self._task(c.current_task_id)
        if self.py_random.random()<self._question_prob(cur,sa): self.daily_questions+=1; c.questions_asked+=1
        if cur and cur.status==TaskStatus.IN_PROGRESS and not cur.external_blockage_active:
            shock=self._pop_shock(c.trade)
            if shock: self._external(cur,c,sa,shock); return
            making_do_risk=0.0
            if cur.making_do_active:
                making_do_risk=self.dvm_scenario.making_do_interruption_rate*(1-cur.make_ready_score)*(1+.5*self.workload_pressure)
            if self.py_random.random()<making_do_risk:
                cur.interruptions+=1; cur.making_do_interruptions+=1; self.daily_making_do_interruptions+=1; c.escalations+=1; self.daily_escalations+=1; c.idle_time+=1; self.daily_coordination_needs+=1
                rework=self.dvm_scenario.making_do_rework_factor*(1-cur.make_ready_score)
                cur.remaining_duration+=rework; cur.rework_due_to_making_do+=rework; self.daily_rework_due_to_making_do+=rework
                return
            if self.py_random.random()<self.dvm_scenario.disturbance_probability*(1-.4*self.planning_quality): cur.interruptions+=1; c.escalations+=1; self.daily_escalations+=1; c.idle_time+=1
            field_support_pressure=clamp_range(float(getattr(self.supervisor,"last_unresolved_field_support_hours",0.0))/max(float(getattr(self,"field_interaction_capacity_hours_today",1.0)),0.01),0.0,2.0)
            backlog_penalty=clamp_range(1.0-.018*self.open_schedule_backlog-.025*self.supervisor.backlog-.12*self.workload_pressure-.08*field_support_pressure,.45,1.0)
            making_do_penalty=clamp_range(1.0-.45*cur.making_do_active*(1-cur.make_ready_score),.45,1.0)
            progress_factor=clamp_range(.72+.24*sa.comprehension+.20*self.planning_quality+.08*self.current_picture.readiness_quality-.10*self.dvm_scenario.reporting_burden,.45,1.35)
            cur.remaining_duration-=c.productivity*progress_factor*backlog_penalty*making_do_penalty; c.working_time+=1
            if cur.remaining_duration<=0:
                cur.status=TaskStatus.COMPLETED
                cur.actual_finish=self.day
                cur.making_do_active=False
                finish_week=self._week_for_day(self.day)
                self.weekly_actual_completion_promises.setdefault(finish_week,set()).add(cur.id)
                c.current_task_id=None
        else:
            task=self._choose_task(c)
            if task is None: c.idle_time+=1; return
            if c.location!=task.location: c.movements+=abs(c.location-task.location); c.location=task.location
            if not self._is_sound_task(task):
                md_prob=clamp(self.dvm_scenario.making_do_tendency*(1-task.make_ready_score)*(1+.6*self.workload_pressure)*(1+.4*self.dvm_scenario.decision_centralization))
                if self.py_random.random()<md_prob:
                    task.making_do_active=True
                    if not task.making_do_started:
                        task.making_do_started=True
                        self.daily_making_do_starts+=1
                    self.daily_harmful+=1
                    self.daily_coordination_needs+=1
                else:
                    c.idle_time+=1
                    self.daily_questions+=1
                    return
            c.current_task_id=task.id; task.status=TaskStatus.IN_PROGRESS; task.actual_start=self.day if task.actual_start is None else task.actual_start
    def _sa(self,c):
        s=self.dvm_scenario; r=self.py_random; p=clamp(.1+.42*self.current_picture.workface_quality*c.effective_use()+.22*(.45*s.crew_access+.25*s.visual_clarity+.2*s.task_relevance+.1*c.dvm_skill)+.13*self.trust_in_data+.1*self.planning_quality+r.normalvariate(0,.04)); comp=clamp(.08+.36*p+.18*c.experience+.16*s.task_relevance+.12*self.trust_in_management+.14*self.planning_quality+r.normalvariate(0,.035)); proj=clamp(.05+.34*comp+.22*self.current_picture.recommendation_quality*c.effective_use()+.16*s.autonomy_level+.13*c.experience+.16*self.planning_quality+r.normalvariate(0,.035)); return AgentSA(p,comp,proj)
    def _question_prob(self,task,sa):
        comp=.65 if task is None else task.complexity; s=self.dvm_scenario
        backlog_pressure=clamp(self.open_schedule_backlog/max(len(self.tasks),1))
        supervisor_pressure=clamp(self.supervisor.backlog/max(self.supervisor.capacity_per_day,.01))
        field_support_pressure=clamp_range(float(getattr(self.supervisor,"last_unresolved_field_support_hours",0.0))/max(float(getattr(self,"field_interaction_capacity_hours_today",1.0)),0.01),0.0,2.0)
        uncertainty=(.55*(1-self.current_picture.workface_quality)+.25*(1-self.current_picture.readiness_quality)+.20*(1-self.planning_quality))
        return clamp(
            .04
            + .34*comp*(1-sa.total)*uncertainty
            + .07*s.decision_centralization*(1-s.autonomy_level)
            + .05*s.reporting_burden*(1-self.trust_in_management)
            + .08*backlog_pressure
            + .05*supervisor_pressure
            + .04*field_support_pressure
            + .07*getattr(s,"workload_pressure_sensitivity",.6)*self.workload_pressure,
            0,.75
        )
    def _task(self,i): return next((t for t in self.tasks if t.id==i),None) if i is not None else None
    def _choose_task(self,c):
        cand=[t for t in self.tasks if t.trade==c.trade and t.status==TaskStatus.READY and not t.external_blockage_active and not t.is_done]
        # v25.3: allow explicitly promised but not-yet-sound tasks to be considered
        # as risky making-do candidates. Without this, making-do may never activate
        # because unsound tasks remain outside the READY candidate set.
        risky=[t for t in self.tasks if t.trade==c.trade and t.committed_week==self.current_week and t.status==TaskStatus.NOT_READY and not t.external_blockage_active and not t.is_done]
        cand=cand+risky
        if not cand:
            return None
        return max(cand,key=lambda t:
            (1.1 if t.id in self.current_committed_task_ids else 0)
            + (0.45 if self._is_sound_task(t) else 0)
            + t.priority
            + .18*self.planning_quality
            + .04*max(0,self.day-self._planned_finish(t))
            - .05*abs(t.location-c.location)
        )
    def _pop_shock(self,trade):
        for sh in self.shock_schedule.get(self.day,[]):
            if not sh.consumed and sh.trade==trade: sh.consumed=True; return sh
        return None
    def _external(self,t,c,sa,shock):
        t.external_blockage_active=True; t.external_blockage_type=shock.disruption_type; t.external_blockage_started=self.day; t.external_blockage_remaining=shock.base_duration; t.status=TaskStatus.BLOCKED_EXTERNAL; t.interruptions+=1; self.external_disruptions+=1; self.external_disruptions_by_type[shock.disruption_type]=self.external_disruptions_by_type.get(shock.disruption_type,0)+1
        backlog_pressure=clamp(self.open_schedule_backlog/max(len(self.tasks),1))
        p_alt=clamp(
            .05
            + .28*sa.total
            + .22*self.current_picture.workface_quality
            + .18*self.current_picture.readiness_quality
            + .18*self.planning_quality
            + .20*self.current_picture.recommendation_quality
            + .14*self.dvm_scenario.autonomy_level
            - .10*self.dvm_scenario.decision_centralization
            - .08*backlog_pressure
            - .06*getattr(self.dvm_scenario,"workload_pressure_sensitivity",.6)*self.workload_pressure
        )
        if self.py_random.random()<p_alt:
            rec=self.py_random.uniform(.15,.8)*(1+.35*(1-sa.total)+.25*(1-self.planning_quality)); self.alternative_task_switches+=1; c.alternative_task_switches+=1; self.daily_useful+=1
        else:
            rec=self.supervisor.last_response_delay+shock.base_duration*(1+.75*(1-self.planning_quality)+.50*(1-self.current_picture.workface_quality)+.25*(1-self.current_picture.readiness_quality)+.20*self.dvm_scenario.reporting_burden+.15*backlog_pressure)+self.py_random.uniform(.25,1.25); self.failed_task_switches+=1; c.failed_task_switches+=1; self.supervisor_recovery_interventions+=1; self.daily_questions+=1; self.daily_escalations+=1; self.daily_recovery_interventions+=1; self.daily_coordination_needs+=1; self.daily_harmful+=1
        self.recovery_times.append(rec); self.total_recovery_time+=rec; c.idle_time+=rec; c.idle_time_external+=rec; self.idle_time_due_to_external_disruptions+=rec; c.current_task_id=None; self.daily_external_pressure+=1+.25*rec
    def _update_trust(self):
        s=self.dvm_scenario; gain=s.trust_sensitivity*self.daily_useful*(1-.6*s.reporting_burden); loss=s.trust_sensitivity*self.daily_harmful*(.35*s.reporting_burden+.45*s.perceived_surveillance+.2*(1-self.planning_quality))
        self.trust_in_data=clamp(self.trust_in_data+.45*gain-.45*loss); self.trust_in_management=clamp(self.trust_in_management+.35*gain-.55*loss-.004*s.compliance_pressure*s.perceived_surveillance)
    def get_model_dataframe(self): return self.datacollector.get_model_vars_dataframe().reset_index(drop=True)
