# Kingdom AI — System Audit

_Generated: 2026-04-19T02:11:46 UTC_
_Source of truth: `/home/kingzilla456/kingdom_ai`_

> This is the mechanical audit. Plain-English walkthrough lives in
> `docs/KINGDOM_AI_FOR_HUMANS.md`.

---

## 1. Headline totals

| Scope | Files | Lines of code |
|---|---:|---:|
| **Kingdom-authored source** | **3,175** | **1,009,665** |
| └ Python                    | 1,782     | 809,849       |
| └ Markdown docs             | 470       | 130,907       |
| └ JSON                      | 240       | 48,004        |
| └ Shell / build             | 182       | 18,138        |
| └ Config (yaml/toml/ini)    | 17        | 1,067         |
| └ JavaScript / HTML / XML   | 14        | 1,700         |
| Vendored / environments     | 361,867   | 86,189,606    |

Vendored totals include `kingdom-venv/`, `ml_packages_venv/`,
`creation_env/`, `node_modules/`, `HunyuanVideo/`, `GPT-SoVITS/`,
`ovr_platform_sdk_71.0/`, `ai_video_restorer/`, `android-stubs/`,
`external_miners/`, `kingdom_backups/`, and similar — they are **not**
Kingdom-authored and are excluded from the primary counts.

---

## 2. Kingdom source by top-level directory

| Directory | Files | LOC | Role |
|---|---:|---:|---|
| `<root>` | 1,056 | 342,720 | Top-level entry-points (launchers, *.py, *.md). |
| `core` | 473 | 302,899 | Primary brain runtime, orchestrators, engines, routers. |
| `gui` | 278 | 173,291 | PyQt6 tabs, widgets, styles, event handlers. |
| `components` | 193 | 35,376 | Named subsystems attached to the brain (Dictionary, MemPalace, Harmonic, etc.). |
| `docs` | 92 | 30,190 | Markdown design notes + this audit. |
| `blockchain` | 68 | 27,048 | Chain-specific adapters and protocol bindings. |
| `tests` | 66 | 18,291 | Automated test suites. |
| `config` | 59 | 10,315 | Runtime configuration files. |
| `ai` | 30 | 9,747 | Standalone AI utilities (classifiers, models). |
| `kingdom-fintech` | 33 | 9,662 | Kingdom Fintech sub-product (fiat + on-ramp). |
| `scripts` | 48 | 8,132 | Build / ops / deploy shell scripts. |
| `infrastructure` | 11 | 7,632 | Cross-cutting infra (logging, tracing, metrics). |
| `mobile` | 5 | 5,177 | Creator/Consumer Mobile Kivy/Android launchers. |
| `data` | 149 | 4,923 | Seed data, fixtures, sample corpora. |
| `mining` | 18 | 4,906 | Mining strategy + rig adapters. |
| `kingdom_modules` | 14 | 3,667 | Reusable internal modules. |
| `ai_modules` | 6 | 2,682 | Older AI modules kept for compatibility. |
| `integrations` | 4 | 1,904 | External-service adapters (MCP, Claw, Thoth). |
| `market` | 4 | 953 | Market-feed providers. |
| `kingdom_keys` | 8 | 939 | Creator-only key material (encrypted). |
| `mock_modules` | 11 | 881 | Mock stand-ins used in tests. |
| `kingdom-landing` | 8 | 822 | Public marketing / download site (Netlify). |
| `moonshot` | 3 | 808 | Experimental moonshot / R&D code. |
| `code` | 2 | 784 | Experimental code sandbox. |
| `meme` | 3 | 760 | Meme-coin detection + interaction. |
| `market_api` | 4 | 755 | Outward-facing market HTTP API. |
| `configs` | 12 | 687 | Legacy per-environment configs. |
| `kingdom_rebuild` | 5 | 573 | Rebuild/bootstrap scripts. |
| `database` | 2 | 401 | Schema + migration helpers. |
| `mcp` | 1 | 379 | MCP tool-server definitions. |
| `meta_learning` | 2 | 353 | Meta-cognition (learning to learn). |
| `copy_trading` | 2 | 316 | Copy-trading strategies. |
| `controls` | 1 | 275 | Form controls (legacy). |
| `codegen` | 1 | 257 | Code-generation helpers. |
| `charts` | 2 | 234 | Charting helpers. |
| `memory` | 2 | 187 | Memory-store back-ends. |
| `kingdom_ai_system` | 12 | 186 | Oldest top-level launcher folder, still referenced. |
| `monitoring` | 2 | 179 | Monitoring + observability helpers. |
| `extensions` | 7 | 132 | Third-party-style extensions. |
| `business` | 5 | 105 | Business-logic specific modules. |
| `consumer` | 1 | 86 | Consumer-Desktop CLI tools (install advisor, bootstrap). |
| `interface` | 2 | 51 | Interface contracts (protocols/ABCs). |

---

## 3. Tabs — the user-facing surface

Kingdom AI Perfect v2 and Kingdom AI Consumer Desktop both present the
same **16 primary tabs**. Mobile launchers present a subset (the 6
lightweight tabs: Dashboard, Wallet, Trading-lite, Thoth AI, API Keys,
Settings). Every tab subscribes to the same `EventBus` and has a brain
router handle, so any tab can publish to any other tab.

| # | Tab | Module | Purpose |
|--:|---|---|---|
| 1 | **Dashboard** | `gui/qt_frames/dashboard_qt.py` | Mission-control overview: live system status, brain health, tab heartbeat. |
| 2 | **API Key Manager** | `gui/qt_frames/api_key_manager_tab.py` | Encrypts, rotates, and distributes every external credential; QR-locked. |
| 3 | **Wallet** | `gui/qt_frames/wallet_tab.py` | Multi-chain balances, deposits, withdrawals, cold/hot key separation. |
| 4 | **Blockchain** | `gui/qt_frames/blockchain_tab.py` | Explorer + read/write adapter for 200+ chains, contracts, and faucets. |
| 5 | **Trading** | `gui/qt_frames/trading/trading_tab.py` | Strategy marketplace, live P&L, whale-tracker, risk dashboards. |
| 6 | **Mining** | `gui/qt_frames/mining_tab.py` | Rig orchestration, auto-switcher, algorithm profitability comparator. |
| 7 | **Device Manager** | `gui/qt_frames/device_manager_tab.py` | Discovers, secures and takes over local/network/edge devices. |
| 8 | **VR** | `gui/qt_frames/vr_qt_tab.py` | Headset pairing, spatial interface for Kingdom AI presence. |
| 9 | **Thoth AI** | `gui/qt_frames/thoth_ai_tab.py` | Conversational cockpit: voice + text interface to the brain. |
| 10 | **Thoth Comms** | `gui/qt_frames/thoth_comms_tab.py` | Phone/radio/mesh bridge; AI routes calls and interprets comms. |
| 11 | **Code Generator** | `gui/qt_frames/code_generator_tab.py` | Claw-code bridge + Codegen engine: AI writes/ships full modules. |
| 12 | **Software Automation** | `gui/qt_frames/software_automation_tab.py` | Ties codegen + device takeover for hands-free software builds. |
| 13 | **MCP Control Center** | `gui/qt_frames/mcp_control_center_tab.py` | Manages every MCP tool server exposed to the AI brain. |
| 14 | **Health Dashboard** | `gui/qt_frames/health_dashboard_tab.py` | Biometric + system telemetry, alarms, self-diagnosis feed. |
| 15 | **KAIG** | `gui/qt_frames/kaig_tab.py` | Kingdom AI Gateway: routes outbound AI calls to any provider. |
| 16 | **Settings** | `gui/qt_frames/settings_tab.py` | Role (creator/consumer), platform (desktop/mobile), theme, keys. |

### 3.1 Cross-tab awareness contract

- Every tab is instantiated **with a reference to the same**
  `UnifiedBrainRouter`, `EventBus`, `InferenceStack`, `DictionaryBrain`,
  `MemPalaceBridge`, `LanguageLearningHub`, and `NeuroprotectionLayer`.
- Events flow through a single bus: any tab publishing
  `brain.ask.request` is answered on `brain.ask.result` after the
  router has run Dictionary → MemPalace → LanguageHub → InferenceStack.
- Tabs never talk directly — they publish events and subscribe to
  responses. This makes every tab simultaneously aware of every other.

---

## 4. Components — 49 named subsystems

