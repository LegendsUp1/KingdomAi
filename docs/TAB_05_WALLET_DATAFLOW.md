# TAB 5: WALLET - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** Wallet Management
**Purpose:** Multi-chain cryptocurrency wallet operations
**Frontend File:** `gui/qt_frames/wallet_tab.py`
**Backend Files:** `core/wallet_manager.py`
**Event Bus Topics:** `wallet.*`, `market.*`, `api.key.*`, `ui.telemetry`
**External APIs:** Web3 RPC, DEX aggregators, Price APIs

---

## 🔌 ACTUAL SIGNAL CONNECTIONS (Enumerated Dec 2025)

| Line | Signal | Handler | Purpose |
|------|--------|---------|--------|
| 522 | `network_combo.currentTextChanged` | `_network_changed` | Switch blockchain network |
| 531 | `refresh_btn.clicked` | `_refresh_wallet_data` | Refresh balances |
| 572 | `send_btn.clicked` | `_send_transaction` | Send crypto |
| 582 | `receive_btn.clicked` | `_show_receive_address` | Show receive QR |
| 592 | `swap_btn.clicked` | `_cross_chain_swap` | Cross-chain swap |
| 602 | `portfolio_btn.clicked` | `_show_portfolio` | View portfolio |
| 669 | `analyze_portfolio_btn.clicked` | `_analyze_portfolio` | AI portfolio analysis |
| 686 | `rebalance_btn.clicked` | `_rebalance_portfolio` | Rebalance holdings |
| 703 | `security_audit_btn.clicked` | `_run_security_audit` | Security audit |
| 720 | `performance_report_btn.clicked` | `_generate_performance_report` | Performance report |
| 1165 | `update_timer.timeout` | `_refresh_wallet_data` | Auto-refresh (10s) |
| 1197 | `price_timer.timeout` | `_update_prices_sync` | Price updates (5s) |
| 2016 | `start_accum_btn.clicked` | `_toggle_accumulation` | Toggle accumulation |
| 2034 | `add_target_btn.clicked` | `_add_accumulation_target` | Add target |
| 2052 | `register_mining_btn.clicked` | `_register_mined_coin` | Register mined coin |
| 2070 | `report_btn.clicked` | `_show_accumulation_report` | Show report |
| 2109 | `_accum_update_timer.timeout` | `_update_accumulation_display` | Update accum (5s) |

## 📡 ACTUAL EVENTBUS SUBSCRIPTIONS

| Topic | Handler |
|-------|---------|
| `api.key.available.*` | `_on_api_key_available` |
| `api.key.list` | `_on_api_key_list` |
| `market.prices` | `_on_market_prices_snapshot` |
| `market:price_update` | `_on_market_price_update` |
| `wallet.transaction_confirmed` | `_handle_tx_confirmed` |
| `wallet.data_updated` | `_handle_wallet_updated` |

## 📡 ACTUAL EVENTBUS PUBLISHES

| Topic | Location | Trigger |
|-------|----------|--------|
| `ui.telemetry` | `_emit_ui_telemetry()` | Button clicks |
| `wallet.network_changed` | `_network_changed()` | Network switch |
| `wallet.refresh` | `_refresh_wallet_data()` | Refresh button |
| `wallet.balance` | `_refresh_wallet_data()` | Balance request |
| `wallet.send` | `_send_transaction()` | Send button |
| `wallet.transaction_confirmed` | `_send_transaction()` | TX confirmed |

---

## ⚠️ CRITICAL WARNING

**REAL MONEY OPERATIONS:**
- Transactions are IRREVERSIBLE
- Wrong address = LOST FUNDS
- Gas fees apply
- Always test with small amounts first
- Double-check recipient addresses

---

## 📊 BUTTON MAPPING (5 BUTTONS)

### Button 1: REFRESH

**Event Listener:**
```python
self.refresh_button.clicked.connect(self._on_refresh_clicked)
```

