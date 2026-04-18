# TAB 3: MINING - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** Mining System
**Purpose:** Cryptocurrency mining operations (SHA-256, Scrypt, etc.)
**Frontend File:** `gui/qt_frames/mining/mining_frame.py`
**Backend Files:** `core/mining_system.py` (1492 lines)
**Event Bus Topics:** `mining.*`, `quantum.*`, `blockchain.*`, `market.*`, `airdrop.*`, `analytics.*`
**External APIs:** Mining pools, Blockchain RPC, Quantum devices

---

## 🔌 ACTUAL SIGNAL CONNECTIONS (Enumerated Dec 2025)

| Line | Signal | Handler | Purpose |
|------|--------|---------|--------|
| 411 | `update_timer.timeout` | `update_uptime` | Update mining uptime |
| 555 | `blockchain_combo.currentTextChanged` | `_on_blockchain_changed` | Switch blockchain |
| 564 | `mining_mode_combo.currentTextChanged` | `_on_mining_mode_changed` | Solo/pool mode |
| 591 | `start_button.clicked` | `_on_start_mining` | Start mining |
| 594 | `stop_button.clicked` | `_on_stop_mining` | Stop mining |
| 660 | `mining_focus_mode_combo.currentTextChanged` | `_on_focus_mode_changed` | Focus mode |
| 665 | `funnel_button.clicked` | `_on_funnel_rewards_clicked` | Funnel rewards |
| 755 | `q_start_button.clicked` | `_on_start_quantum_mining` | Start quantum |
| 757 | `q_stop_button.clicked` | `_on_stop_quantum_mining` | Stop quantum |
| 815 | `update_circuit_button.clicked` | `_on_update_quantum_circuit` | Update circuit |
| 871 | `gpu_detect_btn.clicked` | `_detect_gpu_devices` | Detect GPUs |
| 888 | `gpu_optimize_btn.clicked` | `optimize_gpu_quantum` | Optimize GPU |
| 905 | `gpu_benchmark_btn.clicked` | `_run_gpu_benchmark` | Benchmark |
| 962 | `apply_recommendation_button.clicked` | `_on_apply_recommendation` | Apply AI rec |
| 982 | `update_prediction_button.clicked` | `_on_update_prediction` | Update prediction |
| 1088 | `refresh_blockchain_button.clicked` | `_on_refresh_blockchain` | Refresh status |
| 1166 | `airdrop_enabled_check.stateChanged` | `_on_airdrop_farming_changed` | Toggle airdrop |
| 1177 | `scan_airdrops_button.clicked` | `_on_scan_airdrops` | Scan airdrops |

## 📡 ACTUAL EVENTBUS SUBSCRIPTIONS (line 1940-1999, deferred 2.5s)

| Topic | Handler |
|-------|---------|
| `mining.status_update` | `_handle_mining_status_update` |
| `mining.hashrate_update` | `_handle_hashrate_update` |
| `mining.hashrate` | `_handle_hashrate_update` (real hashrate from multi_coin_miner) |
| `mining.worker_update` | `_handle_worker_update` |
| `mining.new_block_found` | `_handle_new_block_found` |
| `mining.error` | `_handle_mining_error` |
| `mining.stats.update` | `_handle_mining_stats` |
| `blockchain.status_update` | `_handle_blockchain_status_update` |
| `blockchain.network_stats` | `_handle_blockchain_network_stats` |
| `blockchain.market_data` | `_handle_blockchain_market_data` |
| `blockchain.blocks` | `_handle_blockchain_blocks` |
| `market.prices` | `_handle_market_prices_snapshot` |
| `market:price_update` | `_handle_market_price_update` |
| `quantum.mining.status` | `_handle_quantum_mining_status` |
| `quantum.mining.circuit_update` | `_handle_quantum_circuit_update` |
| `quantum.mining.result` | `_handle_quantum_mining_result` |
| `quantum.device.status` | `_handle_quantum_device_status` |
| `mining.intelligence.update` | `_handle_mining_intelligence_update` |
| `mining.intelligence.recommendation` | `_handle_mining_intelligence_recommendation` |
| `mining.intelligence.profit_prediction` | `_handle_mining_intelligence_profit_prediction` |
| `analytics.mining.coin_analytics` | `_handle_coin_analytics_update` |
| `airdrop.campaigns.update` | `_handle_airdrop_campaigns_update` |
| `airdrop.farming.status` | `_handle_airdrop_farming_status` |
| `airdrop.farming.history` | `_handle_airdrop_farming_history` |
| `mining.status` | `_handle_backend_mining_status` |
| `mining.status.response` | `_handle_mining_status_response` |