| File | Purpose |
|---|---|
| `components/__init__.py` | Package exports + feature-flag availability detection. |
| `components/ai/ai_manager.py` | — |
| `components/ai/continuous_response.py` | — |
| `components/ai/inference_engine.py` | — |
| `components/ai/model_loader.py` | — |
| `components/alchemy_system.py` | Recipe engine for manufacturing + chemistry transformations. |
| `components/api/__init__.py` | — |
| `components/api/api_key_manager.py` | — |
| `components/api/api_manager.py` | — |
| `components/api/rest_client.py` | — |
| `components/api/websocket_client.py` | — |
| `components/api_connector.py` | Low-level HTTP/WebSocket pool used by every other component. |
| `components/audio_synthesis_engine.py` | Text-to-speech and waveform synthesis pipeline. |
| `components/autonomous_trading/__init__.py` | — |
| `components/autonomous_trading/autonomous_orchestrator.py` | — |
| `components/autonomous_trading/data_feeds.py` | — |
| `components/autonomous_trading/execution_engine.py` | — |
| `components/autonomous_trading/module_1_portfolio_hedging.py` | — |
| `components/autonomous_trading/module_2_institutional_positioning.py` | — |
| `components/autonomous_trading/module_3_dividend_radar.py` | — |
| `components/autonomous_trading/module_4_correlation_map.py` | — |
| `components/autonomous_trading/module_5_sentiment_arbitrage.py` | — |
| `components/autonomous_trading/module_6_macro_analysis.py` | — |
| `components/autonomous_trading/module_7_short_squeeze.py` | — |
| `components/autonomous_trading/risk_manager.py` | — |
| `components/biological_system.py` | Biometrics + bio-signal modelling (EEG, heart-rate, SpO2). |
| `components/blockchain/bitcoin_wallet.py` | — |
| `components/blockchain/blockchain_connector.py` | — |
| `components/blockchain/ethereum_wallet.py` | — |
| `components/blockchain/smart_contract_handler.py` | — |
| `components/blueprint_engine.py` | Parametric CAD blueprint generator (electronics + mechanics). |
| `components/bone_conduction_driver.py` | Driver for bone-conduction headset/speaker hardware. |
| `components/botsofwallstreet/__init__.py` | — |
| `components/botsofwallstreet/agent.py` | — |
| `components/capital_flow_processor.py` | Stream processor for cross-chain capital movements. |
| `components/chemistry_database.py` | Indexed chemistry reagent / reaction knowledge base. |
| `components/chemistry_manufacturing_integration.py` | Bridges chemistry DB with manufacturing engine. |
| `components/claw_code_bridge.py` | Remote code-execution sandbox over Claw-Code protocol. |
| `components/config/config_manager.py` | — |
| `components/config/profile_manager.py` | — |
| `components/config/settings_loader.py` | — |
| `components/contingency/__init__.py` | — |
| `components/contingency/ai_contingency.py` | — |
| `components/contingency/contingency_manager.py` | — |
| `components/contingency/failover.py` | — |
| `components/contingency/failover_handler.py` | — |
| `components/contingency/recovery_system.py` | — |
| `components/continuous_response.py` | Smaller cousin: short continuous reply manager. |
| `components/continuous_response_generator.py` | Always-on generative loop for long-form replies. |
| `components/contracts/contract_builder.py` | — |
| `components/contracts/contract_deployer.py` | — |
| `components/contracts/contract_manager.py` | — |
| `components/contracts/smart_contracts.py` | — |
| `components/copy_trading/copy_trading.py` | — |
| `components/copy_trading/strategy_replicator.py` | — |
| `components/copy_trading/trader_tracker.py` | — |
| `components/data/__init__.py` | — |
| `components/data/data_analyzer.py` | — |
| `components/data/data_cleaner.py` | — |
| `components/data/data_indexer.py` | — |
| `components/data/data_loader.py` | — |
| `components/data/data_manager.py` | — |
| `components/data/data_transformer.py` | — |
| `components/database/database_manager.py` | — |
| `components/database/db_connector.py` | — |
| `components/database/query_builder.py` | — |
| `components/dictionary_brain.py` | Multi-era dictionary + etymology + semantic brain (SOTA 2026). |
| `components/eeg_signal_processor.py` | Lab-Streaming-Layer EEG decoder and feature extractor. |
| `components/enhanced_file_export_sota_2026.py` | Modern file-export (JSON/Arrow/Parquet) with metadata. |
| `components/error/error_handler.py` | — |
| `components/error/error_logger.py` | — |
| `components/error/error_resolution.py` | — |
| `components/error_resolver.py` | AI-driven error classifier and auto-remediation. |
| `components/event_bus.py` | Primary in-process pub/sub bus (delegates to SOTA impl). |
| `components/exploded_view_engine.py` | Generates exploded / step-by-step assembly renders. |
| `components/hardware_interface_layer.py` | Generic HAL for sensors, actuators, cameras. |
| `components/harmonic_orchestrator_v3.py` | Coordinates AI subsystems into one harmonic cadence. |
| `components/hmd_integration.py` | Head-mounted display (OpenXR) integration. |
| `components/intent/action_mapper.py` | — |
| `components/intent/intent_classifier.py` | — |
| `components/intent/intent_recognition.py` | — |
| `components/language_learning_hub.py` | Multilingual vocab, grammar, context ingestion. |
| `components/lsl_sync_engine.py` | Lab-Streaming-Layer multi-device time-sync engine. |
| `components/manufacturing_engine.py` | Runs fabrication plans against real/virtual machines. |
| `components/market_component.py` | Market-data aggregation façade. |
| `components/market_data/candle_builder.py` | — |
| `components/market_data/market_data_streaming.py` | — |
| `components/market_data/tick_handler.py` | — |
| `components/media_export.py` | Audio/video/image export pipeline. |
| `components/meme/meme_coins.py` | — |
| `components/meme/social_scraper.py` | — |
| `components/meme/trend_analyzer.py` | — |
| `components/memory_palace_manager.py` | Spatial memory index of long-term context. |
| `components/memory_persistence_layer.py` | Durable write-through store beneath MemPalace. |
| `components/mempalace_bridge.py` | Wires MemPalace into the rest of the brain. |
| `components/mempalace_mcp_server.py` | Exposes MemPalace as an MCP tool server. |
| `components/mempalace_setup.py` | First-run MemPalace scaffolding + migrations. |
| `components/metallurgy_engine.py` | Metals + alloys calculation + process planner. |
| `components/mining/__init__.py` | — |
| `components/mining/hashrate_monitor.py` | — |
| `components/mining/miner_manager.py` | — |
| `components/mining/mining_dashboard.py` | — |
| `components/mining/mining_system.py` | — |
| `components/mining_system.py` | Crypto-mining scheduler and pool-switcher. |
| `components/ml/feature_extractor.py` | — |
| `components/ml/meta_learning.py` | — |
| `components/ml/model_trainer.py` | — |
| `components/moonshot/moonshot_integration.py` | — |
| `components/moonshot/opportunity_scanner.py` | — |
| `components/moonshot/risk_calculator.py` | — |
| `components/network/connection_handler.py` | — |
| `components/network/network_manager.py` | — |
| `components/network/network_monitor.py` | — |
| `components/network/network_scanner.py` | — |
| `components/network/retry_manager.py` | — |
| `components/neuroprotection_layer.py` | Input sanitisation + jailbreak/abuse filter. |
| `components/ollama_memory_integration.py` | Ollama HTTP bridge + tool registry (Dictionary tools). |
| `components/order/execution_engine.py` | — |
| `components/order/order_management.py` | — |
| `components/order/order_router.py` | — |
| `components/portfolio/asset_allocator.py` | — |
| `components/portfolio/portfolio_manager.py` | — |
| `components/portfolio/rebalancer.py` | — |
| `components/prediction/forecaster.py` | — |
| `components/prediction/prediction_engine.py` | — |
| `components/prediction/signal_generator.py` | — |
| `components/risk/drawdown_monitor.py` | — |
| `components/risk/exposure_calculator.py` | — |
| `components/risk/risk_management.py` | — |
| `components/risk_assessment.py` | Trading / action risk scorer. |
| `components/sandbox_hardening.py` | Drops privileges, locks resources, isolates AI actions. |
| `components/schematic_engine.py` | Electrical schematic layout + SPICE export. |
| `components/security/auth_handler.py` | — |
| `components/security/encryption_handler.py` | — |
| `components/security/key_manager.py` | — |
| `components/security/security_auditor.py` | — |
| `components/security/security_manager.py` | — |
| `components/sleep_manager.py` | Graceful idle/wake scheduling across subsystems. |
| `components/task_manager.py` | Background job/queue dispatcher. |
| `components/thoth/__init__.py` | — |
| `components/thoth/adapter.py` | — |
| `components/thoth/thoth_ai.py` | — |
| `components/thoth_connector.py` | Link to Thoth voice + NLU service. |
| `components/trading/__init__.py` | — |
| `components/trading/exchange_connector.py` | — |
| `components/trading/market_api.py` | — |
| `components/trading/market_integrator.py` | — |
| `components/trading/market_intelligence.py` | — |
| `components/trading/order_manager.py` | — |
| `components/trading/risk_assessment_core.py` | — |
| `components/trading/trading_component.py` | — |
| `components/trading/trading_system.py` | — |
| `components/trading/verification_manager.py` | — |
| `components/trading_bot.py` | Core rule/strategy runner feeding the Trading tab. |
| `components/trading_strategies/backtest_engine.py` | — |
| `components/trading_strategies/strategy_manager.py` | — |
| `components/trading_strategies/trading_strategies.py` | — |
| `components/universal_equipment_abstraction.py` | Uniform API over CNC, 3D-printers, labware. |
| `components/vision_analysis.py` | Frame-level computer vision (OCR, detection, classification). |
| `components/vision_stream.py` | Live camera ingestion + pre-processing. |
| `components/visualization/chart_generator.py` | — |
| `components/visualization/market_charts.py` | — |
| `components/visualization/order_book.py` | — |
| `components/visualization/system_integration.py` | — |
| `components/visualization/visualization_manager.py` | — |
| `components/visualization_dashboard.py` | Cross-tab plot/stream renderer. |
| `components/voice/__init__.py` | — |
| `components/voice/command_parser.py` | — |
| `components/voice/voice_processor.py` | — |
| `components/voice/voice_recognition.py` | — |
| `components/voice/voice_synth.py` | — |
| `components/voice/voice_system.py` | — |
| `components/voice_assistant.py` | Wake-word + dialogue front-end for voice input. |
| `components/vr/__init__.py` | — |
| `components/vr/vr_analytics.py` | — |
| `components/vr/vr_connector.py` | — |
| `components/vr/vr_controller.py` | — |
| `components/vr/vr_interface.py` | — |
| `components/vr/vr_module.py` | — |
| `components/vr/vr_portfolio_view.py` | — |
| `components/vr/vr_renderer.py` | — |
| `components/vr/vr_scene.py` | — |
| `components/vr/vr_system.py` | — |
| `components/vr/vr_trading_interface.py` | — |
| `components/vr_ai/3d_visualizer.py` | — |
| `components/vr_ai/gesture_recognizer.py` | — |
| `components/vr_ai/vr_ai_interface.py` | — |
| `components/wallet/__init__.py` | — |
| `components/wallet/wallet_system.py` | — |
| `components/wearable_biometric_streamer.py` | Streams wearable biometric packets to biological_system. |
| `components/whale/alert_system.py` | — |
| `components/whale/transaction_monitor.py` | — |
| `components/whale/whale_tracker.py` | — |

