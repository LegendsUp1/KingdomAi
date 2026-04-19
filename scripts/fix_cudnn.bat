@echo off
REM SOTA 2026: Fix cuDNN version mismatch
REM Run this in kingdom-ai conda environment

echo ========================================
echo Kingdom AI - cuDNN Fix (SOTA 2026)
echo ========================================
echo.

echo Upgrading nvidia-cudnn-cu12 to latest version (9.19.0+)...
pip install --upgrade nvidia-cudnn-cu12>=9.19.0
echo.

echo Reinstalling JAX with bundled CUDA 12...
pip install --upgrade "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
echo.

echo ========================================
echo Fix complete! Restart Python to apply.
echo ========================================
pause
