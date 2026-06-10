from __future__ import annotations
from dataclasses import dataclass
import random
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

class DVMConstructionModel(Model):
    def __init__(self, scenario: Scenario|None=None, seed:int=20260609, max_days:int=100, number_of_tasks:int=72, daily_shock_probability:float=.32):
        try: super().__init__(seed=seed)
        except TypeError: super().__init__()
        object.__setattr__(self, "dvm_scenario", scenario or get_default_scenarios()[0]); self.seed=seed; self.max_days=max_days; self.day=0; self.running=True; self.py_random=random.Random(seed)
        self.trust_in_data=self.dvm_scenario.initial_trust_in_data; self.trust_in_management=self.dvm_scenario.initial_trust_in_management; self.planning_quality=self.dvm_scenario.initial_planning_quality; self.data_quality_modifier=1.0
        self.useful_dvm_events=0; self.harmful_events=0; self.external_disruptions=0; self.external_disruptions_by_type={}; self.recovery_times=[]; self.blockage_resolution_times=[]
        self.total_recovery_time=0.0; self.alternative_task_switches=0; self.failed_task_switches=0; self.supervisor_recovery_interventions=0; self.idle_time_due_to_external_disruptions=0.0
        self.daily_questions=0; self.daily_escalations=0; self.daily_coordination_needs=0; self.daily_recovery_interventions=0; self.daily_external_pressure=0; self.daily_useful=0; self.daily_harmful=0
        self.week_length=5; self.current_picture=SituationPicture(0,0,0,0,0,0,0); self.trades=["drywall","mep","finishes","carpentry"]
        self.shock_schedule=generate_external_shock_schedule(seed,self.trades,max_days+40,daily_shock_probability)
        self.tasks=[]; self.crews=[]; self._create_project(number_of_tasks)
        self.planned_project_finish=max((self._planned_finish(t) for t in self.tasks), default=0.0)
        self.datacollector=DataCollector(model_reporters=self._reporters()); self.datacollector.collect(self)
    def _create_project(self,n):
        r=self.py_random
        for i in range(n):
            pred=[r.randrange(max(1,i-10),i)] if i>6 and r.random()<.6 else []
            t=TaskAgent(self,i,r.choice(self.trades),r.randrange(12),r.randrange(42),r.randint(1,5),r.uniform(.2,1),r.uniform(.35,1),pred); self.tasks.append(t)
        for i,tr in enumerate(["drywall","mep","finishes","carpentry","drywall","mep"]):
            ad=clamp(.35+.48*self.dvm_scenario.crew_access-.18*self.dvm_scenario.reporting_burden+r.normalvariate(0,.08)); comp=clamp(self.dvm_scenario.compliance_pressure*(.45+.45*self.dvm_scenario.management_access))
            self.crews.append(CrewAgent(self,1000+i,tr,[0,2,4,6,8,10][i],clamp(r.normalvariate(.6,.15)),clamp(r.normalvariate(.5+.25*self.dvm_scenario.crew_access,.15)),clamp_range(r.normalvariate(1,.1),.75,1.25),ad,comp))
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
            "completed_tasks": lambda m: sum(t.is_done for t in m.tasks),
            "total_tasks": lambda m: len(m.tasks),
            "planned_tasks_this_week": lambda m: m.planned_tasks_this_week,
            "completed_on_plan_this_week": lambda m: m.completed_on_plan_this_week,
            "weekly_ppc": lambda m: m.weekly_ppc,
            "avg_weekly_ppc": lambda m: m.avg_weekly_ppc,
            "last_completed_weekly_ppc": lambda m: m.last_completed_weekly_ppc,
            "weekly_carryover": lambda m: m.weekly_carryover,
            "open_schedule_backlog": lambda m: m.open_schedule_backlog,
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
            "management_picture_quality": lambda m: m.current_picture.management_quality,
            "workface_gap": lambda m: m.current_picture.workface_gap,
            "total_idle_time": lambda m: sum(c.idle_time for c in m.crews),
            "total_idle_time_external": lambda m: sum(c.idle_time_external for c in m.crews),
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
            "supervisor_reactive_time": lambda m: m.supervisor.last_reactive_time,
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
            "supervisor_response_delay": lambda m: m.supervisor.last_response_delay,
            "firefighting_ratio": lambda m: m.supervisor.last_firefighting_ratio,
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

    def _completed_on_plan_in_week(self, week):
        _, end = self._week_bounds(week)
        return [
            t for t in self._planned_in_week(week)
            if t.actual_finish is not None and t.actual_finish <= end
        ]

    def _weekly_ppc_value(self, week):
        planned = self._planned_in_week(week)
        if not planned:
            return 0.0
        return len(self._completed_on_plan_in_week(week)) / len(planned)

    @property
    def planned_tasks_this_week(self):
        return len(self._planned_in_week(self.current_week))

    @property
    def completed_on_plan_this_week(self):
        return len(self._completed_on_plan_in_week(self.current_week))

    @property
    def weekly_ppc(self):
        return self._weekly_ppc_value(self.current_week)

    @property
    def last_completed_weekly_ppc(self):
        completed_weeks = [w for w in range(1, self.current_week + 1) if self.day >= self._week_bounds(w)[1]]
        completed_weeks = [w for w in completed_weeks if self._planned_in_week(w)]
        if not completed_weeks:
            return self.weekly_ppc
        return self._weekly_ppc_value(max(completed_weeks))

    @property
    def avg_weekly_ppc(self):
        completed_weeks = [w for w in range(1, self.current_week + 1) if self.day >= self._week_bounds(w)[1]]
        values = [self._weekly_ppc_value(w) for w in completed_weeks if self._planned_in_week(w)]
        if not values:
            return self.weekly_ppc
        return safe_mean(values)

    @property
    def weekly_carryover(self):
        # Open tasks from the current planned week after the week has ended.
        _, end = self._week_bounds(self.current_week)
        if self.day < end:
            return 0
        return max(0, self.planned_tasks_this_week - self.completed_on_plan_this_week)

    @property
    def open_schedule_backlog(self):
        # Planned to be finished before today, but still not complete.
        return sum((not t.is_done) and self._planned_finish(t) < self.day for t in self.tasks)

    @property
    def cumulative_plan_failures(self):
        # Count all weekly commitments that have already failed. Late completion
        # does not erase the historical PPC failure.
        failures = 0
        for t in self.tasks:
            planned_week = self._week_for_day(self._planned_finish(t))
            _, week_end = self._week_bounds(planned_week)
            if self.day >= week_end:
                if t.actual_finish is None or t.actual_finish > week_end:
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
    def project_delay_days(self):
        if not self.tasks:
            return 0.0
        all_done = all(t.is_done for t in self.tasks)
        if all_done:
            actual_finish = max((t.actual_finish or 0) for t in self.tasks)
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
    def ppc_proxy(self):
        # Backwards-compatible alias. In v2.4 this now means average weekly PPC
        # over completed weeks, not final cumulative completion.
        return self.avg_weekly_ppc

    def step(self):
        self.daily_questions=self.daily_escalations=self.daily_coordination_needs=self.daily_recovery_interventions=0; self.daily_external_pressure=0; self.daily_useful=0; self.daily_harmful=0
        self._update_blockages(); self.current_picture=self._picture(); self._update_readiness()
        for c in list(self.crews): c.step()
        self.daily_coordination_needs += self._baseline_coordination_needs()
        self.supervisor.process_day(self.daily_questions,self.daily_escalations,self.daily_coordination_needs,self.daily_recovery_interventions,self.daily_external_pressure)
        self._update_trust(); self.datacollector.collect(self); self.day+=1
        if self.day>=self.max_days or sum(t.is_done for t in self.tasks)==len(self.tasks): self.running=False
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
    def _update_readiness(self):
        s=self.dvm_scenario; r=self.py_random
        done={t.id for t in self.tasks if t.is_done}
        for t in self.tasks:
            if t.is_done or t.external_blockage_active: continue
            backlog_pressure = clamp(self.open_schedule_backlog / max(len(self.tasks), 1))
            supervisor_pressure = clamp(self.supervisor.backlog / max(self.supervisor.capacity_per_day, 0.01))
            prob=clamp(
                s.initial_plan_reliability
                + .12*s.integration_level
                + .20*self.current_picture.workface_quality
                + .18*self.current_picture.readiness_quality
                + .22*self.planning_quality
                - .18*backlog_pressure
                - .10*supervisor_pressure
                - .12*s.reporting_burden*(1-self.trust_in_management),
                .04,.98
            )
            if self.day<t.planned_start: prob*=.35
            if not t.material_ready and r.random()<prob: t.material_ready=True
            if not t.location_ready and r.random()<prob: t.location_ready=True
            if t.material_ready and t.location_ready and all(p in done for p in t.predecessor_ids) and t.status==TaskStatus.NOT_READY: t.status=TaskStatus.READY
    def step_crew(self,c):
        sa=self._sa(c); c.last_sa=sa.total; cur=self._task(c.current_task_id)
        if self.py_random.random()<self._question_prob(cur,sa): self.daily_questions+=1; c.questions_asked+=1
        if cur and cur.status==TaskStatus.IN_PROGRESS and not cur.external_blockage_active:
            shock=self._pop_shock(c.trade)
            if shock: self._external(cur,c,sa,shock); return
            if self.py_random.random()<self.dvm_scenario.disturbance_probability*(1-.4*self.planning_quality): cur.interruptions+=1; c.escalations+=1; self.daily_escalations+=1; c.idle_time+=1
            backlog_penalty=clamp_range(1.0-.018*self.open_schedule_backlog-.025*self.supervisor.backlog,.55,1.0)
            progress_factor=clamp_range(.72+.24*sa.comprehension+.20*self.planning_quality+.08*self.current_picture.readiness_quality-.10*self.dvm_scenario.reporting_burden,.45,1.35)
            cur.remaining_duration-=c.productivity*progress_factor*backlog_penalty; c.working_time+=1
            if cur.remaining_duration<=0: cur.status=TaskStatus.COMPLETED; cur.actual_finish=self.day; c.current_task_id=None
        else:
            task=self._choose_task(c)
            if task is None: c.idle_time+=1; return
            if c.location!=task.location: c.movements+=abs(c.location-task.location); c.location=task.location
            c.current_task_id=task.id; task.status=TaskStatus.IN_PROGRESS; task.actual_start=self.day if task.actual_start is None else task.actual_start
    def _sa(self,c):
        s=self.dvm_scenario; r=self.py_random; p=clamp(.1+.42*self.current_picture.workface_quality*c.effective_use()+.22*(.45*s.crew_access+.25*s.visual_clarity+.2*s.task_relevance+.1*c.dvm_skill)+.13*self.trust_in_data+.1*self.planning_quality+r.normalvariate(0,.04)); comp=clamp(.08+.36*p+.18*c.experience+.16*s.task_relevance+.12*self.trust_in_management+.14*self.planning_quality+r.normalvariate(0,.035)); proj=clamp(.05+.34*comp+.22*self.current_picture.recommendation_quality*c.effective_use()+.16*s.autonomy_level+.13*c.experience+.16*self.planning_quality+r.normalvariate(0,.035)); return AgentSA(p,comp,proj)
    def _question_prob(self,task,sa):
        comp=.65 if task is None else task.complexity; s=self.dvm_scenario
        backlog_pressure=clamp(self.open_schedule_backlog/max(len(self.tasks),1))
        supervisor_pressure=clamp(self.supervisor.backlog/max(self.supervisor.capacity_per_day,.01))
        uncertainty=(.55*(1-self.current_picture.workface_quality)+.25*(1-self.current_picture.readiness_quality)+.20*(1-self.planning_quality))
        return clamp(
            .04
            + .34*comp*(1-sa.total)*uncertainty
            + .07*s.decision_centralization*(1-s.autonomy_level)
            + .05*s.reporting_burden*(1-self.trust_in_management)
            + .08*backlog_pressure
            + .05*supervisor_pressure,
            0,.75
        )
    def _task(self,i): return next((t for t in self.tasks if t.id==i),None) if i is not None else None
    def _choose_task(self,c):
        cand=[t for t in self.tasks if t.trade==c.trade and t.status==TaskStatus.READY and not t.external_blockage_active and not t.is_done]
        return max(cand,key=lambda t:t.priority+.18*self.planning_quality+.04*max(0,self.day-self._planned_finish(t))-.05*abs(t.location-c.location)) if cand else None
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