**Event Handler:**
```python
def _on_refresh_clicked(self):
    """Refresh all wallet balances"""
    self.event_bus.publish('wallet.refresh_all', {
        'networks': ['ethereum', 'bsc', 'polygon', 'avalanche'],
        'address': self.current_address
    })
```

**Backend:**
```python
async def _handle_refresh_all(self, event_data):
    """Query balances across all networks"""
    from core.blockchain.kingdomweb3_v2 import KingdomWeb3
    
    blockchain = KingdomWeb3()
    balances = {}
    
    for network in event_data['networks']:
        balance = await blockchain.get_balance(
            network,
            event_data['address']
        )
        balances[network] = balance
    
    await self.event_bus.publish('wallet.balances_updated', balances)
```

---

### Button 2: SEND CRYPTO

**Event Listener:**
```python
self.send_button.clicked.connect(self._on_send_clicked)
```

**Event Handler:**
```python
def _on_send_clicked(self):
    """Send cryptocurrency to address"""
    try:
        # Get transaction parameters
        to_address = self.to_address_input.text()
        amount = float(self.amount_input.text())
        network = self.network_combo.currentText()
        
        # Validate inputs
        if not to_address or amount <= 0:
            self._show_error("Invalid transaction parameters")
            return
        
        # Confirmation dialog
        reply = QMessageBox.warning(
            self,
            '⚠️ CONFIRM TRANSACTION',
            f'Send {amount} {network.upper()} to:\n{to_address}\n\n'
            f'This transaction is IRREVERSIBLE!\n\n'
            f'Are you sure?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Disable button during transaction
        self.send_button.setEnabled(False)
        self.send_button.setText("⏳ Sending...")
        
        # Publish send transaction event
        self.event_bus.publish('wallet.send_transaction', {
            'from_address': self.current_address,
            'to_address': to_address,
            'amount': amount,
            'network': network,
            'gas_price': 'auto',
            'timestamp': time.time()
        })
        
        logger.info(f"🔥 SENDING REAL TRANSACTION: {amount} on {network}")
        
    except Exception as e:
        logger.error(f"Send transaction failed: {e}")
        self._show_error(str(e))
```

**Backend Processing:**
```python
# File: core/wallet_manager.py
class WalletManager:
    async def _handle_send_transaction(self, event_data):
        """Execute REAL blockchain transaction"""
        from core.blockchain.kingdomweb3_v2 import KingdomWeb3
        from web3 import Web3
        
        # Extract parameters
        from_addr = event_data['from_address']
        to_addr = event_data['to_address']
        amount = event_data['amount']
        network = event_data['network']
        
        # Initialize blockchain connection
        blockchain = KingdomWeb3()
        w3 = blockchain.get_web3_connection(network)
        
        # Get private key from secure storage
        private_key = self._get_private_key(from_addr)
        
        # Build transaction
        tx = {
            'from': from_addr,
            'to': to_addr,
            'value': w3.to_wei(amount, 'ether'),
            'gas': 21000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(from_addr),
            'chainId': blockchain.get_chain_id(network)
        }
        
        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        
        # Send REAL transaction to blockchain
        logger.info(f"🔥 BROADCASTING TRANSACTION TO {network.upper()}")
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        logger.info(f"✅ TRANSACTION SENT: {tx_hash.hex()}")
        
        # Wait for confirmation
        tx_receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if tx_receipt['status'] == 1:
            logger.info(f"✅ TRANSACTION CONFIRMED: {tx_hash.hex()}")
            
            # Publish success
            await self.event_bus.publish('wallet.transaction_confirmed', {
                'tx_hash': tx_hash.hex(),
                'from': from_addr,
                'to': to_addr,
                'amount': amount,
                'network': network,
                'gas_used': tx_receipt['gasUsed'],
                'block_number': tx_receipt['blockNumber']
            })
        else:
            logger.error(f"❌ TRANSACTION FAILED: {tx_hash.hex()}")
            await self.event_bus.publish('wallet.transaction_failed', {
                'tx_hash': tx_hash.hex(),
                'error': 'Transaction reverted'
            })
```

