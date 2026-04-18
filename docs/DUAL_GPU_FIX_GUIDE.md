# Kingdom AI - Dual NVIDIA GPU Fix Guide (SOTA 2026)

## Problem Statement
- **RTX 4060**: Error Code 31 in Device Manager — "This device is not working properly"
- **RTX 3050**: Working, but on old driver 560.94
- **Root Cause**: Driver version mismatch. RTX 3050 = 560.94, RTX 4060 = 566.36. Windows loads ONE `nvlddmkm.sys` kernel driver — when two GPUs need different versions, the second GPU gets Code 31.

## Solution Overview
1. **DDU** (Display Driver Uninstaller) in Safe Mode to completely remove ALL NVIDIA drivers
2. Install **one unified driver** (591.86 WHQL) that supports BOTH RTX 3050 and RTX 4060
3. Verify both GPUs work, configure Ollama for dual GPU AI inference

---

## Prerequisites (Download BEFORE Starting)

### 1. DDU (Display Driver Uninstaller)
- **Download**: https://www.wagnardsoft.com/display-driver-uninstaller-ddu
- **Latest version**: V18.1.4.1 (released Jan 26, 2026) — DDU's own release notes confirm the Win11 24H2 PIN bug
- **Extract to**: `Desktop\DDU_Tool\` (must be LOCAL disk, not network drive)
- Use the **Portable / Self-Extracting** download, NOT the installer version (avoids Intel cleanup crash bug)

### 2. NVIDIA Game Ready Driver 591.86 WHQL
- **Info page**: https://www.nvidia.com/en-us/drivers/details/263200/
- **Direct download** (876 MB): https://us.download.nvidia.com/Windows/591.86/591.86-desktop-win10-win11-64bit-international-dch-whql.exe
- **Save to**: Desktop
- WHQL-certified DCH package, released January 27, 2026
- This single package supports ALL GeForce GPUs from GTX 750 through RTX 5090
- **Verified**: Both RTX 3050 desktop (Ampere GA106, DEV_2584, CC 8.6) and RTX 4060 (Ada Lovelace AD107, DEV_2882, CC 8.9) are supported in the same INF
- **IMPORTANT**: Download the **DESKTOP** version, NOT the notebook version
- **591.86 is the LATEST driver** as of Feb 13, 2026 (confirmed via nvidia.com/drivers)

### ⚠️ 591.86 + KB5074109 Known Interaction (January 2026)
- Windows 11 January 2026 Update **KB5074109** caused black screens and game artifacts WITH 591.86
- Root cause: KB5074109, NOT the NVIDIA driver itself (confirmed by NVIDIA engineer "Manuel")
- **Your system is on Build 26100.7840 (KB5077181 — Feb 10, 2026 Patch Tuesday)** which **mitigates** the black screen issue
- The r/nvidia FAQ (825 comments) states: "KB5077181 update mitigates the issue on majority (not all) previously impacted system configurations"
- **Action**: No action needed — you already have KB5077181 installed
- **If you experience black screens after driver install**: The cause is KB5074109, not 591.86. Rolling back KB5074109 resolves it, but KB5077181 should have already fixed it

### 591.86 Known Open Issues (NVIDIA Official)
- Call of Duty: Modern Warfare image corruption [5733427]
- Some reports of random freezing on low GPU load (not widespread)
- DLSS FG/MFG frame pacing with VSync enabled in NVIDIA Control Panel
- **None of these affect AI/Ollama workloads or dual GPU operation**

### 3. Create a System Restore Point
- Press `Win+S`, type "Create a restore point"
- Click **Create**, name it `Before DDU GPU Fix`

---

## WSL2 Compatibility & CUDA Version Analysis

### Your Current WSL2 State (Verified Feb 13, 2026)
- **WSL version**: 2.6.1.0 | **Kernel**: 6.6.87.2-1 (well above 5.10.16.3 minimum)
- **Distro**: Ubuntu-22.04, Running, WSL 2
- **WSL nvidia-smi**: Driver 560.94, CUDA 12.6, only RTX 3050 visible (RTX 4060 Code 31)
- **Ollama in WSL2**: v0.15.5 at `/usr/local/bin/ollama` with ~20 models (~40+ GB)
- **Ollama on Windows**: v0.5.11 at `AppData\Local\Programs\Ollama\ollama.exe` (0 GB models)
- **WSL2 CUDA pip packages**: cuda-bindings 12.9.4, nvidia-cuda-cupti-cu12 12.8.90, nvidia-cudnn-cu12 9.10.2.21
- **lxss/lib files**: 15 `.so` files in `C:\Windows\System32\lxss\lib` dated 11/19/2024

### CUDA Version Change: 12.6 → 13.x
- **Current**: Driver 560.94 → nvidia-smi shows CUDA 12.6
- **After fix**: Driver 591.86 (>= 580) → nvidia-smi will show **CUDA 13.x**
- **This is safe because**:
  - NVIDIA drivers are **backward compatible**: "applications built against any of the older CUDA Toolkits always continued to function on newer drivers" (official NVIDIA CUDA Compatibility docs)
  - Your WSL2 pip packages (nvidia-cuda-* 12.8/12.9) will continue working
  - PyTorch compiled for CUDA 12.x works on CUDA 13.x drivers
  - Ollama uses the driver's CUDA API directly — newer driver = better support

### How WSL2 GPU Passthrough Works
1. NVIDIA Windows driver writes stub libraries to `C:\Windows\System32\lxss\lib\`
2. WSL2 auto-mounts this folder as `/usr/lib/wsl/lib/` inside Ubuntu
3. Applications in WSL2 use `libcuda.so` from this mount — **no Linux NVIDIA driver needed**
4. `nvidia-smi` in WSL is actually `C:\Windows\System32\lxss\lib\nvidia-smi`

### What Happens to lxss/lib During DDU + Reinstall
1. **DDU removes** all `.so` files from `C:\Windows\System32\lxss\lib\`
2. **591.86 installer repopulates** them automatically with new versions
3. After PC reboot, WSL2 picks up the new files
4. **You MUST run `wsl --shutdown`** after driver install to force WSL to remount the new files

### WSL2 Multi-GPU Notes
- After fix, **both GPUs will be visible** in `wsl nvidia-smi`
- Known WSL2 limitation: "On multi-GPU systems it is not possible to filter for specific GPU devices" (NVIDIA docs) — `CUDA_VISIBLE_DEVICES` **may not work inside WSL2**
- Ollama on Windows (native) CAN use `CUDA_VISIBLE_DEVICES` normally
- Performance: WSL2 vs Windows native Ollama is virtually identical (Windows Central benchmarks, Feb 2026)

---

## Environment Preservation Analysis

> **DDU ONLY removes NVIDIA driver files**. It does NOT touch user files, Python environments, Ollama, or WSL2 distros.

### What DDU WILL Remove (safe to remove)
| Item | Location | Impact |
|------|----------|--------|
| NVIDIA driver files | `C:\Windows\System32\` + `SysWOW64\` | Required for clean install |
| WSL2 stub libraries | `C:\Windows\System32\lxss\lib\*.so` | **Repopulated by 591.86 installer** |
| NVIDIA registry entries | `HKLM\SOFTWARE\NVIDIA\` | Cleaned for fresh start |
| PhysX, NVML, nvidia-smi.exe | System directories | Reinstalled by 591.86 |
| `C:\NVIDIA\` folder | Root of C: drive | Optional DDU setting |

### What DDU Will NOT Touch (safe)
| Item | Location | Status |
|------|----------|--------|
| **Python venvs (6)** | `.venv`, `kingdom-venv`, `ml_packages_venv`, `venv`, `kingdom_ai\.venv`, `kingdom_ai\venv` | **SAFE** — user files |
| **pip cache** | `AppData\Local\pip\cache` | **SAFE** |
| **node_modules** | Project folder | **SAFE** |
| **Ollama Windows** | `AppData\Local\Programs\Ollama\` | **SAFE** — separate app |
| **Ollama WSL2** | `/usr/local/bin/ollama` in Ubuntu | **SAFE** — WSL2 ext4 filesystem |
| **Ollama models (WSL2)** | `~/.ollama/models/` in Ubuntu (~20 models) | **SAFE** — WSL2 ext4 filesystem |
| **WSL2 Ubuntu 22.04** | `AppData\Local\Packages\CanonicalGroupLimited.*` | **SAFE** — separate VM |
| **WSL2 pip packages** | Inside Ubuntu filesystem | **SAFE** + backward compatible |
| **Kingdom AI codebase** | `Documents\Python Scripts\New folder\` | **SAFE** — user files |
| **D: drive backups** | `D:\kingdom\` | **SAFE** — different drive |

---

## !! CRITICAL WARNING: Windows 11 24H2 Safe Mode PIN Bug !!

> **YOUR SYSTEM IS AFFECTED**: You are running **Windows 11 24H2 Build 26100** with a Microsoft Account (`zilla`) that uses PIN login.
> 
> **Known Bug**: Windows 11 24H2 has a confirmed bug where Safe Mode says **"Something happened and your PIN isn't available"** — you CANNOT log in with PIN in Safe Mode. This has been confirmed on the DDU official forums (Wagnardsoft), ElevenForum, Reddit r/sysadmin (232+ comments), and Microsoft Q&A.
>
> **YOU MUST DO THIS BEFORE ENTERING SAFE MODE:**
> 1. Open **Settings > Accounts > Sign-in options**
> 2. Under **Windows Hello PIN**, click **Remove**
> 3. It will ask for your Microsoft Account password — enter it
> 4. Your PIN is now removed. You will log in with your **Microsoft Account password** instead.
> 5. Proceed with Safe Mode as normal.
> 6. **After the fix is complete**, you can re-add your PIN.
>
> **ALTERNATIVE WORKAROUNDS (if PIN removal doesn't work or you forget):**
>
> **Method 1: Sign in with Microsoft Account password** — On Safe Mode login screen, look for "Sign-in options" or "More login options" → select "Sign in with password" → enter your Microsoft Account password
>
> **Method 2: Create a local admin account with password beforehand** (run in Admin PowerShell NOW):
> ```
> net user DDUAdmin YourPasswordHere /add
> net localgroup administrators DDUAdmin /add
> ```
> In Safe Mode, click the arrow to switch users and log in as DDUAdmin
>
> **Method 3: Disable TPM in BIOS temporarily** — Some users on Microsoft Q&A (June 2025) report that disabling TPM in BIOS → boot Safe Mode → works. Re-enable TPM after returning to normal mode.
>
> **EMERGENCY RECOVERY if you get locked out in Safe Mode:**
>
> **Method A** (if you can see the login screen):
> 1. At the login screen, click the **Power** icon (bottom-right)
> 2. Hold **Shift** and click **Restart**
> 3. Choose **Troubleshoot > Advanced Options > Command Prompt**
> 4. Type: `bcdedit /deletevalue {default} safeboot` and press Enter
> 5. Type: `exit` — PC will restart to normal mode
>
> **Method B** (if completely stuck in a reboot loop):
> 1. Turn PC **off** (hold power button)
> 2. Turn **on**, then force **off** before spinning dots appear — repeat **3 times**
> 3. Windows will say "Preparing Automatic Repair"
> 4. Click **Advanced repair options > Troubleshoot > Advanced Options > Command Prompt**
> 5. Type: `bcdedit /deletevalue {default} safeboot` → Enter → `exit`
>
> This PIN bug is **still NOT patched** as of February 2026 Patch Tuesday (KB5077181). DDU V18.1.4.1 official release notes (Jan 26, 2026) explicitly acknowledge: "(NOT A DDU ISSUE) With Windows 11 24H2, your PIN may not work in Safe Mode."

---

## Step-by-Step Procedure

### PHASE 1: PREPARATION

**Step 0 — Remove Windows Hello PIN (MANDATORY for 24H2)**
> See the critical warning above. You MUST remove your PIN before Safe Mode.
1. **Settings > Accounts > Sign-in options > Windows Hello PIN > Remove**
2. Enter your Microsoft Account password when prompted
3. Confirm PIN is removed

**Step 1 — Block Windows Update Driver Downloads**
> **PURPOSE**: Prevent Windows Update from auto-downloading a mismatched NVIDIA driver between DDU and 591.86 install.

**Option A — Registry keys (keep WiFi on, ~99% effective):**
Run `block_wu_drivers.ps1` as Administrator. This sets 3 registry keys:
- `ExcludeWUDriversInQualityUpdate = 1` — blocks driver quality updates
- `SearchOrderConfig = 0` — prevents online driver search
- `ExcludeWUDrivers = 1` — policy-level driver exclusion

Combined with DDU's "Prevent downloads" option (Step 4), this provides 4 layers of protection.
After the fix, run `restore_wu_drivers.ps1` to re-enable WU driver updates.

**Option B — Disconnect WiFi (100% guaranteed):**
- Unplug Ethernet cable AND disable Wi-Fi, or enable Airplane Mode
- Do NOT reconnect until Step 8

**Additional protection** (both options): DDU has a built-in option "Prevent downloads of drivers from Windows Update" — enable this in Step 4.

**Step 2 — Verify Downloads**
Run the pre-check script (in Admin PowerShell):
```powershell
.\fix_dual_gpu_591.ps1 -PreCheck
```
Confirm DDU and driver installer are both found.

---

### PHASE 2: SAFE MODE + DDU

**Step 3 — Boot into Safe Mode**

Option A (Recommended — Manual):
1. Open **Settings > System > Recovery**
2. Under "Advanced startup", click **Restart now**
3. PC reboots to blue recovery screen
4. Click **Troubleshoot > Advanced options > Startup Settings > Restart**
5. Press **4** on keyboard for "Enable Safe Mode"

Option B (Script-assisted):
```powershell
.\fix_dual_gpu_591.ps1 -SafeModeBoot
```
Type `YES` when prompted. PC will reboot to Safe Mode.

**Step 4 — Run DDU in Safe Mode**
1. Navigate to `Desktop\DDU_Tool\`
2. Run **Display Driver Uninstaller.exe**
3. If prompted about Safe Mode, click OK
4. On the right side dropdown: select **GPU**
5. On the second dropdown: select **NVIDIA**
6. Click **Options** (top-left):
   - Check "Remove C:\NVIDIA folder"
   - Check "Prevent downloads of drivers from Windows Update"
7. Click **Clean and restart**
8. Screen may go black for a few seconds — this is normal
9. PC will reboot automatically (back to normal mode with basic display driver)

> **If stuck in Safe Mode** after reboot:
> - Method 1: Press `Win+R`, type `msconfig`, go to Boot tab, uncheck "Safe boot", click OK, restart.
> - Method 2 (if login fails due to PIN bug): Click Power icon at login → Hold Shift + click Restart → Troubleshoot > Advanced Options > Command Prompt → type `bcdedit /deletevalue {default} safeboot` → exit → restart.

---

### PHASE 3: UNIFIED DRIVER INSTALLATION

**Step 5 — Install NVIDIA 591.86 Driver**
1. PC has rebooted to normal mode with basic/low-res display — this is expected
2. **Still disconnected from internet**
3. Run the NVIDIA driver installer from Desktop
4. When prompted, select **Custom (Advanced)**
5. **CHECK** the box: ☑ **Perform a clean installation**
6. Click Next and let it install
7. Restart when prompted

**Step 6 — Remove Safe Mode Flag (if used script)**
If you used the `-SafeModeBoot` script option, remove the flag:
```powershell
bcdedit /deletevalue "{current}" safeboot
```
Or the `-PostCheck` script does this automatically.

---

### PHASE 4: VERIFICATION

**Step 7 — Reconnect Internet**
- Plug in Ethernet / re-enable Wi-Fi
- Let Windows Update run — it should NOT downgrade 591.86

**Step 8 — Verify Both GPUs Working**
Run (in Admin PowerShell):
```powershell
.\fix_dual_gpu_591.ps1 -PostCheck
```

Manual verification:
```powershell
# Device Manager check
Get-PnpDevice -Class Display | Format-Table FriendlyName, Status

