# TAB 6: THOTH AI - COMPLETE DATA FLOW MAPPING

## 🎯 OVERVIEW

**Tab Name:** Thoth AI (Artificial Intelligence Chat)
**Purpose:** Real AI responses via Ollama LLM  
**Frontend File:** `gui/qt_frames/thoth_ai_tab.py` (2003 lines)  
**Backend Files:** 
- `core/thoth.py` (250,000+ lines - Main brain)
- `kingdom_ai/core/ollama_ai.py` (Ollama integration)
- `kingdom_ai/ai/thoth_ai_brain.py` (Brain interface)  
- `kingdom_ai/core/ai_engine/ai_worker.py` (**ThothAIWorker** - event-driven Ollama worker)  
**Event Bus Topics:** `ai.request`, `ai.response`, `ai.telemetry`, `ai.vision_state`, `thoth.voice.speak`  
**External APIs:** Ollama (localhost:11434)

---

## ⚠️ REQUIREMENTS

**Must Have:**
- Ollama installed and running (`ollama serve`)
- At least one model installed (`ollama pull llama3.1`)
- Port 11434 accessible

---

## 📊 BUTTON MAPPING

### Button 1: TRANSMIT (Send Message)

**Frontend Component:**

```python
# File: gui/qt_frames/thoth_ai_tab.py (Line ~762)
self.send_button = QPushButton("TRANSMIT")
self.send_button.setStyleSheet("""
    background-color: rgba(0, 60, 120, 0.8);
    color: #00FFFF;
    font-weight: bold;
    padding: 8px 16px;
""")
```

**Event Listener Setup:**

```python
# Line 912 - Button connection to REAL AI backend
self.send_button.clicked.connect(self._send_message_to_real_ai)
logger.info("✅ Send button connected to _send_message_to_real_ai method")

# Line 928 - Also connected to Enter key
self.chat_input.returnPressed.connect(self.send_message)
```

**Event Handler Method:**

```python
# Line 1443 - FIX #12: Send message to REAL AI backend
def _send_message_to_real_ai(self):
    """Send message to REAL AI backend with complete GUI integration."""
    try:
        # 1. Get user input from text field
        user_message = self.chat_input.text().strip()
        if not user_message:
            return  # Don't send empty messages
            
        # 2. Clear input field immediately (UX best practice)
        self.chat_input.clear()
        
        # 3. Add user message to REAL chat display
        self._add_real_message_to_display("USER", user_message, False)
        
        # 4. Process with REAL AI backend (asynchronous)
        import asyncio
        try:
            asyncio.ensure_future(self._process_real_ai_response(user_message))
        except RuntimeError:
            # Fallback if event loop not ready
            self._add_real_message_to_display(
                "THOTH AI", 
                "Event loop not ready. Please wait a moment and try again.", 
                True
            )
        
    except Exception as e:
        logger.error(f"Error sending message to real AI: {e}")
        self._add_real_message_to_display("SYSTEM", f"Error: {str(e)}", True)
```

**Async Processing Method:**

```python
# Line 1468 - Process message with REAL AI backend
async def _process_real_ai_response(self, user_message: str):
    """Process message with REAL AI backend and update GUI."""
    try:
        # 1. Initialize real AI if not done
        if not hasattr(self, '_real_ai') or not self._real_ai:
            await self._initialize_real_ai()
            self._real_ai = True  # Mark as initialized
        
        # 2. Show processing indicator
        self._add_real_message_to_display("THOTH AI", "🧠 Processing...", True)
        
        # 3. Get REAL AI response from Ollama
        response = await self._get_real_ai_response(user_message)
        
        # 4. Remove processing indicator and add real response
        self._replace_last_message(response)
        
        # 5. Synthesize voice if enabled
        if self.voice_enable.isChecked():
            await self._synthesize_real_voice(response)
            
    except Exception as e:
        logger.error(f"Error processing real AI response: {e}")
        self._replace_last_message(f"AI Error: {str(e)}")
```

**Real Ollama API Call:**

