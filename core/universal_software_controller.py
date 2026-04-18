#!/usr/bin/env python3
"""
Universal Software Controller - SOTA 2026
==========================================
Full control of external software via Ollama brain commands.

Enables Kingdom AI to:
- Create, delete, open, close any supported software/projects
- Execute commands within software
- Monitor software state
- Respond to natural language commands from Ollama brain

Supported Software:
- Unity (full project lifecycle)
- Blender (3D modeling)
- VS Code (code editing)
- Any software with CLI or automation support

Author: Kingdom AI Team
Version: 1.0.0 SOTA 2026
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("KingdomAI.UniversalController")


class SoftwareType(Enum):
    """Supported software types"""
    UNITY = "unity"
    BLENDER = "blender"
    VSCODE = "vscode"
    UNREAL = "unreal"
    GODOT = "godot"
    CUSTOM = "custom"


class ActionType(Enum):
    """Action types for software control"""
    CREATE = "create"
    DELETE = "delete"
    OPEN = "open"
    CLOSE = "close"
    BUILD = "build"
    RUN = "run"
    EXECUTE = "execute"
    INSTALL = "install"
    UNINSTALL = "uninstall"
    LIST = "list"
    STATUS = "status"


@dataclass
class SoftwareInstance:
    """Represents a running software instance"""
    software_type: SoftwareType
    name: str
    path: str
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    status: str = "stopped"


@dataclass
class CommandResult:
    """Result of a software command"""
    success: bool
    action: ActionType
    software: SoftwareType
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class UniversalSoftwareController:
    """
    Universal controller for all software automation.
    Designed to be called by Ollama brain for natural language control.
    """
    
    _instance = None
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._instances: Dict[str, SoftwareInstance] = {}
        self._software_paths: Dict[SoftwareType, str] = {}
        self._hub_paths: Dict[SoftwareType, str] = {}
        self._project_base_path = Path.home() / "KingdomAI_Projects"
        self._project_base_path.mkdir(parents=True, exist_ok=True)
        
        # Auto-detect software installations
        self._detect_installations()
        
        # Command handlers for natural language
        self._command_patterns = {
            "create": ["create", "make", "new", "generate", "start new"],
            "delete": ["delete", "remove", "destroy", "erase", "get rid of"],
            "open": ["open", "launch", "start", "run", "load"],
            "close": ["close", "exit", "quit", "stop", "shutdown"],
            "build": ["build", "compile", "package", "export"],
            "list": ["list", "show", "display", "what"],
            "status": ["status", "check", "is running", "state"],
        }
        
        logger.info("🎮 UniversalSoftwareController initialized")
    
    @classmethod
    def get_instance(cls, event_bus=None) -> 'UniversalSoftwareController':
        if cls._instance is None:
            cls._instance = cls(event_bus)
        return cls._instance
    
    def _detect_installations(self):
        """Auto-detect installed software"""
        # Unity Hub locations
        import shutil
        unity_hub_paths = [
            Path(shutil.which("unityhub") or "/dev/null"),
            Path.home() / "Unity Hub" / "UnityHub.AppImage",
            Path("/usr/bin/unityhub"),
            Path.home() / "Desktop" / "Unity Hub" / "Unity Hub.exe",
            Path("C:/Program Files/Unity Hub/Unity Hub.exe"),
            Path.home() / "AppData/Local/Programs/Unity Hub/Unity Hub.exe",
        ]
        for p in unity_hub_paths:
            if p.exists():
                self._hub_paths[SoftwareType.UNITY] = str(p)
                logger.info(f"✅ Found Unity Hub: {p}")
                break
        
        # Unity Editor locations
        unity_editor_paths = [
            Path.home() / "Unity" / "Hub" / "Editor",
            Path("/opt/unity/editor"),
            Path.home() / "Desktop",
            Path("C:/Program Files/Unity/Hub/Editor"),
        ]
        for base in unity_editor_paths:
            if base.exists():
                for folder in base.iterdir():
                    if folder.is_dir() and folder.name.startswith("6000") or folder.name.startswith("2022"):
                        editor = folder / "Editor" / "Unity.exe"
                        if editor.exists():
                            self._software_paths[SoftwareType.UNITY] = str(editor)
                            logger.info(f"✅ Found Unity Editor: {editor}")
                            break
        
        # Blender
        blender_paths = [
            Path(shutil.which("blender") or "/dev/null"),
            Path("/usr/bin/blender"),
            Path("/snap/bin/blender"),
            Path("C:/Program Files/Blender Foundation/Blender 4.0/blender.exe"),
            Path("C:/Program Files/Blender Foundation/Blender 3.6/blender.exe"),
        ]
        for p in blender_paths:
            if p.exists():
                self._software_paths[SoftwareType.BLENDER] = str(p)
                logger.info(f"✅ Found Blender: {p}")
                break
        
        # VS Code
        vscode_paths = [
            Path(shutil.which("code") or "/dev/null"),
            Path("/usr/bin/code"),
            Path("/snap/bin/code"),
            Path.home() / "AppData/Local/Programs/Microsoft VS Code/Code.exe",
            Path("C:/Program Files/Microsoft VS Code/Code.exe"),
        ]
        for p in vscode_paths:
            if p.exists():
                self._software_paths[SoftwareType.VSCODE] = str(p)
                logger.info(f"✅ Found VS Code: {p}")
                break
    
    # =========================================================================
    # NATURAL LANGUAGE COMMAND INTERFACE
    # =========================================================================
    
    def process_command(self, command: str) -> CommandResult:
        """
        Process a natural language command from Ollama brain.
        
        Examples:
        - "create a new unity project called MyGame"
        - "open unity project MyGame"
        - "delete the unity project TestProject"
        - "build unity project for windows"
        - "list all unity projects"
        - "close unity"
        """
        command_lower = command.lower().strip()
        
        # Detect software type
        software = self._detect_software_type(command_lower)
        
        # Detect action
        action = self._detect_action(command_lower)
        
        # Extract project name if present
        project_name = self._extract_project_name(command_lower)
        
        logger.info(f"🧠 Command: {command}")
        logger.info(f"   Software: {software}, Action: {action}, Project: {project_name}")
        
        # Route to appropriate handler
        if software == SoftwareType.UNITY:
            return self._handle_unity_command(action, project_name, command_lower)
        elif software == SoftwareType.BLENDER:
            return self._handle_blender_command(action, project_name, command_lower)
        elif software == SoftwareType.VSCODE:
            return self._handle_vscode_command(action, project_name, command_lower)
        else:
            return CommandResult(
                success=False,
                action=action,
                software=software,
                message=f"Unknown software type in command: {command}",
                error="Could not determine which software to control"
            )
    
    def _detect_software_type(self, command: str) -> SoftwareType:
        """Detect which software the command refers to"""
        if any(kw in command for kw in ["unity", "game engine", "3d game"]):
            return SoftwareType.UNITY
        elif any(kw in command for kw in ["blender", "3d model", "mesh"]):
            return SoftwareType.BLENDER
        elif any(kw in command for kw in ["vscode", "vs code", "visual studio code", "code editor"]):
            return SoftwareType.VSCODE
        elif any(kw in command for kw in ["unreal", "ue5", "unreal engine"]):
            return SoftwareType.UNREAL
        elif any(kw in command for kw in ["godot"]):
            return SoftwareType.GODOT
        return SoftwareType.CUSTOM
    
    def _detect_action(self, command: str) -> ActionType:
        """Detect what action to perform"""
        for action, patterns in self._command_patterns.items():
            if any(pattern in command for pattern in patterns):
                return ActionType(action)
        return ActionType.STATUS
    
    def _extract_project_name(self, command: str) -> Optional[str]:
        """Extract project name from command"""
        # Look for "called X", "named X", "project X"
        import re
        patterns = [
            r'called\s+["\']?(\w+)["\']?',
            r'named\s+["\']?(\w+)["\']?',
            r'project\s+["\']?(\w+)["\']?',
            r'open\s+["\']?(\w+)["\']?',
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                name = match.group(1)
                # Filter out common words
                if name not in ["the", "a", "new", "unity", "blender", "for", "to"]:
                    return name
        return None
    
    # =========================================================================
    # UNITY CONTROL
    # =========================================================================
    
    def _handle_unity_command(self, action: ActionType, project_name: Optional[str], 
                               full_command: str) -> CommandResult:
        """Handle Unity-specific commands"""
        
        if action == ActionType.CREATE:
            return self.unity_create_project(project_name or f"Project_{int(time.time())}")
        
        elif action == ActionType.DELETE:
            if not project_name:
                return CommandResult(False, action, SoftwareType.UNITY, 
                                   "Please specify which project to delete")
            return self.unity_delete_project(project_name)
        
        elif action == ActionType.OPEN:
            if project_name:
                return self.unity_open_project(project_name)
            else:
                return self.unity_open_hub()
        
        elif action == ActionType.CLOSE:
            return self.unity_close()
        
        elif action == ActionType.BUILD:
            if not project_name:
                return CommandResult(False, action, SoftwareType.UNITY,
                                   "Please specify which project to build")
            return self.unity_build_project(project_name)
        
        elif action == ActionType.LIST:
            return self.unity_list_projects()
        
        elif action == ActionType.STATUS:
            return self.unity_status()
        
        return CommandResult(False, action, SoftwareType.UNITY,
                           f"Unknown Unity action: {action}")
    
    def unity_create_project(self, name: str, template: str = "3d-core") -> CommandResult:
        """Create a new Unity project"""
        if SoftwareType.UNITY not in self._hub_paths:
            return CommandResult(False, ActionType.CREATE, SoftwareType.UNITY,
                               "Unity Hub not found", error="Please install Unity Hub")
        
        project_path = self._project_base_path / "Unity" / name
        if project_path.exists():
            return CommandResult(False, ActionType.CREATE, SoftwareType.UNITY,
                               f"Project '{name}' already exists at {project_path}")
        
        project_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get installed Unity version
        hub = self._hub_paths[SoftwareType.UNITY]
        try:
            result = subprocess.run(
                [hub, "--headless", "editors", "-i"],
                capture_output=True, text=True, timeout=30
            )
            versions = [line.split()[0] for line in result.stdout.strip().split('\n') 
                       if line and line[0].isdigit()]
            if not versions:
                return CommandResult(False, ActionType.CREATE, SoftwareType.UNITY,
                                   "No Unity versions installed", 
                                   error="Install Unity Editor via Unity Hub")
            version = versions[0]
        except Exception as e:
            return CommandResult(False, ActionType.CREATE, SoftwareType.UNITY,
                               f"Failed to get Unity versions: {e}")
        
        # Create project
        try:
            logger.info(f"🎮 Creating Unity project: {name} with version {version}")
            process = subprocess.Popen(
                [hub, "--headless", "create", "-n", name, 
                 "-p", str(project_path), "-v", version, "-t", template],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            # Wait for creation (can take a while)
            stdout, stderr = process.communicate(timeout=300)
            
            if project_path.exists():
                # Install Kingdom AI scripts
                self._install_kingdom_ai_scripts(project_path)
                
                if self.event_bus:
                    self.event_bus.publish('unity.project.created', {
                        'name': name,
                        'path': str(project_path),
                        'version': version,
                        'template': template
                    })
                
                return CommandResult(True, ActionType.CREATE, SoftwareType.UNITY,
                                   f"✅ Created Unity project '{name}' at {project_path}",
                                   data={'path': str(project_path), 'version': version})
            else:
                return CommandResult(False, ActionType.CREATE, SoftwareType.UNITY,
                                   f"Failed to create project", 
                                   error=stderr.decode() if stderr else "Unknown error")
                
        except subprocess.TimeoutExpired:
            return CommandResult(False, ActionType.CREATE, SoftwareType.UNITY,
                               "Project creation timed out")
        except Exception as e:
            return CommandResult(False, ActionType.CREATE, SoftwareType.UNITY,
                               f"Error creating project: {e}")
    
    def unity_delete_project(self, name: str) -> CommandResult:
        """Delete a Unity project"""
        project_path = self._project_base_path / "Unity" / name
        
        if not project_path.exists():
            # Check if full path was given
            if Path(name).exists():
                project_path = Path(name)
            else:
                return CommandResult(False, ActionType.DELETE, SoftwareType.UNITY,
                                   f"Project '{name}' not found")
        
        try:
            shutil.rmtree(project_path)
            
            if self.event_bus:
                self.event_bus.publish('unity.project.deleted', {'name': name})
            
            return CommandResult(True, ActionType.DELETE, SoftwareType.UNITY,
                               f"✅ Deleted Unity project '{name}'")
        except Exception as e:
            return CommandResult(False, ActionType.DELETE, SoftwareType.UNITY,
                               f"Failed to delete project: {e}")
    
    def unity_open_project(self, name: str) -> CommandResult:
        """Open a Unity project"""
        project_path = self._project_base_path / "Unity" / name
        
        if not project_path.exists():
            if Path(name).exists():
                project_path = Path(name)
            else:
                return CommandResult(False, ActionType.OPEN, SoftwareType.UNITY,
                                   f"Project '{name}' not found")
        
        if SoftwareType.UNITY not in self._software_paths:
            return CommandResult(False, ActionType.OPEN, SoftwareType.UNITY,
                               "Unity Editor not found")
        
        try:
            editor = self._software_paths[SoftwareType.UNITY]
            process = subprocess.Popen([editor, "-projectPath", str(project_path)])
            
            instance = SoftwareInstance(
                software_type=SoftwareType.UNITY,
                name=name,
                path=str(project_path),
                process=process,
                pid=process.pid,
                started_at=datetime.now(),
                status="running"
            )
            self._instances[f"unity_{name}"] = instance
            
            if self.event_bus:
                self.event_bus.publish('unity.project.opened', {
                    'name': name,
                    'path': str(project_path),
                    'pid': process.pid
                })
            
            return CommandResult(True, ActionType.OPEN, SoftwareType.UNITY,
                               f"✅ Opening Unity project '{name}'",
                               data={'pid': process.pid, 'path': str(project_path)})
        except Exception as e:
            return CommandResult(False, ActionType.OPEN, SoftwareType.UNITY,
                               f"Failed to open project: {e}")
    
    def unity_open_hub(self) -> CommandResult:
        """Open Unity Hub"""
        if SoftwareType.UNITY not in self._hub_paths:
            return CommandResult(False, ActionType.OPEN, SoftwareType.UNITY,
                               "Unity Hub not found")
        
        try:
            hub = self._hub_paths[SoftwareType.UNITY]
            process = subprocess.Popen([hub])
            return CommandResult(True, ActionType.OPEN, SoftwareType.UNITY,
                               "✅ Opening Unity Hub",
                               data={'pid': process.pid})
        except Exception as e:
            return CommandResult(False, ActionType.OPEN, SoftwareType.UNITY,
                               f"Failed to open Unity Hub: {e}")
    
    def unity_close(self) -> CommandResult:
        """Close all Unity instances"""
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "Unity.exe"], 
                             capture_output=True)
            else:
                subprocess.run(["pkill", "-f", "Unity"], capture_output=True)
            
            # Clear instances
            unity_keys = [k for k in self._instances if k.startswith("unity_")]
            for k in unity_keys:
                del self._instances[k]
            
            return CommandResult(True, ActionType.CLOSE, SoftwareType.UNITY,
                               "✅ Closed all Unity instances")
        except Exception as e:
            return CommandResult(False, ActionType.CLOSE, SoftwareType.UNITY,
                               f"Failed to close Unity: {e}")
    
    def unity_build_project(self, name: str, target: str = "win64") -> CommandResult:
        """Build a Unity project"""
        project_path = self._project_base_path / "Unity" / name
        
        if not project_path.exists():
            return CommandResult(False, ActionType.BUILD, SoftwareType.UNITY,
                               f"Project '{name}' not found")
        
        if SoftwareType.UNITY not in self._software_paths:
            return CommandResult(False, ActionType.BUILD, SoftwareType.UNITY,
                               "Unity Editor not found")
        
        build_path = project_path / "Builds" / target
        build_path.mkdir(parents=True, exist_ok=True)
        
        try:
            editor = self._software_paths[SoftwareType.UNITY]
            result = subprocess.run([
                editor,
                "-projectPath", str(project_path),
                "-buildTarget", "StandaloneWindows64",
                "-buildPath", str(build_path / f"{name}.exe"),
                "-batchmode",
                "-quit"
            ], capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                return CommandResult(True, ActionType.BUILD, SoftwareType.UNITY,
                                   f"✅ Built '{name}' to {build_path}",
                                   data={'build_path': str(build_path)})
            else:
                return CommandResult(False, ActionType.BUILD, SoftwareType.UNITY,
                                   f"Build failed", error=result.stderr)
        except subprocess.TimeoutExpired:
            return CommandResult(False, ActionType.BUILD, SoftwareType.UNITY,
                               "Build timed out")
        except Exception as e:
            return CommandResult(False, ActionType.BUILD, SoftwareType.UNITY,
                               f"Build error: {e}")
    
    def unity_list_projects(self) -> CommandResult:
        """List all Unity projects"""
        unity_dir = self._project_base_path / "Unity"
        projects = []
        
        if unity_dir.exists():
            for p in unity_dir.iterdir():
                if p.is_dir() and (p / "Assets").exists():
                    projects.append({
                        'name': p.name,
                        'path': str(p),
                        'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat()
                    })
        
        return CommandResult(True, ActionType.LIST, SoftwareType.UNITY,
                           f"Found {len(projects)} Unity projects",
                           data={'projects': projects})
    
    def unity_status(self) -> CommandResult:
        """Get Unity status"""
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq Unity.exe"],
                    capture_output=True, text=True
                )
                running = "Unity.exe" in result.stdout
            else:
                result = subprocess.run(["pgrep", "-f", "Unity"], capture_output=True)
                running = result.returncode == 0
            
            return CommandResult(True, ActionType.STATUS, SoftwareType.UNITY,
                               f"Unity is {'running' if running else 'not running'}",
                               data={'running': running})
        except Exception as e:
            return CommandResult(False, ActionType.STATUS, SoftwareType.UNITY,
                               f"Failed to check status: {e}")
    
    def _install_kingdom_ai_scripts(self, project_path: Path):
        """Install Kingdom AI scripts into a Unity project"""
        scripts_dir = project_path / "Assets" / "Scripts"
        editor_dir = project_path / "Assets" / "Editor"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        editor_dir.mkdir(parents=True, exist_ok=True)
        
        # Source files
        source_base = Path(__file__).parent.parent / "kingdom_ai" / "mcp"
        
        # Copy CommandReceiver.cs
        src_receiver = source_base / "CommandReceiver.cs"
        if src_receiver.exists():
            shutil.copy(src_receiver, scripts_dir / "CommandReceiver.cs")
        
        # Create UnityMainThreadDispatcher.cs
        dispatcher_code = '''using UnityEngine;
using System;
using System.Collections.Generic;

public class UnityMainThreadDispatcher : MonoBehaviour
{
    private static UnityMainThreadDispatcher _instance;
    private static readonly Queue<Action> _executionQueue = new Queue<Action>();
    private static readonly object _lock = new object();

    public static UnityMainThreadDispatcher Instance()
    {
        if (_instance == null)
        {
            var go = new GameObject("UnityMainThreadDispatcher");
            _instance = go.AddComponent<UnityMainThreadDispatcher>();
            DontDestroyOnLoad(go);
        }
        return _instance;
    }

    void Awake()
    {
        if (_instance == null)
        {
            _instance = this;
            DontDestroyOnLoad(gameObject);
        }
    }

    public void Enqueue(Action action)
    {
        lock (_lock) { _executionQueue.Enqueue(action); }
    }

    void Update()
    {
        lock (_lock)
        {
            while (_executionQueue.Count > 0)
                _executionQueue.Dequeue().Invoke();
        }
    }
}
'''
        (scripts_dir / "UnityMainThreadDispatcher.cs").write_text(dispatcher_code)
        
        # Create auto-setup editor script
        editor_code = '''using UnityEngine;
using UnityEditor;

[InitializeOnLoad]
public class KingdomAIAutoSetup
{
    static KingdomAIAutoSetup()
    {
        EditorApplication.delayCall += SetupScene;
    }

    [MenuItem("Kingdom AI/Setup Command Receiver")]
    public static void SetupScene()
    {
        if (Object.FindObjectOfType<CommandReceiver>() != null) return;
        
        var dispatcherGO = new GameObject("UnityMainThreadDispatcher");
        dispatcherGO.AddComponent<UnityMainThreadDispatcher>();
        
        var receiverGO = new GameObject("KingdomAI_CommandReceiver");
        receiverGO.AddComponent<CommandReceiver>();
        
        Debug.Log("✅ Kingdom AI CommandReceiver ready on port 8080");
    }

    [MenuItem("Kingdom AI/Enter Play Mode")]
    public static void EnterPlayMode()
    {
        SetupScene();
        EditorApplication.isPlaying = true;
    }
}
'''
        (editor_dir / "KingdomAIAutoSetup.cs").write_text(editor_code)
        
        logger.info(f"✅ Installed Kingdom AI scripts in {project_path}")
    
    # =========================================================================
    # BLENDER CONTROL
    # =========================================================================
    
    def _handle_blender_command(self, action: ActionType, project_name: Optional[str],
                                 full_command: str) -> CommandResult:
        """Handle Blender commands"""
        if action == ActionType.OPEN:
            return self.blender_open(project_name)
        elif action == ActionType.CLOSE:
            return self.blender_close()
        elif action == ActionType.SAVE:
            return self._send_blender_script("bpy.ops.wm.save_mainfile()")
        elif action == ActionType.RENDER:
            return self._send_blender_script("bpy.ops.render.render(write_still=True)")
        return CommandResult(False, action, SoftwareType.BLENDER,
                           f"Blender action '{action}' is not supported")
    
    def _send_blender_script(self, script: str) -> CommandResult:
        """Execute a Python script inside a running Blender instance."""
        try:
            blender = self._software_paths.get(SoftwareType.BLENDER, "blender")
            result = subprocess.run(
                [blender, "--background", "--python-expr", script],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return CommandResult(True, ActionType.SAVE, SoftwareType.BLENDER,
                                   f"Blender script executed: {script[:40]}")
            return CommandResult(False, ActionType.SAVE, SoftwareType.BLENDER,
                               f"Blender script error: {result.stderr[:200]}")
        except Exception as e:
            return CommandResult(False, ActionType.SAVE, SoftwareType.BLENDER,
                               f"Failed to run Blender script: {e}")

    def blender_open(self, file_path: Optional[str] = None) -> CommandResult:
        """Open Blender"""
        if SoftwareType.BLENDER not in self._software_paths:
            return CommandResult(False, ActionType.OPEN, SoftwareType.BLENDER,
                               "Blender not found")
        
        try:
            blender = self._software_paths[SoftwareType.BLENDER]
            args = [blender]
            if file_path:
                args.append(file_path)
            process = subprocess.Popen(args)
            return CommandResult(True, ActionType.OPEN, SoftwareType.BLENDER,
                               "✅ Opening Blender",
                               data={'pid': process.pid})
        except Exception as e:
            return CommandResult(False, ActionType.OPEN, SoftwareType.BLENDER,
                               f"Failed to open Blender: {e}")
    
    def blender_close(self) -> CommandResult:
        """Close Blender"""
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "blender.exe"], capture_output=True)
            return CommandResult(True, ActionType.CLOSE, SoftwareType.BLENDER,
                               "✅ Closed Blender")
        except Exception as e:
            return CommandResult(False, ActionType.CLOSE, SoftwareType.BLENDER,
                               f"Failed to close Blender: {e}")
    
    # =========================================================================
    # VS CODE CONTROL
    # =========================================================================
    
    def _handle_vscode_command(self, action: ActionType, project_name: Optional[str],
                                full_command: str) -> CommandResult:
        """Handle VS Code commands"""
        if action == ActionType.OPEN:
            return self.vscode_open(project_name)
        elif action == ActionType.CLOSE:
            return self.vscode_close()
        elif action == ActionType.SAVE:
            return CommandResult(True, action, SoftwareType.VSCODE,
                               "VS Code auto-saves; use Ctrl+S for manual save")
        return CommandResult(False, action, SoftwareType.VSCODE,
                           f"VS Code action '{action}' is not supported")
    
    def vscode_open(self, path: Optional[str] = None) -> CommandResult:
        """Open VS Code"""
        if SoftwareType.VSCODE not in self._software_paths:
            # Try 'code' command
            try:
                args = ["code"]
                if path:
                    args.append(path)
                process = subprocess.Popen(args, shell=True)
                return CommandResult(True, ActionType.OPEN, SoftwareType.VSCODE,
                                   "✅ Opening VS Code",
                                   data={'pid': process.pid})
            except:
                return CommandResult(False, ActionType.OPEN, SoftwareType.VSCODE,
                                   "VS Code not found")
        
        try:
            vscode = self._software_paths[SoftwareType.VSCODE]
            args = [vscode]
            if path:
                args.append(path)
            process = subprocess.Popen(args)
            return CommandResult(True, ActionType.OPEN, SoftwareType.VSCODE,
                               "✅ Opening VS Code",
                               data={'pid': process.pid})
        except Exception as e:
            return CommandResult(False, ActionType.OPEN, SoftwareType.VSCODE,
                               f"Failed to open VS Code: {e}")
    
    def vscode_close(self) -> CommandResult:
        """Close VS Code"""
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "Code.exe"], capture_output=True)
            return CommandResult(True, ActionType.CLOSE, SoftwareType.VSCODE,
                               "✅ Closed VS Code")
        except Exception as e:
            return CommandResult(False, ActionType.CLOSE, SoftwareType.VSCODE,
                               f"Failed to close VS Code: {e}")
    
    # =========================================================================
    # OLLAMA BRAIN INTERFACE
    # =========================================================================
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities for Ollama brain system prompt"""
        return {
            "name": "UniversalSoftwareController",
            "description": "Full control of external software via natural language",
            "supported_software": [s.value for s in SoftwareType],
            "actions": [a.value for a in ActionType],
            "examples": [
                "create a new unity project called MyGame",
                "open unity project MyGame",
                "delete unity project TestProject",
                "build unity project MyGame for windows",
                "list all unity projects",
                "close unity",
                "open blender",
                "open vs code"
            ]
        }


# Singleton accessor
def get_software_controller(event_bus=None) -> UniversalSoftwareController:
    return UniversalSoftwareController.get_instance(event_bus)