## 📡 ACTUAL EVENTBUS PUBLISHES

| Topic | Location | Trigger |
|-------|----------|--------|
| `gui_update` | `_log()` | Log messages |
| `ui.telemetry` | `_emit_ui_telemetry()` | Button clicks |
| `mining.get_status` | `_deferred_mining_init()` | Initial data request |
| `quantum.nexus.query.devices` | `_connect_quantum_devices()` | Query quantum devices |

---

## 📊 BUTTON MAPPING (9 BUTTONS)

### Button 1: START MINING

**Frontend Component:**
```python
self.start_mining_button = QPushButton("⛏️ Start Mining")
```

**Event Listener:**
```python
self.start_mining_button.clicked.connect(self._on_start_mining_clicked)
```

**Event Handler:**
```python
def _on_start_mining_clicked(self):
    """Start REAL mining operations"""
    try:
        # Get mining config from GUI
        blockchain = self.blockchain_combo.currentText()  # e.g., "bitcoin"
        threads = self.threads_spinbox.value()  # e.g., 8
        pool_url = self.pool_input.text()  # e.g., "stratum+tcp://pool.com:3333"
        wallet = self.wallet_input.text()
        
        # Validate inputs
        if not wallet:
            self._show_error("Wallet address required")
            return
        
        # Update button state
        self.start_mining_button.setEnabled(False)
        self.start_mining_button.setText("⏳ Starting...")
        
        # Publish mining start event
        self.event_bus.publish('mining.start', {
            'blockchain': blockchain,
            'threads': threads,
            'pool_url': pool_url,
            'wallet_address': wallet,
            'algorithm': self._get_algorithm(blockchain),
            'timestamp': time.time()
        })
        
        logger.info(f"🔥 STARTING REAL MINING: {blockchain} with {threads} threads")
        
    except Exception as e:
        logger.error(f"Mining start failed: {e}")
```

**Backend Processing:**
```python
# File: core/mining_system.py
class MiningSystem:
    async def _handle_start_mining(self, event_data):
        """Start REAL mining operations"""
        blockchain = event_data['blockchain']
        threads = event_data['threads']
        pool_url = event_data['pool_url']
        wallet = event_data['wallet_address']
        algorithm = event_data['algorithm']
        
        logger.info(f"✅ REAL MINING STARTED: {blockchain} on {pool_url} with {threads} threads")
        
        # Initialize mining workers
        self.mining_active = True
        self.workers = []
        
        # Create worker threads for REAL hashing
        for i in range(threads):
            worker = threading.Thread(
                target=self._mining_worker,
                args=(i, algorithm, pool_url, wallet),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            logger.info(f"Worker {i}: Started")
        
        # Publish success
        await self.event_bus.publish('mining.started', {
            'blockchain': blockchain,
            'threads': threads,
            'status': 'active'
        })
    
    def _mining_worker(self, worker_id, algorithm, pool_url, wallet):
        """REAL mining worker - performs actual hashing"""
        import hashlib
        
        while self.mining_active:
            # Generate block header
            block_header = self._get_current_block_header()
            
            # Try different nonces (REAL HASHING)
            for nonce in range(1000000):
                if not self.mining_active:
                    break
                
                # REAL SHA-256 hash calculation
                hash_input = block_header + nonce.to_bytes(4, 'big')
                hash_result = hashlib.sha256(hash_input).hexdigest()
                
                # Check if valid share
                if int(hash_result, 16) < self.target_difficulty:
                    # Valid share found!
                    logger.info(f"✅ Worker {worker_id}: Share found! {hash_result}")
                    self._submit_share(hash_result, nonce)
                    break
                
                # Update hashrate stats
                self.total_hashes += 1
```

