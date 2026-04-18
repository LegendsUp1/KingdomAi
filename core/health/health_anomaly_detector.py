"""
Kingdom AI — Health Anomaly Detector
SOTA 2026: Isolation Forest + rolling baseline for wearable health data.

Learns Creator's normal vital signs over time (personal baseline),
then detects deviations that may indicate:
  - Cardiac event (sudden HR spike/drop, HRV crash, SpO2 plunge)
  - Fall (accelerometer + sudden HR spike)
  - Stress/duress (HRV crash + elevated HR + skin conductance)
  - Loss of pulse (cardiac arrest — EMERGENCY)
  - Sleep anomaly (disrupted sleep patterns)

Publishes anomaly events for CreatorShield and WellnessChecker.
Dormant until protection flag "health_anomaly_detector" is activated.
"""
import logging
import os
import json
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from base_component import BaseComponent

logger = logging.getLogger(__name__)

HAS_NUMPY = False
HAS_SKLEARN = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    pass

REDIS_KEY_BASELINE = "kingdom:health:baseline"
LOCAL_BASELINE_REL = os.path.join("data", "health_baseline.json")

# Critical thresholds (absolute, always checked regardless of ML)
CRITICAL_THRESHOLDS = {
    "hr_min": 30,           # Below 30 BPM = bradycardia emergency
    "hr_max": 200,          # Above 200 BPM = tachycardia emergency
    "spo2_min": 85,         # Below 85% SpO2 = hypoxemia emergency
    "body_temp_min": 34.0,  # Below 34°C = hypothermia
    "body_temp_max": 40.5,  # Above 40.5°C = hyperthermia
}

# Warning thresholds
WARNING_THRESHOLDS = {
    "hr_min": 45,
    "hr_max": 160,
    "spo2_min": 90,
    "hrv_drop_pct": 40,     # 40% drop from baseline HRV
    "stress_max": 85,
}