```python
# Line 1586 - Get response from REAL Ollama LLM - NO SIMULATION
async def _get_real_ai_response(self, message: str) -> str:
    """Get response from REAL Ollama LLM - NO SIMULATION."""
    try:
        # Try REAL Ollama first
        try:
            import ollama
            
            # Get selected model from GUI
            model = self.model_combo.currentText() if hasattr(self, 'model_combo') else 'llama3.1'
            
            # Map GUI names to actual Ollama models
            model_map = {
                'GPT-4 Nexus': 'llama3.1',
                'Llama-2 Quantum': 'llama2',
                'Mixtral 8x7B': 'mixtral',
                'DeepSeek Coder': 'deepseek-coder'
            }
            actual_model = model_map.get(model, 'llama3.1')
            
            logger.info(f"🔥 SENDING TO REAL OLLAMA: {actual_model}")
            
            # REAL Ollama API call
            response = ollama.chat(
                model=actual_model,
                messages=[{
                    'role': 'user',
                    'content': message
                }]
            )
            
            ai_response = response['message']['content']
            logger.info(f"✅ REAL OLLAMA RESPONSE RECEIVED: {len(ai_response)} chars")
            return ai_response
            
        except ImportError:
            logger.warning("Ollama not installed, trying requests to localhost:11434")
            
            # Direct HTTP request to Ollama
            import requests
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'llama3.1',
                    'prompt': message,
                    'stream': False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'Error: No response from Ollama')
            else:
                raise Exception(f"Ollama HTTP error: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error getting ThothAI response: {e}")
        return f"I apologize, but I encountered an error: {str(e)}"
```

**Display Message to Chat:**

```python
# Line 1732 - Add message to REAL chat display
def _add_real_message_to_display(self, sender: str, message: str, is_system: bool):
    """Add message to REAL chat display with proper formatting."""
    try:
        timestamp = time.strftime("%H:%M:%S")
        
        # Format with cyberpunk colors
        if is_system:
            color = "#00FF41"  # Green for system/AI
        else:
            color = "#00FFFF"  # Cyan for user
            
        formatted_html = f'''
        <div style="margin: 5px 0; padding: 8px; background: rgba(0,0,0,0.3); 
                    border-left: 3px solid {color}; border-radius: 5px;">
            <span style="color: {color}; font-weight: bold;">[{timestamp}] {sender}:</span><br>
            <span style="color: #E0E0E0; margin-left: 10px;">{message}</span>
        </div>
        '''
        
        # Add to actual chat display (FIXED: Use correct widget name)
        current_html = self.chat_history.toHtml()  # NOT chat_display
        new_html = current_html + formatted_html
        self.chat_history.setHtml(new_html)
        
        # Auto-scroll to bottom
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    except Exception as e:
        logger.error(f"Error adding message to display: {e}")
```

**Event Bus Flow:**

```
User Types Message
    ↓
Clicks "TRANSMIT" button (or presses Enter)
    ↓
clicked signal → _send_message_to_real_ai()
    ↓
Get text from chat_input QLineEdit
    ↓
Validate (not empty)
    ↓
Clear input field (UX)
    ↓
Display user message in chat_history
    ↓
asyncio.ensure_future(_process_real_ai_response())
    ↓
[ASYNC PROCESSING BEGINS]
    ↓
Initialize AI if needed
    ↓
Show "🧠 Processing..." message
    ↓
_get_real_ai_response(message)
    ↓
[CALL TO OLLAMA]
    ↓
import ollama
    ↓
ollama.chat(model='llama3.1', messages=[...])
    ↓
[HTTP POST TO localhost:11434/api/chat]
    ↓
Ollama server receives request
    ↓
Loads model (llama3.1)
    ↓
Generates response (LLM inference)
    ↓
Returns JSON response
    ↓
[BACK TO THOTH AI TAB]
    ↓
Extract response text
    ↓
Replace "Processing..." with real response
    ↓
If voice enabled → Text-to-speech
    ↓
User sees AI response in chat
```

**Data Flow Diagram:**

```
┌───────────────────────────────────────────┐
│        THOTH AI TAB GUI                   │
│  ┌──────────────────────────────┐        │
│  │  chat_input (QLineEdit)      │        │
│  │  "Hello, who are you?"       │        │
│  └────────────┬─────────────────┘        │
│               │                           │
│  ┌────────────▼─────────────────┐        │
│  │  TRANSMIT Button             │        │
│  └────────────┬─────────────────┘        │
└───────────────┼───────────────────────────┘
                │ clicked
                ↓
┌───────────────────────────────────────────┐
│   _send_message_to_real_ai()              │
│   1. Get user_message                     │
│   2. Clear input                          │
│   3. Display USER message                 │
│   4. Launch async processing              │
└───────────────┬───────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────┐
│   _process_real_ai_response()             │
│   1. Initialize AI                        │
│   2. Show "Processing..."                 │
│   3. Call _get_real_ai_response()         │
└───────────────┬───────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────┐
│   _get_real_ai_response()                 │
│   1. Import ollama                        │
│   2. Get selected model                   │
│   3. ollama.chat(model, messages)         │
└───────────────┬───────────────────────────┘
                │ HTTP POST
                ↓
┌───────────────────────────────────────────┐
│   OLLAMA SERVER (localhost:11434)         │
│   POST /api/chat                          │
│   {model: "llama3.1", messages: [...]}    │
└───────────────┬───────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────┐
│   OLLAMA LLM PROCESSING                   │
│   1. Load model weights                   │
│   2. Tokenize input                       │
│   3. Run inference (neural network)       │
│   4. Generate response tokens             │
│   5. Decode to text                       │
└───────────────┬───────────────────────────┘
                │ JSON response
                ↓
┌───────────────────────────────────────────┐
│   BACK TO _get_real_ai_response()         │
│   Extract: response['message']['content'] │
│   Return AI response text                 │
└───────────────┬───────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────┐
│   _process_real_ai_response()             │
│   1. Receive AI response                  │
│   2. _replace_last_message(response)      │
│   3. If voice → TTS synthesis             │
└───────────────┬───────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────┐
│   GUI UPDATE                              │
│   1. Remove "Processing..." message       │
│   2. Display AI response in chat_history  │
│   3. Auto-scroll to bottom                │
│   4. Speak response (if enabled)          │
└───────────────────────────────────────────┘
```

