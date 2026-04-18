# TAB 4: BLOCKCHAIN - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** Blockchain Operations
**Purpose:** Multi-chain blockchain interactions (467+ networks)
**Frontend File:** `gui/qt_frames/blockchain_tab.py`
**Backend Files:** `core/blockchain/kingdomweb3_v2.py` (2065 lines)
**Event Bus Topics:** `blockchain.*`, `market.*`, `api.key.*`, `ui.telemetry`
**External APIs:** Web3 RPC (Infura, Alchemy, QuickNode, Ankr)

---

## 🔌 ACTUAL SIGNAL CONNECTIONS (Enumerated Dec 2025)

| Line | Signal | Handler | Purpose |
|------|--------|---------|--------|
| 656 | `check_balance_btn.clicked` | `_check_balance` | Check wallet balance |
| 660 | `view_transactions_btn.clicked` | `_view_transactions` | View transaction history |
| 763 | `deploy_contract_btn.clicked` | `_deploy_contract` (async) | Deploy smart contract |
| 783 | `verify_contract_btn.clicked` | `_verify_contract` (async) | Verify contract on explorer |
| 803 | `call_contract_btn.clicked` | `_call_contract_function` (async) | Call contract method |
| 823 | `gas_optimize_btn.clicked` | `_optimize_gas` | Optimize gas settings |

## 📡 ACTUAL EVENTBUS SUBSCRIPTIONS (line 456-476, deferred 4s)

| Topic | Handler |
|-------|---------|
| `api.key.available.*` | `_on_api_key_available` |
| `api.key.list` | `_on_api_key_list` |
| `blockchain.api_keys_ready` | `_on_api_keys_ready` |
| `blockchain.balance_updated` | `_handle_balance_updated` |
| `blockchain.tx_list` | `_handle_tx_list` |
| `blockchain.block_update` | `_handle_block_update` |
| `market.prices` | `_on_market_prices_snapshot` |
| `market:price_update` | `_on_market_price_update` |

## 📡 ACTUAL EVENTBUS PUBLISHES

| Topic | Location | Trigger |
|-------|----------|--------|
| `ui.telemetry` | `_emit_ui_telemetry()` | Button clicks |
| `blockchain.balance.check` | `_check_balance()` | Check balance button |
| `blockchain.feeds.start` | `_start_real_time_blockchain_feeds()` | Start feeds |
| `blockchain.contract.loaded` | `_load_contract()` | Contract loaded |
| `blockchain.contract.verify` | `_verify_contract()` | Verify contract button |
| `blockchain.contract.call` | `_call_contract_function()` | Call method button |

---

## 📊 BUTTON MAPPING (2 BUTTONS)

### Button 1: CHECK BALANCE

**Frontend Component:**
```python
self.check_balance_button = QPushButton("💰 Check Balance")
```

**Event Listener:**
```python
self.check_balance_button.clicked.connect(self._on_check_balance_clicked)
```

**Event Handler:**
```python
def _on_check_balance_clicked(self):
    """Query blockchain for wallet balance"""
    try:
        # Get inputs
        network = self.network_combo.currentText()  # e.g., "ethereum"
        address = self.address_input.text()  # e.g., "0x742d35Cc..."
        
        # Validate address
        if not address or len(address) != 42:
            self._show_error("Invalid Ethereum address")
            return
        
        # Update button state
        self.check_balance_button.setEnabled(False)
        self.check_balance_button.setText("⏳ Checking...")
        
        # Publish balance check event
        self.event_bus.publish('blockchain.check_balance', {
            'network': network,
            'address': address,
            'timestamp': time.time()
        })
        
        logger.info(f"🔍 Checking balance: {address} on {network}")
        
    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        self._show_error(str(e))
    finally:
        QTimer.singleShot(2000, lambda: self.check_balance_button.setEnabled(True))
        QTimer.singleShot(2000, lambda: self.check_balance_button.setText("💰 Check Balance"))
```

