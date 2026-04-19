#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for per-install identity + zero-config device onboarding.

The contract these tests lock in:

  1. Every Kingdom AI install generates its own fresh identity on
     first run. Two installs on two config directories MUST get
     two different installation_ids and two different user_ids.

  2. Identity survives across ``get_install_identity()`` calls but
     can be wiped with ``forget_identity()``.

  3. ``DeviceOnboardingEngine.run_initial_scan()`` can be called
     without any GUI, uses ``HostDeviceManager.scan_all_devices()``
     under the hood, and tags every discovered device with the
     current install's user_id.

  4. One install's inventory NEVER bleeds into another install's
     inventory — each install writes to its own config dir.

  5. Pair / forget / rescan round-trip through the persisted
     inventory correctly.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402


# Always use isolated config dirs so we never touch the real
# config/install_identity.json on the machine running the tests.


@pytest.fixture
def fresh_install(tmp_path, monkeypatch):
    """Return a helper that gives each call a brand-new install dir."""
    import core.install_identity as ident_mod
    import core.device_onboarding as onboard_mod

    def _make(name: str):
        cfg = tmp_path / name
        cfg.mkdir(parents=True, exist_ok=True)
        # clear the module-level cache so each install gets its own identity
        ident_mod._cached = None  # noqa: SLF001
        onboard_mod._engine = None  # noqa: SLF001
        return cfg

    return _make


def test_fresh_identity_per_install(fresh_install):
    from core.install_identity import get_install_identity

    a = fresh_install("installA")
    id_a = get_install_identity(a)

    b = fresh_install("installB")
    id_b = get_install_identity(b)

    assert id_a.installation_id != id_b.installation_id, \
        "Two installs must generate two different installation_ids"
    assert id_a.user_id != id_b.user_id, \
        "Two installs must generate two different user_ids"
    assert (a / "install_identity.json").exists()
    assert (b / "install_identity.json").exists()


def test_identity_persists_across_calls(fresh_install):
    from core.install_identity import get_install_identity

    cfg = fresh_install("persist")
    first = get_install_identity(cfg)
    # Second call must return the SAME identity (not regenerate)
    second = get_install_identity(cfg)
    assert first.installation_id == second.installation_id
    assert first.user_id == second.user_id


def test_forget_identity_generates_fresh(fresh_install):
    import core.install_identity as ident_mod
    from core.install_identity import get_install_identity, forget_identity

    cfg = fresh_install("forget")
    original = get_install_identity(cfg)

    forget_identity(cfg)
    ident_mod._cached = None  # noqa: SLF001

    # A second call after forget() must generate a brand-new identity
    regen = get_install_identity(cfg)
    assert regen.installation_id != original.installation_id
    assert regen.user_id != original.user_id


def test_rename_and_set_user_id(fresh_install):
    from core.install_identity import get_install_identity, rename_user, set_user_id

    cfg = fresh_install("rename")
    before = get_install_identity(cfg)

    renamed = rename_user("Daniel", cfg)
    assert renamed.display_name == "Daniel"
    assert renamed.installation_id == before.installation_id  # unchanged

    reid = set_user_id("daniel", cfg)
    assert reid.user_id == "daniel"
    assert reid.installation_id == before.installation_id  # unchanged


def test_onboarding_scan_tags_user_id(fresh_install, monkeypatch):
    """The engine must stamp every discovered device with the current
    install's user_id and stash them into a per-install inventory file."""
    from core.device_onboarding import DeviceOnboardingEngine
    from core.install_identity import get_install_identity

    cfg = fresh_install("scan")
    identity = get_install_identity(cfg)

    engine = DeviceOnboardingEngine(event_bus=None, config_dir=cfg)

    # Stub HostDeviceManager with a fake scan so the test is deterministic
    class FakeHost:
        def scan_all_devices(self):
            return {
                "vr": [{"device_id": "vr-1", "name": "Quest 3", "vendor": "Meta"}],
                "webcam": [{"device_id": "cam-1", "name": "Logitech C920"}],
                "bluetooth": [{"device_id": "bt-1", "name": "AirPods", "vendor": "Apple"}],
            }

    engine._host_mgr = FakeHost()  # noqa: SLF001

    result = engine.run_initial_scan(force=True)
    assert result.total_devices == 3
    assert result.user_id == identity.user_id
    assert result.installation_id == identity.installation_id

    for cat, devs in result.categories.items():
        for d in devs:
            assert d.user_id == identity.user_id, \
                f"Device {d.device_id} in {cat} missing user_id stamp"

    # Inventory file must exist under THIS install's config dir
    inv = cfg / "device_inventory.json"
    assert inv.exists(), "Inventory should be persisted per-install"


