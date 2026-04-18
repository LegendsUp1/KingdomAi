# Fix for cuDNN/PyTorch CUDA Crash in WSL

## Problem
```
Could not load symbol cudnnGetLibConfig. Error: /root/miniconda3/envs/kingdom-ai/lib/libcudnn_graph.so.9: undefined symbol: cudnnGetLibConfig
Aborted (core dumped)
```

## Root Cause
Mixed CUDA/cuDNN versions in WSL conda environment. The cuDNN graph library (v9) is incompatible with the PyTorch CUDA runtime.

## One-Command Fix Solution

### Complete Fix (Copy & Paste All Commands)

```bash
# 1. Activate environment and clear conflicting paths
conda activate kingdom-ai
unset LD_LIBRARY_PATH
unset CUDA_HOME
unset CUDNN_PATH

# 2. Configure conda for clean install
conda config --set channel_priority strict
conda clean --all -y

# 3. Force reinstall matched PyTorch + CUDA 12.1 stack
conda install -y pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia --force-reinstall

# 4. Verify (must not crash)
python -c "import torch; import torch.backends.cudnn as cudnn; print('PyTorch:', torch.__version__); print('CUDA:', torch.version.cuda); print('GPU Available:', torch.cuda.is_available()); print('cuDNN:', cudnn.version())"

# 5. Run Kingdom AI
cd "/mnt/c/Users/Yeyian PC/Documents/Python Scripts/New folder"
python3 kingdom_ai_perfect.py
```

## Alternative if CUDA 12.1 Fails

Use CUDA 11.8 instead:

```bash
conda activate kingdom-ai
unset LD_LIBRARY_PATH
conda install -y pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia --force-reinstall
python -c "import torch; print('PyTorch:', torch.__version__, 'CUDA:', torch.version.cuda, 'Available:', torch.cuda.is_available())"
cd "/mnt/c/Users/Yeyian PC/Documents/Python Scripts/New folder"
python3 kingdom_ai_perfect.py
```

## Expected Output After Fix

When successful, verification should show:
```
PyTorch: 2.1.2
CUDA: 12.1
GPU Available: True
cuDNN: 8902
```

## Why This Works

1. **Unset LD_LIBRARY_PATH**: Prevents loading wrong CUDA libraries from system paths
2. **Channel Priority Strict**: Forces conda to resolve dependencies from same source
3. **Force Reinstall**: Replaces all mismatched components with compatible versions
4. **pytorch-cuda=12.1**: Installs complete matched runtime (PyTorch + CUDA + cuDNN)

## Verification After Kingdom AI Launches

Once the application starts without crashing:
1. ✅ GPU acceleration working (check VisualCreationCanvas)
2. ✅ VL-JEPA components load with CUDA support
3. ✅ Voice synthesis uses GPU (XTTS Black Panther)
4. ✅ All tabs initialize without cuDNN errors

## Troubleshooting

If still crashing after fix:
```bash
# Check what's actually installed
conda list | grep -E "torch|cuda|cudnn"

# Check for conflicting system CUDA
which nvcc
ls /usr/local/cuda*/lib64/libcudnn*

# Force CPU mode temporarily (last resort)
export CUDA_VISIBLE_DEVICES=""
python3 kingdom_ai_perfect.py
```

---
*Last updated: December 31, 2024*
*Status: Production Ready Fix*