**Backend Processing:**
```python
# File: core/blockchain/kingdomweb3_v2.py
class KingdomWeb3:
    async def _handle_check_balance(self, event_data):
        """Query REAL blockchain for balance"""
        network = event_data['network']
        address = event_data['address']
        
        # Get RPC provider for network
        rpc_url = self._get_rpc_url(network)
        
        # Initialize Web3 connection
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Check connection
        if not w3.is_connected():
            logger.error(f"Failed to connect to {network}")
            await self.event_bus.publish('blockchain.balance_error', {
                'error': 'Connection failed',
                'network': network
            })
            return
        
        # Get REAL balance from blockchain
        balance_wei = w3.eth.get_balance(address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        logger.info(f"✅ Balance retrieved: {balance_eth} ETH for {address}")
        
        # Get USD value
        usd_value = await self._get_usd_value(network, balance_eth)
        
        # Publish result
        await self.event_bus.publish('blockchain.balance_updated', {
            'address': address,
            'network': network,
            'balance_native': float(balance_eth),
            'balance_usd': usd_value,
            'token_symbol': self._get_token_symbol(network),
            'timestamp': time.time()
        })
    
    def _get_rpc_url(self, network):
        """Get RPC URL from API keys"""
        from core.api_key_manager import APIKeyManager
        
        api_keys = APIKeyManager()
        
        # Try different providers
        if network == 'ethereum':
            infura_key = api_keys.get_api_key('infura')
            if infura_key:
                return f"https://mainnet.infura.io/v3/{infura_key['api_key']}"
            
            alchemy_key = api_keys.get_api_key('alchemy')
            if alchemy_key:
                return f"https://eth-mainnet.g.alchemy.com/v2/{alchemy_key['api_key']}"
        
        # Fallback to public RPC
        return self.COMPLETE_BLOCKCHAIN_NETWORKS[network]['rpc_url']
```

**Data Flow:**
```
User Click "Check Balance"
    ↓
_on_check_balance_clicked()
    ↓
Get: network, address
    ↓
Validate address format
    ↓
event_bus.publish('blockchain.check_balance')
    ↓
KingdomWeb3 Backend
    ↓
Load API keys (Infura/Alchemy)
    ↓
Initialize Web3 with RPC URL
    ↓
w3.eth.get_balance(address)
    ↓
[RPC CALL TO BLOCKCHAIN NODE]
    ↓
Infura/Alchemy/QuickNode processes request
    ↓
Queries Ethereum blockchain
    ↓
Returns balance in Wei
    ↓
Convert Wei → ETH
    ↓
Get USD price from CoinGecko
    ↓
event_bus.publish('blockchain.balance_updated')
    ↓
GUI receives result
    ↓
Display: "5.23 ETH ($10,234.50)"
```

**Network Support (467+ Networks):**
```python
COMPLETE_BLOCKCHAIN_NETWORKS = {
    # Layer 1
    'ethereum': {
        'chain_id': 1,
        'rpc_url': 'https://mainnet.infura.io/v3/{API_KEY}',
        'symbol': 'ETH'
    },
    'bsc': {
        'chain_id': 56,
        'rpc_url': 'https://bsc-dataseed.binance.org',
        'symbol': 'BNB'
    },
    'polygon': {
        'chain_id': 137,
        'rpc_url': 'https://polygon-rpc.com',
        'symbol': 'MATIC'
    },
    'avalanche': {
        'chain_id': 43114,
        'rpc_url': 'https://api.avax.network/ext/bc/C/rpc',
        'symbol': 'AVAX'
    },
    'fantom': {
        'chain_id': 250,
        'rpc_url': 'https://rpc.ftm.tools',
        'symbol': 'FTM'
    },
    # Layer 2
    'arbitrum': {
        'chain_id': 42161,
        'rpc_url': 'https://arb1.arbitrum.io/rpc',
        'symbol': 'ETH'
    },
    'optimism': {
        'chain_id': 10,
        'rpc_url': 'https://mainnet.optimism.io',
        'symbol': 'ETH'
    },
    # ... 460 more networks
}
```

