#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gui.qt_frames.device_onboarding_dialog
──────────────────────────────────────
First-run "find my devices" wizard.

Shown automatically the first time a Kingdom AI install boots with a
GUI. Three plain-English steps:

1. "Turn on your headset, webcam, earbuds, controllers, wearables."
2. Click Scan — Kingdom AI finds what's nearby using the same cross-
   platform detectors the Devices tab uses.
3. Tick the devices that are yours, click Pair, and you're in.

There is zero code to edit, zero file to modify, nothing about anybody
else's install. Every discovered device is tagged with *your*
``user_id`` (generated on this machine when you first launched) before
it's saved, so two households running Kingdom AI never see each
other's gear.

If PyQt is unavailable (e.g. headless server consumer), this module
exposes the same flow as a pure-Python fallback via
``run_headless_wizard()``.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger("KingdomAI.DeviceOnboardingDialog")

HAS_QT = False
try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )

    HAS_QT = True
except Exception as e:  # pragma: no cover - environment-dependent
    logger.debug("PyQt6 not available for onboarding dialog: %s", e)

from core.device_onboarding import (  # noqa: E402
    DiscoveredDevice,
    OnboardingResult,
    get_device_onboarding_engine,
)
from core.install_identity import get_install_identity  # noqa: E402

CATEGORY_LABELS = {
    "usb": "USB peripherals",
    "serial": "Serial / Arduino-style boards",
    "bluetooth": "Bluetooth devices (earbuds, wearables, controllers)",
    "audio": "Microphones & speakers",
    "webcam": "Cameras",
    "vr": "VR / AR headsets",
    "sdr": "Radio receivers",
    "network": "Network adapters",
    "microcontrollers": "Microcontrollers",
    "automotive": "OBD-II / CAN vehicle interfaces",
    "lidar": "LiDAR sensors",
    "lab_equipment": "Lab equipment (oscilloscopes, DMMs…)",
    "imaging": "Microscopes & specialty cameras",
    "drones": "Drones / UAVs",
    "kingdom_devices": "Already linked Kingdom devices",
    "cached": "Previously found",
}


def run_headless_wizard(event_bus: Any = None) -> Dict[str, Any]:
    """CLI fallback that performs the same flow without a GUI.

    Prints a friendly message, scans, prints the inventory, and pairs
    everything by default (the user can always ``Forget`` later from
    the Devices tab).
    """
    identity = get_install_identity()
    print(f"\n  👑  Welcome to the Kingdom, {identity.display_name}.")
    print(f"     Your install id: {identity.installation_id[:8]}…")
    print("     Turn on your headset, webcam, earbuds and controllers,")
    print("     then press Enter to let Kingdom AI find them.\n")
    try:
        input("     [Enter] ")
    except EOFError:
        pass
    engine = get_device_onboarding_engine(event_bus=event_bus)
    result = engine.run_initial_scan(force=True)
    print(f"\n  Found {result.total_devices} device(s):")
    for cat, devices in result.categories.items():
        label = CATEGORY_LABELS.get(cat, cat)
        print(f"    {label}:")
        for d in devices:
            print(f"      • {d.name}  [{d.vendor or 'unknown vendor'}]")
            engine.pair_device(d.device_id)
    print("\n  Everything has been paired to your install. Open the")
    print("  Devices tab inside Kingdom AI to manage or forget any.\n")
    return result.to_dict()