---

## 5. Core runtime — 471 files, categorised

### 5.1 Brain / AI orchestration (37 files)

- `core/ai_brain_router_with_self_ask.py`
- `core/ai_command_router.py`
- `core/ai_contingency.py`
- `core/ai_engine.py`
- `core/ai_execution_optimizer.py`
- `core/ai_fallback.py`
- `core/ai_gui_manager.py`
- `core/ai_models/__init__.py`
- `core/ai_models/model_interface.py`
- `core/ai_response_coordinator.py`
- `core/ai_security_engine.py`
- `core/ai_sentience_detection_framework.py`
- `core/ai_trading_system.py`
- `core/ai_visual_engine.py`
- `core/analytics_engine.py`
- `core/architectural_design_engine.py`
- `core/brain_runtime_controller.py`
- `core/cad_mechanical_engineering_engine.py`
- `core/character_consistency_engine.py`
- `core/electronics_circuit_design_engine.py`
- `core/fashion_clothing_design_engine.py`
- `core/hd_wallet_engine.py`
- `core/industrial_product_design_engine.py`
- `core/kaig_engine.py`
- `core/kaig_migration_engine.py`
- `core/medical_reconstruction_engine.py`
- `core/meta_learning.py`
- `core/mining/exahash_quantum_engine.py`
- `core/ocr_linguistics_engine.py`
- `core/prediction_engine.py`
- `core/real_trading_engine.py`
- `core/screenplay_narrative_engine.py`
- `core/security/scene_context_engine.py`
- `core/unified_brain_router.py`
- `core/unified_creative_engine.py`
- `core/universal_animation_engine.py`
- `core/world_generation_engine.py`

### 5.2 Inference + embeddings (SOTA 2026 stack) (8 files)

- `core/inference_stack.py`
- `core/ollama_config.py`
- `core/ollama_gateway.py`
- `core/ollama_learning_integration.py`
- `core/ollama_model_manager.py`
- `core/ollama_vl_jepa_brain.py`
- `core/thoth_ollama_connector.py`
- `core/vl_jepa/embedding_space.py`

### 5.3 Blockchain & wallets (39 files)

- `core/bitcoin_fix.py`
- `core/blockchain.py`
- `core/blockchain/__init__.py`
- `core/blockchain/base58.py`
- `core/blockchain/connector.py`
- `core/blockchain/explorer_browser.py`
- `core/blockchain/kingdomweb3_v2.py`
- `core/blockchain/kingdomweb3_v2_OLD_CONFLICTING.py`
- `core/blockchain/manager.py`
- `core/blockchain/mining_dashboard.py`
- `core/blockchain/network_stats.py`
- `core/blockchain/transaction_monitor.py`
- `core/blockchain/wallet.py`
- `core/blockchain/xrpl.py`
- `core/blockchain_connector.py`
- `core/blockchain_connector_clean.py`
- `core/blockchain_connector_fixed.py`
- `core/blockchain_manager.py`
- `core/blockchain_middleware.py`
- `core/capital_efficiency_module.py`
- `core/coin_accumulation_intelligence.py`
- `core/coin_algorithm_mapping.py`
- `core/coin_family_classifier.py`
- `core/meme_coins.py`
- `core/mining/bitcoin_miner.py`
- `core/mining/blockchain_mining.py`
- `core/mining/multi_coin_coordinator.py`
- `core/multi_coin_miner.py`
- `core/multichain_trade_executor.py`
- `core/sentience/wallet_sentience_integration.py`
- `core/wallet.py`
- `core/wallet_adapters/__init__.py`
- `core/wallet_adapters/external_adapter.py`
- `core/wallet_adapters/monero_adapter.py`
- `core/wallet_creator.py`
- `core/wallet_integration.py`
- `core/wallet_manager.py`
- `core/wallet_system.py`
- `core/whale_tracker.py`

### 5.4 Trading & portfolio (50 files)

- `core/advanced_risk_manager.py`
- `core/autonomous_trading_orchestrator.py`
- `core/copy_trading.py`
- `core/copy_trading_orchestrator.py`
- `core/futures_trading_master.py`
- `core/market.py`
- `core/market_analysis.py`
- `core/market_analysis/__init__.py`
- `core/market_api.py`
- `core/market_api_methods.py`
- `core/market_data_streaming.py`
- `core/market_definitions.py`
- `core/market_stream.py`
- `core/marketapi.py`
- `core/portfolio_analytics.py`
- `core/portfolio_analytics/__init__.py`
- `core/portfolio_analytics_fix.py`
- `core/portfolio_analytics_new.py`
- `core/portfolio_manager.py`
- `core/prediction_market_connector.py`
- `core/quantum_trading_optimizer.py`
- `core/risk_assessment.py`
- `core/risk_assessment_core.py`
- `core/risk_management.py`
- `core/sentience/trading_sentience_integration.py`
- `core/strategy_marketplace.py`
- `core/strategy_marketplace_ai.py`
- `core/strategy_marketplace_handlers.py`
- `core/strategy_repository.py`
- `core/strategy_validator.py`
- `core/trading.py`
- `core/trading/__init__.py`
- `core/trading/quantum_ai_trader.py`
- `core/trading/trading_coordinator.py`
- `core/trading_bootstrap.py`
- `core/trading_calibration_monitor.py`
- `core/trading_funding_matrix.py`
- `core/trading_hub.py`
- `core/trading_intelligence.py`
- `core/trading_intelligence_enhancements.py`
- `core/trading_strategies.py`
- `core/trading_system.py`
- `core/trading_system_connector.py`
- `core/trading_system_integrator.py`
- `core/trading_timestamp_auto_fix.py`
- `core/trading_venue_status.py`
- `core/tradingsystem.py`
- `core/trillion_dollar_strategy.py`
- `core/unified_portfolio_manager.py`
- `core/unified_trading_analysis.py`