---

### Button 2: VIEW TRANSACTIONS

**Frontend Component:**
```python
self.view_transactions_button = QPushButton("📜 View Transactions")
```

**Event Listener:**
```python
self.view_transactions_button.clicked.connect(self._on_view_transactions_clicked)
```

**Event Handler:**
```python
def _on_view_transactions_clicked(self):
    """Fetch transaction history"""
    try:
        network = self.network_combo.currentText()
        address = self.address_input.text()
        
        if not address:
            self._show_error("Please enter an address")
            return
        
        # Update button
        self.view_transactions_button.setEnabled(False)
        self.view_transactions_button.setText("⏳ Loading...")
        
        # Request transaction history
        self.event_bus.publish('blockchain.get_transactions', {
            'network': network,
            'address': address,
            'limit': 100  # Last 100 transactions
        })
        
    except Exception as e:
        logger.error(f"Transaction fetch failed: {e}")
```

**Backend Processing:**
```python
async def _handle_get_transactions(self, event_data):
    """Fetch transaction history from blockchain explorer"""
    network = event_data['network']
    address = event_data['address']
    limit = event_data['limit']
    
    # Get explorer API key
    api_keys = APIKeyManager()
    
    # Use appropriate block explorer API
    if network == 'ethereum':
        # Etherscan API
        etherscan_key = api_keys.get_api_key('etherscan')
        url = f"https://api.etherscan.io/api"
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': address,
            'startblock': 0,
            'endblock': 99999999,
            'sort': 'desc',
            'apikey': etherscan_key['api_key']
        }
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if data['status'] == '1':
                    transactions = data['result'][:limit]
                    
                    # Format transactions
                    formatted_txs = []
                    for tx in transactions:
                        formatted_txs.append({
                            'hash': tx['hash'],
                            'from': tx['from'],
                            'to': tx['to'],
                            'value': float(w3.from_wei(int(tx['value']), 'ether')),
                            'timestamp': int(tx['timeStamp']),
                            'gas_used': int(tx['gasUsed']),
                            'status': 'success' if tx['txreceipt_status'] == '1' else 'failed'
                        })
                    
                    # Publish results
                    await self.event_bus.publish('blockchain.transactions_loaded', {
                        'address': address,
                        'network': network,
                        'transactions': formatted_txs,
                        'count': len(formatted_txs)
                    })
```

**GUI Update:**
```python
def _on_transactions_loaded(self, event_data):
    """Display transactions in table"""
    transactions = event_data['transactions']
    
    # Clear table
    self.tx_table.setRowCount(0)
    
    # Populate table
    for i, tx in enumerate(transactions):
        self.tx_table.insertRow(i)
        
        # Hash (clickable link)
        hash_item = QTableWidgetItem(tx['hash'][:10] + '...')
        self.tx_table.setItem(i, 0, hash_item)
        
        # From address
        from_item = QTableWidgetItem(tx['from'][:10] + '...')
        self.tx_table.setItem(i, 1, from_item)
        
        # To address
        to_item = QTableWidgetItem(tx['to'][:10] + '...')
        self.tx_table.setItem(i, 2, to_item)
        
        # Value
        value_item = QTableWidgetItem(f"{tx['value']:.4f} ETH")
        self.tx_table.setItem(i, 3, value_item)
        
        # Status
        status_item = QTableWidgetItem(tx['status'])
        status_item.setForeground(QColor('green' if tx['status'] == 'success' else 'red'))
        self.tx_table.setItem(i, 4, status_item)
```

---

## 🔗 RPC PROVIDER INTEGRATION

### API Key Distribution

```python
# File: core/api_key_manager.py
# RPC providers configured in config/api_keys.json

{
    "infura": {
        "api_key": "YOUR_INFURA_PROJECT_ID"
    },
    "alchemy": {
        "api_key": "YOUR_ALCHEMY_API_KEY"
    },
    "quicknode": {
        "api_key": "YOUR_QUICKNODE_KEY",
        "endpoint": "https://your-endpoint.quiknode.pro"
    },
    "moralis": {
        "api_key": "YOUR_MORALIS_API_KEY"
    },
    "etherscan": {
        "api_key": "YOUR_ETHERSCAN_API_KEY"
    }
}
```