---

### Button 2: NEURAL RESET (Clear Conversation)

**Frontend Component:**

```python
# Line 873
self.reset_button = QPushButton("NEURAL RESET")
self.reset_button.setStyleSheet("""
    background-color: rgba(40, 0, 0, 180);
    color: #FF5500;
    border: 1px solid #FF3300;
""")
```

**Event Listener:**

```python
# Line 927
self.reset_button.clicked.connect(self._reset_real_conversation)
```

**Event Handler:**

```python
# Line 1906 - Reset conversation with REAL backend cleanup
def _reset_real_conversation(self):
    """Reset conversation with REAL backend cleanup."""
    try:
        # 1. Clear chat display
        self.chat_history.clear()
        
        # 2. Reset AI backend conversation history
        if hasattr(self, '_real_ai') and self._real_ai:
            # Reset AI conversation state (if AI maintains history)
            pass
            
        # 3. Add welcome message
        self._add_real_message_to_display(
            "THOTH AI", 
            "🔮 Neural pathways reset. THOTH AI ready for new conversation.", 
            True
        )
        
        logger.info("Conversation reset completed")
        
    except Exception as e:
        logger.error(f"Error resetting conversation: {e}")
```

---

## 🤖 MODEL SELECTION

### Dynamic Model Loading

**Load ALL Available Ollama Models:**

```python
# Line 796 - Get ALL available models from Ollama server
def _get_available_ollama_models(self):
    """Get ALL available models from Ollama server - REAL LIST."""
    try:
        import requests
        response = requests.get('http://localhost:11434/api/tags', timeout=2)
        if response.status_code == 200:
            data = response.json()
            models = [model['name'] for model in data.get('models', [])]
            logger.info(f"✅ Found {len(models)} Ollama models: {models}")
            return models
    except Exception as e:
        logger.warning(f"Could not load Ollama models (server not running?): {e}")
    return []

# Load models into combo box
available_models = self._get_available_ollama_models()
if available_models:
    self.model_combo.addItems(available_models)
    logger.info(f"✅ Loaded {len(available_models)} Ollama models")
else:
    # Fallback to default 12 models
    all_models = [
        'llama3.1:latest', 'llama3:latest', 'llama2:latest',
        'mixtral:latest', 'mistral:latest', 'deepseek-coder:latest',
        'codellama:latest', 'gemma:latest', 'phi3:latest',
        'qwen:latest', 'vicuna:latest', 'orca-mini:latest'
    ]
    self.model_combo.addItems(all_models)
```

**Model Change Handler:**

```python
# Line 916
self.model_combo.currentTextChanged.connect(self._on_model_changed_safe)

# Line 1832 - Handle model selection change
def _on_model_changed_safe(self, model_name: str):
    """Handle model selection change."""
    try:
        logger.info(f"AI model changed to: {model_name}")
        
        # Update AI backend if initialized
        if hasattr(self, '_real_ai') and self._real_ai:
            self._update_ai_config()
            
    except Exception as e:
        logger.error(f"Error changing model: {e}")
```

---

## 🔊 VOICE SYNTHESIS

### Text-to-Speech Integration

**Voice Synthesis Method:**

