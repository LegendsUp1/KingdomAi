# 82+ Mineable Coins and Wallets – Data Locations

All data for **82+ mineable PoW coins** and their **wallets** is loaded from these config files. MiningSystem and the Mining tab use them for real mining operations.

---

## 1. Mineable coins (82 PoW blockchains)

**File:** `config/pow_blockchains.json`

- **total_count:** 82
- **pow_blockchains:** array of `{ id, symbol, name, algorithm, active, mineable }`
- Used by: Mining tab combo (`_load_pow_blockchains_to_combo`), `utils.data_loader.load_pow_blockchains_sync()`, `core.mining_system.MiningSystem.get_mineable_coins()`

Symbols include: BTC, ETH, LTC, DOGE, XMR, ZEC, DASH, BCH, BSV, ZEN, RVN, ERG, ETC, FLUX, KAS, ALPH, NEXA, CFX, FIRO, BTG, CKB, CLORE, OCTA, NEOX, SERO, VTC, RXD, DNX, BEAM, GRIN, AION, AE, BTM, SBTC, BCD, PPC, NMC, SYS, DGB, VIA, XVG, GRS, MWC, ARRR, PIRL, UBQ, EXP, MUSIC, ELLA, CLO, NULS, MONA, XZC, ZEL, BTCP, ZANO, XHV, WOW, SUMO, TUBE, MSR, ARQ, DERO, XEQ, LOKI, TRTL, XTA, XLA, CCX, XMV, RYO, XWP, AEON, KRB, XDN, BCN, QRL, ETN, XUN, BBR, IRL, GRFT.

---

## 2. Wallets (per-coin addresses)

**File:** `config/multi_coin_wallets.json`

- **cpu_wallets:** Monero-style and CPU-mineable coins (XMR, WOW, XHV, SUMO, MSR, AEON, KRB, XDN, BCN, QRL, ETN, ARQ, DERO, RYO, CCX, TRTL, …).
- **gpu_wallets:** GPU/multi-algo coins (BTC, ETC, OCTA, PIRL, UBQ, EXP, MUSIC, ELLA, CLO, ETH, ETHW, RVN, CLORE, NEOX, ERG, FLUX, KAS, CFX, FIRO, BTG, CKB, BEAM, GRIN, VTC, ZEC, ZEN, ZANO, GRS, DASH, LTC, DOGE, BCH, BSV, NMC, PPC, DGB, VIA, MONA, XVG, SYS, BCD, SBTC, BTCP, ZEL, LOKI, XMV, XLA, XEQ, XWP, BBR, GRFT, XTA, XUN, DNX, AE, AION, NULS, SERO, BTM, TUBE, ARRR, MWC, NEXA, RXD, ALPH, IRL, …).
- **default_wallet,** **default_gpu_wallet,** **default_randomx_wallet,** **default_cryptonight_wallet:** fallbacks.

Used by: `core.mining_system.MiningSystem._load_82_coins_and_wallets()`, `_get_wallet_for_blockchain()`, `get_wallet_for_coin()`. Merged into `_multi_coin_wallets` (gpu + cpu) so every symbol has one address when configured.

---

## 3. Node config (solo / full node)

**File:** `config/pow_nodes.json`

- **nodes:** per-symbol node config: `solo_recommended`, `node_required_for_solo`, `rpc_url_env`, `rpc_user_env`, `rpc_password_env`, `software_hint`.
- Covers all 82 PoW coins for solo/full-node mining.

Used by: Mining tab `pow_nodes` (loaded in `_deferred_mining_init`).

---

## 4. Pools (Stratum / API)

**File:** `config/mining_pools_2025.json`

- **top_pools_2025:** pool entries with `supported_coins`, `stratum_url`, `api_endpoint`, etc.
- Pools: Foundry USA, AntPool, ViaBTC, F2Pool, 2Miners, NiceHash, Binance Pool, HeroMiners, etc.

Used by: pool selection and Stratum URLs; MiningSystem uses `config["pool"]` or defaults (e.g. btc.viabtc.com:3333).

---

## 5. Wallet status (configured POW wallets)

**File:** `data/wallets/kingdom_ai_wallet_status.json`

- **configured_pow_wallets** / **configured_wallets:** list of coin symbols the user has configured.

Used by: Mining tab `configured_pow_coins` (loaded in `_deferred_mining_init`).

---

## 6. Code usage summary

| Component | 82 coins list | Wallets | Nodes | Pools |
|-----------|----------------|---------|-------|-------|
| **config/pow_blockchains.json** | ✅ | — | — | — |
| **config/multi_coin_wallets.json** | — | ✅ | — | — |
| **config/pow_nodes.json** | — | — | ✅ | — |
| **config/mining_pools_2025.json** | — | — | — | ✅ |
| **MiningSystem** | ✅ load + `get_mineable_coins()` | ✅ load + `get_wallet_for_coin()` / `_get_wallet_for_blockchain()` | — | ✅ via config/pool |
| **Mining tab GUI** | ✅ `load_pow_blockchains_sync()` | ✅ wallet_system + configured_pow_coins | ✅ pow_nodes | ✅ pool_combo |

All 82+ mineable coins and their wallets are resolved from the above data; MiningSystem and the Mining tab use this for real mining operations.
