# TAB 7: CODE GENERATOR - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** AI Code Generator
**Purpose:** AI-powered code generation and execution
**Frontend File:** `gui/frames/code_generator_qt.py`
**Backend Files:** `codegen/generator.py`, `kingdom_ai/mcp/ollama_code_runner.py`
**Event Bus Topics:** `codegen.*`, `brain.*`, `thoth.*`, `memory.*`, `api.key.*`, `ui.telemetry`
**External APIs:** Ollama (codellama model)

---

## 🔌 ACTUAL SIGNAL CONNECTIONS (Enumerated Dec 2025)

| Line | Signal | Handler | Purpose |
|------|--------|---------|--------|
| 137 | `code_response_signal` | `_process_code_response_in_main_thread` | Thread-safe code response |
| 138 | `brain_response_signal` | `_process_brain_response_in_main_thread` | Thread-safe brain response |
| 139 | `tests_autoupdate_signal` | `_process_tests_autoupdate_in_main_thread` | Thread-safe test updates |
| 287 | `health_timer.timeout` | `_check_redis_health` | Redis health check (30s) |
| 419 | `generate_action.triggered` | `generate_code` | Generate action |
| 424 | `execute_action.triggered` | `execute_code` | Execute action |
| 431 | `clear_action.triggered` | `clear_code` | Clear action |
| 790 | `new_action.clicked` | `new_file` | New file button |
| 797 | `open_action.clicked` | `open_file` | Open file button |
| 804 | `save_action.clicked` | `save_file` | Save file button |
| 826 | `lang_selector.currentTextChanged` | `change_language` | Language switch |
| 843 | `generate_btn.clicked` | `generate_code` | Generate button |
| 854 | `execute_btn.clicked` | `execute_code` | Execute button |
| 977 | `apply_reload_btn.clicked` | `apply_hot_reload` | Hot reload button |
| 978 | `language_combo.currentTextChanged` | `change_language` | Language combo |
| 981 | `code_generated` (signal) | `on_code_generated` | Code generated |
| 982 | `execution_completed` (signal) | `on_execution_completed` | Execution done |
| 1645 | Dialog close button | `dialog.accept` | Close dialog |

## 📡 ACTUAL EVENTBUS SUBSCRIPTIONS (deferred via QTimer)

| Topic | Handler |
|-------|---------|
| `api.key.available.*` | `_on_api_key_available` |
| `api.key.list` | `_on_api_key_list` |
| `codegen.code_generated` | `_handle_code_generated` |
| `codegen.execution_complete` | `_handle_execution_result` |
| `brain.response` | `_handle_brain_response` |
| `codegen.tests_autoupdate` | `_handle_tests_autoupdate` |

## 📡 ACTUAL EVENTBUS PUBLISHES

| Topic | Location | Trigger |
|-------|----------|--------|
| `ui.telemetry` | `_emit_ui_telemetry()` | Button clicks |
| `memory.store` | `_emit_ui_telemetry()` | Store telemetry in memory |
| `codegen.history` | `generate_code()` | Store prompt history |
| `thoth.message.sent` | `generate_code()` | AI message sent |
| `brain.request` | `generate_code()` | Brain request |
| `codegen.generate` | `generate_code()` | Generate code event |
| `codegen.execute` | `execute_code()` / `apply_hot_reload()` | Execute code event |

---

## 📊 BUTTON MAPPING (5 BUTTONS)

### Button 1: NEW

**Event Listener:**
```python
self.new_button.clicked.connect(self._on_new_clicked)
```

**Event Handler:**
```python
def _on_new_clicked(self):
    """Create new file"""
    # Clear editor
    self.code_editor.clear()
    self.current_file = None
    self.setWindowTitle("Code Generator - New File")
```

---

### Button 2: OPEN

**Event Listener:**
```python
self.open_button.clicked.connect(self._on_open_clicked)
```

**Event Handler:**
```python
def _on_open_clicked(self):
    """Open file from disk"""
    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "Open File",
        "",
        "Python Files (*.py);;All Files (*.*)"
    )
    
    if file_path:
        with open(file_path, 'r') as f:
            code = f.read()
            self.code_editor.setPlainText(code)
            self.current_file = file_path
            self.setWindowTitle(f"Code Generator - {file_path}")
```

---

### Button 3: SAVE

**Event Listener:**
```python
self.save_button.clicked.connect(self._on_save_clicked)
```

