# KAIG Token Rebrand & Migration Playbook

## WHY THIS EXISTS

The creator cannot currently afford trademark protection for the name "KAIG".
If the name is ever stolen, legally challenged, or must change for any reason,
this playbook ensures **zero user fund loss** and a clean transition.

This is not hypothetical — it happens constantly in crypto:
- **MATIC → POL** (Polygon, 2024): 1:1 swap, all exchanges handled automatically
- **FTM → S** (Fantom → Sonic, 2025): 1:1 automatic conversion
- **MKR → SKY** (MakerDAO, 2025): 1:1 migration via contract upgrade
- **EOS → A** (EOS, 2025): 1:1 rebrand migration
- **AI16Z → ELIZAOS** (2025): 1:6 ratio migration

Every one of these preserved all user funds. So will ours.

---

## ARCHITECTURAL PROTECTIONS (ALREADY BUILT)

### 1. Token Identity Abstraction Layer
**File:** `core/kaig_token_identity.py`

Every system in Kingdom AI reads the token name/ticker from ONE source:
```python
from core.kaig_token_identity import get_ticker, get_name, get_token_identity
```
Change `config/kaig/runtime_config.json` → entire system updates.

### 2. Token Migration Engine
**File:** `core/kaig_migration_engine.py`

Automated migration that:
- Snapshots every user's balance before migration
- Executes 1:1 (or custom ratio) transfer to new identity
- Verifies post-migration totals match pre-migration (zero-loss guarantee)
- Publishes events so all systems update
- Writes full audit trail to disk

### 3. Upgradeable Smart Contract (UUPS Proxy)
**File:** `blockchain/contracts/KAIGTokenV1.sol`

The on-chain token uses OpenZeppelin's UUPS proxy pattern:
- `name()` and `symbol()` read from **mutable storage**
- `rebrand(newName, newSymbol, reason)` changes the label without touching balances
- Contract address NEVER changes
- Users don't need to do ANYTHING
- Full rebrand history stored on-chain

### 4. Name-Agnostic Internal Ledger
All internal ledger files (`ledger.json`, `treasury.json`, `wallets.json`, `escrow.json`)
track balances by **wallet address**, never by token name. A name change only changes
display labels — the numbers never move.

---

## STEP-BY-STEP MIGRATION PROCEDURE

### Phase 1: Preparation (Before Announcement)

1. **Choose new name and ticker**
   - Verify the new name is not trademarked in your jurisdiction
   - Check CoinGecko/CoinMarketCap that the ticker is not taken
   - Decide ratio (1:1 recommended for simplicity)

2. **Run a dry-run migration**
   ```python
   from core.kaig_migration_engine import KAIGMigrationEngine
   engine = KAIGMigrationEngine(event_bus=event_bus)
   result = engine.execute_full_migration(
       new_ticker="NEWTICKER",
       new_name="New Name",
       reason="trademark_dispute",
       ratio=1.0,
       dry_run=True,  # Does NOT actually change anything
   )
   print(result)  # Verify balance_match=True
   ```

3. **Review the snapshot** in `config/kaig/migration_snapshots/`
   - Every user's balance is recorded
   - Total balance is calculated
   - Verify the numbers match your expectations

### Phase 2: Execute Migration

4. **Execute the actual migration**
   ```python
   result = engine.execute_full_migration(
       new_ticker="NEWTICKER",
       new_name="New Name",
       reason="trademark_dispute",
       ratio=1.0,
       dry_run=False,  # THIS IS REAL
   )
   ```
   This atomically:
   - Backs up current config
   - Updates `runtime_config.json` with new name/ticker
   - Updates all ledger files
   - Publishes `kaig.identity.changed` event
   - Publishes `kaig.migration.complete` event
   - Writes audit trail to `migration_history.json`

5. **If on-chain: call rebrand on the smart contract**
   ```solidity
   // Via Etherscan or your deployment tool
   kaigToken.rebrand("New Name", "NEWTICKER", "trademark dispute");
   ```
   This changes `name()` and `symbol()` without touching any balances.

6. **Verify migration**
   ```python
   verification = engine.verify_migration(result.migration_id)
   assert verification["verified"] == True
   ```

### Phase 3: External Notifications

7. **Submit CoinGecko Contract Migration/Rebranding Form**
   - URL: https://www.coingecko.com/request-form/migration
   - Select "Rebrand" option
   - Select "1:1 migration" (if applicable)
   - Choose "Update existing page" to preserve price chart history
   - Allow up to 10 business days

8. **Submit CoinMarketCap update request**
   - Similar process, submit ticket with new name/ticker/logo

9. **Notify exchanges**
   - Each exchange where KAIG is listed must be contacted
   - Major exchanges (Binance, Coinbase, Kraken, KuCoin) handle 1:1 swaps automatically
   - Provide: new name, new ticker, new contract address (if changed), ratio, migration date
   - Most exchanges pause trading briefly, convert balances, resume under new ticker

10. **Update external references**
    - Landing page (kingdomai.netlify.app)
    - All social media profiles
    - GitHub repository
    - Any documentation or marketing materials

### Phase 4: User Communication

11. **Publish user-facing announcement**
    - Explain: "Your funds are safe. All balances are preserved exactly."
    - Explain: "You do not need to do anything. The swap is automatic."
    - Provide migration ID for transparency
    - Link to on-chain rebrand transaction (if applicable)

12. **In-app notification**
    - The `kaig.identity.changed` event triggers UI updates
    - All tabs, labels, and references update automatically
    - Show a one-time notification: "Token rebranded from X to Y. All your funds are intact."

---

## WHAT USERS SEE

### Before Migration:
- Token name: KAI Gold
- Ticker: KAIG
- Balance: 1,500 KAIG
- Staked: 500 KAIG

### After Migration (example: KAIG → KDOM):
- Token name: Kingdom Dollar
- Ticker: KDOM
- Balance: 1,500 KDOM ← **EXACT SAME NUMBER**
- Staked: 500 KDOM ← **EXACT SAME NUMBER**
- Contract address: **UNCHANGED**
- Price history: **PRESERVED** (CoinGecko updates the page)

### What the user had to do: **NOTHING.**

---

## EMERGENCY MIGRATION (HOSTILE TAKEOVER)

If someone registers the "KAIG" trademark and sends a cease-and-desist:

1. **Do NOT panic.** The system is built for this.
2. Run the migration engine with `reason="legal_cease_and_desist"`
3. The entire system rebrands in under 60 seconds
4. User funds are not affected at all
5. File the external notifications (CoinGecko, exchanges, etc.)
6. Respond to the legal notice with proof of rebrand compliance

---

## FILES REFERENCE

| File | Purpose |
|------|---------|
| `config/kaig/runtime_config.json` | Single source of truth for token identity |
| `core/kaig_token_identity.py` | Python abstraction layer — all systems read from here |
| `core/kaig_migration_engine.py` | Snapshot + migrate + verify engine |
| `blockchain/contracts/KAIGTokenV1.sol` | Upgradeable ERC-20 with rebrand() function |
| `config/kaig/migration_history.json` | Append-only audit trail of all migrations |
| `config/kaig/migration_snapshots/` | Pre-migration balance snapshots |
| `config/kaig/backups/` | Config file backups before each migration |

---

## KEY PRINCIPLE

> **Balances are tracked by WALLET ADDRESS, never by token name.**
> **A name change only changes labels — the numbers never move.**
> **Users do not need to take any action.**

This is exactly how MATIC→POL, FTM→Sonic, MKR→SKY, and every other
major crypto rebrand has worked. The architecture is standard, proven,
and built into Kingdom AI from day one.