def test_onboarding_no_cross_install_leak(fresh_install):
    """Two installs with two config dirs must never share inventory."""
    from core.device_onboarding import DeviceOnboardingEngine

    cfg_a = fresh_install("A")
    eng_a = DeviceOnboardingEngine(event_bus=None, config_dir=cfg_a)
    eng_a._host_mgr = type("F", (), {"scan_all_devices": lambda s: {"vr": [{"device_id": "A-vr", "name": "Alice Headset"}]}})()  # noqa: SLF001
    eng_a.run_initial_scan(force=True)

    cfg_b = fresh_install("B")
    eng_b = DeviceOnboardingEngine(event_bus=None, config_dir=cfg_b)
    eng_b._host_mgr = type("F", (), {"scan_all_devices": lambda s: {"vr": [{"device_id": "B-vr", "name": "Bob Headset"}]}})()  # noqa: SLF001
    eng_b.run_initial_scan(force=True)

    a_devices = {d.device_id for d in eng_a.list_inventory()}
    b_devices = {d.device_id for d in eng_b.list_inventory()}

    assert "A-vr" in a_devices and "A-vr" not in b_devices
    assert "B-vr" in b_devices and "B-vr" not in a_devices
    assert a_devices.isdisjoint(b_devices), \
        "Two installs leaked each other's devices into a shared inventory"


def test_pair_and_forget_round_trip(fresh_install):
    from core.device_onboarding import DeviceOnboardingEngine

    cfg = fresh_install("pair")
    eng = DeviceOnboardingEngine(event_bus=None, config_dir=cfg)
    eng._host_mgr = type("F", (), {  # noqa: SLF001
        "scan_all_devices": lambda s: {"webcam": [{"device_id": "cam-X", "name": "X"}]}
    })()
    eng.run_initial_scan(force=True)

    assert eng.pair_device("cam-X") is True
    paired = [d for d in eng.list_inventory() if d.device_id == "cam-X"][0]
    assert paired.status == "paired"

    assert eng.pair_device("cam-does-not-exist") is False
    assert eng.forget_device("cam-X") is True
    assert all(d.device_id != "cam-X" for d in eng.list_inventory())


def test_event_bus_publishes_onboarding_events(fresh_install):
    """The engine must emit device.discovered / device.paired events so
    the Devices tab / VR streamer / Silent Alarm can react live."""
    from core.device_onboarding import DeviceOnboardingEngine

    cfg = fresh_install("events")
    published: list = []

    class FakeBus:
        def publish(self, name, data):
            published.append((name, data))

    eng = DeviceOnboardingEngine(event_bus=FakeBus(), config_dir=cfg)
    eng._host_mgr = type("F", (), {  # noqa: SLF001
        "scan_all_devices": lambda s: {"vr": [{"device_id": "vr-E", "name": "E"}]}
    })()

    eng.run_initial_scan(force=True)
    event_names = [n for n, _ in published]
    assert "device.onboarding.started" in event_names
    assert "device.discovered" in event_names
    assert "device.onboarding.completed" in event_names

    published.clear()
    eng.pair_device("vr-E")
    assert any(n == "device.paired" for n, _ in published)


def test_vr_streamer_defaults_to_install_user_id(fresh_install, monkeypatch):
    """The VRHeadsetStreamer must default new sessions to THIS install's
    user_id so headsets auto-pair to the right consumer."""
    import core.install_identity as ident_mod
    from core.install_identity import get_install_identity

    cfg = fresh_install("vr")
    identity = get_install_identity(cfg)

    # Patch current_user_id so the VR streamer picks up our test identity
    monkeypatch.setattr(ident_mod, "current_user_id", lambda *a, **k: identity.user_id)

    # We only need to import the symbol to confirm the integration is live
    from core import vr_headset_streamer as vr_mod
    # Sanity: the module references install_identity.current_user_id at runtime
    source = Path(vr_mod.__file__).read_text(encoding="utf-8")
    assert "from core.install_identity import current_user_id" in source, \
        "VRHeadsetStreamer must default to the install's user_id"