**Data Flow:**
```
User Click "Send"
    ↓
Get: to_address, amount, network
    ↓
Validate inputs
    ↓
Show confirmation dialog
    ↓
User confirms
    ↓
event_bus.publish('wallet.send_transaction')
    ↓
Wallet Manager Backend
    ↓
Load private key (encrypted storage)
    ↓
Initialize Web3 connection
    ↓
Build transaction object
    ↓
Calculate gas price
    ↓
Get nonce from blockchain
    ↓
Sign transaction with private key
    ↓
w3.eth.send_raw_transaction()
    ↓
[BROADCAST TO BLOCKCHAIN NETWORK]
    ↓
Transaction enters mempool
    ↓
Miners include in block
    ↓
Block confirmed
    ↓
w3.eth.wait_for_transaction_receipt()
    ↓
Transaction confirmed on-chain
    ↓
event_bus.publish('wallet.transaction_confirmed')
    ↓
GUI shows success + TX hash
    ↓
Update balance
```

---

### Button 3: RECEIVE CRYPTO

**Event Listener:**
```python
self.receive_button.clicked.connect(self._on_receive_clicked)
```

**Event Handler:**
```python
def _on_receive_clicked(self):
    """Show receive address and QR code"""
    # Generate QR code for address
    import qrcode
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(self.current_address)
    qr.make(fit=True)
    
    # Create QR image
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Display in dialog
    dialog = QDialog(self)
    dialog.setWindowTitle("Receive Crypto")
    
    layout = QVBoxLayout()
    
    # Address label
    address_label = QLabel(self.current_address)
    address_label.setFont(QFont("Courier", 10))
    layout.addWidget(address_label)
    
    # QR code
    qr_label = QLabel()
    qr_label.setPixmap(QPixmap.fromImage(qr_image.toqimage()))
    layout.addWidget(qr_label)
    
    # Copy button
    copy_button = QPushButton("📋 Copy Address")
    copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.current_address))
    layout.addWidget(copy_button)
    
    dialog.setLayout(layout)
    dialog.exec()
```

---

### Button 4: CROSS-CHAIN SWAP

**Event Listener:**
```python
self.swap_button.clicked.connect(self._on_swap_clicked)
```

**Event Handler:**
```python
def _on_swap_clicked(self):
    """Execute cross-chain swap via bridge"""
    from_chain = self.from_chain_combo.currentText()
    to_chain = self.to_chain_combo.currentText()
    amount = float(self.swap_amount_input.text())
    
    self.event_bus.publish('wallet.cross_chain_swap', {
        'from_chain': from_chain,
        'to_chain': to_chain,
        'amount': amount,
        'protocol': 'celer_bridge'  # or 'layerzero', 'synapse', etc.
    })
```

**Backend:**
```python
async def _handle_cross_chain_swap(self, event_data):
    """Execute swap via bridge protocol"""
    # Use bridge aggregator API
    # Examples: Celer Bridge, LayerZero, Synapse
    
    from_chain = event_data['from_chain']
    to_chain = event_data['to_chain']
    amount = event_data['amount']
    
    # Get quote from bridge
    quote = await self._get_bridge_quote(from_chain, to_chain, amount)
    
    # Execute bridge transaction
    tx_hash = await self._execute_bridge(quote)
    
    # Monitor cross-chain transfer
    await self._monitor_bridge_status(tx_hash)
```

---

### Button 5: PORTFOLIO VIEW

**Event Listener:**
```python
self.portfolio_button.clicked.connect(self._on_portfolio_clicked)
```

**Event Handler:**
```python
def _on_portfolio_clicked(self):
    """Show multi-chain portfolio"""
    self.event_bus.publish('wallet.get_portfolio', {
        'address': self.current_address,
        'networks': ['ethereum', 'bsc', 'polygon', 'avalanche', 'arbitrum']
    })
```

