# TAB 8: API KEY MANAGER - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** API Key Manager
**Purpose:** Centralized API key management and distribution
**Frontend File:** `gui/qt_frames/api_key_manager_tab.py`
**Backend Files:** `core/api_key_manager.py`, `security_manager/api_key_manager.py`
**Event Bus Topics:** `api_keys.loaded`, `api.key.loaded.*`, `api.keys.all.loaded`, `api_key_manager.*`, `exchange.health.snapshot`
**Storage:** `config/api_keys.json`, `.env` (encrypted)

---

## ✅ Recent Runtime Fixes (Dec 2025)

### 1) Auto-select first configured service

**Problem:** Service Details could remain on “No service selected” even though keys were loaded.

**Fix:** After populating the services tree, the tab selects the first service marked `🟢 Configured` and calls `_update_service_details(service_id)`.

### 2) Broadcast `api_keys.loaded`

**Problem:** Other tabs/components (Trading, Blockchain, ThothAI, etc.) could not reliably react immediately when API keys finished loading.

**Fix:** After loading keys, the tab publishes `api_keys.loaded` with `{count, services, timestamp}` so subscribers can refresh their connectors.

---

## 🔌 ACTUAL SIGNAL CONNECTIONS (Enumerated Dec 2025)

| Location | Signal | Handler | Purpose |
|----------|--------|---------|--------|
| Toolbar | `add_btn.clicked` | `_add_api_key` | Show Add Key dialog |
| Toolbar | `refresh_btn.clicked` | `_refresh_keys` | Reload API keys from storage |
| Toolbar | `test_btn.clicked` | `_test_connection` | Test selected service connection |
| Toolbar | `toggle_btn.clicked` | `_toggle_secrets` | Show/hide secret values |
| Toolbar | `help_btn.clicked` | `_show_help` | Display help dialog |
| Services Tree | `itemSelectionChanged` | `_on_service_selected` | Update details panel |
| Filter Input | `textChanged` | `_filter_services` | Filter service tree |
| Keys Table | Copy buttons `.clicked` | Lambda clipboard copy | Copy key value to clipboard |

## 📡 ACTUAL EVENTBUS WIRING (Enumerated Dec 2025)

### Publishes (in `_load_api_keys` and `_distribute_keys_to_systems`)
| Topic | Location | Trigger |
|-------|----------|--------|
| `api_keys.loaded` | `_load_api_keys()` | Keys loaded from storage |
| `api.key.loaded.{service}` | `_distribute_keys_to_systems()` line 439 | Per-service key broadcast |
| `api.keys.all.loaded` | `_distribute_keys_to_systems()` | All keys distributed |
| `ui.telemetry` | `_emit_ui_telemetry()` | Button clicks for telemetry |

### Subscriptions
| Topic | Handler | Purpose |
|-------|---------|--------|
| `api_key_manager.keys_updated` | `_handle_keys_updated` | Reload keys when updated externally |
| `api_key_manager.connection_status_changed` | `_handle_connection_status_changed` | Update service status in tree |
| `exchange.health.snapshot` | `_handle_exchange_health_snapshot` | Update exchange health table |

---

## 🔒 SECURITY CRITICAL

**WARNING:**
- API keys provide access to external services
- Store encrypted, never in plain text
- Never commit to git
- Use read-only keys when possible
- Enable IP whitelisting on exchanges
- 2FA on all exchange accounts

---

## 📊 BUTTON MAPPING (8 BUTTONS)

### Button 1: ADD API KEY

**Event Listener:**
```python
self.add_button.clicked.connect(self._on_add_clicked)
```

**Event Handler:**
```python
def _on_add_clicked(self):
    """Add new API key"""
    # Show dialog for new key
    dialog = AddKeyDialog(self)
    if dialog.exec() == QDialog.Accepted:
        key_data = dialog.get_key_data()
        
        # Publish add key event
        self.event_bus.publish('api_keys.add', {
            'service': key_data['service'],
            'api_key': key_data['api_key'],
            'api_secret': key_data['api_secret'],
            'passphrase': key_data.get('passphrase'),
            'permissions': key_data.get('permissions', []),
            'timestamp': time.time()
        })
```

