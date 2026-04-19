# Kingdom AI System

## Overview

This repository contains the Kingdom AI System, an advanced cryptocurrency trading and mining platform with self-modifying capabilities.

## Features

- Advanced trading algorithms with real-time optimization
- Self-modifying AI system with code generation
- Dynamic code injection and runtime modifications
- Quantum computing integration
- Comprehensive security features
- Real-time system adaptation
- Advanced mining system with GPU optimization and real-time monitoring
- Real-time market data integration with websocket support
- Blockchain integration with Web3 support
- Event-driven architecture with async communication
- Voice interface with natural language processing
- VR integration for immersive trading experience
- Secure wallet management and transaction handling

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/kingdom-ai.git
cd kingdom-ai
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure API keys and settings:

```bash
# Copy the example config files
cp config/api_keys.example.json config/api_keys.json

# Edit the API keys file with your credentials
# Add your Infura project ID, Alchemy API key, or other blockchain provider credentials
nano config/api_keys.json
```

## Blockchain Configuration

### 1. Set Up Blockchain Connection

Use the interactive setup script to configure your blockchain connection:

```bash
python scripts/setup_blockchain.py
```

Follow the prompts to configure:
- Network (Mainnet/Testnet/Custom RPC)
- RPC endpoint URL
- Chain ID (for custom RPC)
- SSL settings

### 2. Verify Blockchain Connection

After configuration, verify your blockchain connection:

```bash
python scripts/verify_blockchain.py
```

This will test the connection and provide troubleshooting tips if needed.

### 3. Configuration Files

- `config/blockchain/ethereum.json`: Main blockchain configuration
- `config/api_keys.json`: API keys for blockchain providers and other services

### 4. Environment Variables (Optional)

For advanced configuration, you can set these environment variables:

```bash
# For Infura
INFURA_PROJECT_ID=your_infura_project_id

# For custom RPC
BLOCKCHAIN_RPC_URL=http://your-node:8545
BLOCKCHAIN_CHAIN_ID=1  # 1 for Ethereum Mainnet, 11155111 for Sepolia, etc.
```

## Usage

Basic usage example with self-modifying capabilities:

```python
from kingdom_ai import KingdomAI
from kingdom_ai.code_generator import CodeGenerator
from kingdom_ai.system_modifier import SystemModifier

# Initialize the system
system = KingdomAI()

# Enable real-time code generation and injection
code_generator = CodeGenerator()
system_modifier = SystemModifier()

# Start trading with self-modification enabled
system.start_trading(
    allow_self_modification=True,
    code_generator=code_generator,
    system_modifier=system_modifier
)

# System will now:
# 1. Monitor performance metrics
# 2. Generate optimized code
# 3. Test generated code in sandbox
# 4. Inject verified improvements
# 5. Adapt in real-time
```

### Mining System Usage

The Kingdom AI Mining System provides powerful cryptocurrency mining capabilities with intelligent optimization:

```python
from kingdom_ai import KingdomAI
from kingdom_ai.core.mining_system import MiningSystem, MiningConfig
from kingdom_ai.core.event_bus import EventBus

# Initialize the system
system = KingdomAI()
event_bus = EventBus.get_instance()

# Configure mining system
config = MiningConfig(
    algorithm="SHA-256",
    threads=4,
    target_difficulty=4,
    wallet_address="your_wallet_address"
)

# Initialize mining system
mining = MiningSystem(config, event_bus)

# Start mining with automatic optimization
async def start_mining():
    # Initialize mining system
    if not mining.initialize():
        raise Exception("Failed to initialize mining system")
    
    # Subscribe to mining events
    await event_bus.subscribe("mining.block_mined", handle_block_mined)
    await event_bus.subscribe("mining.stats", handle_mining_stats)
    
    # Start mining
    if not await mining.start():
        raise Exception("Failed to start mining")
    
    # Monitor mining stats
    while True:
        stats = await mining.get_stats()
        print(f"Mining stats: {stats}")
        await asyncio.sleep(10)

async def handle_block_mined(event):
    """Handle block mined event."""
    print(f"Block mined: {event}")

async def handle_mining_stats(event):
    """Handle mining stats event."""
    print(f"Mining stats update: {event}")
```