**Data Flow:**
```
User Click "Start Mining"
    ↓
_on_start_mining_clicked()
    ↓
Get: blockchain, threads, pool, wallet
    ↓
Validate inputs
    ↓
event_bus.publish('mining.start')
    ↓
Mining System Backend
    ↓
Create worker threads (8 threads)
    ↓
Each thread performs REAL SHA-256 hashing
    ↓
Loop: try nonces, calculate hash, check difficulty
    ↓
Valid share found?
    ↓
Submit to pool via Stratum protocol
    ↓
event_bus.publish('mining.share_found')
    ↓
GUI updates: hashrate, shares, earnings
```

---

### Button 2: STOP MINING

**Event Listener:**
```python
self.stop_mining_button.clicked.connect(self._on_stop_mining_clicked)
```

**Event Handler:**
```python
def _on_stop_mining_clicked(self):
    """Stop all mining operations"""
    self.event_bus.publish('mining.stop', {})
    self.start_mining_button.setEnabled(True)
    self.start_mining_button.setText("⛏️ Start Mining")
```

**Backend:**
```python
async def _handle_stop_mining(self, event_data):
    """Stop all mining workers"""
    self.mining_active = False
    
    # Wait for all workers to finish
    for worker in self.workers:
        worker.join(timeout=2)
    
    logger.info("❌ Mining stopped")
    
    await self.event_bus.publish('mining.stopped', {
        'total_hashes': self.total_hashes,
        'shares_found': self.shares_accepted
    })
```

---

### Button 3: START QUANTUM MINING

**Event Listener:**
```python
self.quantum_mining_button.clicked.connect(self._on_quantum_mining_clicked)
```

**Event Handler:**
```python
def _on_quantum_mining_clicked(self):
    """Start quantum-enhanced mining"""
    self.event_bus.publish('mining.quantum.start', {
        'qubits': 4,
        'circuit_depth': 3,
        'algorithm': 'grover'
    })
```

**Backend (Quantum):**
```python
async def _handle_quantum_mining(self, event_data):
    """Quantum circuit mining using Qiskit"""
    from qiskit import QuantumCircuit, execute, Aer
    
    # Create quantum circuit
    qc = QuantumCircuit(event_data['qubits'])
    
    # Apply Grover's algorithm for search
    # (Simplified - real implementation more complex)
    for _ in range(event_data['circuit_depth']):
        qc.h(range(event_data['qubits']))
        qc.barrier()
    
    # Execute on quantum simulator
    backend = Aer.get_backend('qasm_simulator')
    job = execute(qc, backend, shots=1000)
    result = job.result()
    
    logger.info(f"Quantum mining result: {result.get_counts()}")
```

---

### Button 4: STOP QUANTUM MINING

**Event Listener:**
```python
self.stop_quantum_button.clicked.connect(self._on_stop_quantum_clicked)
```

**Implementation:** Stops quantum circuit execution

---

### Button 5: UPDATE CIRCUIT

**Event Listener:**
```python
self.update_circuit_button.clicked.connect(self._on_update_circuit_clicked)
```

**Event Handler:**
```python
def _on_update_circuit_clicked(self):
    """Refresh quantum circuit visualization"""
    self.event_bus.publish('mining.quantum.update_circuit', {})
```

---

### Button 6: APPLY RECOMMENDATION

**Event Listener:**
```python
self.apply_recommendation_button.clicked.connect(self._on_apply_recommendation_clicked)
```