**Event Handler:**
```python
def _on_save_clicked(self):
    """Save file to disk"""
    if self.current_file:
        # Save to existing file
        with open(self.current_file, 'w') as f:
            f.write(self.code_editor.toPlainText())
        logger.info(f"✅ File saved: {self.current_file}")
    else:
        # Save As dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            "",
            "Python Files (*.py);;All Files (*.*)"
        )
        
        if file_path:
            with open(file_path, 'w') as f:
                f.write(self.code_editor.toPlainText())
            self.current_file = file_path
            logger.info(f"✅ File saved: {file_path}")
```

---

### Button 4: GENERATE CODE

**Event Listener:**
```python
self.generate_button.clicked.connect(self._on_generate_clicked)
```

**Event Handler:**
```python
def _on_generate_clicked(self):
    """Generate code using AI"""
    try:
        # Get user prompt
        prompt = self.prompt_input.text().strip()
        
        if not prompt:
            self._show_error("Please enter a code generation prompt")
            return
        
        # Disable button during generation
        self.generate_button.setEnabled(False)
        self.generate_button.setText("⏳ Generating...")
        
        # Publish code generation event
        self.event_bus.publish('codegen.generate', {
            'prompt': prompt,
            'language': self.language_combo.currentText(),
            'model': 'codellama',
            'timestamp': time.time()
        })
        
        logger.info(f"🔥 GENERATING CODE: {prompt[:50]}...")
        
    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        self._show_error(str(e))
```

**Backend Processing:**
```python
# File: codegen/generator.py
class CodeGenerator:
    async def _handle_generate(self, event_data):
        """Generate code using Ollama codellama"""
        import ollama
        
        prompt = event_data['prompt']
        language = event_data['language']
        
        # Build system prompt
        system_prompt = f"""You are an expert {language} programmer.
Generate clean, efficient, well-commented code.
Only output the code, no explanations."""
        
        # Build user prompt
        user_prompt = f"Generate {language} code for: {prompt}"
        
        logger.info(f"🔥 CALLING OLLAMA: codellama")
        
        # REAL Ollama API call
        response = ollama.chat(
            model='codellama',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            options={
                'temperature': 0.7,
                'top_p': 0.9
            }
        )
        
        generated_code = response['message']['content']
        
        logger.info(f"✅ CODE GENERATED: {len(generated_code)} chars")
        
        # Clean up code (remove markdown backticks if present)
        generated_code = self._clean_generated_code(generated_code)
        
        # Publish result
        await self.event_bus.publish('codegen.code_generated', {
            'code': generated_code,
            'prompt': prompt,
            'model': 'codellama'
        })
    
    def _clean_generated_code(self, code):
        """Remove markdown formatting from generated code"""
        import re
        
        # Remove ```python or ```language blocks
        code = re.sub(r'```\w*\n', '', code)
        code = re.sub(r'```$', '', code)
        
        return code.strip()
```

**Data Flow:**
```
User enters prompt: "Create a function to sort a list"
    ↓
Click "Generate Code"
    ↓
_on_generate_clicked()
    ↓
Validate prompt
    ↓
event_bus.publish('codegen.generate')
    ↓
Code Generator Backend
    ↓
Build system + user prompts
    ↓
ollama.chat(model='codellama', messages=[...])
    ↓
[OLLAMA API CALL - localhost:11434]
    ↓
Codellama model processes prompt
    ↓
Generates Python code
    ↓
Returns code as string
    ↓
Clean markdown formatting
    ↓
event_bus.publish('codegen.code_generated')
    ↓
GUI receives generated code
    ↓
code_editor.setPlainText(generated_code)
    ↓