### Market Data Integration

Example of using the market data API:

```python
from kingdom_ai import KingdomAI
from kingdom_ai.core.market_api import MarketAPI
from kingdom_ai.core.event_bus import EventBus

# Initialize the system
system = KingdomAI()
event_bus = EventBus.get_instance()

# Initialize market API
market = MarketAPI(
    api_key="your_api_key",
    api_secret="your_api_secret",
    event_bus=event_bus
)

# Start market data streaming
async def start_market_data():
    # Initialize API
    if not await market.initialize():
        raise Exception("Failed to initialize market API")
    
    # Connect to websocket
    if not await market.connect_websocket():
        raise Exception("Failed to connect to websocket")
    
    # Subscribe to market data
    await market.subscribe("BTCUSDT", ["trade", "kline_1m"])
    
    # Monitor market data
    while True:
        data = market.get_market_data("BTCUSDT")
        print(f"Market data: {data}")
        await asyncio.sleep(1)
```

### Blockchain Integration

Example of using the blockchain connector:

```python
from kingdom_ai import KingdomAI
from kingdom_ai.core.blockchain import BlockchainConnector, BlockchainConfig

# Initialize the system
system = KingdomAI()

# Configure blockchain connector
config = BlockchainConfig(
    network="mainnet",
    node_url="https://mainnet.infura.io/v3/your-project-id",
    chain_id=1,
    contracts={
        "token": "0x123...",
        "exchange": "0x456..."
    }
)

# Initialize blockchain connector
blockchain = BlockchainConnector(config)

# Use blockchain features
async def use_blockchain():
    # Connect to network
    if not await blockchain.connect():
        raise Exception("Failed to connect to blockchain")
    
    # Get balance
    balance = await blockchain.get_balance("0x789...")
    print(f"Balance: {balance}")
    
    # Send transaction
    tx_hash = await blockchain.send_transaction(
        from_address="0x123...",
        to_address="0x456...",
        value=1000000000000000000  # 1 ETH in wei
    )
    print(f"Transaction sent: {tx_hash}")
    
    # Get transaction details
    tx = await blockchain.get_transaction(tx_hash)
    print(f"Transaction details: {tx}")
```

## Architecture

The Kingdom AI System uses an event-driven architecture with the following key components:

1. Core Components:
   - Event Bus: Central communication system
   - Component Manager: Lifecycle management
   - Security Manager: Access control and validation
   - Configuration Manager: System settings
   
2. Trading Components:
   - Market API: Real-time market data
   - Trading Engine: Order execution
   - Strategy Engine: Trading algorithms
   - Risk Manager: Position management
   
3. Mining Components:
   - Mining System: Proof of work mining
   - Block Manager: Blockchain operations
   - Hash Power Manager: Resource optimization
   - Mining Pool Connector: Pool integration
   
4. AI Components:
   - Thoth AI: Advanced reasoning
   - Code Generator: Self-modification
   - System Modifier: Runtime adaptation
   - Model Manager: AI model handling
   
5. Interface Components:
   - Voice Manager: Speech processing
   - VR Manager: Virtual reality
   - GUI Manager: User interface
   - API Server: External access

## Security

The system implements comprehensive security measures:

1. Code Validation:
   - Runtime code verification
   - Sandbox testing
   - Security policy enforcement
   
2. Access Control:
   - Role-based permissions
   - API key management
   - Request validation
   
3. Data Protection:
   - Encryption at rest
   - Secure communication
   - Key management
   
4. System Security:
   - Process isolation
   - Resource limits
   - Error handling
   
5. Monitoring:
   - Activity logging
   - Anomaly detection
   - Performance tracking

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