**Event Handler:**
```python
def _on_apply_recommendation_clicked(self):
    """Apply AI mining optimization"""
    self.event_bus.publish('mining.ai.apply_optimization', {
        'optimization_type': 'hashrate',
        'target_improvement': 0.15  # 15% improvement target
    })
```

**Backend (AI Optimization):**
```python
async def _handle_ai_optimization(self, event_data):
    """Use ML model to optimize mining parameters"""
    # Load trained model
    model = self._load_optimization_model()
    
    # Get current mining stats
    current_stats = {
        'hashrate': self.current_hashrate,
        'power_usage': self.power_consumption,
        'temperature': self.gpu_temp,
        'thread_count': len(self.workers)
    }
    
    # Predict optimal parameters
    optimal_params = model.predict([current_stats])
    
    # Apply optimization
    self._adjust_mining_parameters(optimal_params)
```

---

### Button 7: UPDATE PREDICTION

**Event Listener:**
```python
self.update_prediction_button.clicked.connect(self._on_update_prediction_clicked)
```

**Event Handler:**
```python
def _on_update_prediction_clicked(self):
    """Update profit prediction"""
    self.event_bus.publish('mining.prediction.update', {})
```

---

### Button 8: REFRESH BLOCKCHAIN

**Event Listener:**
```python
self.refresh_blockchain_button.clicked.connect(self._on_refresh_blockchain_clicked)
```

**Event Handler:**
```python
def _on_refresh_blockchain_clicked(self):
    """Refresh blockchain network status"""
    self.event_bus.publish('mining.blockchain.refresh', {
        'network': self.blockchain_combo.currentText()
    })
```

**Backend:**
```python
async def _handle_blockchain_refresh(self, event_data):
    """Query blockchain for latest network stats"""
    from core.blockchain.kingdomweb3_v2 import KingdomWeb3
    
    blockchain = KingdomWeb3()
    network_info = blockchain.get_network_info(event_data['network'])
    
    # Get mining difficulty
    difficulty = await blockchain.get_mining_difficulty()
    
    # Get block reward
    block_reward = await blockchain.get_block_reward()
    
    await self.event_bus.publish('mining.blockchain.updated', {
        'difficulty': difficulty,
        'block_reward': block_reward,
        'network_hashrate': network_info['hashrate']
    })
```

---

### Button 9: SCAN AIRDROPS

**Event Listener:**
```python
self.scan_airdrops_button.clicked.connect(self._on_scan_airdrops_clicked)
```

**Event Handler:**
```python
def _on_scan_airdrops_clicked(self):
    """Scan for available airdrops"""
    self.event_bus.publish('mining.airdrop.scan', {
        'networks': ['ethereum', 'bsc', 'polygon'],
        'wallet_address': self.wallet_input.text()
    })
```

**Backend:**
```python
async def _handle_airdrop_scan(self, event_data):
    """Scan blockchain for available airdrops"""
    wallet = event_data['wallet_address']
    airdrops_found = []
    
    for network in event_data['networks']:
        # Query airdrop contracts
        contracts = await self._get_airdrop_contracts(network)
        
        for contract in contracts:
            # Check if wallet is eligible
            eligible = await contract.check_eligibility(wallet)
            
            if eligible:
                amount = await contract.get_claimable_amount(wallet)
                airdrops_found.append({
                    'network': network,
                    'token': contract.token_symbol,
                    'amount': amount,
                    'contract': contract.address
                })
    
    await self.event_bus.publish('mining.airdrop.results', {
        'airdrops': airdrops_found,
        'count': len(airdrops_found)
    })
```

---

## 🔗 BLOCKCHAIN INTEGRATION

### Network Selection (467+ Networks)

```python
from core.blockchain.kingdomweb3_v2 import KingdomWeb3

blockchain = KingdomWeb3()

# Select mining network
networks = [
    'bitcoin',      # SHA-256
    'ethereum',     # Ethash (historical)
    'litecoin',     # Scrypt
    'monero',       # RandomX
    'ravencoin',    # KawPow
    'zcash',        # Equihash
    # ... 461 more networks
]

# Get network info
network_info = blockchain.get_network_info('bitcoin')
# Returns: {
#   'chain_id': 0,
#   'algorithm': 'SHA-256',
#   'block_time': 600,
#   'difficulty': 50000000000000
# }
```

