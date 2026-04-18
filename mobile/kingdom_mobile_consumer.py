#!/usr/bin/env python3
"""Kingdom AI Mobile - CONSUMER EDITION launcher (workspace copy)."""
import os
import sys

os.environ["KINGDOM_APP_MODE"] = "consumer"


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
            "present: " + ", ".join(offenders)
        )
        print(msg, file=sys.stderr)
        raise RuntimeError(msg)


_assert_consumer_bundle_clean()

import flet as ft
from kingdom_mobile import main

if __name__ == "__main__":
    ft.app(target=main)