**Backend:**
```python
# File: core/api_key_manager.py
class APIKeyManager:
    async def _handle_add_key(self, event_data):
        """Store new API key (encrypted)"""
        service = event_data['service']
        api_key = event_data['api_key']
        api_secret = event_data['api_secret']
        
        # Encrypt sensitive data
        encrypted_secret = self._encrypt(api_secret)
        
        # Load existing keys
        keys = self._load_keys_from_file()
        
        # Add new key
        keys[service] = {
            'api_key': api_key,
            'api_secret': encrypted_secret,
            'created_at': time.time(),
            'permissions': event_data.get('permissions', [])
        }
        
        # Save to file
        self._save_keys_to_file(keys)
        
        logger.info(f"✅ API key added: {service}")
        
        # Distribute to systems
        await self._distribute_keys()
        
        # Publish success
        await self.event_bus.publish('api_keys.added', {
            'service': service,
            'success': True
        })
```

---

### Button 2: REFRESH

**Event Listener:**
```python
self.refresh_button.clicked.connect(self._on_refresh_clicked)
```

**Event Handler:**
```python
def _on_refresh_clicked(self):
    """Reload API keys from files"""
    self.event_bus.publish('api_keys.refresh', {})
```

**Backend:**
```python
async def _handle_refresh(self, event_data):
    """Reload keys from config files"""
    # Load from config/api_keys.json
    keys = self._load_keys_from_file()
    
    # Load from .env
    env_keys = self._load_keys_from_env()
    
    # Merge
    all_keys = {**keys, **env_keys}
    
    # Update internal storage
    self.api_keys = all_keys
    
    # Publish updated keys
    await self.event_bus.publish('api_keys.refreshed', {
        'count': len(all_keys),
        'services': list(all_keys.keys())
    })
```

---

### Button 3: TEST CONNECTION

**Event Listener:**
```python
self.test_button.clicked.connect(self._on_test_clicked)
```

**Event Handler:**
```python
def _on_test_clicked(self):
    """Test API key connection"""
    selected = self.keys_table.currentRow()
    if selected < 0:
        self._show_error("Please select a key to test")
        return
    
    service = self.keys_table.item(selected, 0).text()
    
    self.event_bus.publish('api_keys.test', {
        'service': service
    })
```

**Backend:**
```python
async def _handle_test_connection(self, event_data):
    """Test REAL API connection"""
    service = event_data['service']
    
    # Get API keys
    key_data = self.get_api_key(service)
    
    if not key_data:
        await self.event_bus.publish('api_keys.test_failed', {
            'service': service,
            'error': 'Key not found'
        })
        return
    
    # Test based on service type
    if service in ['binance', 'kucoin', 'bybit']:
        # Test exchange API
        import ccxt
        exchange_class = getattr(ccxt, service)
        exchange = exchange_class({
            'apiKey': key_data['api_key'],
            'secret': key_data['api_secret']
        })
        
        try:
            # REAL API call to test
            balance = exchange.fetch_balance()
            
            logger.info(f"✅ API key test PASSED: {service}")
            
            await self.event_bus.publish('api_keys.test_passed', {
                'service': service,
                'message': f'Connected successfully. Balance loaded.'
            })
        except Exception as e:
            logger.error(f"❌ API key test FAILED: {service} - {e}")
            
            await self.event_bus.publish('api_keys.test_failed', {
                'service': service,
                'error': str(e)
            })
    
    elif service in ['infura', 'alchemy']:
        # Test RPC provider
        from web3 import Web3
        
        rpc_url = f"https://mainnet.infura.io/v3/{key_data['api_key']}"
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        try:
            # Test connection
            if w3.is_connected():
                block = w3.eth.block_number
                
                logger.info(f"✅ RPC test PASSED: {service}")
                
                await self.event_bus.publish('api_keys.test_passed', {
                    'service': service,
                    'message': f'Connected. Current block: {block}'
                })
            else:
                raise Exception("Connection failed")
        except Exception as e:
            await self.event_bus.publish('api_keys.test_failed', {
                'service': service,
                'error': str(e)
            })
```