### 5.5 Mining (16 files)

- `core/mining.py`
- `core/mining/__init__.py`
- `core/mining/advanced_mining_manager.py`
- `core/mining/gpu_miners.py`
- `core/mining/hashrate_tracker.py`
- `core/mining/intelligent_optimizer.py`
- `core/mining/mining_dashboard.py`
- `core/mining/mining_system.py`
- `core/mining/quantum_pow_functions.py`
- `core/mining/sha256_ontology.py`
- `core/mining/stratum_client.py`
- `core/mining_dashboard.py`
- `core/mining_intelligence.py`
- `core/mining_system.py`
- `core/quantum_mining.py`
- `core/sentience/mining_sentience_integration.py`

### 5.6 Security, keys, QR, hardening (44 files)

- `core/api_key_broadcaster.py`
- `core/api_key_file_watcher.py`
- `core/api_key_manager.py`
- `core/api_key_manager.py.sentience_methods.py`
- `core/api_key_manager_connector.py`
- `core/api_keys.py`
- `core/biometric_security_manager.py`
- `core/code_sandbox.py`
- `core/secrets_loader.py`
- `core/security.py`
- `core/security/__init__.py`
- `core/security/_m.py`
- `core/security/advanced_hardening.py`
- `core/security/ambient_transcriber.py`
- `core/security/army_comms.py`
- `core/security/consumer_installer.py`
- `core/security/contact_manager.py`
- `core/security/creator_shield.py`
- `core/security/digital_trust.py`
- `core/security/duress_auth.py`
- `core/security/evidence_collector.py`
- `core/security/file_integrity.py`
- `core/security/hive_mind.py`
- `core/security/hostile_audio_detector.py`
- `core/security/hostile_visual_detector.py`
- `core/security/liveness_detector.py`
- `core/security/ml_anomaly_detector.py`
- `core/security/nlp_policy_evolver.py`
- `core/security/presence_monitor.py`
- `core/security/protection_flags.py`
- `core/security/protection_policy.py`
- `core/security/recovery_vault.py`
- `core/security/safe_haven.py`
- `core/security/secrets_vault.py`
- `core/security/silent_alarm.py`
- `core/security/threat_nlp_analyzer.py`
- `core/security/wellness_checker.py`
- `core/security_manager.py`
- `core/security_manager/__init__.py`
- `core/security_manager/api_key_manager.py`
- `core/security_manager/security_manager.py`
- `core/security_policy_manager.py`
- `core/securitymanager.py`
- `core/sentience/api_key_sentience_integration.py`

### 5.7 Voice + comms (18 files)

- `core/always_on_voice.py`
- `core/comms_call_backend.py`
- `core/comms_rf_backend.py`
- `core/dynamic_event_bus.py`
- `core/dynamic_renderer.py`
- `core/secure_comms.py`
- `core/thoth_voice_handlers.py`
- `core/universal_comms_system.py`
- `core/voice.py`
- `core/voice/__init__.py`
- `core/voice/text_to_speech.py`
- `core/voice/voice_recognition.py`
- `core/voice_cloner_integration.py`
- `core/voice_command_manager.py`
- `core/voice_integration.py`
- `core/voice_manager.py`
- `core/voice_processing_system.py`
- `core/voice_runtime.py`

### 5.8 Vision / VR / video (12 files)

- `core/device_framework_manager.py`
- `core/health/health_anomaly_detector.py`
- `core/mass_framework.py`
- `core/sentience/vr_sentience_integration.py`
- `core/vision_service.py`
- `core/vl_jepa/vision_encoder.py`
- `core/vr_ai_interface.py`
- `core/vr_headset_streamer.py`
- `core/vr_integration.py`
- `core/vr_print_export.py`
- `core/vr_sota_2026_integration.py`
- `core/vr_system.py`

### 5.9 Device / hardware / HAL (8 files)

- `core/device_brain_controller.py`
- `core/device_logbook.py`
- `core/device_registry.py`
- `core/device_takeover_system.py`
- `core/host_device_manager.py`
- `core/network_device_control.py`
- `core/sentience/hardware_awareness.py`
- `core/universal_device_flasher.py`

### 5.10 Code generation (3 files)

- `core/code_generator.py`
- `core/nemoclaw_bridge.py`
- `core/nemoclaw_integration_setup.py`

### 5.11 Data I/O + persistence (3 files)

- `core/database_manager.py`
- `core/intelligent_storage_orchestrator.py`
- `core/persistence_manager.py`

### 5.12 UI support (non-tab) (9 files)

- `core/gui_ai_integration.py`
- `core/gui_demo.py`
- `core/gui_initializer.py`
- `core/gui_manager.py`
- `core/sota_2026_tab_integration.py`
- `core/styles.py`
- `core/tab_highway_system.py`
- `core/thoth_gui_integration.py`
- `core/windows_host_bridge.py`

### 5.13 Runtime + event loop + scheduler (13 files)

- `core/async_support.py`
- `core/async_task_manager.py`
- `core/event_bus.py`
- `core/event_bus_connector.py`
- `core/event_bus_patch.py`
- `core/event_bus_sota_2026.py`
- `core/event_bus_wrapper.py`
- `core/event_loop_manager.py`
- `core/gpu_scheduler.py`
- `core/kaig_runtime_config.py`
- `core/runtime_resource_orchestrator.py`
- `core/task_manager.py`
- `core/unity_runtime_bridge.py`

### 5.14 Misc / cross-cutting (211 files)