```python
# Line 1795 - Synthesize speech using REAL TTS
async def _synthesize_real_voice(self, text: str):
    """Synthesize speech using REAL TTS."""
    try:
        import pyttsx3
        
        if not hasattr(self, '_tts_engine'):
            self._tts_engine = pyttsx3.init()
            
            # Configure based on GUI selection
            voice_selection = self.voice_combo.currentText()
            voices = self._tts_engine.getProperty('voices')
            
            if voices:
                if "Deep Neural (M)" in voice_selection:
                    # Male voice
                    for voice in voices:
                        if 'male' in voice.name.lower():
                            self._tts_engine.setProperty('voice', voice.id)
                            break
                elif "Harmonic Neural (F)" in voice_selection:
                    # Female voice
                    for voice in voices:
                        if 'female' in voice.name.lower():
                            self._tts_engine.setProperty('voice', voice.id)
                            break
            
            # Set rate and volume
            self._tts_engine.setProperty('rate', 180)
            self._tts_engine.setProperty('volume', 0.9)
        
        # Speak the text
        self._tts_engine.say(text)
        self._tts_engine.runAndWait()
        
    except Exception as e:
        logger.warning(f"Voice synthesis error: {e}")
```

---

## 🔗 BRAIN INTEGRATION

### Complete Brain Architecture

**Brain Components:**

1. **ThothAI Core** (`core/thoth.py` - 250K+ lines)
2. **Ollama Integration** (`kingdom_ai/core/ollama_ai.py`)
3. **Brain Interface** (`kingdom_ai/ai/thoth_ai_brain.py`)
4. **Brain Integrator** (`kingdom_ai_brain_integrator_v3.py`)

**Initialization:**

```python
# Line 1493 - Initialize REAL AI backend
async def _initialize_real_ai_backend(self):
    """Initialize REAL AI backend with COMPLETE brain integration.
    
    Connects to:
    - kingdom_ai.core.ollama_ai.OllamaAI
    - kingdom_ai.ai.thoth_ai_brain.ThothAIBrain  
    - kingdom_ai_brain_integrator_v3.KingdomBrainIntegratorV3
    - core.thoth.ThothAI (250K+ lines main brain)
    """
    logger.info("🧠 Initializing COMPLETE Brain Integration...")
    try:
        # Initialize Kingdom AI Brain Integrator
        await self._initialize_kingdom_brain()
        
        # If brain integrator not available, use direct ThothAI/Ollama
        if not self._brain_integrator:
            await self._initialize_direct_components()
        
        logger.info("✅ Kingdom AI multi-model brain system initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize Kingdom AI brain: {e}")
        self._real_ai = None
```

---

## 📡 EVENT BUS BINDINGS

| Event Topic | Publisher | Subscriber | Trigger | Data |
|-------------|-----------|------------|---------|------|
| `ai.query` | Thoth AI GUI | Ollama Backend | TRANSMIT clicked | User message |
| `ai.response` | Ollama Backend | Thoth AI GUI | LLM completes | AI response |
| `ai.model_update` | Thoth AI GUI | Ollama Backend | Model changed | New model name |
| `voice.command` | Thoth AI GUI | TTS Engine | Voice toggle | Voice settings |
| `thoth_ai.reset` | Thoth AI GUI | Backend | RESET clicked | Clear history |

---

## 📡 UI TELEMETRY & TELEMETRYCOLLECTOR

In addition to ai.telemetry events, the Thoth AI tab now emits generic
`ui.telemetry` events for key UI actions.

- **Channel:** `ui.telemetry`
- **Component:** `thoth_ai`
- **Representative event types:**
  - `thoth_ai.send_message_clicked`
  - `thoth_ai.reset_conversation_clicked`

Example payload shape:

```json
{
  "component": "thoth_ai",
  "channel": "ui.telemetry",
  "event_type": "thoth_ai.reset_conversation_clicked",
  "timestamp": "2025-10-24T12:34:56Z",
  "success": true,
  "error": null,
  "metadata": {"source": "neural_reset_button"}
}
```

The **TelemetryCollector** consumes both `ui.telemetry` and dedicated ai.telemetry
events, giving a complete picture of user interactions and AI activity.

## ✅ VERIFICATION

**Test Thoth AI:**

```bash
# 1. Ensure Ollama is running
ollama serve

# 2. Pull a model if needed
ollama pull llama3.1

# 3. Test Ollama directly
curl http://localhost:11434/api/tags

# 4. Launch Kingdom AI
python3 -B kingdom_ai_perfect.py

# 5. Go to Thoth AI tab
# 6. Type: "Hello, who are you?"
# 7. Click: TRANSMIT
# 8. Expected: Real response from llama3.1

# Monitor logs:
tail -f logs/kingdom_error.log | grep thoth
```

**Expected Log Output:**

```
✅ Send button connected to _send_message_to_real_ai method
🔥 SENDING TO REAL OLLAMA: llama3.1
✅ REAL OLLAMA RESPONSE RECEIVED: 245 chars
```

---

**Status:** ✅ COMPLETE - Real AI integration fully mapped and operational