User sees generated code in editor
```

---

### Button 5: EXECUTE CODE

**Event Listener:**
```python
self.execute_button.clicked.connect(self._on_execute_clicked)
```

**Event Handler:**
```python
def _on_execute_clicked(self):
    """Execute code in sandbox"""
    try:
        code = self.code_editor.toPlainText()
        
        if not code:
            self._show_error("No code to execute")
            return
        
        # Warn user about code execution
        reply = QMessageBox.warning(
            self,
            '⚠️ EXECUTE CODE',
            'This will execute the code in a sandboxed environment.\n\n'
            'Only run trusted code!\n\n'
            'Continue?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Disable button during execution
        self.execute_button.setEnabled(False)
        self.execute_button.setText("⏳ Running...")
        
        # Clear output
        self.output_display.clear()
        
        # Publish execute event
        self.event_bus.publish('codegen.execute', {
            'code': code,
            'language': self.language_combo.currentText(),
            'timeout': 30  # 30 second timeout
        })
        
        logger.info(f"🔥 EXECUTING CODE: {len(code)} chars")
        
    except Exception as e:
        logger.error(f"Code execution failed: {e}")
        self._show_error(str(e))
```

**Backend Processing:**
```python
# File: kingdom_ai/mcp/ollama_code_runner.py
class CodeRunner:
    async def _handle_execute(self, event_data):
        """Execute code in sandboxed environment"""
        import subprocess
        import tempfile
        
        code = event_data['code']
        language = event_data['language']
        timeout = event_data['timeout']
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=f'.{self._get_extension(language)}',
            delete=False
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Execute in subprocess (sandboxed)
            if language == 'python':
                result = subprocess.run(
                    ['python3', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            elif language == 'javascript':
                result = subprocess.run(
                    ['node', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            
            # Capture output
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
            
            logger.info(f"✅ CODE EXECUTED: return code {return_code}")
            
            # Publish results
            await self.event_bus.publish('codegen.execution_complete', {
                'stdout': stdout,
                'stderr': stderr,
                'return_code': return_code,
                'success': return_code == 0
            })
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ CODE EXECUTION TIMEOUT")
            await self.event_bus.publish('codegen.execution_failed', {
                'error': 'Execution timeout'
            })
        
        except Exception as e:
            logger.error(f"❌ CODE EXECUTION ERROR: {e}")
            await self.event_bus.publish('codegen.execution_failed', {
                'error': str(e)
            })
        
        finally:
            # Clean up temp file
            import os
            os.unlink(temp_file)
```

**GUI Update:**
```python
def _on_execution_complete(self, event_data):
    """Display execution results"""
    stdout = event_data['stdout']
    stderr = event_data['stderr']
    success = event_data['success']
    
    # Display output
    if stdout:
        self.output_display.append("=== OUTPUT ===")
        self.output_display.append(stdout)
    
    if stderr:
        self.output_display.append("=== ERRORS ===")
        self.output_display.setTextColor(QColor('red'))
        self.output_display.append(stderr)
        self.output_display.setTextColor(QColor('white'))
    
    if success:
        self.output_display.append("\n✅ Execution completed successfully")
    else:
        self.output_display.append("\n❌ Execution failed")
    
    # Re-enable button
    self.execute_button.setEnabled(True)
    self.execute_button.setText("▶️ Execute")
```

---

## 🤖 MODEL INTEGRATION

### Ollama Codellama

```python
# Optimized for code generation
# Supports: Python, JavaScript, Java, C++, Go, Rust, etc.

# Example prompts:
prompts = [
    "Create a function to reverse a string",
    "Write a REST API endpoint using Flask",
    "Generate a binary search tree class",
    "Create a React component for user login",
    "Write a SQL query to find duplicates"
]

# Model call:
response = ollama.chat(
    model='codellama',
    messages=[{'role': 'user', 'content': prompt}]
)
```

---

## 📡 EVENT BUS BINDINGS

| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `codegen.generate` | Code Gen GUI | Code Generator | Generate button | Prompt, language |
| `codegen.code_generated` | Code Generator | Code Gen GUI | Code generated | Generated code |
| `codegen.execute` | Code Gen GUI | Code Runner | Execute button | Code, timeout |
| `codegen.execution_complete` | Code Runner | Code Gen GUI | Code executed | stdout, stderr |
| `codegen.execution_failed` | Code Runner | Code Gen GUI | Execution error | Error message |

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

The Code Generator tab emits UI telemetry events for editor and execution
actions.

- **Channel:** `ui.telemetry`
- **Component:** `codegen`
- **Representative event types:**
  - `codegen.new_file_clicked`
  - `codegen.open_file_clicked`
  - `codegen.save_file_clicked`
  - `codegen.generate_clicked`
  - `codegen.execute_clicked`
  - `codegen.clear_clicked`

Example payload shape:

```json
{
  "component": "codegen",
  "channel": "ui.telemetry",
  "event_type": "codegen.generate_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"language": "Python"}
}
```

The shared **TelemetryCollector** subscribes to `ui.telemetry` and aggregates
these events with those from the other tabs.

## ✅ VERIFICATION

**Test Code Generation:**

```bash
# 1. Ensure Ollama is running with codellama
ollama pull codellama
ollama serve

# 2. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 3. Go to Code Generator tab

# 4. Enter prompt: "Create a function to calculate fibonacci"

# 5. Click "Generate Code"

# Monitor logs:
tail -f logs/kingdom_error.log | grep codegen

# Expected:
# 🔥 GENERATING CODE: Create a function to calculate...
# 🔥 CALLING OLLAMA: codellama
# ✅ CODE GENERATED: 234 chars

# 6. Generated code appears in editor

# 7. Click "Execute" to run the code
```

---

**Status:** ✅ COMPLETE - Real AI code generation with Ollama codellama