if HAS_QT:

    class DeviceOnboardingDialog(QDialog):
        """Modal onboarding wizard. Blocks until the user finishes.

        Three pages in a ``QStackedWidget``:
          0 — welcome + "turn your stuff on, click Scan"
          1 — live scan progress
          2 — checkbox list of discovered devices; pair / finish
        """

        def __init__(self, event_bus: Any = None, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Kingdom AI — Find Your Devices")
            self.setMinimumSize(640, 520)
            self.setModal(True)

            self.event_bus = event_bus
            self.engine = get_device_onboarding_engine(event_bus=event_bus)
            self.identity = get_install_identity()
            self._result: Optional[OnboardingResult] = None
            self._checkboxes: Dict[str, QCheckBox] = {}

            root = QVBoxLayout(self)

            self._stack = QStackedWidget(self)
            root.addWidget(self._stack, 1)

            self._stack.addWidget(self._build_welcome_page())
            self._stack.addWidget(self._build_scanning_page())
            self._stack.addWidget(self._build_results_page())

            bar = QHBoxLayout()
            bar.addStretch(1)
            self.btn_skip = QPushButton("Skip for now")
            self.btn_skip.clicked.connect(self.reject)
            bar.addWidget(self.btn_skip)

            self.btn_action = QPushButton("Find my devices")
            self.btn_action.clicked.connect(self._on_action)
            self.btn_action.setDefault(True)
            bar.addWidget(self.btn_action)
            root.addLayout(bar)

        # ── page 0: welcome ─────────────────────────────────────────────
        def _build_welcome_page(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)

            title = QLabel("Welcome to the Kingdom.")
            f = QFont()
            f.setPointSize(18)
            f.setBold(True)
            title.setFont(f)
            lay.addWidget(title)

            sub = QLabel(
                f"Signed in as <b>{self.identity.display_name}</b>  "
                f"<span style='color:#888'>"
                f"(install id {self.identity.installation_id[:8]}…)"
                f"</span>"
            )
            sub.setTextFormat(Qt.TextFormat.RichText)
            lay.addWidget(sub)

            lay.addSpacing(12)
            body = QLabel(
                "This is your Kingdom AI — brand new, just for you. "
                "It knows nothing about anybody else's gear.<br><br>"
                "Please turn on your things now:<br>"
                " • VR or AR headset<br>"
                " • Webcam<br>"
                " • Bluetooth earbuds, controllers, wearables<br>"
                " • Any other devices you'd like Kingdom AI to work with<br><br>"
                "Then click <b>Find my devices</b> and we'll look around and list "
                "whatever's nearby. You pick which ones are yours. You can change "
                "this at any time from the Devices tab."
            )
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            lay.addWidget(body)
            lay.addStretch(1)
            return w

        # ── page 1: scanning ───────────────────────────────────────────
        def _build_scanning_page(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)

            title = QLabel("Looking around…")
            f = QFont()
            f.setPointSize(16)
            f.setBold(True)
            title.setFont(f)
            lay.addWidget(title)

            self._progress_label = QLabel("Starting scan…")
            self._progress_label.setWordWrap(True)
            lay.addWidget(self._progress_label)

            self._progress_bar = QProgressBar()
            self._progress_bar.setRange(0, 0)  # indeterminate
            lay.addWidget(self._progress_bar)

            lay.addStretch(1)
            return w

        # ── page 2: results ────────────────────────────────────────────
        def _build_results_page(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)

            title = QLabel("Here's what we found.")
            f = QFont()
            f.setPointSize(16)
            f.setBold(True)
            title.setFont(f)
            lay.addWidget(title)

            self._results_hint = QLabel(
                "Tick the devices that are yours. Everything you tick will be paired to your install."
            )
            self._results_hint.setWordWrap(True)
            lay.addWidget(self._results_hint)

            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._scroll_body = QWidget()
            self._scroll_layout = QVBoxLayout(self._scroll_body)
            self._scroll.setWidget(self._scroll_body)
            lay.addWidget(self._scroll, 1)
            return w

        # ── actions ────────────────────────────────────────────────────
        def _on_action(self) -> None:
            page = self._stack.currentIndex()
            if page == 0:
                self._start_scan()
            elif page == 1:
                pass  # button disabled while scanning
            else:
                self._finish()

        def _start_scan(self) -> None:
            self._stack.setCurrentIndex(1)
            self.btn_action.setEnabled(False)
            self.btn_action.setText("Scanning…")

            self._thread = threading.Thread(target=self._run_scan_thread, daemon=True)
            self._thread.start()

        def _run_scan_thread(self) -> None:
            try:
                def _cb(msg: str) -> None:
                    QTimer.singleShot(0, lambda m=msg: self._progress_label.setText(m))

                self.engine._progress_cb = _cb  # noqa: SLF001
                result = self.engine.run_initial_scan(force=True)
            except Exception as e:
                logger.exception("Scan failed: %s", e)
                result = OnboardingResult(0, 0, {}, 0, "", "")
            QTimer.singleShot(0, lambda r=result: self._on_scan_done(r))

        def _on_scan_done(self, result: OnboardingResult) -> None:
            self._result = result
            self._populate_results(result)
            self._stack.setCurrentIndex(2)
            self.btn_action.setEnabled(True)
            self.btn_action.setText("Pair selected")

        def _populate_results(self, result: OnboardingResult) -> None:
            while self._scroll_layout.count():
                item = self._scroll_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._checkboxes.clear()

            if result.total_devices == 0:
                hint = QLabel(
                    "No devices detected yet.<br><br>"
                    "Make sure your devices are powered on and in pairing mode, "
                    "then click <b>Rescan</b>. Some devices need to be plugged in "
                    "over USB the first time."
                )
                hint.setWordWrap(True)
                hint.setTextFormat(Qt.TextFormat.RichText)
                self._scroll_layout.addWidget(hint)
                self.btn_action.setText("Rescan")
                try:
                    self.btn_action.clicked.disconnect()
                except Exception:
                    pass
                self.btn_action.clicked.connect(self._start_scan)
                return

            for cat, devices in result.categories.items():
                label = CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
                header = QLabel(f"<b>{label}</b>  ({len(devices)})")
                header.setTextFormat(Qt.TextFormat.RichText)
                self._scroll_layout.addWidget(header)
                for d in devices:
                    cb = QCheckBox(self._format_device(d))
                    cb.setChecked(True)
                    self._scroll_layout.addWidget(cb)
                    self._checkboxes[d.device_id] = cb
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFrameShadow(QFrame.Shadow.Sunken)
                self._scroll_layout.addWidget(sep)

            self._scroll_layout.addStretch(1)

        def _format_device(self, d: DiscoveredDevice) -> str:
            bits = [d.name or "(no name)"]
            if d.vendor:
                bits.append(f"· {d.vendor}")
            return "   ".join(bits)

        def _finish(self) -> None:
            paired = 0
            for device_id, cb in self._checkboxes.items():
                if cb.isChecked():
                    if self.engine.pair_device(device_id):
                        paired += 1
            QMessageBox.information(
                self,
                "You're in.",
                f"Paired {paired} device(s) to your install.\n\n"
                "Open the Devices tab at any time to add, forget, or rescan.",
            )
            self.accept()


    def run_qt_wizard(event_bus: Any = None, parent=None) -> Optional[OnboardingResult]:
        """Show the wizard and block until the user finishes or skips."""
        app = QApplication.instance()
        owned_app = False
        if app is None:
            app = QApplication([])
            owned_app = True

        dlg = DeviceOnboardingDialog(event_bus=event_bus, parent=parent)
        code = dlg.exec()

        if owned_app:
            app.processEvents()

        if code == QDialog.DialogCode.Accepted and dlg._result is not None:
            return dlg._result
        return None

else:  # pragma: no cover - PyQt missing

    def run_qt_wizard(event_bus: Any = None, parent=None):  # type: ignore[misc]
        logger.info("PyQt6 unavailable — falling back to headless wizard.")
        return run_headless_wizard(event_bus=event_bus)


__all__ = ["run_qt_wizard", "run_headless_wizard", "HAS_QT"]