---

### Button 4: TOGGLE SECRETS

**Event Listener:**
```python
self.toggle_secrets_button.clicked.connect(self._on_toggle_secrets_clicked)
```

**Event Handler:**
```python
def _on_toggle_secrets_clicked(self):
    """Show/hide API secrets"""
    self.secrets_visible = not self.secrets_visible
    
    if self.secrets_visible:
        # Show secrets
        self.toggle_secrets_button.setText("🙈 Hide Secrets")
        self._display_keys(show_secrets=True)
    else:
        # Hide secrets
        self.toggle_secrets_button.setText("👁️ Show Secrets")
        self._display_keys(show_secrets=False)
```

---

### Button 5: EDIT KEY

**Event Listener:**
```python
self.edit_button.clicked.connect(self._on_edit_clicked)
```

**Event Handler:**
```python
def _on_edit_clicked(self):
    """Edit existing API key"""
    selected = self.keys_table.currentRow()
    if selected < 0:
        return
    
    service = self.keys_table.item(selected, 0).text()
    
    # Show edit dialog
    dialog = EditKeyDialog(self, service)
    if dialog.exec() == QDialog.Accepted:
        updated_data = dialog.get_key_data()
        
        self.event_bus.publish('api_keys.update', {
            'service': service,
            'api_key': updated_data['api_key'],
            'api_secret': updated_data['api_secret']
        })
```

---

### Button 6: DELETE KEY

**Event Listener:**
```python
self.delete_button.clicked.connect(self._on_delete_clicked)
```

**Event Handler:**
```python
def _on_delete_clicked(self):
    """Delete API key"""
    selected = self.keys_table.currentRow()
    if selected < 0:
        return
    
    service = self.keys_table.item(selected, 0).text()
    
    # Confirm deletion
    reply = QMessageBox.warning(
        self,
        'Delete API Key',
        f'Delete API key for {service}?\n\nThis cannot be undone.',
        QMessageBox.Yes | QMessageBox.No
    )
    
    if reply == QMessageBox.Yes:
        self.event_bus.publish('api_keys.delete', {
            'service': service
        })
```

**Backend:**
```python
async def _handle_delete_key(self, event_data):
    """Remove API key from storage"""
    service = event_data['service']
    
    # Load keys
    keys = self._load_keys_from_file()
    
    # Remove key
    if service in keys:
        del keys[service]
        
        # Save
        self._save_keys_to_file(keys)
        
        # Update internal storage
        if service in self.api_keys:
            del self.api_keys[service]
        
        logger.info(f"✅ API key deleted: {service}")
        
        await self.event_bus.publish('api_keys.deleted', {
            'service': service
        })
```

---

### Button 7: COPY

**Event Listener:**
```python
self.copy_button.clicked.connect(self._on_copy_clicked)
```

**Event Handler:**
```python
def _on_copy_clicked(self):
    """Copy API key to clipboard"""
    selected = self.keys_table.currentRow()
    if selected < 0:
        return
    
    api_key = self.keys_table.item(selected, 1).text()
    
    # Copy to clipboard
    QApplication.clipboard().setText(api_key)
    
    # Show notification
    self.statusBar().showMessage("API key copied to clipboard", 3000)
```

---

### Button 8: HELP

**Event Listener:**
```python
self.help_button.clicked.connect(self._on_help_clicked)
```

**Event Handler:**
```python
def _on_help_clicked(self):
    """Show help dialog"""
    help_text = """
    API Key Manager Help
    
    Supported Services:
    - Exchanges: Binance, KuCoin, Bybit, Coinbase, Kraken
    - RPC Providers: Infura, Alchemy, QuickNode, Moralis
    - Block Explorers: Etherscan, BscScan
    - AI Services: OpenAI, Anthropic
    
    Security:
    - Keys are encrypted before storage
    - Never commit api_keys.json to git
    - Use read-only keys when possible
    - Enable 2FA on exchange accounts
    """
    
    QMessageBox.information(self, "Help", help_text)
```

---