- `core/__init__.py`
- `core/adversarial_validation.py`
- `core/api_connection_tester.py`
- `core/api_connector.py`
- `core/api_mega_loader.py`
- `core/audio_adapter.py`
- `core/base_component.py`
- `core/base_component_v2.py`
- `core/base_tab.py`
- `core/book_data_manager.py`
- `core/booktok_aggregator.py`
- `core/booktok_context_aggregator.py`
- `core/cinema_engine_sota_2026.py`
- `core/codebase_indexer.py`
- `core/codebase_introspector.py`
- `core/colored_logging.py`
- `core/communication_capabilities.py`
- `core/compat/__init__.py`
- `core/compat/cryptography_wrapper.py`
- `core/component_connector.py`
- `core/component_helper.py`
- `core/component_manager.py`
- `core/component_mapping.py`
- `core/component_registry.py`
- `core/config.py`
- `core/config_manager.py`
- `core/config_manager_proxy.py`
- `core/configmanager.py`
- `core/conformal.py`
- `core/connection_manager.py`
- `core/continuous_response.py`
- `core/continuous_response_generator.py`
- `core/cql_cvar_policy.py`
- `core/crash_recovery_system.py`
- `core/crash_recovery_watchdog.py`
- `core/creation_orchestrator.py`
- `core/creator_install_server.py`
- `core/cross_platform_arbitrage.py`
- `core/cross_venue_transfer_manager.py`
- `core/crypto_loader.py`
- `core/data_pipeline.py`
- `core/enhanced_learning_system_sota_2026.py`
- `core/enhanced_logging.py`
- `core/env_manager.py`
- `core/environment_integration.py`
- `core/environment_manager.py`
- `core/error_resolution.py`
- `core/error_resolution_system.py`
- `core/error_tracker.py`
- `core/event_catalog.py`
- `core/event_handlers.py`
- `core/event_handlers_fix.py`
- `core/exchange_time_sync.py`
- `core/exchange_universe.py`
- `core/file_manager.py`
- `core/full_connectivity_report.py`
- `core/funding_rate_arbitrage.py`
- `core/genie3_world_model.py`
- `core/global_poa_patch.py`
- `core/gpu_quantum_integration.py`
- `core/guimanager.py`
- `core/health/__init__.py`
- `core/health/ble_manager.py`
- `core/health/health_advisor.py`
- `core/health/wearable_hub.py`
- `core/health_check.py`
- `core/hft_communication.py`
- `core/high_speed_pipeline.py`
- `core/initialization_tracker.py`
- `core/install_advisor.py`
- `core/intent.py`
- `core/intent_recognition.py`
- `core/kaig_autopilot.py`
- `core/kaig_intelligence_bridge.py`
- `core/kaig_token_identity.py`
- `core/kingdom_ai_brain.py`
- `core/kingdom_brain_orchestrator.py`
- `core/kingdom_component_connector.py`
- `core/kingdom_config_loader.py`
- `core/kingdom_event_names.py`
- `core/kingdom_logging.py`
- `core/kingdom_paths.py`
- `core/kingdom_system.py`
- `core/kingdom_system_registry.py`
- `core/knowledge_aggregator.py`
- `core/learning_orchestrator.py`
- `core/liquidity_analyzer.py`
- `core/live_autotrade_policy.py`
- `core/live_creative_studio.py`
- `core/live_data_integrator.py`
- `core/loading_orchestrator.py`
- `core/logger.py`
- `core/logging_manager.py`
- `core/manifesto.py`
- `core/master_orchestrator_v3.py`
- `core/master_system_integrator.py`
- `core/mcp_connector.py`
- `core/ml_env_loader.py`
- `core/mobile_sync_server.py`
- `core/moonshot_integration.py`
- `core/multimodal_web_scraper_sota_2026.py`
- `core/natural_language_transfer_router.py`
- `core/network_manager.py`
- `core/nexus/__init__.py`
- `core/nexus/redis_quantum_nexus.py`
- `core/nexus/validate_redis_connection.py`
- `core/nlp.py`
- `core/nltk_fix.py`
- `core/numpy_compatibility.py`
- `core/online_rl_trainer.py`
- `core/options_hedger.py`
- `core/order_management.py`
- `core/paper_autotrade_orchestrator.py`
- `core/placeholder_generator.py`
- `core/plaid_ach_bridge.py`
- `core/position_monitor.py`
- `core/position_sizing.py`
- `core/prediction.py`
- `core/prompt_guard.py`
- `core/quantum.py`
- `core/quantum_enhancement_bridge.py`
- `core/quantum_nexus_enforcer.py`
- `core/quantum_nexus_initializer.py`
- `core/real_exchange_executor.py`
- `core/real_stock_executor.py`
- `core/realtime_creative_studio.py`
- `core/redis_channels.py`
- `core/redis_client.py`
- `core/redis_connection.py`
- `core/redis_connector.py`
- `core/redis_connector_corrupted.py`
- `core/redis_fallback.py`
- `core/redis_manager.py`
- `core/redis_nexus.py`
- `core/redis_quantum_funding_tracker.py`
- `core/redis_quantum_manager.py`
- `core/redis_quantum_nexus.py`
- `core/resilience_patterns.py`
- `core/resource_cleanup_manager.py`
- `core/resource_monitor.py`
- `core/secure_transactions.py`
- `core/self_healing_supervisor.py`
- `core/sentience/__init__.py`
- `core/sentience/base.py`
- `core/sentience/consciousness_field.py`
- `core/sentience/frequency_432.py`
- `core/sentience/integrated_information.py`
- `core/sentience/live_data_connector.py`
- `core/sentience/monitor.py`
- `core/sentience/quantum_consciousness.py`
- `core/sentience/self_model.py`
- `core/sentience/self_model_system.py`
- `core/sentience/settings_sentience_integration.py`
- `core/sentience/thoth_integration.py`
- `core/serial_port_manager.py`
- `core/session_manager.py`
- `core/settings.py`
- `core/signal_analyzer.py`
- `core/sleep_manager.py`
- `core/smart_contracts.py`
- `core/software_automation_manager.py`
- `core/sota_2026_integration.py`
- `core/storyboard_planner.py`
- `core/stratum_protocol.py`
- `core/system_context_provider.py`
- `core/system_knowledge_loader.py`
- `core/system_profile.py`
- `core/system_stability_manager.py`
- `core/system_state_manager.py`
- `core/system_updater.py`
- `core/telemetry_collector.py`
- `core/thoth.py`
- `core/thoth.py.sentience_methods.py`
- `core/thoth_ai_handlers.py`
- `core/thoth_extensions.py`
- `core/thoth_fixes.py`
- `core/thoth_integration.py`
- `core/thoth_live_integration.py`
- `core/thoth_wrapper.py`
- `core/thothai.py`
- `core/truth_seeker.py`
- `core/truth_timeline_data.py`
- `core/twilio_manager.py`
- `core/twilio_webhook_server.py`
- `core/unified_ai_router.py`
- `core/unified_creation_orchestrator.py`
- `core/unity_connector.py`
- `core/unity_mcp_integration.py`
- `core/universal_data_aggregator.py`
- `core/universal_data_display.py`
- `core/universal_data_visualizer.py`
- `core/universal_software_controller.py`
- `core/user_identity.py`
- `core/username_registry.py`
- `core/utils.py`
- `core/utils/__init__.py`
- `core/utils/crypto.py`
- `core/version_info.py`
- `core/visual_ai_manager.py`
- `core/visualization.py`
- `core/vl_jepa/__init__.py`
- `core/vl_jepa/core.py`
- `core/vl_jepa/integration.py`
- `core/vl_jepa/predictor_network.py`
- `core/vl_jepa/text_encoder.py`
- `core/vr.py`
- `core/web3_connector.py`
- `core/web_mcp_integration.py`
- `core/web_scraper.py`
- `core/wisdom_gatherer.py`
- `core/wsl_audio_bridge.py`

---

## 6. Tests — 65 files

- `tests/__init__.py`
- `tests/_probe_bus.py`
- `tests/conftest.py`
- `tests/detect_gpus.py`
- `tests/enhanced_logging_system.py`
- `tests/gui_integration_test (1).py`
- `tests/gui_integration_test.py`
- `tests/gui_verification_framework.py`
- `tests/gui_verifier.py`
- `tests/integration_test.py`
- `tests/mocks/gui/qt_frames/trading/widgets/__init__.py`
- `tests/nl_transfer.py`
- `tests/nl_transfer_sweep.py`
- `tests/performance/run_perf_tests.py`
- `tests/performance/run_unittest.py`
- `tests/preload_model.py`
- `tests/print_funding_matrix.py`
- `tests/run_kingdom_system_tests.py`
- `tests/temp/__init__.py`
- `tests/test_all_new_modules_runtime.py`
- `tests/test_code_generator_integration.py`
- `tests/test_compile_sanity.py`
- `tests/test_creation_canvas_e2e.py`
- `tests/test_data/api_key_generator.py`
- `tests/test_data/code_generator.py`
- `tests/test_data/dashboard_generator.py`
- `tests/test_data/data_generator_factory.py`
- `tests/test_data/generator_base.py`
- `tests/test_data/mining_generator.py`
- `tests/test_data/settings_generator.py`
- `tests/test_data/thoth_generator.py`
- `tests/test_data/trading_generator.py`
- `tests/test_data/voice_generator.py`
- `tests/test_data/vr_generator.py`
- `tests/test_data/wallet_generator.py`
- `tests/test_dictionary_brain.py`
- `tests/test_full_kingdom_system.py`
- `tests/test_gemini_agent_integration.py`
- `tests/test_gui_headless_smoke.py`
- `tests/test_gui_live_buttons.py`
- `tests/test_inference_stack.py`
- `tests/test_live_hardware_skipped.py`
- `tests/test_mining_intelligence.py`
- `tests/test_redis_nexus_optional.py`
- `tests/test_startup_e2e.py`
- `tests/test_trading_readiness.py`
- `tests/test_unified_brain_router.py`
- `tests/test_unified_system_runtime.py`
- `tests/test_visualization.py`
- `tests/test_wallet_backend.py`
- `tests/test_wallet_integration.py`
- `tests/test_wallet_trading_integration.py`
- `tests/trading_tab_live_data_harness.py`
- `tests/verifiers/api_key_verifier.py`
- `tests/verifiers/base_verifier.py`
- `tests/verifiers/code_generator_verifier.py`
- `tests/verifiers/dashboard_verifier.py`
- `tests/verifiers/mining_verifier.py`
- `tests/verifiers/settings_verifier.py`
- `tests/verifiers/thoth_ai_verifier.py`
- `tests/verifiers/trading_verifier.py`
- `tests/verifiers/voice_verifier.py`
- `tests/verifiers/vr_verifier.py`
- `tests/verifiers/wallet_verifier.py`
- `tests/vr_frame_test.py`

### 6.1 Latest run