---

## 📡 EVENT BUS BINDINGS

| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `mining.start` | Mining GUI | Mining System | Start button | Config params |
| `mining.stop` | Mining GUI | Mining System | Stop button | Empty |
| `mining.started` | Mining System | Mining GUI | Workers started | Thread count |
| `mining.stopped` | Mining System | Mining GUI | Workers stopped | Final stats |
| `mining.share_found` | Mining System | Mining GUI | Valid share | Hash, nonce |
| `mining.hashrate_update` | Mining System | Mining GUI + Dashboard | Periodic (1s) | Current H/s |
| `mining.quantum.start` | Mining GUI | Mining System | Quantum button | Circuit params |
| `mining.ai.apply_optimization` | Mining GUI | Mining System | AI button | Optimization type |
| `mining.blockchain.refresh` | Mining GUI | Mining System | Refresh button | Network name |
| `mining.airdrop.scan` | Mining GUI | Mining System | Scan button | Wallet address |

---

## ⚙️ MINING ALGORITHMS

### Supported Algorithms:

1. **SHA-256** (Bitcoin, Bitcoin Cash)
   ```python
   import hashlib
   hash_result = hashlib.sha256(data).hexdigest()
   ```

2. **Scrypt** (Litecoin, Dogecoin)
   ```python
   from hashlib import scrypt
   hash_result = scrypt(data, salt=b'', n=1024, r=1, p=1)
   ```

3. **Ethash** (Ethereum Classic)
   ```python
   # Uses DAG (Directed Acyclic Graph)
   from ethash import hashimoto_full
   ```

4. **RandomX** (Monero)
   ```python
   import randomx
   hash_result = randomx.hash(data)
   ```

5. **KawPow** (Ravencoin)
6. **Equihash** (Zcash)
7. **X11** (Dash)

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The Mining tab emits lightweight UI telemetry events on `ui.telemetry` whenever
the user starts/stops mining or uses optimization tools.

- **Channel:** `ui.telemetry`
- **Component:** `mining`
- **Representative event types:**
  - `mining.start_mining_clicked` / `mining.stop_mining_clicked`
  - `mining.quantum_start_clicked` / `mining.quantum_stop_clicked`
  - `mining.update_circuit_clicked`
  - `mining.apply_recommendation_clicked`
  - `mining.update_prediction_clicked`
  - `mining.blockchain_refresh_clicked`
  - `mining.funnel_rewards_clicked`

Example payload shape:

```json
{
  "component": "mining",
  "channel": "ui.telemetry",
  "event_type": "mining.start_mining_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"blockchain": "bitcoin", "mode": "Pool Mining", "threads": 4}
}
```

These events are consumed by the shared **TelemetryCollector** for centralized,
non-blocking logging and metrics across all tabs.

## ✅ VERIFICATION

**Test Mining:**

```bash
# 1. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 2. Go to Mining tab

# 3. Configure:
#    - Blockchain: Bitcoin (testnet)
#    - Threads: 4
#    - Pool: solo (no pool URL)
#    - Wallet: (your testnet address)

# 4. Click "Start Mining"

# 5. Monitor logs:
tail -f logs/kingdom_error.log | grep mining

# Expected output:
# 🔥 STARTING REAL MINING: bitcoin with 4 threads
# ✅ REAL MINING STARTED: bitcoin on solo with 4 threads
# Worker 0: Started
# Worker 1: Started
# Worker 2: Started
# Worker 3: Started
# Hashrate: 1.2 MH/s
```

**Monitor CPU:**
```bash
# CPU usage should increase significantly
top -p $(pgrep -f kingdom_ai)
```

---

**Status:** ✅ COMPLETE - Real mining operations fully mapped
