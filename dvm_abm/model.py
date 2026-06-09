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
        try: super().__init__(rng=seed)
        except TypeError: super().__init__(seed=seed)
        self.scenario=scenario or get_default_scenarios()[0]; self.seed=seed; self.max_days=max_days; self.day=0; self.running=True; self.py_random=random.Random(seed)
        self.trust_in_data=self.scenario.initial_trust_in_data; self.trust_in_management=self.scenario.initial_trust_in_management; self.planning_quality=self.scenario.initial_planning_quality; self.data_quality_modifier=1.0
        self.useful_dvm_events=0; self.harmful_events=0; self.external_disruptions=0; self.external_disruptions_by_type={}; self.recovery_times=[]; self.blockage_resolution_times=[]
        self.total_recovery_time=0.0; self.alternative_task_switches=0; self.failed_task_switches=0; self.supervisor_recovery_interventions=0; self.idle_time_due_to_external_disruptions=0.0
        self.daily_questions=0; self.daily_escalations=0; self.daily_coordination_needs=0; self.daily_recovery_interventions=0; self.daily_external_pressure=0; self.daily_useful=0; self.daily_harmful=0
        self.current_picture=SituationPicture(0,0,0,0,0,0,0); self.trades=["drywall","mep","finishes","carpentry"]
        self.shock_schedule=generate_external_shock_schedule(seed,self.trades,max_days+40,daily_shock_probability)
        self.tasks=[]; self.crews=[]; self._create_project(number_of_tasks)
        self.datacollector=DataCollector(model_reporters=self._reporters()); self.datacollector.collect(self)
    def _create_project(self,n):
        r=self.py_random
        for i in range(n):
            pred=[r.randrange(max(1,i-10),i)] if i>6 and r.random()<.6 else []
            t=TaskAgent(self,i,r.choice(self.trades),r.randrange(12),r.randrange(42),r.randint(1,5),r.uniform(.2,1),r.uniform(.35,1),pred); self.tasks.append(t)
        for i,tr in enumerate(["drywall","mep","finishes","carpentry","drywall","mep"]):
            ad=clamp(.35+.48*self.scenario.crew_access-.18*self.scenario.reporting_burden+r.normalvariate(0,.08)); comp=clamp(self.scenario.compliance_pressure*(.45+.45*self.scenario.management_access))
            self.crews.append(CrewAgent(self,1000+i,tr,[0,2,4,6,8,10][i],clamp(r.normalvariate(.6,.15)),clamp(r.normalvariate(.5+.25*self.scenario.crew_access,.15)),clamp_range(r.normalvariate(1,.1),.75,1.25),ad,comp))
        self.supervisor=SupervisorAgent(self,9000,self.scenario.supervisor_capacity,self.scenario.question_handling_time,self.scenario.escalation_handling_time,self.scenario.reporting_time_base,self.scenario.coordination_task_time)
    def _reporters(self):
        return {"scenario":lambda m:m.scenario.name,"day":"day","completed_tasks":lambda m:sum(t.is_done for t in m.tasks),"total_tasks":lambda m:len(m.tasks),"ppc_proxy":lambda m:m.ppc_proxy,"avg_sa":lambda m:safe_mean([c.last_sa for c in m.crews]),"planning_quality":"planning_quality","trust_in_data":"trust_in_data","trust_in_management":"trust_in_management","avg_adoption":lambda m:safe_mean([c.adoption for c in m.crews]),"avg_effective_use":lambda m:safe_mean([c.effective_use() for c in m.crews]),"workface_picture_quality":lambda m:m.current_picture.workface_quality,"management_picture_quality":lambda m:m.current_picture.management_quality,"workface_gap":lambda m:m.current_picture.workface_gap,"total_idle_time":lambda m:sum(c.idle_time for c in m.crews),"total_idle_time_external":lambda m:sum(c.idle_time_external for c in m.crews),"total_working_time":lambda m:sum(c.working_time for c in m.crews),"total_interruptions":lambda m:sum(t.interruptions for t in m.tasks),"alternative_task_switches":"alternative_task_switches","failed_task_switches":"failed_task_switches","supervisor_recovery_interventions":"supervisor_recovery_interventions","external_disruptions":"external_disruptions","avg_recovery_time":lambda m:safe_mean(m.recovery_times),"idle_time_due_to_external_disruptions":"idle_time_due_to_external_disruptions","supervisor_reactive_time":lambda m:m.supervisor.last_reactive_time,"supervisor_planning_time":lambda m:m.supervisor.last_planning_time,"firefighting_ratio":lambda m:m.supervisor.last_firefighting_ratio,"supervisor_backlog":lambda m:m.supervisor.backlog,"active_external_blockages":lambda m:sum(t.external_blockage_active for t in m.tasks)}
    @property
    def ppc_proxy(self):
        due=[t for t in self.tasks if t.planned_start+t.planned_duration<=self.day]; return sum(t.is_done for t in due)/len(due) if due else 0
    def step(self):
        self.daily_questions=self.daily_escalations=self.daily_coordination_needs=self.daily_recovery_interventions=0; self.daily_external_pressure=0; self.daily_useful=0; self.daily_harmful=0
        self._update_blockages(); self.current_picture=self._picture(); self._update_readiness()
        for c in list(self.crews): c.step()
        self.supervisor.process_day(self.daily_questions,self.daily_escalations,self.daily_coordination_needs,self.daily_recovery_interventions,self.daily_external_pressure)
        self._update_trust(); self.datacollector.collect(self); self.day+=1
        if self.day>=self.max_days or sum(t.is_done for t in self.tasks)==len(self.tasks): self.running=False
    def _picture(self):
        s=self.scenario; r=self.py_random; base=.22*r.triangular(0,1,s.capture_rate)+.22*r.triangular(0,1,s.data_accuracy)+.2*r.triangular(0,1,s.data_timeliness)+.18*s.data_completeness+.18*s.integration_level
        adj=clamp(base*self.data_quality_modifier+.05*self.planning_quality-.1*s.reporting_burden); wf=clamp(adj*(.45*s.crew_access+.25*s.visual_clarity+.30*s.task_relevance)); mg=clamp(adj*(.60*s.management_access+.2*s.visual_clarity+.2*s.integration_level))
        return SituationPicture(wf,mg,wf*s.task_recommendation_quality,wf*s.readiness_visibility,wf*s.material_visibility,wf*s.congestion_visibility,wf*s.priority_visibility)
    def _update_blockages(self):
        for t in self.tasks:
            if t.external_blockage_active:
                t.external_blockage_remaining-=1
                if t.external_blockage_remaining<=0: t.external_blockage_active=False; t.status=TaskStatus.READY; self.blockage_resolution_times.append(self.day-(t.external_blockage_started or self.day))
    def _update_readiness(self):
        s=self.scenario; r=self.py_random
        done={t.id for t in self.tasks if t.is_done}
        for t in self.tasks:
            if t.is_done or t.external_blockage_active: continue
            prob=clamp(s.initial_plan_reliability+.09*s.integration_level+.08*self.current_picture.workface_quality+.2*self.planning_quality-.12*s.reporting_burden*(1-self.trust_in_management),.04,.98)
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
            if self.py_random.random()<self.scenario.disturbance_probability*(1-.4*self.planning_quality): cur.interruptions+=1; c.escalations+=1; self.daily_escalations+=1; c.idle_time+=1
            cur.remaining_duration-=c.productivity*clamp_range(.78+.22*sa.comprehension+.18*self.planning_quality-.08*self.scenario.reporting_burden,.55,1.3); c.working_time+=1
            if cur.remaining_duration<=0: cur.status=TaskStatus.COMPLETED; cur.actual_finish=self.day; c.current_task_id=None
        else:
            task=self._choose_task(c)
            if task is None: c.idle_time+=1; return
            if c.location!=task.location: c.movements+=abs(c.location-task.location); c.location=task.location
            c.current_task_id=task.id; task.status=TaskStatus.IN_PROGRESS; task.actual_start=self.day if task.actual_start is None else task.actual_start
    def _sa(self,c):
        s=self.scenario; r=self.py_random; p=clamp(.1+.42*self.current_picture.workface_quality*c.effective_use()+.22*(.45*s.crew_access+.25*s.visual_clarity+.2*s.task_relevance+.1*c.dvm_skill)+.13*self.trust_in_data+.1*self.planning_quality+r.normalvariate(0,.04)); comp=clamp(.08+.36*p+.18*c.experience+.16*s.task_relevance+.12*self.trust_in_management+.14*self.planning_quality+r.normalvariate(0,.035)); proj=clamp(.05+.34*comp+.22*self.current_picture.recommendation_quality*c.effective_use()+.16*s.autonomy_level+.13*c.experience+.16*self.planning_quality+r.normalvariate(0,.035)); return AgentSA(p,comp,proj)
    def _question_prob(self,task,sa):
        comp=.65 if task is None else task.complexity; s=self.scenario; return clamp(.22*comp*(1-sa.total)*(1-self.current_picture.workface_quality)*(1-self.planning_quality)+.04*s.reporting_burden*(1-self.trust_in_management),0,.65)
    def _task(self,i): return next((t for t in self.tasks if t.id==i),None) if i is not None else None
    def _choose_task(self,c):
        cand=[t for t in self.tasks if t.trade==c.trade and t.status==TaskStatus.READY and not t.external_blockage_active and not t.is_done]
        return max(cand,key=lambda t:t.priority+.2*self.planning_quality-.05*abs(t.location-c.location)) if cand else None
    def _pop_shock(self,trade):
        for sh in self.shock_schedule.get(self.day,[]):
            if not sh.consumed and sh.trade==trade: sh.consumed=True; return sh
        return None
    def _external(self,t,c,sa,shock):
        t.external_blockage_active=True; t.external_blockage_type=shock.disruption_type; t.external_blockage_started=self.day; t.external_blockage_remaining=shock.base_duration; t.status=TaskStatus.BLOCKED_EXTERNAL; t.interruptions+=1; self.external_disruptions+=1; self.external_disruptions_by_type[shock.disruption_type]=self.external_disruptions_by_type.get(shock.disruption_type,0)+1
        p_alt=clamp(.08+.30*sa.total+.24*self.current_picture.workface_quality+.22*self.planning_quality+.18*self.current_picture.recommendation_quality+.12*self.scenario.autonomy_level-.10*self.scenario.decision_centralization)
        if self.py_random.random()<p_alt:
            rec=self.py_random.uniform(.15,.8)*(1+.35*(1-sa.total)+.25*(1-self.planning_quality)); self.alternative_task_switches+=1; c.alternative_task_switches+=1; self.daily_useful+=1
        else:
            rec=self.supervisor.last_response_delay+shock.base_duration*(1+.65*(1-self.planning_quality)+.45*(1-self.current_picture.workface_quality)+.25*self.scenario.reporting_burden)+self.py_random.uniform(.25,1.25); self.failed_task_switches+=1; c.failed_task_switches+=1; self.supervisor_recovery_interventions+=1; self.daily_questions+=1; self.daily_escalations+=1; self.daily_recovery_interventions+=1; self.daily_coordination_needs+=1; self.daily_harmful+=1
        self.recovery_times.append(rec); self.total_recovery_time+=rec; c.idle_time+=rec; c.idle_time_external+=rec; self.idle_time_due_to_external_disruptions+=rec; c.current_task_id=None; self.daily_external_pressure+=1+.25*rec
    def _update_trust(self):
        s=self.scenario; gain=s.trust_sensitivity*self.daily_useful*(1-.6*s.reporting_burden); loss=s.trust_sensitivity*self.daily_harmful*(.35*s.reporting_burden+.45*s.perceived_surveillance+.2*(1-self.planning_quality))
        self.trust_in_data=clamp(self.trust_in_data+.45*gain-.45*loss); self.trust_in_management=clamp(self.trust_in_management+.35*gain-.55*loss-.004*s.compliance_pressure*s.perceived_surveillance)
    def get_model_dataframe(self): return self.datacollector.get_model_vars_dataframe().reset_index(drop=True)
