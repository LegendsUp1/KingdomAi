"""
Kingdom AI — Health Advisor
SOTA 2026: Proactive health intelligence powered by Ollama LLM.

Analyzes Creator's health trends, provides personalized advice,
and generates natural language health insights from wearable data.

Examples:
  "Your HRV has been declining for 3 days — consider extra rest."
  "Sleep score dropped 15 points — screen time before bed may be a factor."
  "Heart rate during meetings is consistently elevated — stress management suggested."

Uses Ollama/ThothAI for natural language generation when available,
falls back to template-based advice.
Dormant until protection flag "health_advisor" is activated.
"""
import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from base_component import BaseComponent

logger = logging.getLogger(__name__)

# Template-based advice (fallback when LLM unavailable)
ADVICE_TEMPLATES = {
    "low_sleep_score": {
        "title": "Sleep Quality Declining",
        "advice": "Your sleep score has been below {threshold} for {days} days. "
                  "Consider: reducing screen time 1hr before bed, keeping a consistent "
                  "sleep schedule, and avoiding caffeine after 2pm.",
        "priority": "medium",
    },
    "high_stress": {
        "title": "Elevated Stress Detected",
        "advice": "Your stress level has been consistently high (avg {avg_stress}). "
                  "Try: 5-minute breathing exercises, a short walk, or progressive muscle relaxation.",
        "priority": "medium",
    },
    "low_hrv": {
        "title": "HRV Below Baseline",
        "advice": "Your heart rate variability is {pct_below}% below your baseline. "
                  "This may indicate: overtraining, poor recovery, or accumulated stress. "
                  "Consider a recovery day.",
        "priority": "medium",
    },
    "low_spo2": {
        "title": "Blood Oxygen Trending Down",
        "advice": "Your SpO2 has averaged {avg_spo2}% recently. If this persists, "
                  "consider consulting a healthcare provider. Ensure good ventilation in your space.",
        "priority": "high",
    },
    "dehydration_risk": {
        "title": "Possible Dehydration",
        "advice": "Your resting heart rate is elevated while HRV is depressed — "
                  "a common pattern for dehydration. Increase water intake.",
        "priority": "low",
    },
    "exercise_needed": {
        "title": "Activity Reminder",
        "advice": "You've been sedentary for {hours} hours. A 10-minute walk can "
                  "improve focus, mood, and cardiovascular health.",
        "priority": "low",
    },
    "recovery_good": {
        "title": "Great Recovery!",
        "advice": "Your readiness score is {score} and HRV is above baseline. "
                  "You're well-recovered — good day for intense activity if desired.",
        "priority": "low",
    },
}


class HealthInsight:
    """A single health insight/advice item."""

    def __init__(self, insight_type: str, title: str, advice: str,
                 priority: str = "low", data: Optional[Dict] = None):
        self.insight_type = insight_type
        self.title = title
        self.advice = advice
        self.priority = priority
        self.data = data or {}
        self.created_at = datetime.utcnow().isoformat()
        self.acknowledged = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_type": self.insight_type,
            "title": self.title,
            "advice": self.advice,
            "priority": self.priority,
            "data": self.data,
            "created_at": self.created_at,
            "acknowledged": self.acknowledged,
        }


