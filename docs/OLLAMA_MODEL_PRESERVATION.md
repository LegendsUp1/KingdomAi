# Ollama Model Preservation & Auto-Update System

## SOTA 2026 - Models Work FOREVER

Kingdom AI now includes a comprehensive Ollama Model Manager that guarantees your pre-installed models will **ALWAYS work**, regardless of:

- Ollama updates
- Cloud services going down
- New versions not supporting older models
- Any other compatibility issues

## Key Features

### 1. **Auto-Backup Before Updates**
Every model blob is automatically backed up before any Ollama update:
- Full model weights preserved
- Manifest files saved
- Compatible Ollama version tracked

### 2. **Safe Auto-Update**
Ollama updates happen safely:
1. Current binary backed up
2. All model blobs preserved
3. Update performed
4. All models verified
5. If any fail → Legacy runner enabled automatically

### 3. **Legacy Model Runner**
If a model becomes incompatible with new Ollama:
- Backed-up Ollama binary is used
- Model runs in isolated environment
- Zero user intervention needed

### 4. **Model Restoration**
If models get deleted or corrupted:
- Automatic restoration from backup
- All layers and manifests restored
- Model works immediately

## Storage Locations

```
data/ollama_backups/
├── models/           # Backed up model blobs
├── binaries/         # Ollama version backups
├── manifests/        # Model manifests
└── ollama_model_registry.json  # Registry of all preserved models
```

## EventBus Topics

| Topic | Description |
|-------|-------------|
| `ollama.update.request` | Request Ollama update |
| `ollama.update.complete` | Update completed |
| `ollama.model.pull` | Pull and preserve a model |
| `ollama.model.run` | Run model (uses legacy if needed) |
| `ollama.manager.status` | Manager status updates |

## Usage

### Automatic (Recommended)
The system automatically:
- Preserves all models on startup
- Checks for Ollama updates
- Updates safely if available
- Enables legacy runners as needed

### Manual Control

```python
from core.ollama_model_manager import get_ollama_model_manager

# Get manager
manager = get_ollama_model_manager(event_bus)
await manager.initialize()

# Get preserved models
models = manager.get_preserved_models()

# Pull and preserve a new model
success, msg = await manager.pull_and_preserve("llama3:latest")

# Safe update
success, msg = await manager.safe_update_ollama()

# Run model (auto-uses legacy if needed)
response = await manager.run_model("llama2:latest", "Hello!")
```

## How It Works

### SOTA 2026 Model Discovery (WSL/Linux/Windows)
The system automatically finds your models regardless of installation type:

```
Priority order for model storage discovery:
1. OLLAMA_MODELS env var (if set)
2. /usr/share/ollama/.ollama/models  (Linux systemd service - 43GB+ in your setup)
3. ~/.ollama/models                   (User install)
4. /var/lib/ollama/.ollama/models    (Alternative service path)
5. /mnt/c/Users/<user>/.ollama/models (WSL Windows mount)

Fallback: API query to http://127.0.0.1:11434/api/tags
```

### Model Preservation Flow
```
1. Discover actual model storage (multi-path scan)
2. Query Ollama API for model list (most reliable)
3. For each model:
   a. Read manifest JSON
   b. Extract all layer digests
   c. Copy blobs to backup
   d. Save manifest copy
   e. Record in registry
```

### Update Flow
```
1. Backup current Ollama binary
2. Preserve all models
3. Run update command
4. Verify all models work
5. For failed models:
   a. Check required Ollama version
   b. Enable legacy runner if backup exists
   c. Mark model for legacy execution
```

### Legacy Execution Flow
```
1. Model marked as needing legacy runner
2. Request comes in for that model
3. System spawns backed-up Ollama binary
4. Runs on alternate port (11435)
5. Returns response
6. User sees no difference
```

## Troubleshooting

### "Model requires newer version" Error
The system handles this automatically:
1. First tries to update Ollama
2. If update fails, uses legacy runner
3. If no legacy backup, restores model and retries

### Models Missing After Update
The system auto-restores:
1. Detects missing model
2. Copies blobs from backup
3. Restores manifest
4. Model works again

### Check Preserved Models
```python
from core.ollama_model_manager import get_ollama_model_manager
manager = get_ollama_model_manager()
for m in manager.get_preserved_models():
    print(f"{m['name']}: {m['size_mb']:.1f}MB (Ollama {m['ollama_version']})")
```

## Configuration

Environment variables:
- `OLLAMA_HOST`: Ollama server address (default: 127.0.0.1:11434)
- `KINGDOM_OLLAMA_BACKUP_DIR`: Custom backup location

## Integration Points

### ThothOllamaConnector
Automatically initialized on startup:
```python
# In thoth_ollama_connector.py initialize():
if self._model_manager_enabled:
    self._model_manager = await initialize_ollama_manager(self.event_bus)
    await self._model_manager.check_and_auto_update()
```

### Kingdom AI Perfect
Can be called from main startup:
```python
from core.ollama_model_manager import initialize_ollama_manager
manager = await initialize_ollama_manager(event_bus)
```

## Guarantees

✅ **Models NEVER get deleted during updates**
✅ **Models ALWAYS run even if Ollama version is incompatible**
✅ **Pre-existing models work FOREVER regardless of cloud status**
✅ **Auto-updates Ollama without breaking existing functionality**
✅ **Zero user intervention required**