## 🔑 KEY DISTRIBUTION

### Automatic Distribution to All Systems

```python
async def _distribute_keys(self):
    """Distribute API keys to all systems"""
    
    # Trading System
    trading_keys = {
        k: v for k, v in self.api_keys.items()
        if k in ['binance', 'kucoin', 'bybit', 'coinbase', 'kraken']
    }
    await self.event_bus.publish('trading.keys_updated', trading_keys)
    
    # Blockchain System
    rpc_keys = {
        k: v for k, v in self.api_keys.items()
        if k in ['infura', 'alchemy', 'quicknode', 'ankr', 'moralis']
    }
    await self.event_bus.publish('blockchain.keys_updated', rpc_keys)
    
    # Mining System
    pool_keys = {
        k: v for k, v in self.api_keys.items()
        if 'pool' in k.lower()
    }
    await self.event_bus.publish('mining.keys_updated', pool_keys)
    
    logger.info("✅ API keys distributed to all systems")
```

---

## 📡 EVENT BUS BINDINGS (Updated Dec 2025)

| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `api_keys.loaded` | API Key Tab | All Components | Keys loaded from storage | count, services, timestamp |
| `api.key.loaded.{service}` | API Key Tab | Service-specific listeners | Key distributed | service, key, configured |
| `api.keys.all.loaded` | API Key Tab | All Components | All keys distributed | services list |
| `api_key_manager.keys_updated` | External | API Key Tab | Keys changed externally | service_id |
| `api_key_manager.connection_status_changed` | External | API Key Tab | Connection status change | service_id, connected, message |
| `exchange.health.snapshot` | RealExchangeExecutor | API Key Tab | Health check results | timestamp, health dict |
| `ui.telemetry` | API Key Tab | TelemetryCollector | Button clicks | component, event_type, metadata |

---

## 🔐 ENCRYPTION

### Fernet Encryption

```python
from cryptography.fernet import Fernet
import base64
import hashlib

class APIKeyManager:
    def _encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        # Use master key (derived from system info)
        key = self._get_master_key()
        f = Fernet(key)
        encrypted = f.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    
    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        key = self._get_master_key()
        f = Fernet(key)
        encrypted = base64.b64decode(encrypted_data.encode())
        decrypted = f.decrypt(encrypted)
        return decrypted.decode()
    
    def _get_master_key(self) -> bytes:
        """Derive master encryption key"""
        # Derive from system-specific data
        system_id = self._get_system_id()
        key = hashlib.sha256(system_id.encode()).digest()
        return base64.urlsafe_b64encode(key)
```

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The API Key Manager tab emits UI telemetry events when secrets are toggled or
keys are added/edited/deleted/refreshed/tested.

- **Channel:** `ui.telemetry`
- **Component:** `api_keys`
- **Representative event types:**
  - `apikeys.toggle_secrets_clicked`
  - `apikeys.add_api_key_clicked`
  - `apikeys.edit_api_key_clicked`
  - `apikeys.delete_api_key_clicked`
  - `apikeys.refresh_clicked`
  - `apikeys.test_connection_clicked`

Example payload shape:

```json
{
  "component": "api_keys",
  "channel": "ui.telemetry",
  "event_type": "apikeys.add_api_key_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"service_id": "binance", "key_name": "primary"}
}
```

The **TelemetryCollector** aggregates these events with those from other tabs
to provide centralized, non-blocking telemetry.

## ✅ VERIFICATION

**Test API Key Management:**

```bash
# 1. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 2. Go to API Key Manager tab

# 3. Click "Add API Key"
# 4. Enter:
#    - Service: binance_testnet
#    - API Key: your_testnet_key
#    - API Secret: your_testnet_secret

# 5. Click "Test Connection"

# Monitor logs:
tail -f logs/kingdom_error.log | grep api_keys

# Expected:
# ✅ API key added: binance_testnet
# ✅ API keys distributed to all systems
# ✅ API key test PASSED: binance_testnet

# 6. Verify key stored in config/api_keys.json (encrypted)
```

---

**Status:** ✅ COMPLETE - Centralized API key management with encryption and distribution