class HealthAdvisor(BaseComponent):
    """
    Proactive health intelligence for Creator wellness.

    Periodically analyzes health trends from WearableHub and
    HealthAnomalyDetector baseline data, generates insights,
    and publishes them for the health dashboard and voice system.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        self._insights: deque = deque(maxlen=100)
        self._lock = threading.Lock()

        # Cooldowns to prevent insight spam
        self._last_insight_time: Dict[str, float] = {}
        self._insight_cooldown = 3600  # 1 hour between same insight types

        # Analysis thread
        self._analysis_thread: Optional[threading.Thread] = None
        self._running = False
        self._analysis_interval = int(self.config.get("analysis_interval_seconds", 900))  # 15 min

        self._subscribe_events()
        self._initialized = True
        logger.info("HealthAdvisor initialized (dormant until activated)")

    # ------------------------------------------------------------------
    # Insight generation
    # ------------------------------------------------------------------

    def analyze_trends(self, vitals_history: List[Dict], baseline: Dict[str, Dict]) -> List[HealthInsight]:
        """
        Analyze recent vitals history against baseline and generate insights.
        """
        if not self._is_active():
            return []

        if not vitals_history or len(vitals_history) < 5:
            return []

        insights: List[HealthInsight] = []

        # Extract recent values
        recent_hr = [v.get("heart_rate") for v in vitals_history[-30:] if v.get("heart_rate")]
        recent_hrv = [v.get("hrv_rmssd") for v in vitals_history[-30:] if v.get("hrv_rmssd")]
        recent_spo2 = [v.get("spo2") for v in vitals_history[-30:] if v.get("spo2")]
        recent_stress = [v.get("stress_level") for v in vitals_history[-30:] if v.get("stress_level")]
        recent_sleep = [v.get("sleep_score") for v in vitals_history[-10:] if v.get("sleep_score")]
        recent_steps = [v.get("steps_today") for v in vitals_history[-5:] if v.get("steps_today")]
        recent_readiness = [v.get("readiness_score") for v in vitals_history[-5:] if v.get("readiness_score")]

        # Sleep quality check
        if recent_sleep:
            avg_sleep = sum(recent_sleep) / len(recent_sleep)
            if avg_sleep < 70:
                insight = self._create_template_insight(
                    "low_sleep_score",
                    threshold=70,
                    days=len(recent_sleep),
                )
                if insight:
                    insights.append(insight)

        # Stress check
        if recent_stress:
            avg_stress = sum(recent_stress) / len(recent_stress)
            if avg_stress > 60:
                insight = self._create_template_insight(
                    "high_stress",
                    avg_stress=round(avg_stress),
                )
                if insight:
                    insights.append(insight)

        # HRV trend check
        if recent_hrv and "hrv_rmssd" in baseline:
            avg_hrv = sum(recent_hrv) / len(recent_hrv)
            baseline_hrv = baseline["hrv_rmssd"].get("mean", 0)
            if baseline_hrv > 0:
                pct_below = ((baseline_hrv - avg_hrv) / baseline_hrv) * 100
                if pct_below > 20:
                    insight = self._create_template_insight(
                        "low_hrv",
                        pct_below=round(pct_below),
                    )
                    if insight:
                        insights.append(insight)

        # SpO2 trend check
        if recent_spo2:
            avg_spo2 = sum(recent_spo2) / len(recent_spo2)
            if avg_spo2 < 94:
                insight = self._create_template_insight(
                    "low_spo2",
                    avg_spo2=round(avg_spo2),
                )
                if insight:
                    insights.append(insight)

        # Dehydration pattern
        if recent_hr and recent_hrv and "heart_rate" in baseline:
            avg_hr = sum(recent_hr) / len(recent_hr)
            avg_hrv_val = sum(recent_hrv) / len(recent_hrv)
            baseline_hr = baseline["heart_rate"].get("mean", 0)
            baseline_hrv_val = baseline.get("hrv_rmssd", {}).get("mean", 0)
            if baseline_hr > 0 and baseline_hrv_val > 0:
                hr_elevated = avg_hr > baseline_hr * 1.1
                hrv_depressed = avg_hrv_val < baseline_hrv_val * 0.8
                if hr_elevated and hrv_depressed:
                    insight = self._create_template_insight("dehydration_risk")
                    if insight:
                        insights.append(insight)

        # Good recovery check
        if recent_readiness:
            avg_readiness = sum(recent_readiness) / len(recent_readiness)
            if avg_readiness > 80:
                insight = self._create_template_insight(
                    "recovery_good",
                    score=round(avg_readiness),
                )
                if insight:
                    insights.append(insight)

        # Record and publish
        for insight in insights:
            self._record_insight(insight)
            self._publish_insight(insight)

        return insights

    def _create_template_insight(self, insight_type: str, **kwargs) -> Optional[HealthInsight]:
        """Create insight from template with cooldown check."""
        # Cooldown check
        now = time.time()
        last_time = self._last_insight_time.get(insight_type, 0)
        if now - last_time < self._insight_cooldown:
            return None

        template = ADVICE_TEMPLATES.get(insight_type)
        if not template:
            return None

        try:
            advice = template["advice"].format(**kwargs)
        except (KeyError, ValueError):
            advice = template["advice"]

        self._last_insight_time[insight_type] = now

        return HealthInsight(
            insight_type=insight_type,
            title=template["title"],
            advice=advice,
            priority=template.get("priority", "low"),
            data=kwargs,
        )

    # ------------------------------------------------------------------
    # LLM-powered advice (optional enhancement)
    # ------------------------------------------------------------------

    def generate_llm_insight(self, vitals_summary: str) -> Optional[str]:
        """
        Use Ollama/ThothAI to generate personalized health advice.
        Falls back to None if LLM unavailable.
        """
        if not self.event_bus:
            return None

        try:
            # Request LLM analysis via event bus
            self.event_bus.publish("ai.request", {
                "text": f"As a health advisor, analyze these vitals and provide brief, "
                        f"actionable advice (2-3 sentences max): {vitals_summary}",
                "source": "health_advisor",
                "priority": "low",
            })
            return None  # Response comes async via event bus
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Insight management
    # ------------------------------------------------------------------

    def _record_insight(self, insight: HealthInsight) -> None:
        with self._lock:
            self._insights.append(insight.to_dict())

    def _publish_insight(self, insight: HealthInsight) -> None:
        if not self.event_bus:
            return
        self.event_bus.publish("health.insight.new", insight.to_dict())

        # For high priority, also speak it
        if insight.priority in ("high", "critical"):
            self.event_bus.publish("voice.speak", {
                "text": f"Health alert: {insight.title}. {insight.advice}",
                "priority": "normal",
                "source": "health_advisor",
            })

    def get_recent_insights(self, count: int = 10) -> List[Dict]:
        with self._lock:
            return list(self._insights)[-count:]

    # ------------------------------------------------------------------
    # Background analysis
    # ------------------------------------------------------------------

    def start_analysis(self) -> None:
        if self._running:
            return
        self._running = True
        self._analysis_thread = threading.Thread(
            target=self._analysis_loop, daemon=True, name="HealthAdvisor",
        )
        self._analysis_thread.start()
        logger.info("Health advisor analysis started (interval=%ds)", self._analysis_interval)

    def stop_analysis(self) -> None:
        self._running = False
        if self._analysis_thread and self._analysis_thread.is_alive():
            self._analysis_thread.join(timeout=5)

    def _analysis_loop(self) -> None:
        while self._running:
            try:
                if self._is_active():
                    self._run_periodic_analysis()
            except Exception as e:
                logger.error("Health analysis error: %s", e)

            for _ in range(self._analysis_interval):
                if not self._running:
                    return
                time.sleep(1)

    def _run_periodic_analysis(self) -> None:
        """Fetch latest data and run analysis."""
        if not self.event_bus:
            return

        # Request vitals history from WearableHub
        self.event_bus.publish("health.vitals.query", {})
        # Request baseline from HealthAnomalyDetector
        self.event_bus.publish("health.baseline.query", {})

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("health_advisor")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("health.advisor.analyze", self._handle_analyze)
        self.event_bus.subscribe("health.insights.query", self._handle_query)
        self.event_bus.subscribe("protection.flag.changed", self._handle_flag_change)

    def _handle_analyze(self, data: Any) -> None:
        if isinstance(data, dict):
            history = data.get("vitals_history", [])
            baseline = data.get("baseline", {})
            self.analyze_trends(history, baseline)

    def _handle_query(self, data: Any) -> None:
        count = 10
        if isinstance(data, dict):
            count = data.get("count", 10)
        if self.event_bus:
            self.event_bus.publish("health.insights.list", self.get_recent_insights(count))

    def _handle_flag_change(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        if data.get("module") in ("health_advisor", "__all__"):
            if data.get("active"):
                self.start_analysis()
            else:
                self.stop_analysis()

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self.stop_analysis()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "insights_count": len(self._insights),
            "running": self._running,
            "recent_insights": self.get_recent_insights(5),
        }
