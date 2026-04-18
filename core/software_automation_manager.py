import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _is_wsl() -> bool:
    try:
        if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
            return True
        if sys.platform.startswith("linux"):
            try:
                with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                    return "microsoft" in f.read().lower()
            except Exception:
                return False
        return False
    except Exception:
        return False


def _can_use_windows_host() -> bool:
    if os.name == "nt":
        return True
    return _is_wsl()


def _powershell_exe() -> str:
    if _is_wsl():
        return "powershell.exe"
    return "powershell"


def _encode_powershell(script: str) -> str:
    raw = script.encode("utf-16le")
    return base64.b64encode(raw).decode("ascii")


def _run_powershell_encoded(script: str, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_powershell_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", _encode_powershell(script)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


_UIA_PS = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient | Out-Null
Add-Type -AssemblyName UIAutomationTypes | Out-Null
Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
}
"@ | Out-Null

$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP   = 0x0004
$MOUSEEVENTF_RIGHTDOWN = 0x0008
$MOUSEEVENTF_RIGHTUP   = 0x0010

function Convert-ControlType([string]$name) {
  if (-not $name) { return $null }
  $n = $name.Trim().ToLowerInvariant()
  $ct = [System.Windows.Automation.ControlType]
  switch ($n) {
    'window' { return $ct::Window }
    'button' { return $ct::Button }
    'edit' { return $ct::Edit }
    'document' { return $ct::Document }
    'pane' { return $ct::Pane }
    'menuitem' { return $ct::MenuItem }
    'menu' { return $ct::Menu }
    'list' { return $ct::List }
    'listitem' { return $ct::ListItem }
    'tab' { return $ct::Tab }
    'tabitem' { return $ct::TabItem }
    'text' { return $ct::Text }
    'tree' { return $ct::Tree }
    'treeitem' { return $ct::TreeItem }
    'combo' { return $ct::ComboBox }
    'combobox' { return $ct::ComboBox }
    'toolbar' { return $ct::ToolBar }
    'hyperlink' { return $ct::Hyperlink }
    'checkbox' { return $ct::CheckBox }
    'radiobutton' { return $ct::RadioButton }
    'slider' { return $ct::Slider }
    'scrollbar' { return $ct::ScrollBar }
    default { return $null }
  }
}

function Get-TopWindows {
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  $children = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
  $out = @()
  foreach ($el in $children) {
    try {
      $ct = $el.Current.ControlType.ProgrammaticName
      $name = $el.Current.Name
      $pid = $el.Current.ProcessId
      $hwnd = $el.Current.NativeWindowHandle
      if ($hwnd -eq 0) { continue }
      $out += [pscustomobject]@{
        name = $name
        process_id = $pid
        hwnd = $hwnd
        control_type = $ct
        class_name = $el.Current.ClassName
        automation_id = $el.Current.AutomationId
      }
    } catch {}
  }
  return $out
}

function Resolve-Window($sel) {
  $windows = Get-TopWindows
  if ($null -eq $sel) { return $null }
  if ($sel.hwnd) {
    $h = [int]$sel.hwnd
    foreach ($w in $windows) { if ([int]$w.hwnd -eq $h) { return $w } }
  }
  if ($sel.process_id) {
    $pid = [int]$sel.process_id
    $cands = @($windows | Where-Object { [int]$_.process_id -eq $pid })
    if ($cands.Count -gt 0) { return $cands[0] }
  }
  if ($sel.name_contains) {
    $q = [string]$sel.name_contains
    $cands = @($windows | Where-Object { $_.name -and $_.name.ToLowerInvariant().Contains($q.ToLowerInvariant()) })
    if ($cands.Count -gt 0) { return $cands[0] }
  }
  return $null
}