**Backend:**
```python
async def _handle_get_portfolio(self, event_data):
    """Aggregate portfolio across all chains"""
    address = event_data['address']
    networks = event_data['networks']
    
    portfolio = {
        'total_value_usd': 0,
        'chains': []
    }
    
    for network in networks:
        # Get native balance
        native_balance = await self._get_balance(network, address)
        
        # Get token balances
        token_balances = await self._get_token_balances(network, address)
        
        # Calculate USD values
        native_usd = await self._get_usd_value(network, native_balance)
        tokens_usd = sum([t['value_usd'] for t in token_balances])
        
        portfolio['chains'].append({
            'network': network,
            'native_balance': native_balance,
            'native_value_usd': native_usd,
            'tokens': token_balances,
            'total_value_usd': native_usd + tokens_usd
        })
        
        portfolio['total_value_usd'] += native_usd + tokens_usd
    
    await self.event_bus.publish('wallet.portfolio_loaded', portfolio)
```

---

## 🔒 SECURITY

### Private Key Storage

```python
# Encrypted storage using Fernet
from cryptography.fernet import Fernet

class WalletManager:
    def _encrypt_private_key(self, private_key, password):
        """Encrypt private key with user password"""
        # Derive key from password
        key = self._derive_key(password)
        
        # Encrypt
        f = Fernet(key)
        encrypted = f.encrypt(private_key.encode())
        
        # Store encrypted key
        self._save_encrypted_key(encrypted)
    
    def _get_private_key(self, address):
        """Decrypt and retrieve private key"""
        encrypted_key = self._load_encrypted_key(address)
        
        # Decrypt with user password
        key = self._derive_key(self.user_password)
        f = Fernet(key)
        private_key = f.decrypt(encrypted_key).decode()
        
        return private_key
```

---

## 📡 EVENT BUS BINDINGS

| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `wallet.refresh_all` | Wallet GUI | Wallet Manager | Refresh button | Networks, address |
| `wallet.balances_updated` | Wallet Manager | Wallet GUI | Balances fetched | Balance data |
| `wallet.send_transaction` | Wallet GUI | Wallet Manager | Send button | TX params |
| `wallet.transaction_confirmed` | Wallet Manager | Wallet GUI + Dashboard | TX confirmed | TX hash, receipt |
| `wallet.cross_chain_swap` | Wallet GUI | Wallet Manager | Swap button | Bridge params |
| `wallet.portfolio_loaded` | Wallet Manager | Wallet GUI | Portfolio fetched | Portfolio data |

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The Wallet tab emits UI telemetry events for key actions like refresh, send,
receive, cross-chain swap, and portfolio tools.

- **Channel:** `ui.telemetry`
- **Component:** `wallet`
- **Representative event types:**
  - `wallet.refresh_clicked`
  - `wallet.send_transaction_clicked`
  - `wallet.receive_clicked`
  - `wallet.cross_chain_swap_clicked`
  - `wallet.portfolio_view_clicked`
  - `wallet.analyze_portfolio_clicked`

Example payload shape:

```json
{
  "component": "wallet",
  "channel": "ui.telemetry",
  "event_type": "wallet.send_transaction_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"network": "goerli", "amount": 0.001}
}
```

The **TelemetryCollector** consumes these `ui.telemetry` events together with
other tabs, providing a unified stream of non-blocking UI telemetry.

## ✅ VERIFICATION

**Test Transaction (TESTNET ONLY):**

```bash
# 1. Use testnet addresses and funds
# 2. Configure testnet RPC URLs
# 3. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 4. Go to Wallet tab
# 5. Network: Goerli (Ethereum testnet)
# 6. To: 0x... (testnet address)
# 7. Amount: 0.001 (small test amount)
# 8. Click "Send"

# Monitor logs:
tail -f logs/kingdom_error.log | grep wallet

# Expected:
# 🔥 SENDING REAL TRANSACTION: 0.001 on goerli
# 🔥 BROADCASTING TRANSACTION TO GOERLI
# ✅ TRANSACTION SENT: 0xabc123...
# ✅ TRANSACTION CONFIRMED: 0xabc123...
```

