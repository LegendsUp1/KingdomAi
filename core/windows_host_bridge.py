#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOTA 2026 - Unified Windows Host Bridge for WSL2

Provides complete access to Windows host system from WSL2:
- Audio devices (microphone, speakers) via PowerShell
- Video devices (webcams) via MJPEG server
- USB devices (SDR, serial) via USB/IP or direct access
- Network interfaces for UDP calls
- Windows Speech Recognition for voice commands
- Windows TTS for voice output

This module unifies:
- core/wsl_audio_bridge.py
- utils/windows_audio_bridge.py  
- config/windows_audio_devices.py

Usage:
    from core.windows_host_bridge import get_windows_host_bridge
    bridge = get_windows_host_bridge()
    
    # Check what's available
    status = bridge.get_bridge_status()
    
    # Use Windows audio
    bridge.speak("Hello from Kingdom AI")
    text = bridge.listen(duration=5)
"""

import os
import sys
import subprocess
import logging
import threading
import time
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("KingdomAI.WindowsHostBridge")


class BridgeType(Enum):
    """Types of bridges available"""
    AUDIO_OUTPUT = "audio_output"      # TTS, sound playback
    AUDIO_INPUT = "audio_input"        # Microphone, speech recognition
    VIDEO = "video"                    # Webcam via MJPEG
    USB = "usb"                        # USB devices via passthrough
    NETWORK = "network"                # Network interfaces
    SPEECH_RECOGNITION = "speech_recognition"  # Windows STT
    TEXT_TO_SPEECH = "text_to_speech"  # Windows TTS


@dataclass
class BridgeStatus:
    """Status of a bridge connection"""
    bridge_type: BridgeType
    available: bool
    method: str = ""
    details: str = ""
    last_check: float = 0.0


class WindowsHostBridge:
    """
    SOTA 2026 Unified Windows Host Bridge
    
    Provides WSL2 access to Windows host hardware and services.
    Uses the most reliable methods discovered through testing:
    
    - Audio Output: PowerShell SoundPlayer (proven reliable)
    - Audio Input: Windows Speech Recognition via PowerShell
    - Video: MJPEG server running on Windows host
    - USB: PowerShell device enumeration
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._lock = threading.Lock()
        
        # Detect environment
        self.in_wsl = self._detect_wsl()
        self.windows_host_ip = self._get_windows_host_ip() if self.in_wsl else "127.0.0.1"
        
        # Bridge status cache
        self._bridge_status: Dict[BridgeType, BridgeStatus] = {}
        
        # Configuration
        self.mjpeg_port = int(os.environ.get("KINGDOM_MJPEG_PORT", "8090"))
        self.mjpeg_path = os.environ.get("KINGDOM_MJPEG_PATH", "/brio.mjpg")
        
        # Vision capture state
        self._vision_capture_active = False
        self._vision_capture_thread = None
        
        # Voice recognition state
        self._voice_listening = False
        
        # Initialize bridges
        if self.in_wsl:
            logger.info(f"🌉 WSL2 detected - Windows host IP: {self.windows_host_ip}")
            self._initialize_bridges()
        else:
            logger.info("🖥️ Native Windows/Linux detected - direct hardware access")
    
    def _detect_wsl(self) -> bool:
        """Detect if running in WSL/WSL2 environment.
        
        On native Linux, /proc/version won't contain 'microsoft'.
        Returns False so all public methods use native Linux paths.
        """
        try:
            if os.environ.get('WSL_DISTRO_NAME') or os.environ.get('WSL_INTEROP'):
                return True
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    content = f.read().lower()
                    return 'microsoft' in content
        except Exception:
            pass
        return False
    
    def _get_windows_host_ip(self) -> str:
        """Get Windows host IP from WSL2"""
        # Method 1: Default gateway (MOST RELIABLE for accessing Windows services)
        try:
            result = subprocess.run(
                ['ip', 'route', 'show', 'default'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.split()
                if len(parts) >= 3 and parts[0] == 'default' and parts[1] == 'via':
                    gateway_ip = parts[2]
                    logger.debug(f"Windows host IP from gateway: {gateway_ip}")
                    return gateway_ip
        except Exception:
            pass
        
        # Method 2: Check /etc/resolv.conf (fallback)
        try:
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.strip().startswith('nameserver'):
                        ip = line.strip().split()[1]
                        if not ip.startswith('127.'):
                            return ip
        except Exception:
            pass
        
        # Method 3: WSLg socket path (Windows 11)
        if os.path.exists('/mnt/wslg'):
            # WSLg is available - try to get host IP from environment
            try:
                result = subprocess.run(
                    ['hostname', '-I'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    ips = result.stdout.strip().split()
                    for ip in ips:
                        if ip.startswith('172.') or ip.startswith('10.'):
                            # Derive host IP (usually .1 on same subnet)
                            parts = ip.split('.')
                            parts[-1] = '1'
                            return '.'.join(parts)
            except Exception:
                pass
        
        return "172.17.0.1"  # Fallback
    
    def _initialize_bridges(self) -> None:
        """Initialize all available bridges"""
        # Check each bridge type
        self._check_audio_output()
        self._check_audio_input()
        self._check_video()
        self._check_speech_recognition()
        self._check_tts()
        self._check_network()
    
    def _run_powershell(self, script: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """Run PowerShell command on Windows host from WSL"""
        try:
            result = subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode == 0, result.stdout.strip(), result.stderr.strip())
        except subprocess.TimeoutExpired:
            return (False, "", "Timeout")
        except FileNotFoundError:
            return (False, "", "PowerShell not found")
        except Exception as e:
            return (False, "", str(e))
    
    def _check_audio_output(self) -> BridgeStatus:
        """Check if audio output is available via PowerShell SoundPlayer"""
        status = BridgeStatus(
            bridge_type=BridgeType.AUDIO_OUTPUT,
            available=False,
            method="PowerShell SoundPlayer",
            last_check=time.time()
        )
        
        if not self.in_wsl:
            status.available = True
            status.method = "Direct"
            status.details = "Native Windows/Linux audio"
        else:
            # Test PowerShell audio capability
            script = "[System.Media.SoundPlayer]::new() | Out-Null; Write-Output 'OK'"
            success, stdout, stderr = self._run_powershell(script, timeout=10)
            status.available = success and 'OK' in stdout
            status.details = "PowerShell SoundPlayer available" if status.available else stderr
        
        self._bridge_status[BridgeType.AUDIO_OUTPUT] = status
        return status
    
    def _check_audio_input(self) -> BridgeStatus:
        """Check if audio input is available"""
        status = BridgeStatus(
            bridge_type=BridgeType.AUDIO_INPUT,
            available=False,
            method="Windows Speech Recognition",
            last_check=time.time()
        )
        
        if not self.in_wsl:
            # Check for sounddevice
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                inputs = [d for d in devices if d.get('max_input_channels', 0) > 0]
                status.available = len(inputs) > 0
                status.method = "sounddevice"
                status.details = f"{len(inputs)} input devices"
            except Exception as e:
                status.details = str(e)
        else:
            # Test Windows Speech Recognition availability
            script = '''
Add-Type -AssemblyName System.Speech
try {
    $r = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $r.Dispose()
    Write-Output 'OK'
} catch {
    Write-Output 'FAIL'
}
'''
            success, stdout, stderr = self._run_powershell(script, timeout=15)
            status.available = success and 'OK' in stdout
            status.details = "Windows Speech Recognition available" if status.available else stderr
        
        self._bridge_status[BridgeType.AUDIO_INPUT] = status
        return status
    
    def _check_speech_recognition(self) -> BridgeStatus:
        """Alias for audio input check focused on STT"""
        return self._check_audio_input()
    
    def _check_tts(self) -> BridgeStatus:
        """Check if text-to-speech is available"""
        status = BridgeStatus(
            bridge_type=BridgeType.TEXT_TO_SPEECH,
            available=False,
            method="Windows SAPI",
            last_check=time.time()
        )
        
        if not self.in_wsl:
            # Check for pyttsx3 or similar
            try:
                import pyttsx3
                status.available = True
                status.method = "pyttsx3"
                status.details = "Native TTS available"
            except ImportError:
                status.details = "pyttsx3 not installed"
        else:
            # Test Windows SAPI
            script = '''
Add-Type -AssemblyName System.Speech
try {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.Dispose()
    Write-Output 'OK'
} catch {
    Write-Output 'FAIL'
}
'''
            success, stdout, stderr = self._run_powershell(script, timeout=15)
            status.available = success and 'OK' in stdout
            status.details = "Windows SAPI TTS available" if status.available else stderr
        
        self._bridge_status[BridgeType.TEXT_TO_SPEECH] = status
        return status
    
    def _check_video(self) -> BridgeStatus:
        """Check if video stream is available via MJPEG"""
        status = BridgeStatus(
            bridge_type=BridgeType.VIDEO,
            available=False,
            method="MJPEG HTTP",
            last_check=time.time()
        )
        
        mjpeg_url = f"http://{self.windows_host_ip}:{self.mjpeg_port}{self.mjpeg_path}"
        status.details = mjpeg_url
        
        # Try multiple methods to check MJPEG availability
        try:
            # Method 1: Use curl for more reliable check (handles MJPEG streams better)
            result = subprocess.run(
                ['curl', '-I', '--connect-timeout', '2', '-s', mjpeg_url],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and ('200' in result.stdout or 'multipart' in result.stdout.lower()):
                status.available = True
                status.details = f"MJPEG stream available at {mjpeg_url}"
                self._bridge_status[BridgeType.VIDEO] = status
                return status
        except Exception:
            pass
        
        # Method 2: urllib fallback with GET (some MJPEG servers don't support HEAD)
        try:
            import urllib.request
            req = urllib.request.Request(mjpeg_url)
            resp = urllib.request.urlopen(req, timeout=3)
            if resp.status == 200:
                status.available = True
                status.details = f"MJPEG stream available at {mjpeg_url}"
        except Exception as e:
            status.details = f"MJPEG not reachable: {mjpeg_url}"
        
        self._bridge_status[BridgeType.VIDEO] = status
        return status
    
    def start_mjpeg_server(self, timeout: int = 10) -> bool:
        """
        Auto-start the MJPEG webcam server on Windows host.
        
        This starts brio_mjpeg_server.py on the Windows host via PowerShell.
        The server streams webcam video as MJPEG on port 8090.
        
        Returns:
            True if server started successfully or already running
        """
        if not self.in_wsl:
            logger.info("Not in WSL - MJPEG server should be started directly on Windows")
            return False
        
        # First check if already running
        video_status = self._check_video()
        if video_status.available:
            logger.info("✅ MJPEG server already running")
            return True
        
        logger.info("🚀 Attempting to auto-start MJPEG server on Windows host...")
        
        # Get the path to the server script
        # Convert WSL path to Windows path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # PowerShell script to start the MJPEG server
        # Use Start-Process to run it in background without blocking
        script = f'''
$ErrorActionPreference = "SilentlyContinue"

# Find Python
$pythonPaths = @(
    "python",
    "python3",
    "$env:LOCALAPPDATA\\Programs\\Python\\Python311\\python.exe",
    "$env:LOCALAPPDATA\\Programs\\Python\\Python310\\python.exe",
    "C:\\Python311\\python.exe",
    "C:\\Python310\\python.exe"
)

$python = $null
foreach ($p in $pythonPaths) {{
    try {{
        $ver = & $p --version 2>$null
        if ($LASTEXITCODE -eq 0) {{
            $python = $p
            break
        }}
    }} catch {{}}
}}

if (-not $python) {{
    Write-Output "ERROR: Python not found"
    exit 1
}}

# Convert WSL path to Windows path
$wslPath = "{project_root}"
$winPath = wsl.exe wslpath -w "$wslPath" 2>$null
if (-not $winPath) {{
    $winPath = $wslPath -replace '^/mnt/([a-z])/', '$1:\\'  -replace '/', '\\'
}}

$serverScript = Join-Path $winPath "brio_mjpeg_server.py"

if (-not (Test-Path $serverScript)) {{
    Write-Output "ERROR: Server script not found at $serverScript"
    exit 1
}}

# Start the server in a new hidden window
$proc = Start-Process -FilePath $python -ArgumentList $serverScript -WindowStyle Hidden -PassThru
Write-Output "STARTED:$($proc.Id)"
'''
        
        success, stdout, stderr = self._run_powershell(script, timeout=timeout)
        
        if success and 'STARTED:' in stdout:
            pid = stdout.split('STARTED:')[1].strip()
            logger.info(f"✅ MJPEG server started with PID: {pid}")
            
            # Wait a moment for server to initialize
            time.sleep(2)
            
            # Verify it's actually running
            video_status = self._check_video()
            if video_status.available:
                logger.info("✅ MJPEG server verified running")
                return True
            else:
                logger.warning("⚠️ Server started but not responding yet, may need more time")
                return True  # Still return True as it was started
        else:
            error_msg = stderr if stderr else stdout
            logger.error(f"❌ Failed to start MJPEG server: {error_msg}")
            return False
    
    def ensure_video_available(self) -> Tuple[bool, str]:
        """
        Ensure video stream is available, auto-starting server if needed.
        
        Returns:
            Tuple of (available: bool, mjpeg_url: str)
        """
        mjpeg_url = f"http://{self.windows_host_ip}:{self.mjpeg_port}{self.mjpeg_path}"
        
        # Check if already available
        video_status = self._check_video()
        if video_status.available:
            return True, mjpeg_url
        
        # Try to auto-start
        if self.start_mjpeg_server():
            # Give it a moment
            time.sleep(1)
            video_status = self._check_video()
            return video_status.available, mjpeg_url
        
        return False, mjpeg_url
    
    def _check_network(self) -> BridgeStatus:
        """Check network interfaces"""
        status = BridgeStatus(
            bridge_type=BridgeType.NETWORK,
            available=True,  # Network is always available
            method="Native",
            last_check=time.time()
        )
        
        try:
            import psutil
            interfaces = psutil.net_if_addrs()
            active = sum(1 for name in interfaces if name != 'lo')
            status.details = f"{active} interfaces available"
        except ImportError:
            status.details = "psutil not installed"
        
        self._bridge_status[BridgeType.NETWORK] = status
        return status
    
    # =========================================================================
    # PUBLIC API - Audio Output
    # =========================================================================
    
    def speak(self, text: str, voice: str = None, rate: int = 150) -> bool:
        """
        Speak text using Windows TTS (SAPI) from WSL2.
        
        Args:
            text: Text to speak
            voice: Voice name (optional)
            rate: Speech rate (words per minute)
            
        Returns:
            True if successful
        """
        if not text:
            return False
        
        if self.in_wsl:
            # Use Windows SAPI via PowerShell
            escaped_text = text.replace('"', '`"').replace("'", "''")
            script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {max(-10, min(10, (rate - 150) // 15))}
$synth.Speak("{escaped_text}")
$synth.Dispose()
'''
            success, _, stderr = self._run_powershell(script, timeout=60)
            if not success:
                logger.warning(f"TTS failed: {stderr}")
            return success
        else:
            # Native TTS
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty('rate', rate)
                engine.say(text)
                engine.runAndWait()
                return True
            except Exception as e:
                logger.debug(f"pyttsx3 TTS failed: {e}, trying espeak/spd-say")
                import shutil
                for tts_cmd in ['espeak', 'spd-say']:
                    if shutil.which(tts_cmd):
                        try:
                            subprocess.run([tts_cmd, text], timeout=60, capture_output=True)
                            return True
                        except Exception:
                            pass
                logger.error(f"Native TTS failed: {e}")
                return False
    
    def play_audio_file(self, file_path: str) -> bool:
        """
        Play audio file using Windows from WSL2.
        
        Args:
            file_path: Path to audio file (WAV, MP3)
            
        Returns:
            True if successful
        """
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return False
        
        if self.in_wsl:
            # Convert to Windows path
            abs_path = os.path.abspath(file_path)
            
            if abs_path.startswith('/mnt/'):
                # /mnt/c/... -> C:\...
                drive = abs_path[5].upper()
                windows_path = f"{drive}:{abs_path[6:]}".replace('/', '\\')
            else:
                # Copy to Windows-accessible location
                try:
                    os.makedirs('/mnt/c/Temp/kingdom_ai_audio', exist_ok=True)
                    target = f'/mnt/c/Temp/kingdom_ai_audio/audio_{int(time.time()*1000)}.wav'
                    subprocess.run(['cp', abs_path, target], check=True)
                    windows_path = target.replace('/mnt/c/', 'C:\\').replace('/', '\\')
                except Exception as e:
                    logger.error(f"Failed to copy audio: {e}")
                    return False
            
            # Play via PowerShell SoundPlayer
            script = f'''
$player = New-Object System.Media.SoundPlayer
$player.SoundLocation = "{windows_path}"
$player.PlaySync()
'''
            success, _, stderr = self._run_powershell(script, timeout=120)
            return success
        else:
            # Native playback
            try:
                import simpleaudio as sa
                wave_obj = sa.WaveObject.from_wave_file(file_path)
                play_obj = wave_obj.play()
                play_obj.wait_done()
                return True
            except Exception:
                pass
            
            # Fallback to system player
            try:
                if sys.platform == 'win32':
                    os.startfile(file_path)
                elif sys.platform == 'darwin':
                    subprocess.run(['afplay', file_path])
                else:
                    import shutil
                    if shutil.which('paplay') and shutil.which('ffmpeg'):
                        resampled = file_path + '.play.wav'
                        subprocess.run(
                            ['ffmpeg', '-y', '-i', file_path,
                             '-ar', '44100', '-ac', '2', '-f', 'wav', resampled],
                            capture_output=True, timeout=30,
                        )
                        if os.path.exists(resampled):
                            subprocess.run(['paplay', resampled], timeout=120)
                            try:
                                os.unlink(resampled)
                            except OSError:
                                pass
                            return True
                    subprocess.run(['aplay', file_path])
                return True
            except Exception as e:
                logger.error(f"Failed to play audio: {e}")
                return False
    
    # =========================================================================
    # PUBLIC API - Audio Input / Speech Recognition
    # =========================================================================
    
    def listen(self, duration: float = 5.0) -> str:
        """
        Listen for speech and return recognized text.
        
        Uses Windows Speech Recognition via PowerShell in WSL2.
        
        Args:
            duration: Maximum listen duration in seconds
            
        Returns:
            Recognized text, or empty string if nothing recognized
        """
        if self.in_wsl:
            script = f'''
Add-Type -AssemblyName System.Speech
$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$grammar = New-Object System.Speech.Recognition.DictationGrammar
$recognizer.LoadGrammar($grammar)
$recognizer.SetInputToDefaultAudioDevice()
$recognizer.BabbleTimeout = [TimeSpan]::FromSeconds(3)
$recognizer.InitialSilenceTimeout = [TimeSpan]::FromSeconds({max(duration, 10)})
$recognizer.EndSilenceTimeout = [TimeSpan]::FromSeconds(2)
try {{
    $result = $recognizer.Recognize()
    if ($result -and $result.Text.Trim()) {{
        Write-Output $result.Text.Trim()
    }}
}} catch {{
    # Silent fail
}} finally {{
    $recognizer.Dispose()
}}
'''
            success, stdout, stderr = self._run_powershell(script, timeout=int(duration) + 15)
            if success and stdout:
                logger.info(f"🎤 Recognized: {stdout}")
                
                # Publish voice recognition event
                if stdout and self.event_bus:
                    self.event_bus.publish('voice.recognition.result', {
                        'text': stdout,
                        'source': 'windows_speech',
                        'timestamp': time.time(),
                        'confidence': 1.0
                    })
                    logger.info(f"📡 Published voice.recognition.result: {stdout}")
                
                return stdout
            return ""
        else:
            # Native speech recognition
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    logger.info(f"🎤 Listening for {duration}s...")
                    audio = recognizer.listen(source, timeout=duration)
                    # Use getattr for type checker compatibility
                    recognize_fn = getattr(recognizer, 'recognize_google', None)
                    if recognize_fn and callable(recognize_fn):
                        text = recognize_fn(audio)
                        logger.info(f"🎤 Recognized: {text}")
                        
                        # Publish voice recognition event
                        if text and self.event_bus:
                            self.event_bus.publish('voice.recognition.result', {
                                'text': str(text),
                                'source': 'microphone',
                                'timestamp': time.time(),
                                'confidence': 1.0
                            })
                            logger.info(f"📡 Published voice.recognition.result: {text}")
                        
                        return str(text) if text else ""
                    return ""
            except Exception as e:
                logger.debug(f"Speech recognition failed: {e}")
                return ""
    
    # =========================================================================
    # PUBLIC API - Device Enumeration
    # =========================================================================
    
    def get_windows_audio_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get list of Windows audio devices via PowerShell.
        
        Returns:
            Dict with 'input' and 'output' device lists
        """
        devices = {'input': [], 'output': []}
        
        if not self.in_wsl:
            # Use sounddevice
            try:
                import sounddevice as sd
                all_devices = sd.query_devices()
                for i, d in enumerate(all_devices):
                    info = {'index': i, 'name': d['name']}
                    if d.get('max_input_channels', 0) > 0:
                        devices['input'].append(info)
                    if d.get('max_output_channels', 0) > 0:
                        devices['output'].append(info)
            except Exception as e:
                logger.debug(f"sounddevice query failed: {e}")
            return devices
        
        # WSL2: Use PowerShell to enumerate Windows devices
        script = '''
Get-CimInstance Win32_SoundDevice | ForEach-Object {
    Write-Output "$($_.Name)|$($_.Status)"
}
'''
        success, stdout, _ = self._run_powershell(script, timeout=15)
        if success and stdout:
            for line in stdout.strip().split('\n'):
                if '|' in line:
                    name, status = line.split('|', 1)
                    devices['output'].append({'name': name.strip(), 'status': status.strip()})
                    devices['input'].append({'name': name.strip(), 'status': status.strip()})
        
        return devices
    
    def get_windows_serial_ports(self) -> List[Dict[str, Any]]:
        """
        Get Windows serial ports with FULL device info via PowerShell.
        Works from WSL2 to detect Windows COM ports!
        
        Returns:
            List of serial port info dicts with VID, PID, serial number, etc.
        """
        ports = []
        
        # Simple PowerShell - just get raw data, parse VID/PID in Python
        script = r'''
Get-WmiObject Win32_PnPEntity | Where-Object { $_.Name -match 'COM[0-9]+' } | ForEach-Object {
    $name = $_.Name
    $deviceId = $_.DeviceID
    $mfg = $_.Manufacturer
    $desc = $_.Description
    $status = $_.Status
    $pnpClass = $_.PNPClass
    
    # Extract COM port number
    $comPort = "UNKNOWN"
    if ($name -match '\(COM(\d+)\)') {
        $comPort = "COM" + $Matches[1]
    }
    
    # Output pipe-delimited - let Python parse VID/PID from deviceId
    Write-Output "$comPort|$name|$mfg|$deviceId|$desc|$status|$pnpClass"
}
'''
        success, stdout, stderr = self._run_powershell(script, timeout=15)
        
        if success and stdout:
            import re
            for line in stdout.strip().split('\n'):
                line = line.strip()
                if not line or '|' not in line:
                    continue
                    
                parts = line.split('|')
                if len(parts) >= 4:
                    com_port = parts[0] if len(parts) > 0 else ""
                    name = parts[1] if len(parts) > 1 else ""
                    mfg = parts[2] if len(parts) > 2 else ""
                    device_id = parts[3] if len(parts) > 3 else ""
                    desc = parts[4] if len(parts) > 4 else ""
                    status = parts[5] if len(parts) > 5 else ""
                    pnp_class = parts[6] if len(parts) > 6 else ""
                    
                    # Parse VID and PID from Device ID using Python regex
                    # Device ID format: USB\VID_2B04&PID_C00C&MI_00\serial
                    vid_int = None
                    pid_int = None
                    vid_hex = None
                    pid_hex = None
                    serial = ""
                    
                    vid_match = re.search(r'VID_([0-9A-Fa-f]{4})', device_id)
                    pid_match = re.search(r'PID_([0-9A-Fa-f]{4})', device_id)
                    
                    if vid_match:
                        vid_hex = vid_match.group(1).upper()
                        try:
                            vid_int = int(vid_hex, 16)
                        except ValueError:
                            pass
                    
                    if pid_match:
                        pid_hex = pid_match.group(1).upper()
                        try:
                            pid_int = int(pid_hex, 16)
                        except ValueError:
                            pass
                    
                    # Extract serial number (after last backslash)
                    if '\\' in device_id:
                        serial = device_id.split('\\')[-1]
                    
                    ports.append({
                        'port': com_port,
                        'name': name,
                        'description': desc or name,
                        'vid': vid_int,
                        'pid': pid_int,
                        'vid_hex': f"0x{vid_hex}" if vid_hex else None,
                        'pid_hex': f"0x{pid_hex}" if pid_hex else None,
                        'manufacturer': mfg,
                        'serial_number': serial,
                        'device_id': device_id,
                        'status': status,
                        'pnp_class': pnp_class,
                        'hwid': f"USB VID:PID={vid_hex}:{pid_hex} SER={serial}" if vid_hex and pid_hex else device_id
                    })
        
        return ports
    
    def start_vision_capture(self, fps: int = 10) -> bool:
        """Start capturing webcam frames and publishing vision.frame events.
        
        Args:
            fps: Frames per second to capture
            
        Returns:
            True if capture started successfully
        """
        if self._vision_capture_active:
            logger.warning("🎥 Vision capture already active")
            return True
            
        self._vision_capture_active = True
        
        def capture_loop():
            frame_interval = 1.0 / fps
            logger.info(f"🎥 Starting vision capture at {fps} FPS")
            
            while self._vision_capture_active:
                try:
                    # Capture frame from MJPEG stream or direct camera
                    frame_data = self.capture_webcam_frame()
                    
                    if frame_data and self.event_bus:
                        # Publish vision.frame event
                        self.event_bus.publish('vision.frame', {
                            'frame': frame_data,
                            'timestamp': time.time(),
                            'source': 'webcam',
                            'format': 'jpeg'
                        })
                        
                        # Also publish vision.request for AI processing
                        self.event_bus.publish('vision.request', {
                            'image_data': frame_data,
                            'source': 'webcam',
                            'timestamp': time.time()
                        })
                    
                    time.sleep(frame_interval)
                    
                except Exception as e:
                    logger.error(f"Vision capture error: {e}")
                    time.sleep(1)
            
            logger.info("🎥 Vision capture stopped")
        
        self._vision_capture_thread = threading.Thread(target=capture_loop, daemon=True)
        self._vision_capture_thread.start()
        logger.info("✅ Vision capture started")
        return True
    
    def stop_vision_capture(self) -> None:
        """Stop capturing webcam frames."""
        self._vision_capture_active = False
        if self._vision_capture_thread:
            self._vision_capture_thread.join(timeout=2)
            self._vision_capture_thread = None
        logger.info("🛑 Vision capture stopped")
    
    def capture_webcam_frame(self) -> Optional[bytes]:
        """Capture a single frame from webcam.
        
        Returns:
            JPEG bytes of captured frame or None
        """
        if self.in_wsl:
            # Try MJPEG stream from Windows host
            mjpeg_url = f"http://{self.windows_host_ip}:{self.mjpeg_port}{self.mjpeg_path}"
            
            try:
                import requests
                # Get single frame from MJPEG stream
                response = requests.get(mjpeg_url, timeout=2, stream=True)
                
                if response.status_code == 200:
                    # Read MJPEG boundary and extract JPEG frame
                    for line in response.iter_lines(decode_unicode=True):
                        if line and line.startswith('Content-Type: image/jpeg'):
                            # Read content length
                            next_line = next(response.iter_lines(decode_unicode=True))
                            if next_line.startswith('Content-Length:'):
                                length = int(next_line.split(':')[1].strip())
                                # Skip empty line
                                next(response.iter_lines(decode_unicode=True))
                                # Read JPEG data
                                jpeg_data = response.raw.read(length)
                                return jpeg_data
                            break
            except Exception as e:
                logger.debug(f"MJPEG capture failed: {e}")
            
            # Fallback: Try PowerShell webcam capture
            return self._capture_via_powershell()
        else:
            # Native capture using OpenCV
            try:
                import cv2
                cap = cv2.VideoCapture(0)
                ret, frame = cap.read()
                cap.release()
                
                if ret:
                    # Encode frame as JPEG
                    _, jpeg_data = cv2.imencode('.jpg', frame)
                    return jpeg_data.tobytes()
            except Exception as e:
                logger.debug(f"OpenCV capture failed: {e}")
        
        return None
    
    def _capture_via_powershell(self) -> Optional[bytes]:
        """Capture webcam frame via PowerShell (WSL2 fallback)."""
        script = r'''
$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Create webcam capture
$webcam = New-Object -ComObject WIA.DeviceManager
$devices = $webcam.DeviceInfos | Where-Object { $_.Type -eq 1 }

if ($devices.Count -gt 0) {
    $device = $devices.Item(1).Connect()
    $item = $device.ExecuteCommand("{AF933CAC-ACAD-11D2-A093-00C04F72DC3C}")
    
    if ($item) {
        $image = $item.Transfer("{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}")
        $bytes = $image.FileData.BinaryData
        [Convert]::ToBase64String($bytes)
    }
}
'''
        success, stdout, _ = self._run_powershell(script, timeout=5)
        
        if success and stdout:
            try:
                import base64
                return base64.b64decode(stdout.strip())
            except Exception:
                pass
        
        return None
    
    def get_windows_webcams(self) -> List[Dict[str, Any]]:
        """Get list of Windows webcams with FULL device info via PowerShell"""
        webcams = []
        
        # WSL2 or Windows: PowerShell device enumeration with full info
        script = r'''
Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' -or $_.Name -match 'Camera|Webcam|Brio'
} | ForEach-Object {
    $name = $_.Name
    $deviceId = $_.DeviceID
    $mfg = $_.Manufacturer
    $desc = $_.Description
    $status = $_.Status
    $pnpClass = $_.PNPClass
    Write-Output "$name|$mfg|$deviceId|$desc|$status|$pnpClass"
}
'''
        success, stdout, _ = self._run_powershell(script, timeout=15)
        if success and stdout:
            import re
            for i, line in enumerate(stdout.strip().split('\n')):
                if '|' not in line:
                    continue
                parts = line.strip().split('|')
                name = parts[0] if len(parts) > 0 else ""
                mfg = parts[1] if len(parts) > 1 else ""
                device_id = parts[2] if len(parts) > 2 else ""
                desc = parts[3] if len(parts) > 3 else ""
                status = parts[4] if len(parts) > 4 else ""
                pnp_class = parts[5] if len(parts) > 5 else ""
                
                # Parse VID/PID from device_id
                vid_match = re.search(r'VID_([0-9A-Fa-f]{4})', device_id)
                pid_match = re.search(r'PID_([0-9A-Fa-f]{4})', device_id)
                vid_hex = vid_match.group(1).upper() if vid_match else None
                pid_hex = pid_match.group(1).upper() if pid_match else None
                
                webcams.append({
                    'index': i,
                    'name': name,
                    'manufacturer': mfg,
                    'device_id': device_id,
                    'description': desc or name,
                    'status': status,
                    'pnp_class': pnp_class,
                    'vid': f"0x{vid_hex}" if vid_hex else None,
                    'pid': f"0x{pid_hex}" if pid_hex else None
                })
        
        return webcams
    
    def get_windows_bluetooth_devices(self) -> List[Dict[str, Any]]:
        """Get Bluetooth devices with FULL info via PowerShell"""
        devices = []
        
        script = r'''
Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.PNPClass -eq 'Bluetooth' -or $_.DeviceID -match 'BTHENUM' -or $_.DeviceID -match 'BTH'
} | ForEach-Object {
    $name = $_.Name
    $deviceId = $_.DeviceID
    $mfg = $_.Manufacturer
    $desc = $_.Description
    $status = $_.Status
    $pnpClass = $_.PNPClass
    Write-Output "$name|$mfg|$deviceId|$desc|$status|$pnpClass"
}
'''
        success, stdout, _ = self._run_powershell(script, timeout=15)
        if success and stdout:
            import re
            for line in stdout.strip().split('\n'):
                if '|' not in line:
                    continue
                parts = line.strip().split('|')
                name = parts[0] if len(parts) > 0 else ""
                mfg = parts[1] if len(parts) > 1 else ""
                device_id = parts[2] if len(parts) > 2 else ""
                desc = parts[3] if len(parts) > 3 else ""
                status = parts[4] if len(parts) > 4 else ""
                pnp_class = parts[5] if len(parts) > 5 else ""
                
                # Extract MAC address from device_id if present
                mac_match = re.search(r'([0-9A-Fa-f]{12})', device_id)
                mac = None
                if mac_match:
                    mac_raw = mac_match.group(1)
                    mac = ':'.join([mac_raw[i:i+2] for i in range(0, 12, 2)])
                
                devices.append({
                    'name': name,
                    'manufacturer': mfg,
                    'device_id': device_id,
                    'description': desc or name,
                    'status': status,
                    'pnp_class': pnp_class,
                    'mac_address': mac
                })
        
        return devices
    
    def get_windows_usb_devices(self) -> List[Dict[str, Any]]:
        """Get ALL USB devices with FULL info via PowerShell"""
        devices = []
        
        script = r'''
Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.DeviceID -match '^USB'
} | ForEach-Object {
    $name = $_.Name
    $deviceId = $_.DeviceID
    $mfg = $_.Manufacturer
    $desc = $_.Description
    $status = $_.Status
    $pnpClass = $_.PNPClass
    Write-Output "$name|$mfg|$deviceId|$desc|$status|$pnpClass"
}
'''
        success, stdout, _ = self._run_powershell(script, timeout=15)
        if success and stdout:
            import re
            for line in stdout.strip().split('\n'):
                if '|' not in line:
                    continue
                parts = line.strip().split('|')
                name = parts[0] if len(parts) > 0 else ""
                mfg = parts[1] if len(parts) > 1 else ""
                device_id = parts[2] if len(parts) > 2 else ""
                desc = parts[3] if len(parts) > 3 else ""
                status = parts[4] if len(parts) > 4 else ""
                pnp_class = parts[5] if len(parts) > 5 else ""
                
                # Parse VID/PID
                vid_match = re.search(r'VID_([0-9A-Fa-f]{4})', device_id)
                pid_match = re.search(r'PID_([0-9A-Fa-f]{4})', device_id)
                vid_hex = vid_match.group(1).upper() if vid_match else None
                pid_hex = pid_match.group(1).upper() if pid_match else None
                vid_int = int(vid_hex, 16) if vid_hex else None
                pid_int = int(pid_hex, 16) if pid_hex else None
                
                # Extract serial
                serial = device_id.split('\\')[-1] if '\\' in device_id else ""
                
                devices.append({
                    'name': name,
                    'manufacturer': mfg,
                    'device_id': device_id,
                    'description': desc or name,
                    'status': status,
                    'pnp_class': pnp_class,
                    'vid': vid_int,
                    'pid': pid_int,
                    'vid_hex': f"0x{vid_hex}" if vid_hex else None,
                    'pid_hex': f"0x{pid_hex}" if pid_hex else None,
                    'serial_number': serial
                })
        
        return devices
    
    def get_all_windows_devices(self) -> Dict[str, Any]:
        """Get ALL Windows devices with full info - comprehensive scan"""
        return {
            'serial_ports': self.get_windows_serial_ports(),
            'usb_devices': self.get_windows_usb_devices(),
            'bluetooth_devices': self.get_windows_bluetooth_devices(),
            'webcams': self.get_windows_webcams(),
            'audio_devices': self.get_windows_audio_devices()
        }
    
    # =========================================================================
    # PUBLIC API - Serial Port Communication (WSL2 -> Windows COM ports)
    # =========================================================================
    
    def connect_serial(self, port: str, baudrate: int = 9600) -> bool:
        """
        Connect to a Windows COM port from WSL2 via PowerShell.
        SOTA 2026: Fixed semaphore timeout with proper flow control.
        
        Args:
            port: COM port name (e.g., "COM6")
            baudrate: Baud rate (default 9600)
            
        Returns:
            True if connection successful
        """
        script = f'''
$port = New-Object System.IO.Ports.SerialPort("{port}", {baudrate})
$port.Handshake = [System.IO.Ports.Handshake]::None
$port.DtrEnable = $true
$port.RtsEnable = $true
$port.ReadTimeout = 3000
$port.WriteTimeout = 3000
try {{
    $port.Open()
    Start-Sleep -Milliseconds 100
    if ($port.IsOpen) {{
        Write-Output "CONNECTED"
        $port.Close()
    }} else {{
        Write-Output "FAILED"
    }}
}} catch {{
    Write-Output "ERROR: $($_.Exception.Message)"
}}
'''
        success, stdout, stderr = self._run_powershell(script, timeout=10)
        return success and "CONNECTED" in stdout
    
    def send_serial_command(self, port: str, command: str, baudrate: int = 9600, 
                           wait_response: bool = True, timeout_ms: int = 5000) -> Dict[str, Any]:
        """
        Send a command to a Windows COM port from WSL2 and optionally read response.
        SOTA 2026: Fixed semaphore timeout with proper flow control settings.
        
        Args:
            port: COM port name (e.g., "COM6")
            command: Command string to send
            baudrate: Baud rate (default 9600)
            wait_response: Whether to wait for and return response
            timeout_ms: Timeout in milliseconds for response
            
        Returns:
            Dict with 'success', 'response', 'error' keys
        """
        # Escape the command for PowerShell
        escaped_cmd = command.replace('"', '`"').replace("'", "''").replace("`", "``")
        
        # PowerShell boolean must be $true or $false
        ps_wait = "$true" if wait_response else "$false"
        
        # SOTA 2026: Fix semaphore timeout - proper serial port configuration
        script = f'''
$port = New-Object System.IO.Ports.SerialPort("{port}", {baudrate})
# CRITICAL: Set handshake to None to prevent semaphore timeout
$port.Handshake = [System.IO.Ports.Handshake]::None
$port.DtrEnable = $true
$port.RtsEnable = $true
$port.ReadTimeout = {timeout_ms}
$port.WriteTimeout = {timeout_ms}
$port.NewLine = "`r`n"

try {{
    $port.Open()
    Start-Sleep -Milliseconds 100  # Let port stabilize
    
    if ($port.IsOpen) {{
        # Clear buffers
        $port.DiscardInBuffer()
        $port.DiscardOutBuffer()
        
        # Send command with newline
        $port.Write("{escaped_cmd}`r`n")
        
        # Wait for response if requested
        $response = ""
        if ({ps_wait}) {{
            $deadline = [DateTime]::UtcNow.AddMilliseconds({timeout_ms})
            $lastRead = [DateTime]::UtcNow
            $hadData = $false
            while ([DateTime]::UtcNow -lt $deadline) {{
                Start-Sleep -Milliseconds 25
                if ($port.BytesToRead -gt 0) {{
                    $chunk = $port.ReadExisting()
                    if ($chunk) {{
                        $response += $chunk
                        $lastRead = [DateTime]::UtcNow
                        $hadData = $true
                    }}
                }} else {{
                    if ($hadData) {{
                        $idleMs = ([DateTime]::UtcNow - $lastRead).TotalMilliseconds
                        if ($idleMs -ge 200) {{ break }}
                    }}
                }}
            }}
        }}
        
        $port.Close()
        Write-Output "SUCCESS|$response"
    }} else {{
        Write-Output "FAILED|Could not open port"
    }}
}} catch {{
    Write-Output "ERROR|$($_.Exception.Message)"
}} finally {{
    try {{ if ($port.IsOpen) {{ $port.Close() }} }} catch {{ }}
}}
'''
        success, stdout, stderr = self._run_powershell(script, timeout=15)
        
        result = {
            'success': False,
            'response': '',
            'error': ''
        }
        
        if success and stdout:
            parts = stdout.strip().split('|', 1)
            status = parts[0]
            data = parts[1] if len(parts) > 1 else ''
            
            if status == "SUCCESS":
                result['response'] = data.strip()
                if wait_response and command.strip() and not result['response']:
                    result['success'] = False
                    result['error'] = 'No response received from device'
                else:
                    result['success'] = True
            else:
                result['error'] = data
        else:
            result['error'] = stderr or "PowerShell execution failed"
        
        return result
    
    def read_serial(self, port: str, baudrate: int = 9600, timeout_ms: int = 2000) -> Dict[str, Any]:
        """
        Read data from a Windows COM port.
        
        Args:
            port: COM port name
            baudrate: Baud rate
            timeout_ms: Read timeout
            
        Returns:
            Dict with 'success', 'data', 'error' keys
        """
        script = f'''
$port = New-Object System.IO.Ports.SerialPort("{port}", {baudrate})
$port.ReadTimeout = {timeout_ms}
try {{
    $port.Open()
    if ($port.IsOpen) {{
        $data = ""
        Start-Sleep -Milliseconds 100
        while ($port.BytesToRead -gt 0) {{
            $data += $port.ReadExisting()
        }}
        $port.Close()
        Write-Output "SUCCESS|$data"
    }} else {{
        Write-Output "FAILED|Could not open port"
    }}
}} catch {{
    Write-Output "ERROR|$($_.Exception.Message)"
}} finally {{
    if ($port.IsOpen) {{ $port.Close() }}
}}
'''
        success, stdout, stderr = self._run_powershell(script, timeout=10)
        
        result = {'success': False, 'data': '', 'error': ''}
        
        if success and stdout:
            parts = stdout.strip().split('|', 1)
            if parts[0] == "SUCCESS":
                result['success'] = True
                result['data'] = parts[1] if len(parts) > 1 else ''
            else:
                result['error'] = parts[1] if len(parts) > 1 else 'Unknown error'
        else:
            result['error'] = stderr or "PowerShell execution failed"
        
        return result
    
    # =========================================================================
    # PUBLIC API - Status
    # =========================================================================
    
    def get_bridge_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all bridges.
        
        Returns:
            Dict with bridge status information
        """
        # Refresh status
        self._check_audio_output()
        self._check_audio_input()
        self._check_video()
        self._check_tts()
        self._check_network()
        
        return {
            'in_wsl': self.in_wsl,
            'windows_host_ip': self.windows_host_ip,
            'bridges': {
                bt.value: {
                    'available': status.available,
                    'method': status.method,
                    'details': status.details
                }
                for bt, status in self._bridge_status.items()
            },
            'summary': {
                'working': [bt.value for bt, s in self._bridge_status.items() if s.available],
                'not_available': [bt.value for bt, s in self._bridge_status.items() if not s.available]
            }
        }
    
    def get_available_features(self) -> List[str]:
        """Get list of features that are currently available"""
        features = []
        
        status = self.get_bridge_status()
        bridges = status.get('bridges', {})
        
        if bridges.get('audio_output', {}).get('available'):
            features.append('voice_output')
            features.append('audio_playback')
        
        if bridges.get('audio_input', {}).get('available'):
            features.append('voice_commands')
            features.append('sonar')
            features.append('udp_voice_calls')
        
        if bridges.get('text_to_speech', {}).get('available'):
            features.append('tts')
        
        if bridges.get('video', {}).get('available'):
            features.append('video_stream')
        
        if bridges.get('network', {}).get('available'):
            features.append('network_comms')
        
        return features


# =============================================================================
# SINGLETON
# =============================================================================

_windows_host_bridge: Optional[WindowsHostBridge] = None

def get_windows_host_bridge(event_bus=None) -> WindowsHostBridge:
    """Get or create the singleton WindowsHostBridge instance"""
    global _windows_host_bridge
    if _windows_host_bridge is None:
        _windows_host_bridge = WindowsHostBridge(event_bus=event_bus)
    return _windows_host_bridge


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("\n" + "="*60)
    print(" SOTA 2026 - Windows Host Bridge Status")
    print("="*60 + "\n")
    
    bridge = get_windows_host_bridge()
    status = bridge.get_bridge_status()
    
    print(f"Environment: {'WSL2' if status['in_wsl'] else 'Native'}")
    print(f"Windows Host IP: {status['windows_host_ip']}")
    print()
    
    print("Bridge Status:")
    for name, info in status['bridges'].items():
        icon = "✅" if info['available'] else "❌"
        print(f"  {icon} {name}: {info['method']}")
        print(f"      {info['details']}")
    
    print()
    print(f"✅ Working: {status['summary']['working']}")
    print(f"❌ Not Available: {status['summary']['not_available']}")
    print()
    
    # Test TTS if available
    if status['bridges'].get('text_to_speech', {}).get('available'):
        print("Testing TTS...")
        bridge.speak("Kingdom AI Windows Host Bridge is operational")
        print("TTS test complete!")
    
    print("\n" + "="*60 + "\n")