- `tests/test_dictionary_brain.py` — **31 / 31 pass**
- `tests/test_inference_stack.py`  — **32 / 32 pass**
- `tests/test_unified_brain_router.py` — **14 / 14 pass**
- `tests/test_compile_sanity.py` — **clean**

**Aggregate: 77 / 77 assertions green, zero silent exceptions.**

---

## 7. Top-level entry points (514 Python files at repo root)

- `3keys.py` — —
- `4keys.py` — —
- `COMPLETE_TAB_INTEGRATION_SCRIPT.py` — —
- `COMPLETE_TAB_VERIFICATION.py` — —
- `COMPLETE_TRADING_INTELLIGENCE_ANALYSIS.py` — —
- `CONTINUOUS_MARKET_MONITORING_SYSTEM.py` — —
- `KINGDOM_AI_MASTER_INTEGRATION.py` — —
- `UPDATED_RPC_ENDPOINTS_2024.py` — —
- `__init__.py` — —
- `_check_btc.py` — —
- `_check_wallet.py` — —
- `_execute_cleanup.py` — —
- `_find_btc_address.py` — —
- `_live_verification.py` — —
- `_live_verification_v2.py` — —
- `_netlify_cleanup.py` — —
- `_runtime_trading_analysis.py` — —
- `_test_codegen.py` — —
- `activate_futures_trading.py` — —
- `activate_mining_trading.py` — —
- `add_api_listeners_all_tabs.py` — —
- `add_blockchain_indicators.py` — —
- `add_except_block.py` — —
- `add_except_block_line161.py` — —
- `add_key_features.py` — —
- `add_mock_path.py` — —
- `advanced_ai_strategies.py` — —
- `ai_safety.py` — —
- `analyze_full_codebase.py` — —
- `analyze_huge_file.py` — —
- `analyze_indentation.py` — —
- `analyze_runtime_files.py` — —
- `api_key_validator.py` — —
- `apply_component_factory_all_tabs.py` — —
- `audio_library_installer.py` — —
- `auto_device_control.py` — —
- `auto_start_camera_server.py` — —
- `backup_4keys_working.py` — —
- `backup_verification.py` — —
- `balance_quotes.py` — —
- `base_component.py` — —
- `base_component_new.py` — —
- `black_panther_bluetooth.py` — —
- `black_panther_greeting.py` — —
- `black_panther_voice.py` — —
- `black_panther_voice_cloner.py` — —
- `blockchain_manager.py` — —
- `brio_mjpeg_server.py` — —
- `build_kingdom_ai_system_book_pdf.py` — —
- `build_redis_quantum_nexus.py` — —
- `chart_manager.py` — —
- `chat_kingdom.py` — —
- `chat_with_voice.py` — —
- `check_dependencies.py` — —
- `check_deployment.py` — —
- `check_env.py` — —
- `check_environment_safety.py` — —
- `check_envs.py` — —
- `check_librosa.py` — —
- `check_main_window_files.py` — —
- `check_missing_packages.py` — —
- `check_ollama_version.py` — —
- `check_redis_config.py` — —
- `check_redis_status.py` — —
- `clean_all_string_artifacts.py` — —
- `clean_docstring.py` — —
- `clean_duplicate_method.py` — —
- `clean_function.py` — —
- `clean_init_method.py` — —
- `clean_installer_logs.py` — —
- `cleanup_kingdom_ai.py` — —
- `cleanup_main_window_variants.py` — —
- `cleanup_unused_files.py` — —
- `code_generator_analysis.py` — —
- `code_generator_core.py` — —
- `code_generator_thoth_integration.py` — —
- `codegen_core_methods.py` — —
- `codegen_event_handlers.py` — —
- `codegen_tab_init.py` — —
- `complete_kingdom_reset.py` — —
- `component_manager.py` — —
- `component_validator.py` — —
- `comprehensive_network_validator.py` — —
- `comprehensive_restoration.py` — —
- `config_manager.py` — —
- `connect_quest3.py` — —
- `connect_to_pool_method.py` — —
- `connect_web3_to_redis_quantum.py` — —
- `connection_manager.py` — —
- `copy_trader.py` — —
- `copy_trading_integration.py` — —
- `copy_trading_standalone.py` — —
- `count_networks.py` — —
- `create_components.py` — —
- `create_dirs.py` — —
- `create_icons.py` — —
- `creation_engine_service.py` — —
- `cUsersYeyian PCDocumentsPython ScriptsNew folderhelper_functions.py` — —
- `dashboard_core_methods.py` — —
- `dashboard_event_handlers.py` — —
- `dashboard_status_update.py` — —
- `dashboard_tab_init.py` — —
- `demo_dashboard_tabs.py` — —
- `demo_mining_tab.py` — —
- `demo_nodes_connected.py` — —
- `demo_voice_cloning.py` — —
- `demo_voice_play.py` — —
- `detect_real_duplicates.py` — —
- `device_auto_watcher.py` — —
- `diagnose_camera_setup.py` — —
- `diagnose_eventbus.py` — —
- `diagnose_issues.py` — —
- `diagnose_numpy_compatibility.py` — —
- `diagnose_syntax.py` — —
- `direct_bluetooth_play.py` — —
- `direct_code_replace.py` — —
- `direct_kingdom_restore.py` — —
- `docstring_checker.py` — —
- `embed_ollama_connector.py` — —
- `ensure_voice_output.py` — —
- `event_bus.py` — —
- `event_bus_patch.py` — —
- `event_bus_validator.py` — —
- `exact_restore.py` — —
- `exact_whitespace_analysis.py` — —
- `examine_context.py` — —
- `examine_structure.py` — —
- `exchange_key_diagnostic.py` — —
- `extract_redis_data.py` — —
- `fast_kingdom_deduplicator.py` — —
- `final_kingdom_solution.py` — —
- `final_network_count.py` — —
- `final_thoth_solution.py` — —
- `find_except.py` — —
- `find_quest3_wireless.py` — —
- `find_syntax_error.py` — —
- `find_unclosed_docstring.py` — —
- `find_web3_async_http_imports.py` — —
- `fix_trading_system_part1.py` — —
- `fix_trading_system_part2.py` — —
- `fix_trading_system_strategies.py` — —
- `flash_firmware_now.py` — —
- `force_launch.py` — —
- `force_try_content.py` — —
- `full_blockchain_verification.py` — —
- `generate_kingdom_ai_tree.py` — —
- `generate_reference_audio.py` — —
- `global_api_keys.py` — —
- `handlers_to_add.py` — —
- `hex_dump.py` — —
- `improve_voice_quality.py` — —
- `improved_black_panther.py` — —
- `init_all_fixes.py` — —
- `initialize_complete_sota_2026.py` — —
- `initialize_intelligent_storage.py` — —
- `initialize_sota_2026_systems.py` — —
- `initialize_thoth_live.py` — —
- `install_missing_packages.py` — —
- `integrate_black_panther_voice.py` — —
- `integrate_kingdom_ai.py` — —
- `integrate_trading_intelligence.py` — —
- `intent_recognition_integration.py` — —
- `interactive_voice_creation.py` — —
- `jax_compat.py` — —
- `jax_config.py` — —
- `keys2kingdom.py` — —
- `keys2kingdom.py.reconstructed.py` — —
- `king_zilla_greeting.py` — —
- `kingdom_ai.py` — —
- `kingdom_ai_brain_integrator.py` — —
- `kingdom_ai_brain_integrator_v2.py` — —
- `kingdom_ai_brain_integrator_v3.py` — —
- `kingdom_ai_complete_restore.py` — —
- `kingdom_ai_component_scanner.py` — —
- `kingdom_ai_component_scanner_main.py` — —
- `kingdom_ai_component_scanner_part2.py` — —
- `kingdom_ai_consumer.py` — **Consumer Desktop launcher** — MODE=consumer, PLATFORM=desktop, full stack, no creator keys/data.
- `kingdom_ai_fixed.py` — —
- `kingdom_ai_full_restore.py` — —
- `kingdom_ai_launcher.py` — —
- `kingdom_ai_master_restore.py` — —
- `kingdom_ai_perfect.py` — Legacy PyQt6 creator launcher (kept as fallback).
- `kingdom_ai_perfect_v2.py` — **Creator Desktop launcher** — sets MODE=creator, PLATFORM=desktop, full stack + creator keys.
- `kingdom_ai_setup.py` — —
- `kingdom_ai_soul.py` — —
- `kingdom_ai_system_integrator.py` — —
- `kingdom_ai_unified_new.py` — —
- `kingdom_ai_verification.py` — —
- `kingdom_analytics_engine.py` — —
- `kingdom_api_gateway.py` — —
- `kingdom_blockchain_connector_core.py` — —
- `kingdom_bridge.py` — —
- `kingdom_clean_template.py` — —
- `kingdom_cleanup.py` — —
- `kingdom_complete_builder.py` — —
- `kingdom_complete_init.py` — —
- `kingdom_complete_integration.py` — —
- `kingdom_complete_integrator.py` — —
- `kingdom_complete_rebuild.py` — —
- `kingdom_complete_solution.py` — —
- `kingdom_config_manager.py` — —
- `kingdom_connector.py` — —
- `kingdom_context_awareness.py` — —
- `kingdom_core_rebuild.py` — —
- `kingdom_data_manager.py` — —
- `kingdom_deep_analysis.py` — —
- `kingdom_dependency_install.py` — —
- `kingdom_diagnostic.py` — —
- `kingdom_direct_line_editor.py` — —
- `kingdom_direct_replacement.py` — —
- `kingdom_direct_solution.py` — —
- `kingdom_env_manager.py` — —
- `kingdom_environment.py` — —
- `kingdom_error_handler.py` — —
- `kingdom_event_processor.py` — —
- `kingdom_factory_add.py` — —
- `kingdom_final_connector.py` — —
- `kingdom_final_gui_solution.py` — —
- `kingdom_final_indentation_cleanup.py` — —
- `kingdom_final_integration.py` — —
- `kingdom_final_launcher.py` — —
- `kingdom_final_resolver.py` — —
- `kingdom_final_solution.py` — —
- `kingdom_final_solution_28apr.py` — —
- `kingdom_fresh.py` — —
- `kingdom_full_restore.py` — —
- `kingdom_fullrestore.py` — —
- `kingdom_greeting.py` — —
- `kingdom_gui_complete_bridge.py` — —
- `kingdom_gui_display_bridge.py` — —
- `kingdom_gui_guaranteed.py` — —
- `kingdom_gui_launcher.py` — —
- `kingdom_gui_windows.py` — —
- `kingdom_headless.py` — —
- `kingdom_indentation_final_solution.py` — —
- `kingdom_indentation_guardian.py` — —
- `kingdom_initialize_all.py` — —
- `kingdom_initializer.py` — —
- `kingdom_integration.py` — —
- `kingdom_integration_core.py` — —
- `kingdom_integration_final.py` — —
- `kingdom_integration_launcher.py` — —
- `kingdom_integration_part1.py` — —
- `kingdom_integration_part1_core.py` — —
- `kingdom_integration_part2_ai.py` — —
- `kingdom_integration_part3_trading.py` — —
- `kingdom_integration_part4_blockchain.py` — —
- `kingdom_integration_part5_vr.py` — —
- `kingdom_integration_runner.py` — —
- `kingdom_integration_solution.py` — —
- `kingdom_integrator.py` — —
- `kingdom_integrator_chunked.py` — —
- `kingdom_issue_analysis.py` — —
- `kingdom_launch_safe.py` — —
- `kingdom_launcher.py` — —
- `kingdom_logging_manager.py` — —
- `kingdom_main.py` — Older unified main (creator-default).
- `kingdom_market_data_core.py` — —
- `kingdom_master_integration.py` — —
- `kingdom_master_integrator.py` — —
- `kingdom_master_restore.py` — —
- `kingdom_metacognition_bridge.py` — —
- `kingdom_ml_engine_core.py` — —
- `kingdom_ml_global.py` — —
- `kingdom_monitor.py` — —
- `kingdom_multi_chain_ai.py` — —
- `kingdom_nlp_processor.py` — —
- `kingdom_notification_manager.py` — —
- `kingdom_polish.py` — —
- `kingdom_portfolio_manager_core.py` — —
- `kingdom_preserve_all_components.py` — —
- `kingdom_python_compiler.py` — —
- `kingdom_quick_init.py` — —
- `kingdom_readiness.py` — —
- `kingdom_readiness_100.py` — —
- `kingdom_rebuild.py` — —
- `kingdom_rebuild_clean.py` — —
- `kingdom_reset.py` — —
- `kingdom_restoration.py` — —
- `kingdom_restore.py` — —
- `kingdom_risk_analyzer.py` — —
- `kingdom_safe_integration.py` — —
- `kingdom_safe_launch.py` — —
- `kingdom_security_manager.py` — —
- `kingdom_simple_solution.py` — —
- `kingdom_syntax_cleaner.py` — —
- `kingdom_syntax_resolver.py` — —
- `kingdom_syntax_validator.py` — —
- `kingdom_system.py` — —
- `kingdom_system_monitor.py` — —
- `kingdom_system_nexus_connector.py` — —
- `kingdom_system_restore.py` — —
- `kingdom_system_verifier.py` — —
- `kingdom_task_scheduler.py` — —
- `kingdom_trading_adapter.py` — —
- `kingdom_trading_connector.py` — —
- `kingdom_trading_engine_core.py` — —
- `kingdom_trading_strategy_core.py` — —
- `kingdom_ui_base.py` — —
- `kingdom_ui_loading_screen.py` — —
- `kingdom_ultimate_solution.py` — —
- `kingdom_voice_bluetooth.py` — —
- `kingdom_voice_brain_service.py` — —
- `kingdom_voice_cloner_redis.py` — —
- `kingdom_voice_cloner_xtts.py` — —
- `kingdom_voice_edge_tts.py` — —
- `kingdom_voice_gptsovits.py` — —
- `kingdom_voice_xtts.py` — —
- `kingdom_vr_core.py` — —
- `kingdom_wallet_manager_core.py` — —
- `kingdom_windows_gui.py` — —
- `kingdomai_runner.py` — —
- `kingdomgui_integrator.py` — —
- `kingdomkeys.direct.py` — —
- `kingdomkeys.new.py` — —
- `kingdomkeys.py` — —
- `kingdomkeys.temp.py` — —
- `kingdomkeys_clean.py` — —
- `kingdomkeys_complete_rebuild.py` — —
- `kingdomkeys_minimal.py` — —
- `kingdomkeys_original.py` — —
- `kingdomkeys_rebuild.py` — —
- `kingdomkeys_rebuilt.py` — —
- `kingdomkeys_standalone.py` — —
- `kingdomkeys_updated.py` — —
- `kingdomkeys_updated2.py` — —
- `kingdomweb3_v2.py` — —
- `launch_kingdom.py` — —
- `launch_kingdom_clean.py` — —
- `launch_kingdom_updated.py` — —
- `line_by_line_analysis.py` — —
- `lint_tab_manager.py` — —
- `live_voice_ollama_creation.py` — —
- `loading_screen.py` — —
- `log_monitor.py` — —
- `main.py` — —
- `market_analyzer.py` — —
- `market_analyzer_new.py` — —
- `market_data_provider.py` — —
- `meme_coin_analyzer.py` — —
- `meme_coin_interaction.py` — —
- `meta_learning_integration.py` — —
- `meta_learning_system.py` — —
- `minimal_deduplicator.py` — —
- `mining_dashboard.py` — —
- `mining_dashboard_driver.py` — —
- `mining_dashboard_integration.py` — —
- `mining_dashboard_standalone.py` — —
- `ml_venv_importer.py` — —
- `modify_4keys_directly.py` — —
- `monitor_status.py` — —
- `moonshot_integration.py` — —
- `network_count_check.py` — —
- `normalize_all_indentation.py` — —
- `numpy_binary_override.py` — —
- `numpy_compatibility_loader.py` — —
- `ollama_device_control.py` — —
- `ollama_starter.py` — —
- `order_manager.py` — —
- `organize_kingdom_ai.py` — —
- `package_installer.py` — —
- `patch_rich.py` — —
- `perfect_black_panther.py` — —
- `performance_manager.py` — —
- `platform_manager.py` — —
- `play_bluetooth_exact.py` — —
- `play_bp_sample.py` — —
- `play_generated_voice.py` — —
- `play_to_bluetooth.py` — —
- `portfolio_analytics_adapter.py` — —
- `portfolio_manager.py` — —
- `prediction_engine_integration.py` — —
- `preflight_check.py` — —
- `quantum_enhanced_strategies.py` — —
- `quick_count.py` — —
- `real_visual_creation.py` — —
- `real_voice_unity_creation.py` — —
- `rebuild_kingdom.py` — —
- `rebuild_kingdomkeys.py` — —
- `rebuild_ultimate_kingdom.py` — —
- `rebuilt_kingdomkeys.py` — —
- `redis_package_data.py` — —
- `redis_password_finder.py` — —
- `redis_quantum_nexus_starter.py` — —
- `redis_quantum_package_provider.py` — —
- `redis_video_service.py` — —
- `redis_voice_service.py` — —
- `remove_duplicate.py` — —
- `remove_problematic_try.py` — —
- `remove_testnets.py` — —
- `replace_dummy_tk.py` — —
- `replace_files.py` — —
- `rewrite_function.py` — —
- `risk_manager.py` — —
- `rug_sniffer_ai.py` — —
- `run_audio_tests.py` — —
- `run_black_panther_greeting.py` — —
- `run_blockchain_integration.py` — —
- `run_deployment_check.py` — —
- `run_e2e_tests.py` — —
- `run_gui_tests.py` — —
- `run_gui_verification.py` — —
- `run_kingdom_guardian.py` — —
- `run_kingdom_system_tests.py` — —
- `run_ollama_auto_update.py` — —
- `run_vr_frame_tests.py` — —
- `runtime_method_injection.py` — —
- `security_manager.py` — —
- `security_manager_integration.py` — —
- `set_redis_available_true.py` — —
- `setup.py` — —
- `simple_bp_greeting.py` — —
- `simple_camera_server.py` — —
- `simple_ollama_connector.py` — —
- `simple_thoth_connector.py` — —
- `sitecustomize.py` — —
- `smart_contract.py` — —
- `start_kingdom.py` — —
- `start_redis.py` — —
- `start_redis_connection.py` — —
- `start_redis_if_needed.py` — —
- `start_redis_server.py` — —
- `start_webcam_server.py` — —
- `strategy_coordinator.py` — —
- `strategy_implementations.py` — —
- `strategy_manager.py` — —
- `strategy_marketplace_integration.py` — —
- `strategy_marketplace_standalone.py` — —
- `streamlined_black_panther.py` — —
- `stress_testing.py` — —
- `suppress_alsa.py` — —
- `sync_redis_config.py` — —
- `syntax_check_new.py` — —
- `syntax_checker.py` — —
- `system_dependencies.py` — —
- `system_integration_complete.py` — —
- `system_readiness_checks.py` — —
- `tab_integration_master.py` — —
- `tab_manager_method_cleanup.py` — —
- `test_all_imports.py` — —
- `test_creation_env.py` — —
- `test_dashboard_tab.py` — —
- `test_fabrication_pipeline.py` — —
- `test_focus_window.py` — —
- `test_full_voice_path.py` — —
- `test_gui_only.py` — —
- `test_kingdom_fixes.py` — —
- `test_main_window.py` — —
- `test_minimal_gui.py` — —
- `test_minimal_working_gui.py` — —
- `test_multi_screen.py` — —
- `test_play_voice_now.py` — —
- `test_pyqt6_display.py` — —
- `test_trading_tab.py` — —
- `test_video_pipeline.py` — —
- `test_voice_quick.py` — —
- `test_window_position.py` — —
- `tester.py` — —
- `testing_framework.py` — —
- `thoth_connector.py` — —
- `thoth_integration_main_part1.py` — —
- `thoth_integration_main_part2.py` — —
- `thoth_mcp.py` — —
- `time_series_transformer.py` — —
- `time_series_transformer_class_alias.py` — —
- `total_rebuild.py` — —
- `trading_environment.py` — —
- `trading_frame_additions.py` — —
- `trading_frame_redis_init.py` — —
- `trading_hub.py` — —
- `trading_system_code_generator.py` — —
- `trading_tab_init_method.py` — —
- `train_xtts_voice.py` — —
- `truncate_file.py` — —
- `tts_subprocess_worker.py` — —
- `ultimate_black_panther.py` — —
- `ultimate_numpy_solution.py` — —
- `universal_ollama_brain.py` — —
- `update_audio_system.py` — —
- `update_compatibility.py` — —
- `update_dashboard_direct.py` — —
- `update_mining_tab.py` — —
- `update_redis_config.py` — —
- `update_trading_tab.py` — —
- `use_existing_kingdom_ai.py` — —
- `validate_creation_wiring.py` — —
- `validate_kingdom_ai.py` — —
- `validate_restoration.py` — —
- `verify_creation_env.py` — —
- `verify_creation_env_quick.py` — —
- `verify_installation.py` — —
- `verify_unity_hub_integration.py` — —
- `voice_cloning.py` — —
- `voice_refinement.py` — —
- `voice_test_no_numba.py` — —
- `vr_core_methods.py` — —
- `vr_event_handlers.py` — —
- `vr_frame_methods.py` — —
- `vr_interface.py` — —
- `wallet_backend.py` — —
- `wallet_frame_wrapper.py` — —
- `wallet_integrations.py` — —
- `wallet_manager.py` — —
- `web3_connector.py` — —
- `websocket_manager.py` — —
- `websocket_server.py` — —
- `whale_tracker.py` — —
- `whitespace_analyzer.py` — —
- `whitespace_checker.py` — —
- `windsurf_kingdom_ai_setup.py` — —
- `working_live_interface.py` — —
- `wsl_environment.py` — —
- `wsl_runtime_manager.py` — —
- `xtts_continuous_learning.py` — —

