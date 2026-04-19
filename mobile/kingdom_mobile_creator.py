#!/usr/bin/env python3
"""
Kingdom AI Mobile — CREATOR EDITION
Your personal app with pre-loaded API keys, direct Ollama brain,
Black Panther voice, and full Kingdom AI desktop integration.

Usage:
  flet run mobile/kingdom_mobile_creator.py
"""
import os
os.environ["KINGDOM_APP_MODE"] = "creator"
# Mobile platform — light dependency tier (no torch, no TRT-LLM, no vLLM,
# no sentence-transformers). Generation routes through Ollama HTTP with a
# tiny default model; embeddings fall back to SHA pseudo-vectors.
os.environ["KINGDOM_APP_PLATFORM"] = "mobile"

# Import and run the shared app engine
from kingdom_mobile import main
import flet as ft

if __name__ == "__main__":
    ft.app(target=main)
