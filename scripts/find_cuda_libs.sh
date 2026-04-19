#!/bin/bash
# Find all CUDA .so files installed by pip

echo "🔍 Searching for pip-installed CUDA libraries..."
echo ""

# Search in common pip installation locations
for search_path in \
    "/usr/local/lib/python3.10/dist-packages" \
    "/root/miniconda3/envs/kingdom-ai-ml/lib/python3.10/site-packages" \
    "/usr/lib/python3.10/dist-packages" \
    "$HOME/.local/lib/python3.10/site-packages"
do
    if [ -d "$search_path" ]; then
        echo "Checking: $search_path"
        
        # Find nvidia packages
        nvidia_dirs=$(find "$search_path" -maxdepth 1 -type d -name "nvidia*" 2>/dev/null)
        
        for nv_dir in $nvidia_dirs; do
            # Look for lib directories
            if [ -d "$nv_dir/lib" ]; then
                lib_count=$(find "$nv_dir/lib" -name "*.so*" 2>/dev/null | wc -l)
                if [ $lib_count -gt 0 ]; then
                    echo "  ✅ $(basename $nv_dir)/lib: $lib_count libraries"
                    # Show first few libraries
                    find "$nv_dir/lib" -name "*.so*" 2>/dev/null | head -3 | while read lib; do
                        echo "      - $(basename $lib)"
                    done
                fi
            fi
            
            # Some packages put libs directly in package dir
            so_count=$(find "$nv_dir" -maxdepth 1 -name "*.so*" 2>/dev/null | wc -l)
            if [ $so_count -gt 0 ]; then
                echo "  ✅ $(basename $nv_dir): $so_count libraries"
                find "$nv_dir" -maxdepth 1 -name "*.so*" 2>/dev/null | head -3 | while read lib; do
                    echo "      - $(basename $lib)"
                done
            fi
        done
        
        # Also check for jax-cuda packages
        jax_dirs=$(find "$search_path" -maxdepth 1 -type d -name "jax_cuda*" 2>/dev/null)
        for jax_dir in $jax_dirs; do
            if [ -d "$jax_dir" ]; then
                echo "  ✅ Found: $(basename $jax_dir)"
                # Check for pjrt libraries
                find "$jax_dir" -name "*.so*" 2>/dev/null | head -5 | while read lib; do
                    echo "      - $(basename $lib)"
                done
            fi
        done
        echo ""
    fi
done

echo ""
echo "🔍 Searching entire filesystem for libcudart.so..."
find /usr -name "libcudart.so*" 2>/dev/null | head -10
find /opt -name "libcudart.so*" 2>/dev/null | head -10
find "$HOME" -name "libcudart.so*" 2>/dev/null | head -10

echo ""
echo "🔍 Checking what pip thinks is installed..."
pip list | grep -i cuda
pip list | grep -i nvidia