function Get-AutomationElementByHwnd([int]$hwnd) {
  $prop = [System.Windows.Automation.AutomationElement]::NativeWindowHandleProperty
  $cond = New-Object System.Windows.Automation.PropertyCondition($prop, $hwnd)
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  return $root.FindFirst([System.Windows.Automation.TreeScope]::Subtree, $cond)
}

function Resolve-Control($winEl, $controlSel) {
  if ($null -eq $winEl) { return $null }
  $root = Get-AutomationElementByHwnd([int]$winEl.hwnd)
  if ($null -eq $root) { return $null }
  if ($null -eq $controlSel) { return $root }

  $conds = @()
  if ($controlSel.automation_id) {
    $conds += New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, [string]$controlSel.automation_id)
  }
  if ($controlSel.name_contains) {
    $conds += New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, [string]$controlSel.name_contains)
  }
  if ($controlSel.class_name) {
    $conds += New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, [string]$controlSel.class_name)
  }
  if ($controlSel.control_type) {
    $ct = Convert-ControlType([string]$controlSel.control_type)
    if ($ct) {
      $conds += New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, $ct)
    }
  }

  $cond = [System.Windows.Automation.Condition]::TrueCondition
  if ($conds.Count -eq 1) {
    $cond = $conds[0]
  } elseif ($conds.Count -gt 1) {
    $cond = New-Object System.Windows.Automation.AndCondition($conds)
  }

  $scope = [System.Windows.Automation.TreeScope]::Descendants
  $matches = $root.FindAll($scope, $cond)
  $idx = 0
  if ($controlSel.index -ne $null) { $idx = [int]$controlSel.index }
  if ($matches.Count -le $idx) { return $null }
  return $matches[$idx]
}

function Element-ToObject($el) {
  if ($null -eq $el) { return $null }
  $r = $el.Current.BoundingRectangle
  return [pscustomobject]@{
    name = $el.Current.Name
    automation_id = $el.Current.AutomationId
    class_name = $el.Current.ClassName
    control_type = $el.Current.ControlType.ProgrammaticName
    process_id = $el.Current.ProcessId
    hwnd = $el.Current.NativeWindowHandle
    bounding = [pscustomobject]@{ x=$r.X; y=$r.Y; width=$r.Width; height=$r.Height }
  }
}

function Invoke-Element($el) {
  $pat = $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
  if ($pat) { $pat.Invoke(); return $true }
  $t = $el.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
  if ($t) { $t.Toggle(); return $true }
  $s = $el.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
  if ($s) { $s.Select(); return $true }
  $a = $el.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern)
  if ($a) { $a.DoDefaultAction(); return $true }
  return $false
}

function Set-ElementValue($el, [string]$value) {
  $vp = $el.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
  if ($vp) { $vp.SetValue($value); return $true }
  $a = $el.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern)
  if ($a) { $a.SetValue($value); return $true }
  return $false
}

function Focus-Window([int]$hwnd) {
  [Win32]::ShowWindow([intptr]$hwnd, 9) | Out-Null
  Start-Sleep -Milliseconds 80
  return [Win32]::SetForegroundWindow([intptr]$hwnd)
}