### Provider Selection Logic

```python
def _get_best_rpc_provider(self, network):
    """Select best available RPC provider"""
    api_keys = APIKeyManager()
    
    # Priority order
    providers = ['infura', 'alchemy', 'quicknode', 'ankr', 'public']
    
    for provider in providers:
        try:
            key = api_keys.get_api_key(provider)
            if key:
                url = self._format_rpc_url(network, provider, key['api_key'])
                
                # Test connection
                if self._test_rpc_connection(url):
                    logger.info(f"✅ Using {provider} for {network}")
                    return url
        except:
            continue
    
    # Fallback to public RPC
    return self.COMPLETE_BLOCKCHAIN_NETWORKS[network]['rpc_url']
```

---

## 📡 EVENT BUS BINDINGS

| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `blockchain.check_balance` | Blockchain GUI | KingdomWeb3 | Check Balance button | Network, address |
| `blockchain.balance_updated` | KingdomWeb3 | Blockchain GUI + Wallet + Dashboard | Balance retrieved | Balance data |
| `blockchain.get_transactions` | Blockchain GUI | KingdomWeb3 | View Transactions button | Address, network |
| `blockchain.transactions_loaded` | KingdomWeb3 | Blockchain GUI | Transactions fetched | TX array |
| `blockchain.send_transaction` | Wallet/Trading | KingdomWeb3 | Trade/Send button | TX params |
| `blockchain.transaction_confirmed` | KingdomWeb3 | All subscribers | TX mined | TX hash, receipt |

---

## 🌐 SUPPORTED NETWORKS

### Complete Network List (467+)

**Mainnets:**
- Ethereum, BSC, Polygon, Avalanche, Fantom, Arbitrum, Optimism
- Solana, Cardano, Polkadot, Cosmos, Algorand, Near, Tezos
- Harmony, Celo, Moonbeam, Moonriver, Cronos, Aurora, Metis
- ... 440+ more

**Testnets:**
- Goerli, Sepolia, Mumbai, Fuji, BSC Testnet, Fantom Testnet
- ... 20+ testnets

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The Blockchain tab emits UI telemetry on `ui.telemetry` when users check
balances, view transactions, or work with contracts.

- **Channel:** `ui.telemetry`
- **Component:** `blockchain`
- **Representative event types:**
  - `blockchain.check_balance_clicked`
  - `blockchain.view_transactions_clicked`
  - `blockchain.deploy_contract_clicked`
  - `blockchain.verify_contract_clicked`
  - `blockchain.call_contract_clicked`
  - `blockchain.optimize_gas_clicked`

Example payload shape:

```json
{
  "component": "blockchain",
  "channel": "ui.telemetry",
  "event_type": "blockchain.view_transactions_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"network": "ethereum", "address_provided": true}
}
```

The **TelemetryCollector** subscribes to `ui.telemetry` and aggregates these
events with those from other tabs for analysis and monitoring.

## ✅ VERIFICATION

**Test Balance Check:**

```bash
# 1. Configure API keys in config/api_keys.json
{
  "infura": {"api_key": "YOUR_KEY"}
}

# 2. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 3. Go to Blockchain tab

# 4. Select Network: Ethereum
# 5. Enter Address: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
# 6. Click "Check Balance"

# Expected output:
# 🔍 Checking balance: 0x742d35... on ethereum
# ✅ Balance retrieved: 1,234.56 ETH for 0x742d35...
# Display shows: "1,234.56 ETH ($2,567,890.12)"
```

**Monitor Logs:**
```bash
tail -f logs/kingdom_error.log | grep blockchain
```

---

**Status:** ✅ COMPLETE - 467+ blockchain networks accessible with real RPC queries