Mobile launchers live under `mobile/` and `mobile_build/`:

- `mobile/kingdom_mobile_creator.py`          — Creator Mobile (MODE=creator, PLATFORM=mobile, light tier).
- `mobile/kingdom_mobile_consumer.py`         — Consumer Mobile (MODE=consumer, PLATFORM=mobile, light tier).
- `mobile_build/kingdom_mobile_creator.py`    — Buildozer/Kivy launcher for APK (creator).
- `mobile_build/kingdom_mobile_consumer.py`   — Buildozer/Kivy launcher for APK (consumer).
- `mobile_build/main.py`                      — Shared APK entry point (sets PLATFORM=mobile).

---

## 8. Platform × Role matrix (the "four quadrants")

| Quadrant | Role | Platform | Tier | Launcher |
|---|---|---|---|---|
| 1 | Creator  | Desktop | **Full** (TRT-LLM → vLLM → Ollama → Cloud, 64-bit embeddings) | `kingdom_ai_perfect_v2.py` |
| 2 | Consumer | Desktop | **Full** (same as creator, minus creator keys/data)            | `kingdom_ai_consumer.py`   |
| 3 | Creator  | Mobile  | **Light** (Ollama-only, int8 embeddings, offline model)        | `mobile/kingdom_mobile_creator.py` |
| 4 | Consumer | Mobile  | **Light** (same as creator-mobile, minus creator keys/data)    | `mobile/kingdom_mobile_consumer.py` |