function Click-At([int]$x, [int]$y, [string]$button) {
  [Win32]::SetCursorPos($x, $y) | Out-Null
  Start-Sleep -Milliseconds 30
  $b = ($button | ForEach-Object { $_.ToLowerInvariant() })
  if ($b -eq 'right') {
    [Win32]::mouse_event($MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 30
    [Win32]::mouse_event($MOUSEEVENTF_RIGHTUP, 0, 0, 0, [UIntPtr]::Zero)
    return
  }
  [Win32]::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 30
  [Win32]::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
}

function Main($req) {
  $action = [string]$req.action

  if ($action -eq 'start_process') {
    $path = [string]$req.path
    if (-not $path) { return [pscustomobject]@{ success=$false; error='missing_path' } }
    $args = ''
    if ($req.args) { $args = [string]$req.args }
    $wd = $null
    if ($req.working_dir) { $wd = [string]$req.working_dir }
    try {
      if ($wd) {
        $p = Start-Process -FilePath $path -ArgumentList $args -WorkingDirectory $wd -PassThru
      } else {
        $p = Start-Process -FilePath $path -ArgumentList $args -PassThru
      }
      Start-Sleep -Milliseconds 300
      return [pscustomobject]@{ success=$true; process_id=[int]$p.Id }
    } catch {
      return [pscustomobject]@{ success=$false; error=($_.Exception.Message) }
    }
  }

  if ($action -eq 'wait_window') {
    $timeoutMs = 15000
    if ($req.timeout_ms -ne $null) { $timeoutMs = [int]$req.timeout_ms }
    $start = [Environment]::TickCount
    while ( ([Environment]::TickCount - $start) -lt $timeoutMs ) {
      $w = Resolve-Window $req.window
      if ($w) { return [pscustomobject]@{ success=$true; window=$w } }
      Start-Sleep -Milliseconds 200
    }
    return [pscustomobject]@{ success=$false; error='window_timeout' }
  }

  if ($action -eq 'list_windows') {
    return [pscustomobject]@{ success=$true; windows=(Get-TopWindows) }
  }

  if ($action -eq 'focus_window') {
    $w = Resolve-Window $req.window
    if ($null -eq $w) { return [pscustomobject]@{ success=$false; error='window_not_found' } }
    $ok = Focus-Window([int]$w.hwnd)
    return [pscustomobject]@{ success=$true; focused=$ok; window=$w }
  }

  if ($action -eq 'list_controls') {
    $w = Resolve-Window $req.window
    if ($null -eq $w) { return [pscustomobject]@{ success=$false; error='window_not_found' } }
    $root = Get-AutomationElementByHwnd([int]$w.hwnd)
    if ($null -eq $root) { return [pscustomobject]@{ success=$false; error='uia_root_not_found' } }
    $scope = [System.Windows.Automation.TreeScope]::Descendants
    $cond = [System.Windows.Automation.Condition]::TrueCondition
    $all = $root.FindAll($scope, $cond)
    $max = 250
    if ($req.max -ne $null) { $max = [int]$req.max }
    $out = @()
    for ($i=0; $i -lt $all.Count -and $i -lt $max; $i++) {
      $out += (Element-ToObject $all[$i])
    }
    return [pscustomobject]@{ success=$true; window=$w; controls=$out; count=$out.Count }
  }

  if ($action -eq 'find_control') {
    $w = Resolve-Window $req.window
    if ($null -eq $w) { return [pscustomobject]@{ success=$false; error='window_not_found' } }
    $el = Resolve-Control $w $req.control
    if ($null -eq $el) { return [pscustomobject]@{ success=$false; error='control_not_found' } }
    return [pscustomobject]@{ success=$true; window=$w; control=(Element-ToObject $el) }
  }

  if ($action -eq 'invoke_control') {
    $w = Resolve-Window $req.window
    if ($null -eq $w) { return [pscustomobject]@{ success=$false; error='window_not_found' } }
    $el = Resolve-Control $w $req.control
    if ($null -eq $el) { return [pscustomobject]@{ success=$false; error='control_not_found' } }
    $ok = Invoke-Element $el
    return [pscustomobject]@{ success=$ok; window=$w; control=(Element-ToObject $el) }
  }

  if ($action -eq 'set_value') {
    $w = Resolve-Window $req.window
    if ($null -eq $w) { return [pscustomobject]@{ success=$false; error='window_not_found' } }
    $el = Resolve-Control $w $req.control
    if ($null -eq $el) { return [pscustomobject]@{ success=$false; error='control_not_found' } }
    $ok = Set-ElementValue $el ([string]$req.value)
    return [pscustomobject]@{ success=$ok; window=$w; control=(Element-ToObject $el) }
  }

  if ($action -eq 'send_keys') {
    $w = Resolve-Window $req.window
    if ($null -eq $w) { return [pscustomobject]@{ success=$false; error='window_not_found' } }
    Focus-Window([int]$w.hwnd) | Out-Null
    if ($req.control) {
      $el = Resolve-Control $w $req.control
      if ($el) { try { $el.SetFocus() } catch {} }
    }
    [System.Windows.Forms.SendKeys]::SendWait([string]$req.keys)
    return [pscustomobject]@{ success=$true; window=$w }
  }

  if ($action -eq 'click_at') {
    $w = Resolve-Window $req.window
    if ($null -eq $w) { return [pscustomobject]@{ success=$false; error='window_not_found' } }
    Focus-Window([int]$w.hwnd) | Out-Null
    $x = [int]$req.x
    $y = [int]$req.y
    $btn = 'left'
    if ($req.button) { $btn = [string]$req.button }
    Click-At $x $y $btn
    return [pscustomobject]@{ success=$true; window=$w }
  }

  return [pscustomobject]@{ success=$false; error='unknown_action'; action=$action }
}
'''


@dataclass
class SoftwareAutomationManager:
    # Active window target - auto-injected when window param is omitted
    _active_target: Optional[Dict[str, Any]] = None
    
    def set_active_target(self, window_selector: Dict[str, Any]) -> None:
        """Set the active window target for auto-connect.
        
        Args:
            window_selector: Dict with hwnd, process_id, or name_contains
        """
        self._active_target = window_selector
    
    def get_active_target(self) -> Optional[Dict[str, Any]]:
        """Get the current active window target."""
        return self._active_target
    
    def clear_active_target(self) -> None:
        """Clear the active window target."""
        self._active_target = None
    
    def execute(self, request: Dict[str, Any], timeout: float = 60) -> Dict[str, Any]:
        if not _can_use_windows_host():
            return {"success": False, "error": "windows_host_not_available"}

        payload_b64 = base64.b64encode(json.dumps(request).encode("utf-8")).decode("ascii")
        script = _UIA_PS + "\n" + rf"$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{payload_b64}'))\n" + r"$req = $json | ConvertFrom-Json\n" + r"$res = Main $req\n" + r"$res | ConvertTo-Json -Depth 8\n"
        result = _run_powershell_encoded(script, timeout=timeout)

        out = (result.stdout or "").strip()
        if result.returncode != 0:
            return {
                "success": False,
                "error": (result.stderr or "").strip() or "powershell_failed",
                "raw": out,
            }
        if not out:
            return {"success": False, "error": "no_output"}
        try:
            return json.loads(out)
        except Exception:
            return {"success": False, "error": "invalid_json", "raw": out}


class SoftwareAutomationMCPTools:
    def __init__(self, manager: SoftwareAutomationManager):
        self.manager = manager

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "start_process",
                "description": "Start a Windows process by executable path (runs on Windows host)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "args": {"type": "string"},
                        "working_dir": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "list_windows",
                "description": "List top-level desktop windows on the Windows host",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "wait_window",
                "description": "Wait until a window exists (by hwnd/process_id/name_contains)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        },
                        "timeout_ms": {"type": "integer"},
                    },
                    "required": ["window"],
                },
            },
            {
                "name": "focus_window",
                "description": "Bring a window to the foreground",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        }
                    },
                    "required": ["window"],
                },
            },
            {
                "name": "list_controls",
                "description": "List UIA controls for a window (descendants)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        },
                        "max": {"type": "integer"},
                    },
                    "required": ["window"],
                },
            },
            {
                "name": "find_control",
                "description": "Find a control in a window via UIA selectors",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        },
                        "control": {
                            "type": "object",
                            "properties": {
                                "automation_id": {"type": "string"},
                                "name_contains": {"type": "string"},
                                "class_name": {"type": "string"},
                                "control_type": {"type": "string"},
                                "index": {"type": "integer"},
                            },
                        },
                    },
                    "required": ["window", "control"],
                },
            },
            {
                "name": "invoke_control",
                "description": "Invoke/click a control using UIA patterns (Invoke/Toggle/Select/DoDefaultAction)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        },
                        "control": {
                            "type": "object",
                            "properties": {
                                "automation_id": {"type": "string"},
                                "name_contains": {"type": "string"},
                                "class_name": {"type": "string"},
                                "control_type": {"type": "string"},
                                "index": {"type": "integer"},
                            },
                        },
                    },
                    "required": ["window", "control"],
                },
            },
            {
                "name": "set_value",
                "description": "Set text/value of a control using ValuePattern or LegacyIAccessible",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        },
                        "control": {
                            "type": "object",
                            "properties": {
                                "automation_id": {"type": "string"},
                                "name_contains": {"type": "string"},
                                "class_name": {"type": "string"},
                                "control_type": {"type": "string"},
                                "index": {"type": "integer"},
                            },
                        },
                        "value": {"type": "string"},
                    },
                    "required": ["window", "control", "value"],
                },
            },
            {
                "name": "send_keys",
                "description": "Focus a window (and optionally a control) then send keys using SendKeys",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        },
                        "control": {
                            "type": "object",
                            "properties": {
                                "automation_id": {"type": "string"},
                                "name_contains": {"type": "string"},
                                "class_name": {"type": "string"},
                                "control_type": {"type": "string"},
                                "index": {"type": "integer"},
                            },
                        },
                        "keys": {"type": "string"},
                    },
                    "required": ["window", "keys"],
                },
            },
            {
                "name": "click_at",
                "description": "Focus a window then click at screen coordinates (x,y)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        },
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "button": {"type": "string"},
                    },
                    "required": ["window", "x", "y"],
                },
            },
            # SOTA 2026: Auto-connect tools for runtime software selection
            {
                "name": "connect_software",
                "description": "Connect to a software window as the active target (auto-used by other tools)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "object",
                            "properties": {
                                "hwnd": {"type": "integer"},
                                "process_id": {"type": "integer"},
                                "name_contains": {"type": "string"},
                            },
                        }
                    },
                    "required": ["window"],
                },
            },
            {
                "name": "disconnect_software",
                "description": "Disconnect from the active software window target",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_connected_software",
                "description": "Get the currently connected software window target",
                "parameters": {"type": "object", "properties": {}},
            },
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in {
            "start_process",
            "list_windows",
            "wait_window",
            "focus_window",
            "list_controls",
            "find_control",
            "invoke_control",
            "set_value",
            "send_keys",
            "click_at",
            "connect_software",
            "disconnect_software",
            "get_connected_software",
        }:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        # Handle connect/disconnect/get_connected_software locally
        if tool_name == "connect_software":
            window_sel = parameters.get("window")
            if not window_sel:
                return {"success": False, "error": "window selector required"}
            self.manager.set_active_target(window_sel)
            return {"success": True, "connected": window_sel}
        
        if tool_name == "disconnect_software":
            self.manager.clear_active_target()
            return {"success": True, "disconnected": True}
        
        if tool_name == "get_connected_software":
            target = self.manager.get_active_target()
            return {"success": True, "connected": target is not None, "target": target}

        request: Dict[str, Any] = {"action": tool_name}
        request.update(parameters or {})
        
        # SOTA 2026: Auto-inject active window target when window param is omitted
        tools_needing_window = {
            "focus_window", "list_controls", "find_control", "invoke_control",
            "set_value", "send_keys", "click_at", "wait_window"
        }
        if tool_name in tools_needing_window:
            if "window" not in request or not request.get("window"):
                active = self.manager.get_active_target()
                if active:
                    request["window"] = active
                else:
                    return {"success": False, "error": "no_window_specified_and_no_active_target"}
        
        return self.manager.execute(request)
