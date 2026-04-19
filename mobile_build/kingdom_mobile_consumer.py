#!/usr/bin/env python3
"""
Kingdom AI Mobile - CONSUMER EDITION launcher.

For end users: provide your own API keys, optional desktop connection,
data auto-syncs when you choose.

Usage:
  flet run mobile/kingdom_mobile_consumer.py
"""
import os
import sys

# Phase E: hard-force consumer mode BEFORE any other import.
os.environ["KINGDOM_APP_MODE"] = "consumer"
# Mobile platform — light dependency tier regardless of role.
os.environ["KINGDOM_APP_PLATFORM"] = "mobile"


def _assert_consumer_bundle_clean() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.join(here, "config", "mobile_config_creator.json"),
        os.path.join(here, "config", "account_link.json"),
        os.path.join(here, "config", ".secrets.env"),
    )
    offenders = [p for p in candidates if os.path.exists(p)]
    if offenders:
        msg = (
            "Kingdom AI consumer bundle refused to start: creator-only files "
            "present in the asset tree: " + ", ".join(offenders)
        )
        print(msg, file=sys.stderr)
        raise RuntimeError(msg)


_assert_consumer_bundle_clean()

import flet as ft
from kingdom_mobile import main

if __name__ == "__main__":
    ft.app(target=main)