Tier is driven **only** by `KINGDOM_APP_PLATFORM`. Role is driven **only**
by `KINGDOM_APP_MODE`. The two are independent — fixing the historical
bug where consumer desktop was incorrectly downgraded to the mobile
light tier.

---

## 9. Environment variables that steer the bootstrap

| Variable | Values | Effect |
|---|---|---|
| `KINGDOM_APP_MODE`     | `creator` / `consumer` | Unlocks creator keys, data dirs, private tabs. |
| `KINGDOM_APP_PLATFORM` | `desktop` / `mobile`   | Selects full vs light inference tier. |
| `KINGDOM_DISABLE_TRT`  | `1` / unset            | Skips TensorRT-LLM probe. |
| `KINGDOM_DISABLE_VLLM` | `1` / unset            | Skips vLLM probe. |
| `TF_CPP_MIN_LOG_LEVEL` | `3` (default)          | Silences TensorFlow warnings from `tf-keras` shim. |

---

## 10. Verification status

- ✔ Every Python file Kingdom-authored (1,782 files) compiles.
- ✔ 77/77 test assertions pass.
- ✔ All 9 launchers carry the correct `MODE` + `PLATFORM` env pair.
- ✔ UnifiedBrainRouter wired into both desktop launchers.
- ✔ Dictionary methods registered as Ollama tools on startup.
- ✔ Four-quadrant matrix verified via `tests/test_inference_stack.py`
     routing-table regression guard.
- ⏳ Pending: consumer secret-scan, Easy-Store backup, GitHub push,
     Netlify deploy (awaiting final green-light per plan).

---

_End of audit._