# nvidia-smi (should show 2 GPUs)
nvidia-smi

# Detailed GPU info
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv
```

**Expected output:**
```
index, name, driver_version, memory.total [MiB]
0, NVIDIA GeForce RTX 4060, 591.86, 8188 MiB
1, NVIDIA GeForce RTX 3050, 591.86, 8192 MiB
```

Both GPUs should show:
- ✅ Status = OK in Device Manager (no yellow triangle)
- ✅ Same driver version (591.86 / 32.0.15.9186)
- ✅ Visible in nvidia-smi

---

### PHASE 5: OLLAMA DUAL GPU CONFIGURATION

**Step 9 — Configure Ollama**
Run:
```powershell
.\fix_dual_gpu_591.ps1 -ConfigOllama
```

Key facts about Ollama multi-GPU:
- **Ollama automatically detects and uses ALL visible NVIDIA GPUs** — no config needed
- **New Model Scheduling (Sep 2025)**: Ollama's new engine has "significantly improved multi-GPU and mismatched GPU performance" with exact memory measurement
- Layer allocation: sorts GPUs by free VRAM, assigns layers to GPU with most space
- For models > 8GB VRAM: Ollama splits layers across RTX 4060 + RTX 3050 automatically
- Combined VRAM pool: **~16GB** for large model inference
- Flash attention: enabled for both GPUs (compute capability ≥ 7.0)

**Performance expectations (after fix):**
- Single RTX 4060 (8GB): ~40-50 tokens/s for 7-8B models (Q4_K_M quantization)
- Single RTX 3050 (8GB): ~25-35 tokens/s for 7-8B models
- **Dual GPU (16GB combined)**: Can run 13B+ parameter models split across both GPUs
- 7-8B models fit entirely on one GPU — second GPU handles concurrent requests or larger models
- Recommended models for 16GB combined: Qwen3 14B, Llama3 13B, DeepSeek-Coder 16B

**Optional environment variables:**
```powershell
# Use both GPUs (default behavior, usually not needed)
$env:CUDA_VISIBLE_DEVICES = "0,1"