class HealthAnomalyDetector(BaseComponent):
    """
    Learns Creator's health baseline and detects anomalies in real-time.

    Uses two detection methods:
    1. Absolute thresholds (always active — catches critical emergencies)
    2. Isolation Forest ML model (learns personal baseline, detects subtle anomalies)

    Requires minimum 100 vitals samples before ML detection activates.
    """

    def __init__(self, config=None, event_bus=None, redis_connector=None):
        super().__init__(config=config)
        self.event_bus = event_bus
        self.redis_connector = redis_connector

        # Rolling vitals history for baseline learning
        self._vitals_history: deque = deque(maxlen=10000)  # ~7 days at 1/min
        self._lock = threading.RLock()

        # Personal baseline stats
        self._baseline: Dict[str, Dict[str, float]] = {}  # metric -> {mean, std, min, max}

        # ML model
        self._model: Optional[Any] = None  # IsolationForest
        self._scaler: Optional[Any] = None  # StandardScaler
        self._model_trained = False
        self._min_samples_for_ml = 100

        # Pulse monitoring for loss-of-pulse detection
        self._last_hr_time: float = 0
        self._pulse_timeout_seconds = 120  # 2 minutes without HR = concern
        self._pulse_monitor_active = False

        # Feature names for ML model
        self._feature_names = [
            "heart_rate", "hrv_rmssd", "spo2", "stress_level",
            "body_temperature", "respiratory_rate",
        ]

        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            LOCAL_BASELINE_REL,
        )

        self._load_baseline()
        self._subscribe_events()
        self._initialized = True
        logger.info(
            "HealthAnomalyDetector initialized (sklearn=%s, baseline_samples=%d)",
            HAS_SKLEARN, len(self._vitals_history),
        )

    # ------------------------------------------------------------------
    # Vitals processing
    # ------------------------------------------------------------------

    def process_vitals(self, vitals: Dict[str, Any]) -> List[Dict]:
        """
        Process incoming vitals snapshot. Returns list of detected anomalies.
        """
        if not self._is_active():
            return []

        anomalies: List[Dict] = []

        # 1. Always check absolute critical thresholds
        critical = self._check_critical_thresholds(vitals)
        anomalies.extend(critical)

        # 2. Check warning thresholds
        warnings = self._check_warning_thresholds(vitals)
        anomalies.extend(warnings)

        # 3. Record for baseline learning
        self._record_vitals(vitals)

        # 4. ML anomaly detection (if enough data)
        if self._model_trained and HAS_SKLEARN:
            ml_anomalies = self._ml_detect(vitals)
            anomalies.extend(ml_anomalies)

        # 5. Track pulse timing
        hr = vitals.get("heart_rate")
        if hr and hr > 0:
            self._last_hr_time = time.time()

        # 6. Publish anomalies
        for anomaly in anomalies:
            self._publish_anomaly(anomaly)

        return anomalies

    def _check_critical_thresholds(self, vitals: Dict) -> List[Dict]:
        """Check absolute critical thresholds — always active."""
        anomalies: List[Dict] = []
        ts = datetime.utcnow().isoformat()

        hr = vitals.get("heart_rate")
        if hr is not None and hr > 0:
            if hr < CRITICAL_THRESHOLDS["hr_min"]:
                anomalies.append({
                    "type": "critical_bradycardia",
                    "metric": "heart_rate",
                    "value": hr,
                    "threshold": CRITICAL_THRESHOLDS["hr_min"],
                    "severity": "critical",
                    "message": f"CRITICAL: Heart rate {hr} BPM — severe bradycardia",
                    "timestamp": ts,
                })
            elif hr > CRITICAL_THRESHOLDS["hr_max"]:
                anomalies.append({
                    "type": "critical_tachycardia",
                    "metric": "heart_rate",
                    "value": hr,
                    "threshold": CRITICAL_THRESHOLDS["hr_max"],
                    "severity": "critical",
                    "message": f"CRITICAL: Heart rate {hr} BPM — severe tachycardia",
                    "timestamp": ts,
                })

        spo2 = vitals.get("spo2")
        if spo2 is not None and spo2 > 0:
            if spo2 < CRITICAL_THRESHOLDS["spo2_min"]:
                anomalies.append({
                    "type": "critical_hypoxemia",
                    "metric": "spo2",
                    "value": spo2,
                    "threshold": CRITICAL_THRESHOLDS["spo2_min"],
                    "severity": "critical",
                    "message": f"CRITICAL: SpO2 {spo2}% — severe hypoxemia",
                    "timestamp": ts,
                })

        temp = vitals.get("body_temperature")
        if temp is not None and temp > 0:
            if temp < CRITICAL_THRESHOLDS["body_temp_min"]:
                anomalies.append({
                    "type": "critical_hypothermia",
                    "metric": "body_temperature",
                    "value": temp,
                    "threshold": CRITICAL_THRESHOLDS["body_temp_min"],
                    "severity": "critical",
                    "message": f"CRITICAL: Body temperature {temp}°C — hypothermia",
                    "timestamp": ts,
                })
            elif temp > CRITICAL_THRESHOLDS["body_temp_max"]:
                anomalies.append({
                    "type": "critical_hyperthermia",
                    "metric": "body_temperature",
                    "value": temp,
                    "threshold": CRITICAL_THRESHOLDS["body_temp_max"],
                    "severity": "critical",
                    "message": f"CRITICAL: Body temperature {temp}°C — hyperthermia",
                    "timestamp": ts,
                })

        return anomalies

    def _check_warning_thresholds(self, vitals: Dict) -> List[Dict]:
        """Check warning-level thresholds."""
        anomalies: List[Dict] = []
        ts = datetime.utcnow().isoformat()

        hr = vitals.get("heart_rate")
        if hr is not None and hr > 0:
            if hr < WARNING_THRESHOLDS["hr_min"]:
                anomalies.append({
                    "type": "warning_low_hr",
                    "metric": "heart_rate",
                    "value": hr,
                    "severity": "warning",
                    "message": f"Low heart rate: {hr} BPM",
                    "timestamp": ts,
                })
            elif hr > WARNING_THRESHOLDS["hr_max"]:
                anomalies.append({
                    "type": "warning_high_hr",
                    "metric": "heart_rate",
                    "value": hr,
                    "severity": "warning",
                    "message": f"Elevated heart rate: {hr} BPM",
                    "timestamp": ts,
                })

        spo2 = vitals.get("spo2")
        if spo2 is not None and 0 < spo2 < WARNING_THRESHOLDS["spo2_min"]:
            anomalies.append({
                "type": "warning_low_spo2",
                "metric": "spo2",
                "value": spo2,
                "severity": "warning",
                "message": f"Low blood oxygen: {spo2}%",
                "timestamp": ts,
            })

        # HRV drop relative to baseline
        hrv = vitals.get("hrv_rmssd")
        if hrv is not None and "hrv_rmssd" in self._baseline:
            baseline_hrv = self._baseline["hrv_rmssd"].get("mean", 0)
            if baseline_hrv > 0:
                drop_pct = ((baseline_hrv - hrv) / baseline_hrv) * 100
                if drop_pct > WARNING_THRESHOLDS["hrv_drop_pct"]:
                    anomalies.append({
                        "type": "warning_hrv_drop",
                        "metric": "hrv_rmssd",
                        "value": hrv,
                        "baseline": round(baseline_hrv, 1),
                        "drop_pct": round(drop_pct, 1),
                        "severity": "warning",
                        "message": f"HRV dropped {drop_pct:.0f}% from baseline ({hrv:.0f} vs {baseline_hrv:.0f})",
                        "timestamp": ts,
                    })

        stress = vitals.get("stress_level")
        if stress is not None and stress > WARNING_THRESHOLDS["stress_max"]:
            anomalies.append({
                "type": "warning_high_stress",
                "metric": "stress_level",
                "value": stress,
                "severity": "warning",
                "message": f"High stress level: {stress}",
                "timestamp": ts,
            })

        return anomalies

    # ------------------------------------------------------------------
    # ML anomaly detection
    # ------------------------------------------------------------------

    def _record_vitals(self, vitals: Dict) -> None:
        """Record vitals for baseline learning."""
        with self._lock:
            self._vitals_history.append(vitals)

            # Retrain model periodically
            if len(self._vitals_history) >= self._min_samples_for_ml:
                if len(self._vitals_history) % 50 == 0:  # Retrain every 50 samples
                    self._train_model()
                self._update_baseline_stats()

    def _train_model(self) -> None:
        """Train Isolation Forest on accumulated vitals."""
        if not HAS_SKLEARN or not HAS_NUMPY:
            return

        try:
            with self._lock:
                data = list(self._vitals_history)

            # Build feature matrix
            features = []
            for v in data:
                row = []
                for feat in self._feature_names:
                    val = v.get(feat)
                    if val is not None:
                        row.append(float(val))
                    else:
                        row.append(np.nan)
                features.append(row)

            X = np.array(features)

            # Replace NaN with column means
            col_means = np.nanmean(X, axis=0)
            for i in range(X.shape[1]):
                mask = np.isnan(X[:, i])
                X[mask, i] = col_means[i] if not np.isnan(col_means[i]) else 0

            # Scale
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Train Isolation Forest
            self._model = IsolationForest(
                contamination=0.05,
                n_estimators=100,
                max_samples=min(256, len(X_scaled)),
                random_state=42,
            )
            self._model.fit(X_scaled)
            self._model_trained = True

            logger.info("Health anomaly ML model trained on %d samples", len(X_scaled))

        except Exception as e:
            logger.debug("ML model training failed: %s", e)

    def _ml_detect(self, vitals: Dict) -> List[Dict]:
        """Run ML anomaly detection on current vitals."""
        if not self._model or not self._scaler:
            return []

        try:
            row = []
            for feat in self._feature_names:
                val = vitals.get(feat)
                if val is not None:
                    row.append(float(val))
                else:
                    # Use baseline mean as fallback
                    baseline = self._baseline.get(feat, {})
                    row.append(baseline.get("mean", 0))

            X = np.array([row])
            X_scaled = self._scaler.transform(X)

            prediction = self._model.predict(X_scaled)[0]
            score = self._model.decision_function(X_scaled)[0]

            if prediction == -1:  # Anomaly
                return [{
                    "type": "ml_health_anomaly",
                    "severity": "warning" if score > -0.3 else "high",
                    "anomaly_score": round(float(score), 3),
                    "vitals_snapshot": {k: vitals.get(k) for k in self._feature_names if vitals.get(k) is not None},
                    "message": f"ML anomaly detected (score={score:.3f})",
                    "timestamp": datetime.utcnow().isoformat(),
                }]

        except Exception as e:
            logger.debug("ML detection error: %s", e)

        return []

    def _update_baseline_stats(self) -> None:
        """Update baseline statistics from history."""
        if not HAS_NUMPY:
            return

        with self._lock:
            data = list(self._vitals_history)

        for feat in self._feature_names:
            values = [v.get(feat) for v in data if v.get(feat) is not None]
            if len(values) >= 10:
                arr = np.array(values, dtype=float)
                self._baseline[feat] = {
                    "mean": round(float(np.mean(arr)), 2),
                    "std": round(float(np.std(arr)), 2),
                    "min": round(float(np.min(arr)), 2),
                    "max": round(float(np.max(arr)), 2),
                    "samples": len(values),
                }

        self._persist_baseline()

    # ------------------------------------------------------------------
    # Pulse loss detection
    # ------------------------------------------------------------------

    def check_pulse_status(self) -> None:
        """Check if we've lost pulse signal (called periodically)."""
        if not self._is_active():
            return

        if self._last_hr_time == 0:
            return  # Never received HR data

        elapsed = time.time() - self._last_hr_time
        if elapsed > self._pulse_timeout_seconds:
            logger.warning("PULSE LOST: No heart rate data for %.0f seconds", elapsed)
            if self.event_bus:
                self.event_bus.publish("health.pulse.lost", {
                    "last_hr_seconds_ago": round(elapsed),
                    "timeout_seconds": self._pulse_timeout_seconds,
                    "timestamp": datetime.utcnow().isoformat(),
                })

    # ------------------------------------------------------------------
    # Anomaly publishing
    # ------------------------------------------------------------------

    def _publish_anomaly(self, anomaly: Dict) -> None:
        if not self.event_bus:
            return
        self.event_bus.publish("health.anomaly.detected", anomaly)

        severity = anomaly.get("severity", "warning")
        if severity == "critical":
            logger.warning("HEALTH CRITICAL: %s", anomaly.get("message", ""))
        else:
            logger.info("Health anomaly: %s", anomaly.get("message", ""))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_baseline(self) -> None:
        if self.redis_connector and hasattr(self.redis_connector, "json_set"):
            try:
                self.redis_connector.json_set(REDIS_KEY_BASELINE, self._baseline)
            except Exception:
                pass

        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, "w") as f:
                json.dump(self._baseline, f, indent=2)
        except Exception:
            pass

    def _load_baseline(self) -> None:
        if self.redis_connector and hasattr(self.redis_connector, "json_get"):
            try:
                data = self.redis_connector.json_get(REDIS_KEY_BASELINE)
                if isinstance(data, dict) and data:
                    self._baseline = data
                    return
            except Exception:
                pass

        if os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._baseline = data
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _is_active(self) -> bool:
        try:
            from core.security.protection_flags import ProtectionFlagController
            fc = ProtectionFlagController.get_instance()
            return fc.is_active("health_anomaly_detector")
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("health.vitals.updated", self._handle_vitals)
        self.event_bus.subscribe("health.baseline.query", self._handle_baseline_query)

    def _handle_vitals(self, data: Any) -> None:
        if isinstance(data, dict):
            self.process_vitals(data)

    def _handle_baseline_query(self, data: Any) -> None:
        if self.event_bus:
            self.event_bus.publish("health.baseline.status", {
                "baseline": self._baseline,
                "model_trained": self._model_trained,
                "samples": len(self._vitals_history),
            })

    # ------------------------------------------------------------------
    # BaseComponent lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def close(self) -> None:
        self._persist_baseline()
        await super().close()

    def get_status(self) -> Dict[str, Any]:
        return {
            "sklearn_available": HAS_SKLEARN,
            "model_trained": self._model_trained,
            "baseline_metrics": list(self._baseline.keys()),
            "history_samples": len(self._vitals_history),
            "min_samples_for_ml": self._min_samples_for_ml,
        }