---

**Status:** ✅ COMPLETE - Real wallet operations with multi-chain support

---

## 📅 DECEMBER 2025 UPDATE

### Wallet ↔ Trading Integration

**Date:** December 14, 2025

#### Coin Accumulation Intelligence Integration

The Wallet Tab now integrates with the Trading Tab's **Coin Accumulation Intelligence** system, enabling:

1. **Portfolio Value Telemetry**: Wallet broadcasts portfolio snapshots to Trading Tab
2. **Mining Reward Reinvestment**: Mining rewards can trigger accumulation strategies
3. **Cross-Tab Portfolio Tracking**: Unified view of holdings across wallet and trading

#### New Event Subscriptions

```
wallet.intelligence.portfolio_value  → Trading Tab profit goal updates
wallet.balance_update               → Accumulation Intelligence triggers
mining.reward_received              → Auto-reinvestment evaluation
```

#### Wallet → Trading Data Flow

```
┌─────────────┐                    ┌─────────────┐
│  Wallet Tab │                    │ Trading Tab │
│             │  portfolio.snapshot │             │
│  Balances   ├───────────────────►│ Profit Goal │
│  Holdings   │                    │    Bar      │
│             │  wallet.balance_   │             │
│             │     update         │ Accumulation│
│             ├───────────────────►│ Intelligence│
└─────────────┘                    └─────────────┘
```

#### Trading Tab Profit Goal Bar Updates

The Trading Tab's `profit_goal_bar` now receives live data from wallet snapshots:

```python
# Event: trading.portfolio.snapshot
# Handler: TradingTab._update_profit_goal_from_portfolio_snapshot()
# Data: {
#   "breakdown": {
#     "stable_usd": float,
#     "crypto_nonstable_usd": float,
#     "stocks_usd": float,
#     "internal_total_usd": float,
#     "external_total_usd": float,
#     "by_wallet": {...}
#   },
#   "total_usd": float
# }
```

#### Multi-Chain Wallet Connections in Trading Tab

The Trading Tab now displays wallet blockchain connections:

| Blockchain | Adapter | Trading Tab Widget |
|------------|---------|-------------------|
| ETH/BSC/Polygon | `kingdom_web3` | `copy_whale_display` |
| Solana | `solana_adapter` | `copy_whale_display` |
| XRP Ledger | `xrp_adapter` | `copy_whale_display` |

#### Backend Services Integration

Trading Tab starts services that interact with wallet data:

```python
# Started from setup_trading_intelligence_hub() → _start_all_backend_services()
_start_whale_tracking_service()    # Monitors on-chain whale wallets
_start_market_data_service()       # Fetches DEX prices for wallet tokens
_start_risk_monitoring_service()   # Tracks portfolio risk across wallets
```

#### Related Telemetry Events

| Event | Source | Consumer | Purpose |
|-------|--------|----------|---------|
| `trading.portfolio.snapshot` | TradingComponent | WalletTab, TradingTab | Unified portfolio view |
| `wallet.balance_update` | WalletManager | TradingTab | Accumulation triggers |
| `accumulation.status` | AccumulationIntelligence | TradingTab | Strategy status |
| `accumulation.executed` | AccumulationIntelligence | TradingTab | Execution confirmation |
| `trading.profit.report` | TradingComponent | TradingTab | Profit goal progress |

#### Cross-Reference Documentation

- See `docs/TRADING_TAB_WIRING_MAP.md` for complete Trading Tab panel wiring
- See `docs/TAB_02_TRADING_DATAFLOW.md` for Trading Tab event flow
- See `docs/DATAFLOW_MASTER_INDEX.md` for December 2025 update log