# Use only RTX 4060
$env:CUDA_VISIBLE_DEVICES = "0"

# Use only RTX 3050  
$env:CUDA_VISIBLE_DEVICES = "1"

# Enable debug logging to see GPU allocation
$env:OLLAMA_DEBUG = "1"
ollama serve
```

**Step 10 — Verify WSL2 GPU Passthrough (CRITICAL)**

WSL2 needs a full restart to pick up the new driver libraries:
```powershell
# Step 10a: Shut down WSL completely
wsl --shutdown

# Step 10b: Wait 5 seconds, then verify lxss/lib was repopulated
Start-Sleep 5
Get-ChildItem C:\Windows\System32\lxss\lib\*.so | Select-Object Name, Length

# Step 10c: Start WSL and check GPU visibility
wsl nvidia-smi
```

**Expected WSL2 output:**
```
+-------------------------------------------------------------------------+
| NVIDIA-SMI 591.xx    Driver Version: 591.86    CUDA Version: 13.x      |
|   0  NVIDIA GeForce RTX 4060   ...   8188MiB                           |
|   1  NVIDIA GeForce RTX 3050   ...   6144MiB                           |
+-------------------------------------------------------------------------+
```

**Step 10d: Verify WSL2 CUDA pip packages still work**
```bash
# Inside WSL2 Ubuntu
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}, Devices: {torch.cuda.device_count()}')"
```

**Step 10e: Verify WSL2 Ollama detects both GPUs**
```bash
# Inside WSL2 Ubuntu
OLLAMA_DEBUG=1 ollama serve &
sleep 3
ollama run tinyllama "Hello" --verbose
```
Check debug output for GPU detection lines showing both GPUs.

**If `nvidia-smi` fails in WSL2 after driver install:**
1. Check `C:\Windows\System32\lxss\lib\` has `.so` files (should be freshly dated)
2. Run `wsl --shutdown` again, then retry
3. Check `/dev/dxg` exists in WSL: `wsl bash -c "ls -la /dev/dxg"`
4. Known harmless warning: `libcuda.so.1 is not a symbolic link` during `apt update` — ignore this
5. If still failing: `wsl --update` to ensure latest WSL kernel
6. Known WSL2 issue (GitHub #13773, Nov 2025): `libcuda.so.1` can segfault after driver change if `/usr/lib/wsl/lib/` has stale files. Fix: `wsl --shutdown` + ensure `C:\Windows\System32\lxss\lib\` has fresh .so files

**WSL2 multi-GPU limitation:** `CUDA_VISIBLE_DEVICES` may not work for GPU filtering inside WSL2 (NVIDIA documented limitation). Both GPUs will be visible but you cannot select specific ones from within WSL.

---

## Troubleshooting

### Code 31 persists after driver install
1. Ensure you did DDU in **Safe Mode**, not normal mode
2. Ensure internet was **disconnected** during DDU + install
3. **Check registry for stale filters** (DDU should clean these, but verify):
   - Open `regedit` → navigate to `HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}`
   - If `UpperFilters` or `LowerFilters` values exist in the right pane, **delete them**
   - Restart PC
4. **Check BIOS settings** (Resizable BAR / Above 4G Decoding):
   - Your motherboard: **ASUS PRIME B660M-A AC D4** (BIOS 3403)
   - Enter BIOS: Press **F2** or **Del** at boot
   - Switch to **Advanced Mode** (press **F7**)
   - Navigate: **Advanced → PCI Subsystem Settings**
   - Set **"Above 4G Decoding"** to **Enabled**
   - Set **"Re-size BAR Support"** to **Auto**
   - Navigate: **Boot → CSM (Compatibility Support Module)**
   - Set **"Launch CSM"** to **Disabled** (only if your Windows is installed in UEFI/GPT mode — check with `msinfo32` → BIOS Mode should say "UEFI")
   - Press **F10** to save and exit
5. Try a different PCIe slot for the RTX 4060

### nvidia-smi shows only 1 GPU
- Check Device Manager for disabled/hidden devices (View → Show hidden devices)
- Verify both GPUs are physically seated and powered
- Check PCIe power cables on RTX 4060
- **Check PCIe slot assignment** — your motherboard has:
  - **Slot 1** (CPU, top): PCIe 4.0/3.0 **x16** — RTX 4060 should be here
  - **Slot 2** (Chipset): PCIe 3.0 x16 physical but runs at **x4** — RTX 3050 should be here
  - Slots 3-4: x1 only — **do NOT use for GPUs**
  - PCIe 3.0 x4 bandwidth is sufficient for AI inference on RTX 3050 (not a bottleneck for Ollama)

### Ollama uses only 1 GPU
- Run `$env:OLLAMA_DEBUG = "1"` then `ollama serve` to see GPU detection logs
- Verify with `nvidia-smi -L` that both GPUs are listed
- Restart Ollama service after driver changes

### Stuck in Safe Mode
```powershell
# Press Win+R, type msconfig
# Go to Boot tab, uncheck "Safe boot", click OK, restart
# OR from command prompt:
bcdedit /deletevalue "{current}" safeboot
shutdown /r /t 0
```

---

## Automated Script Reference

| Command | Purpose |
|---------|---------|
| `.\fix_dual_gpu_591.ps1` | Show workflow overview |
| `.\fix_dual_gpu_591.ps1 -Diagnose` | Current GPU state + driver versions |
| `.\fix_dual_gpu_591.ps1 -PreCheck` | Verify DDU + driver downloaded |
| `.\fix_dual_gpu_591.ps1 -SafeModeBoot` | Configure Safe Mode + reboot |
| `.\fix_dual_gpu_591.ps1 -PostCheck` | Verify fix + remove safe mode flag |
| `.\fix_dual_gpu_591.ps1 -ConfigOllama` | Configure Ollama for dual GPU |

---

## System Details (Your Hardware)
- **Motherboard**: ASUS PRIME B660M-A AC D4 (BIOS 3403, 2024-08-08)
- **PCIe Slots**: Slot 1 = PCIe 4.0 x16 (CPU), Slot 2 = PCIe 3.0 x4 (Chipset)
- **OS**: Windows 11 24H2 (Build 26100.7840)
- **GPU 1**: NVIDIA GeForce RTX 3050 8GB (Ampere GA106, DEV_2584, PCI slot E4, CC 8.6) — driver 560.94 — Status: OK
- **GPU 2**: NVIDIA GeForce RTX 4060 8GB (Ada Lovelace AD107, DEV_2882, PCI slot 08, CC 8.9) — driver 566.36 — Status: Error (Code 31)
- **Accounts**: `zilla` (Microsoft Account with PIN), `yeyian` (local), `Yeyian PC` (local)
- **Target Driver**: NVIDIA 591.86 WHQL (Game Ready, DCH, Desktop)
- **WSL2**: v2.6.1.0, Kernel 6.6.87.2-1, Ubuntu-22.04
- **Ollama Windows**: v0.5.11 (`AppData\Local\Programs\Ollama\`)
- **Ollama WSL2**: v0.15.5 (`/usr/local/bin/ollama`) — ~20 models
- **Python venvs**: 6 virtual environments in project (all safe during DDU)
- **CUDA change**: 12.6 → 13.x (backward compatible)

---

## Sources (Verified SOTA 2026)
- DDU Official Guide: https://www.wagnardsoft.com/content/How-use-Display-Driver-Uninstaller-DDU-Guide-Tutorial
- DDU V18.1.4.1 Release: https://www.wagnardsoft.com/forums/viewtopic.php?t=5498
- DDU Safe Mode PIN Bug (official forum): https://www.wagnardsoft.com/forums/viewtopic.php?t=5118
- Win11 24H2 PIN Bug (r/sysadmin 232 comments): https://www.reddit.com/r/sysadmin/comments/1fw3t2t/
- Win11 24H2 PIN Bug (ElevenForum): https://www.elevenforum.com/t/safe-mode-something-happened-and-your-pin-isnt-available.29605/
- Win11 24H2 PIN Bug (Microsoft Q&A - real lockout case): https://learn.microsoft.com/en-us/answers/questions/3920959/desperation-windows-11-24h2-safe-mode-error
- NVIDIA Driver 591.86 Info: https://www.nvidia.com/en-us/drivers/details/263200/
- NVIDIA Driver 591.86 Direct DL: https://us.download.nvidia.com/Windows/591.86/591.86-desktop-win10-win11-64bit-international-dch-whql.exe
- NVIDIA 591.86 Release Notes: https://us.download.nvidia.com/Windows/591.86/591.86-win11-win10-release-notes.pdf
- NVIDIA 591.86 WHQL Analysis: https://windowsforum.com/threads/nvidia-geforce-driver-591-86-whql-dlss-4-support-and-key-fixes.399137/
- NVIDIA 591.86 Reddit Discussion (802 comments): https://www.reddit.com/r/nvidia/comments/1qoemdy/game_ready_driver_59186_faqdiscussion/
- Dual GPU Code 31 Fix (Tom's Hardware, solved): https://forums.tomshardware.com/threads/help-with-dual-graphics-cards.3760026/
- Code 31 Registry UpperFilters Fix: https://www.sharkyextreme.com/graphics-device-driver-error-code-31/
- ASUS PRIME B660M-A AC D4 Tech Specs: https://www.asus.com/us/motherboards-components/motherboards/prime/prime-b660m-a-ac-d4/techspec/
- ASUS ReBAR Enable Guide: https://edgeup.asus.com/2021/guide-how-to-enable-resizable-bar-on-your-asus-powered-gaming-pc/
- Windows Update Driver Block Methods: https://windowsforum.com/threads/block-a-specific-driver-update-in-windows-11-gp-registry-and-wushowhide.384429/
- Ollama GPU Docs: https://docs.ollama.com/gpu
- Ollama New Model Scheduling (Sep 2025): https://ollama.com/blog/new-model-scheduling
- Ollama Multi-GPU Architecture: https://deepwiki.com/ollama/ollama/6-gpu-and-hardware-support
- Ollama VRAM Requirements 2026 Guide: https://localllm.in/blog/ollama-vram-requirements-for-local-llms
- RTX 4060 Ollama Benchmarks: https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx4060
- RTX 3050 Ollama Benchmarks: https://www.reddit.com/r/LocalLLaMA/comments/1pskvnj/ollama_benchmarks_on_ryzen_5600_rtx_3050_8gb/
- DDU Step-by-Step: https://pcbottleneckchecker.com/how-to-use-ddu-display-driver-uninstaller-complete-step-by-step-guide/
- NVIDIA CUDA Compatibility Guide: https://docs.nvidia.com/deploy/cuda-compatibility/
- NVIDIA CUDA on WSL2 User Guide: https://docs.nvidia.com/cuda/wsl-user-guide/index.html
- Microsoft Enable CUDA on WSL2: https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl
- WSL2 lxss/lib Missing Files (GitHub #7314): https://github.com/microsoft/WSL/issues/7314
- WSL2 libcuda.so Symlink Issue (GitHub #5548): https://github.com/microsoft/WSL/issues/5548
- CUDA on WSL2 Troubleshooting: https://leehanchung.github.io/blogs/2023/03/29/CUDA-x-WSL2/
- Everything About CUDA in WSL2: https://gist.github.com/Ayke/5f37ebdb84c758f57d7a3c8b847648bb
- Ollama WSL2 vs Windows Benchmarks: https://www.windowscentral.com/artificial-intelligence/ollama-on-wsl-works-just-as-well-as-natively-on-windows-11
- CUDA Toolkit Release Notes (version matrix): https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html
- NVIDIA 591.86 + KB5074109 black screen issue: https://www.windowslatest.com/2026/02/03/nvidia-is-looking-into-gaming-issues-after-windows-11-kb5074109-january-2026-update-artifacts-black-screen-and-other-problems/
- KB5077181 mitigates black screen: https://www.reddit.com/r/nvidia/comments/1r1npb0/microsoft_released_the_kb5077181_to_fix_the_black/
- Ollama fitGPU multi-GPU layer allocation: https://deepwiki.com/ollama/ollama/6-gpu-and-hardware-support
- WSL2 libcuda.so.1 segfault after driver change (GitHub #13773): https://github.com/microsoft/WSL/issues/13773
- Win11 24H2 Safe Mode PIN - TPM disable workaround (Microsoft Q&A): https://learn.microsoft.com/en-us/answers/questions/3930982/cant-log-in-in-safe-mode-using-pin-after-clean-win
- DDU Safe Mode PIN bug acknowledged in V18.1.4.1 release notes: https://www.wagnardsoft.com/forums/viewtopic.php?t=5498
- Registry WU driver blocking (ElevenForum, 3-key method): https://www.elevenforum.com/t/enable-or-disable-include-drivers-with-windows-updates-in-windows-11.2232/
- Registry WU driver blocking (Microsoft Q&A, confirmed 2026): https://learn.microsoft.com/en-us/answers/questions/4037530/how-to-prevent-automatic-windows-11-updates-from-o
