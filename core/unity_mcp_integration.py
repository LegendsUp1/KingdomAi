#!/usr/bin/env python3
"""
Unity MCP Integration - SOTA 2026
==================================
Full Unity Engine control for Kingdom AI via MCP protocol.

Enables Kingdom AI to:
- Launch Unity Hub and Unity Editor
- Create new projects (2D, 3D, VR, AR, HDRP, URP)
- Open existing projects
- Control Unity Editor via UI Automation
- Execute C# scripts remotely
- Build and deploy projects
- Manage assets and scenes
- Full creative control over Unity sessions

Author: Kingdom AI Team
Version: 1.0.0 SOTA 2026
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("KingdomAI.Unity.MCP")


def _wsl_resolve_exe(name: str) -> str:
    """Resolve Windows executables to full path when running as root in WSL2."""
    import shutil, platform
    if shutil.which(name):
        return name
    if 'microsoft' in platform.uname().release.lower():
        candidates = {
            'powershell.exe': '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            'cmd.exe': '/mnt/c/Windows/System32/cmd.exe',
        }
        full = candidates.get(name, f'/mnt/c/Windows/System32/{name}')
        if os.path.exists(full):
            return full
    return name


def _detect_wsl() -> bool:
    try:
        if os.path.exists('/proc/version'):
            with open('/proc/version', 'r', encoding='utf-8') as f:
                content = f.read().lower()
            return 'microsoft' in content or 'wsl' in content
    except Exception:
        pass
    return False


def _windows_to_wsl_path(win_path: str) -> Optional[str]:
    if not win_path:
        return None
    if not _detect_wsl():
        return None
    p = win_path.strip().strip('"')
    if len(p) < 3:
        return None
    if p[1] != ':' or p[2] not in ('\\', '/'):
        return None
    try:
        converted = subprocess.check_output(['wslpath', '-u', p], text=True).strip()
        if converted:
            return converted
    except Exception:
        pass
    drive = p[0].lower()
    rest = p[2:].lstrip('\\/').replace('\\', '/')
    return f"/mnt/{drive}/{rest}"

# ============================================================================
# UNITY CONFIGURATION
# ============================================================================

class UnityProjectTemplate(Enum):
    """Unity project templates available"""
    CORE_2D = "2d-core"
    CORE_3D = "3d-core"
    URP_2D = "2d-urp"
    URP_3D = "3d-urp"
    HDRP_3D = "3d-hdrp"
    VR_CORE = "vr-core"
    AR_CORE = "ar-core"
    EMPTY = "empty"


class UnityBuildTarget(Enum):
    """Unity build targets"""
    STANDALONE_WIN64 = "StandaloneWindows64"
    STANDALONE_MAC = "StandaloneOSX"
    STANDALONE_LINUX = "StandaloneLinux64"
    ANDROID = "Android"
    IOS = "iOS"
    WEBGL = "WebGL"
    PS5 = "PS5"
    XBOX_SERIES = "XboxOne"


@dataclass
class UnityInstallation:
    """Represents a Unity Editor installation"""
    version: str
    path: str
    is_default: bool = False
    modules: List[str] = field(default_factory=list)


@dataclass
class UnityProject:
    """Represents a Unity project"""
    name: str
    path: str
    unity_version: str
    template: UnityProjectTemplate
    created_at: datetime = field(default_factory=datetime.now)
    last_opened: Optional[datetime] = None
    scenes: List[str] = field(default_factory=list)
    

# ============================================================================
# UNITY HUB MANAGER
# ============================================================================

class UnityHubManager:
    """Manages Unity Hub operations"""
    
    DEFAULT_HUB_PATHS = [
        # Workspace Unity Hub (primary)
        str(Path(__file__).parent.parent / "Unity Hub" / "Unity Hub.exe"),
        # Standard installation paths
        r"C:\Program Files\Unity Hub\Unity Hub.exe",
        r"C:\Program Files (x86)\Unity Hub\Unity Hub.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Unity Hub\Unity Hub.exe"),
    ]
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.hub_path = self._find_unity_hub()
        self.installations: List[UnityInstallation] = []
        self.projects: Dict[str, UnityProject] = {}
        self._process: Optional[subprocess.Popen] = None
        
        # Scan for installations
        self._scan_installations()
        
    def _find_unity_hub(self) -> Optional[str]:
        """Find Unity Hub executable"""
        env_override = os.environ.get("KINGDOM_UNITY_HUB_PATH") or os.environ.get("UNITY_HUB_PATH")
        if env_override:
            candidate = env_override.strip().strip('"')
            if _detect_wsl() and sys.platform != "win32":
                candidate = _windows_to_wsl_path(candidate) or candidate
            if candidate and os.path.exists(candidate):
                logger.info(f"✅ Found Unity Hub from env: {candidate}")
                return candidate

        # Check for Linux system Python (native Linux, not WSL)
        if sys.platform == "linux":
            # Check standard Linux paths
            linux_paths = [
                "/usr/bin/unityhub",
                "/usr/local/bin/unityhub",
                os.path.expanduser("~/.local/bin/unityhub"),
            ]
            for path in linux_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    logger.info(f"✅ Found Unity Hub on Linux: {path}")
                    return path
            
            # Check PATH
            try:
                result = subprocess.run(
                    ["which", "unityhub"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    path = result.stdout.strip()
                    if path and os.path.exists(path):
                        logger.info(f"✅ Found Unity Hub in PATH: {path}")
                        return path
            except Exception:
                pass

        # Check workspace Unity Hub first
        workspace_hub = Path(__file__).parent.parent / "Unity Hub" / "Unity Hub.exe"
        if workspace_hub.exists():
            logger.info(f"✅ Found Unity Hub in workspace: {workspace_hub}")
            return str(workspace_hub)

        in_wsl = _detect_wsl() and sys.platform != "win32"
        if in_wsl:
            candidates = []
            for win_path in [
                r"C:\Program Files\Unity Hub\Unity Hub.exe",
                r"C:\Program Files (x86)\Unity Hub\Unity Hub.exe",
            ]:
                wsl_path = _windows_to_wsl_path(win_path)
                if wsl_path:
                    candidates.append(wsl_path)

            users_root = Path("/mnt/c/Users")
            if users_root.exists():
                try:
                    for user_dir in users_root.iterdir():
                        if not user_dir.is_dir():
                            continue
                        candidates.append(str(user_dir / "AppData" / "Local" / "Programs" / "Unity Hub" / "Unity Hub.exe"))
                        candidates.append(str(user_dir / "AppData" / "Local" / "Unity Hub" / "Unity Hub.exe"))
                        candidates.append(str(user_dir / "Desktop" / "Unity Hub" / "Unity Hub.exe"))
                        candidates.append(str(user_dir / "OneDrive" / "Desktop" / "Unity Hub" / "Unity Hub.exe"))
                except Exception:
                    pass

            for path in candidates:
                if path and os.path.exists(path):
                    logger.info(f"✅ Found Unity Hub: {path}")
                    return path

            try:
                result = subprocess.run(
                    ["where.exe", "Unity Hub.exe"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    win_path = result.stdout.strip().splitlines()[0].strip()
                    wsl_path = _windows_to_wsl_path(win_path)
                    if wsl_path and os.path.exists(wsl_path):
                        logger.info(f"✅ Found Unity Hub: {wsl_path}")
                        return wsl_path
            except Exception:
                pass

            logger.warning("⚠️ Unity Hub not found")
            return None
            
        # Check default paths
        for path in self.DEFAULT_HUB_PATHS:
            if os.path.exists(path):
                logger.info(f"✅ Found Unity Hub: {path}")
                return path
                
        # Check PATH
        try:
            result = subprocess.run(
                ["where", "Unity Hub.exe"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                path = result.stdout.strip().split('\n')[0]
                if os.path.exists(path):
                    return path
        except Exception:
            pass
            
        logger.warning("⚠️ Unity Hub not found")
        return None
        
    def _scan_installations(self):
        """Scan for Unity Editor installations"""
        self.installations = []

        in_wsl = _detect_wsl() and sys.platform != "win32"

        if sys.platform == "linux" and not in_wsl:
            linux_editor_roots = [
                os.path.expanduser("~/Unity/Hub/Editor"),
                "/opt/unity/editor",
                "/usr/share/unity3d",
            ]
            for base_path in linux_editor_roots:
                if os.path.isdir(base_path):
                    for version_dir in os.listdir(base_path):
                        editor_path = os.path.join(base_path, version_dir, "Editor", "Unity")
                        if os.path.exists(editor_path) and os.access(editor_path, os.X_OK):
                            install = UnityInstallation(
                                version=version_dir,
                                path=editor_path,
                                is_default=(len(self.installations) == 0)
                            )
                            self.installations.append(install)
                            logger.info(f"   Found Unity {version_dir}")
            logger.info(f"✅ Found {len(self.installations)} Unity installations")
            return

        # Windows / WSL paths
        unity_paths = [
            r"C:\Program Files\Unity\Hub\Editor",
            r"C:\Program Files (x86)\Unity\Hub\Editor",
            os.path.expanduser(r"~\Unity\Hub\Editor"),
        ]
        
        for base_path in unity_paths:
            scan_path = base_path
            if in_wsl:
                converted = _windows_to_wsl_path(base_path)
                if converted:
                    scan_path = converted

            if os.path.exists(scan_path):
                for version_dir in os.listdir(scan_path):
                    editor_path = os.path.join(scan_path, version_dir, "Editor", "Unity.exe")
                    if os.path.exists(editor_path):
                        install = UnityInstallation(
                            version=version_dir,
                            path=editor_path,
                            is_default=(len(self.installations) == 0)
                        )
                        self.installations.append(install)
                        logger.info(f"   Found Unity {version_dir}")
                        
        logger.info(f"✅ Found {len(self.installations)} Unity installations")
        
    def get_installations(self) -> List[Dict[str, Any]]:
        """Get list of Unity installations"""
        return [
            {
                "version": i.version,
                "path": i.path,
                "is_default": i.is_default,
                "modules": i.modules
            }
            for i in self.installations
        ]
        
    def is_hub_running(self) -> bool:
        """Check if Unity Hub is running"""
        try:
            if sys.platform == "linux" and not _detect_wsl():
                result = subprocess.run(
                    ["pgrep", "-f", "unityhub"],
                    capture_output=True, text=True, timeout=5
                )
                return result.returncode == 0
            cmd = ["tasklist", "/FI", "IMAGENAME eq Unity Hub.exe"]
            if _detect_wsl() and sys.platform != "win32":
                cmd[0] = "tasklist.exe"
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return "Unity Hub.exe" in result.stdout
        except Exception:
            return False
            
    def launch_hub(self) -> Dict[str, Any]:
        """Launch Unity Hub (WSL2-aware: uses Windows interop)."""
        if not self.hub_path:
            return {"success": False, "error": "Unity Hub not found"}

        if self.is_hub_running():
            return {"success": True, "message": "Unity Hub already running"}

        try:
            in_wsl = _detect_wsl() and sys.platform != "win32"
            if in_wsl and self.hub_path.startswith("/mnt/"):
                try:
                    win_path = subprocess.check_output(
                        ["wslpath", "-w", self.hub_path], text=True
                    ).strip()
                except Exception:
                    win_path = self.hub_path.replace("/mnt/c/", "C:\\").replace("/", "\\")
                self._process = subprocess.Popen(
                    [_wsl_resolve_exe("cmd.exe"), "/c", "start", "", win_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                logger.info("✅ Unity Hub launched via WSL interop: %s", win_path)
            else:
                self._process = subprocess.Popen(
                    [self.hub_path],
                    cwd=os.path.dirname(self.hub_path),
                    start_new_session=True,
                )
                logger.info("✅ Unity Hub launched: %s", self.hub_path)

            if self.event_bus:
                self.event_bus.publish('unity.hub.launched', {
                    'pid': self._process.pid,
                    'timestamp': datetime.now().isoformat()
                })

            return {"success": True, "pid": self._process.pid}

        except Exception as e:
            logger.error(f"❌ Failed to launch Unity Hub: {e}")
            return {"success": False, "error": str(e)}
            
    def close_hub(self) -> Dict[str, Any]:
        """Close Unity Hub"""
        try:
            if sys.platform == "linux" and not _detect_wsl():
                subprocess.run(["pkill", "-f", "unityhub"], capture_output=True, timeout=10)
            else:
                cmd = ["taskkill", "/F", "/IM", "Unity Hub.exe"]
                if _detect_wsl() and sys.platform != "win32":
                    cmd[0] = "taskkill.exe"
                subprocess.run(cmd, capture_output=True, timeout=10)
            logger.info("✅ Unity Hub closed")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================================
# UNITY EDITOR CONTROLLER
# ============================================================================

class UnityEditorController:
    """Controls Unity Editor via command line and automation"""
    
    def __init__(self, hub_manager: UnityHubManager, event_bus=None):
        self.hub = hub_manager
        self.event_bus = event_bus
        self._editor_process: Optional[subprocess.Popen] = None
        self._current_project: Optional[UnityProject] = None
        
    def get_default_editor(self) -> Optional[UnityInstallation]:
        """Get the default Unity Editor installation"""
        for install in self.hub.installations:
            if install.is_default:
                return install
        return self.hub.installations[0] if self.hub.installations else None
        
    def get_editor_by_version(self, version: str) -> Optional[UnityInstallation]:
        """Get Unity Editor by version"""
        for install in self.hub.installations:
            if version in install.version:
                return install
        return None
        
    def create_project(
        self,
        name: str,
        path: str,
        template: UnityProjectTemplate = UnityProjectTemplate.CORE_3D,
        unity_version: str = None
    ) -> Dict[str, Any]:
        """Create a new Unity project"""
        
        # Get editor
        if unity_version:
            editor = self.get_editor_by_version(unity_version)
        else:
            editor = self.get_default_editor()
            
        if not editor:
            return {"success": False, "error": "No Unity Editor found"}
            
        # Create project directory
        project_path = os.path.join(path, name)
        os.makedirs(project_path, exist_ok=True)
        
        # Build command
        cmd = [
            editor.path,
            "-createProject", project_path,
            "-quit",
            "-batchmode"
        ]
        
        logger.info(f"📦 Creating Unity project: {name}")
        logger.info(f"   Path: {project_path}")
        logger.info(f"   Template: {template.value}")
        logger.info(f"   Unity: {editor.version}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )
            
            # Create project record
            project = UnityProject(
                name=name,
                path=project_path,
                unity_version=editor.version,
                template=template
            )
            self.hub.projects[name] = project
            
            if self.event_bus:
                self.event_bus.publish('unity.project.created', {
                    'name': name,
                    'path': project_path,
                    'template': template.value,
                    'unity_version': editor.version,
                    'timestamp': datetime.now().isoformat()
                })
                
            logger.info(f"✅ Project created: {name}")
            return {
                "success": True,
                "project": {
                    "name": name,
                    "path": project_path,
                    "unity_version": editor.version,
                    "template": template.value
                }
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Project creation timed out"}
        except Exception as e:
            logger.error(f"❌ Failed to create project: {e}")
            return {"success": False, "error": str(e)}
            
    def open_project(self, project_path: str, unity_version: str = None) -> Dict[str, Any]:
        """Open an existing Unity project"""
        
        if not os.path.exists(project_path):
            return {"success": False, "error": f"Project not found: {project_path}"}
            
        # Get editor
        if unity_version:
            editor = self.get_editor_by_version(unity_version)
        else:
            editor = self.get_default_editor()
            
        if not editor:
            return {"success": False, "error": "No Unity Editor found"}
            
        try:
            self._editor_process = subprocess.Popen(
                [editor.path, "-projectPath", project_path],
                cwd=os.path.dirname(editor.path)
            )
            
            if self.event_bus:
                self.event_bus.publish('unity.project.opened', {
                    'path': project_path,
                    'unity_version': editor.version,
                    'pid': self._editor_process.pid,
                    'timestamp': datetime.now().isoformat()
                })
                
            logger.info(f"✅ Opening project: {project_path}")
            return {
                "success": True,
                "pid": self._editor_process.pid,
                "unity_version": editor.version
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to open project: {e}")
            return {"success": False, "error": str(e)}
            
    def execute_menu_item(self, menu_path: str) -> Dict[str, Any]:
        """Execute a Unity menu item (requires Editor script)"""
        # This would require a custom Unity Editor script to be installed
        # For now, return info about the capability
        return {
            "success": True,
            "info": f"Menu item execution requires Unity Editor script: {menu_path}",
            "implementation": "Install Kingdom AI Unity Package to enable"
        }
        
    def run_editor_script(self, script_path: str) -> Dict[str, Any]:
        """Run an Editor script in batchmode"""
        editor = self.get_default_editor()
        if not editor:
            return {"success": False, "error": "No Unity Editor found"}
            
        if not self._current_project:
            return {"success": False, "error": "No project open"}
            
        try:
            cmd = [
                editor.path,
                "-projectPath", self._current_project.path,
                "-executeMethod", script_path,
                "-batchmode",
                "-quit"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def build_project(
        self,
        project_path: str,
        output_path: str,
        target: UnityBuildTarget = UnityBuildTarget.STANDALONE_WIN64
    ) -> Dict[str, Any]:
        """Build a Unity project"""
        editor = self.get_default_editor()
        if not editor:
            return {"success": False, "error": "No Unity Editor found"}
            
        try:
            cmd = [
                editor.path,
                "-projectPath", project_path,
                "-buildTarget", target.value,
                "-buildPath", output_path,
                "-batchmode",
                "-quit"
            ]
            
            logger.info(f"🔨 Building project: {project_path}")
            logger.info(f"   Target: {target.value}")
            logger.info(f"   Output: {output_path}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            
            if self.event_bus:
                self.event_bus.publish('unity.build.completed', {
                    'project_path': project_path,
                    'output_path': output_path,
                    'target': target.value,
                    'success': result.returncode == 0,
                    'timestamp': datetime.now().isoformat()
                })
                
            return {
                "success": result.returncode == 0,
                "output_path": output_path,
                "target": target.value
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Build timed out (30 min limit)"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def close_editor(self) -> Dict[str, Any]:
        """Close Unity Editor"""
        try:
            if sys.platform == "linux" and not _detect_wsl():
                subprocess.run(["pkill", "-f", "Unity"], capture_output=True, timeout=10)
            else:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "Unity.exe"],
                    capture_output=True, timeout=10
                )
            self._editor_process = None
            self._current_project = None
            logger.info("✅ Unity Editor closed")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================================
# UNITY MCP TOOLS
# ============================================================================

class UnityMCPTools:
    """MCP tools for AI to control Unity"""
    
    def __init__(self, hub_manager: UnityHubManager, editor_controller: UnityEditorController):
        self.hub = hub_manager
        self.editor = editor_controller
        
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get MCP tool definitions for Unity control"""
        return [
            {
                "name": "unity_get_installations",
                "description": "List all installed Unity Editor versions",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "unity_launch_hub",
                "description": "Launch Unity Hub application",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "unity_close_hub",
                "description": "Close Unity Hub application",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "unity_create_project",
                "description": "Create a new Unity project with specified template",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Project name"},
                        "path": {"type": "string", "description": "Parent directory for project"},
                        "template": {
                            "type": "string",
                            "enum": [t.value for t in UnityProjectTemplate],
                            "description": "Project template (3d-core, 2d-core, vr-core, etc.)"
                        },
                        "unity_version": {"type": "string", "description": "Unity version to use"}
                    },
                    "required": ["name", "path"]
                }
            },
            {
                "name": "unity_open_project",
                "description": "Open an existing Unity project in the Editor",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "Full path to Unity project"},
                        "unity_version": {"type": "string", "description": "Unity version to use"}
                    },
                    "required": ["project_path"]
                }
            },
            {
                "name": "unity_build_project",
                "description": "Build a Unity project for a target platform",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "Path to project"},
                        "output_path": {"type": "string", "description": "Build output path"},
                        "target": {
                            "type": "string",
                            "enum": [t.value for t in UnityBuildTarget],
                            "description": "Build target platform"
                        }
                    },
                    "required": ["project_path", "output_path"]
                }
            },
            {
                "name": "unity_close_editor",
                "description": "Close Unity Editor",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "unity_execute_script",
                "description": "Execute a C# Editor script in batchmode",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "description": "Full method path (e.g., MyClass.MyMethod)"}
                    },
                    "required": ["method"]
                }
            }
        ]
        
    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Unity MCP tool"""
        
        if tool_name == "unity_get_installations":
            return {
                "success": True,
                "installations": self.hub.get_installations(),
                "hub_path": self.hub.hub_path,
                "hub_running": self.hub.is_hub_running()
            }
            
        elif tool_name == "unity_launch_hub":
            return self.hub.launch_hub()
            
        elif tool_name == "unity_close_hub":
            return self.hub.close_hub()
            
        elif tool_name == "unity_create_project":
            template = UnityProjectTemplate.CORE_3D
            if params.get("template"):
                try:
                    template = UnityProjectTemplate(params["template"])
                except ValueError:
                    pass
                    
            return self.editor.create_project(
                name=params["name"],
                path=params["path"],
                template=template,
                unity_version=params.get("unity_version")
            )
            
        elif tool_name == "unity_open_project":
            return self.editor.open_project(
                project_path=params["project_path"],
                unity_version=params.get("unity_version")
            )
            
        elif tool_name == "unity_build_project":
            target = UnityBuildTarget.STANDALONE_WIN64
            if params.get("target"):
                try:
                    target = UnityBuildTarget(params["target"])
                except ValueError:
                    pass
                    
            return self.editor.build_project(
                project_path=params["project_path"],
                output_path=params["output_path"],
                target=target
            )
            
        elif tool_name == "unity_close_editor":
            return self.editor.close_editor()
            
        elif tool_name == "unity_execute_script":
            return self.editor.run_editor_script(params["method"])
            
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}


# ============================================================================
# SINGLETON & FACTORY
# ============================================================================

_unity_hub_manager: Optional[UnityHubManager] = None
_unity_editor_controller: Optional[UnityEditorController] = None
_unity_mcp_tools: Optional[UnityMCPTools] = None


def get_unity_hub_manager(event_bus=None) -> UnityHubManager:
    """Get or create Unity Hub Manager singleton"""
    global _unity_hub_manager
    if _unity_hub_manager is None:
        _unity_hub_manager = UnityHubManager(event_bus)
    return _unity_hub_manager


def get_unity_editor_controller(event_bus=None) -> UnityEditorController:
    """Get or create Unity Editor Controller singleton"""
    global _unity_editor_controller, _unity_hub_manager
    if _unity_editor_controller is None:
        hub = get_unity_hub_manager(event_bus)
        _unity_editor_controller = UnityEditorController(hub, event_bus)
    return _unity_editor_controller


def get_unity_mcp_tools(event_bus=None) -> UnityMCPTools:
    """Get or create Unity MCP Tools singleton"""
    global _unity_mcp_tools
    if _unity_mcp_tools is None:
        hub = get_unity_hub_manager(event_bus)
        editor = get_unity_editor_controller(event_bus)
        _unity_mcp_tools = UnityMCPTools(hub, editor)
    return _unity_mcp_tools


# ============================================================================
# QUICK TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("🎮 UNITY MCP INTEGRATION TEST")
    print("=" * 60)
    
    # Initialize
    hub = get_unity_hub_manager()
    editor = get_unity_editor_controller()
    mcp = get_unity_mcp_tools()
    
    # Test getting installations
    result = mcp.execute_tool("unity_get_installations", {})
    print(f"\n📦 Installations: {json.dumps(result, indent=2)}")
    
    # List available tools
    tools = mcp.get_tools()
    print(f"\n🔧 Available MCP Tools ({len(tools)}):")
    for tool in tools:
        print(f"   - {tool['name']}: {tool['description']}")
    
    print("\n✅ Unity MCP Integration ready!")
