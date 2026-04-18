# Kingdom AI Quantum Computing Integration

## SOTA 2026 Update: Universal Quantum Enhancement

All Kingdom AI components can now utilize real IBM Quantum and OpenQuantum hardware through the **QuantumEnhancementBridge**. This provides quantum-enhanced operations for:

- **Vision Stream** - Quantum-optimized image processing parameters
- **Trading** - QAOA portfolio optimization, Grover arbitrage detection
- **Mining** - Real quantum hardware for Grover's algorithm mining
- **Code Generation** - Quantum-optimized code pattern selection
- **AI/ML** - Quantum uncertainty quantification
- **Consciousness** - Real quantum coherence and entanglement

## Overview

Kingdom AI integrates with real quantum computing hardware through two providers:

1. **IBM Quantum Platform** - Access to IBM's fleet of quantum processors via `qiskit-ibm-provider`
2. **OpenQuantum SDK** - Multi-provider quantum access via `openquantum-sdk`

**NO SIMULATORS OR MOCKS** - The system prioritizes real quantum hardware. Local simulators are only used as a fallback when no real hardware is available.

## Configuration

### API Keys Setup

Add your quantum API keys to `config/api_keys.env`:

```bash
# IBM Quantum API Key (from quantum.ibm.com)
IBM_QUANTUM_API_KEY=your_ibm_quantum_token_here
QISKIT_IBM_TOKEN=your_ibm_quantum_token_here

# OpenQuantum SDK Key (from openquantum.com)
OPENQUANTUM_SDK_KEY=your_openquantum_sdk_key_here
OPENQUANTUM_API_KEY=your_openquantum_sdk_key_here
```

Or add to `config/api_keys.json`:

```json
{
  "_QUANTUM_COMPUTING": {
    "ibm_quantum": {
      "api_key": "your_ibm_quantum_token_here",
      "token": "your_ibm_quantum_token_here",
      "instance": "ibm-q/open/main"
    },
    "openquantum": {
      "sdk_key": "your_openquantum_sdk_key_here",
      "api_key": "your_openquantum_sdk_key_here"
    }
  }
}
```

### Getting API Keys

#### IBM Quantum
1. Visit [quantum.ibm.com](https://quantum.ibm.com)
2. Create an account or log in
3. Go to Account Settings → API Token
4. Copy your API token

#### OpenQuantum
1. Visit [openquantum.com](https://www.openquantum.com)
2. Create an account
3. Navigate to SDK Keys section
4. Generate and copy your SDK key

## Dependencies

Install required packages:

```bash
pip install qiskit qiskit-ibm-provider openquantum-sdk
```

Optional for local simulation fallback:
```bash
pip install qiskit-aer
```

## Usage

### Detecting Quantum Hardware

```python
from core.quantum_mining import QuantumMiningSupport, is_real_quantum_available

# Check if real quantum hardware is available
if is_real_quantum_available():
    print("Real quantum hardware available!")

# Detect all available backends
import asyncio
devices = asyncio.run(QuantumMiningSupport.detect_quantum_hardware())

for device in devices:
    print(f"Device: {device['name']}")
    print(f"  Type: {device['type']}")
    print(f"  Provider: {device.get('provider', 'unknown')}")
    print(f"  Qubits: {device['qubits']}")
```

### Submitting Jobs to IBM Quantum

```python
from qiskit import QuantumCircuit
from core.quantum_mining import QuantumMiningSupport
import asyncio

# Create a simple circuit
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

# Submit to IBM Quantum
result = asyncio.run(QuantumMiningSupport.submit_to_ibm_quantum(qc, shots=1024))

if result:
    print(f"Backend: {result['backend']}")
    print(f"Counts: {result['counts']}")
```

### Submitting Jobs to OpenQuantum

```python
from core.quantum_mining import QuantumMiningSupport
import asyncio

# QASM circuit string
qasm = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""

# Submit to OpenQuantum
result = asyncio.run(QuantumMiningSupport.submit_to_openquantum(qasm, shots=1024))

if result:
    print(f"Job ID: {result['job_id']}")
    print(f"Counts: {result['counts']}")
```

### Getting Provider Status

```python
from core.quantum_mining import QuantumMiningSupport

status = QuantumMiningSupport.get_quantum_status()

print(f"Qiskit Available: {status['qiskit_available']}")
print(f"IBM Quantum Available: {status['ibm_quantum']['available']}")
print(f"IBM Backends: {status['ibm_quantum']['backend_count']}")
print(f"OpenQuantum Available: {status['openquantum']['available']}")
print(f"Fallback Simulator: {status['fallback_simulator']}")
```

## Architecture

### QuantumProviderManager

Singleton class that manages all quantum provider connections:

- Loads API keys from `GlobalAPIKeys` registry or environment variables
- Initializes IBM Quantum provider with token
- Initializes OpenQuantum SDK clients
- Filters out simulators to ensure real hardware usage
- Provides thread-safe access to backends

### QuantumMiningSupport

Main class for quantum mining operations:

- `detect_quantum_hardware()` - Detect all available quantum backends
- `run_quantum_mining_iteration()` - Execute mining iteration on quantum hardware
- `submit_to_ibm_quantum()` - Submit circuit to IBM Quantum
- `submit_to_openquantum()` - Submit QASM to OpenQuantum
- `get_quantum_status()` - Get provider availability status

### Priority Order

1. **IBM Quantum Real Hardware** - Always preferred when available
2. **OpenQuantum Multi-Provider** - Secondary option for multi-provider access
3. **Local Simulator** - Only used as fallback when no real hardware available

## Graceful Degradation

The system operates correctly regardless of quantum key availability:

| Scenario | Behavior |
|----------|----------|
| Both keys configured | Use real quantum hardware from both providers |
| Only IBM key | Use IBM Quantum backends only |
| Only OpenQuantum key | Use OpenQuantum backends only |
| No keys configured | Fall back to local simulator (if available) |
| No simulator available | Quantum mining disabled, classical mining continues |

## Troubleshooting

### "IBM Quantum provider not configured"

This info message appears when:
- No IBM Quantum API key is configured
- The API key is invalid or expired
- Network connectivity issues

**Solution**: Ensure `IBM_QUANTUM_API_KEY` is set correctly in your environment or config files.

### "OpenQuantum init failed"

This warning appears when:
- No OpenQuantum SDK key is configured
- The SDK key is invalid
- OpenQuantum servers are unreachable

**Solution**: Verify your OpenQuantum SDK key and network connectivity.

### TLS/SSL Errors

If you encounter TLS errors:
1. Update your Python SSL certificates
2. Check firewall settings
3. Verify network proxy configuration

## Integration with Mining System

The quantum mining module is automatically integrated with the Kingdom AI mining system:

```python
from core.mining_system import MiningSystem

# MiningSystem automatically uses QuantumMiningSupport
mining = MiningSystem(event_bus=event_bus)
await mining.start_mining(algorithm="quantum")
```

## Event Bus Topics

The quantum system publishes events on these topics:

- `quantum.hardware.detected` - When quantum backends are discovered
- `quantum.job.submitted` - When a job is submitted
- `quantum.job.completed` - When a job completes
- `quantum.provider.status` - Provider status changes

## Security Notes

- API keys are never logged in full
- Keys are loaded from secure config files
- IBM Quantum accounts are saved locally for session persistence
- OpenQuantum SDK uses secure HTTPS connections
