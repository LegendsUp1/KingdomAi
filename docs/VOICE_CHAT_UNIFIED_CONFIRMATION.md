# Voice System + Chat + Unified Systems – CONFIRMED

**Status:** Voice is wired with chat and the unified AI pipeline. This document confirms the flow and subscriptions.

---

## 1. Unified pipeline (chat → AI → response → chat + voice)

```
User types/speaks in Chat
    → ai.request (request_id, prompt, model)
    → UnifiedAIRouter / BrainRouter
    → Ollama (or ThothLiveIntegration)
    → ai.response / ai.response.unified
    → Chat: message added to chat_widget
    → voice.speak (or thoth.voice.speak): user HEARS the response
```

- **Chat → AI:** ThothQt/ChatWidget publishes `ai.request` on send (and voice input publishes after `voice.transcription`).
- **Unified routing:** `initialize_unified_router(event_bus)` and BrainRouter ensure all `ai.request` events go through the same path; responses are deduplicated as `ai.response.unified`.
- **Response → Chat:** ThothQt subscribes to `ai.response.unified`; ChatWidget adds the message to the chat UI.
- **Response → Voice:** On `ai.response.unified`, ThothQtWidget publishes `voice.speak` with the response text (and greeting path publishes `voice.speak` for the welcome message). So chat and voice are in sync.

---

## 2. Voice system subscriptions (authoritative handler)

**core.voice_manager.VoiceManager** (registered as `voice_manager` on event_bus):

- Subscribes via **subscribe_sync** to:
  - `voice.speak` → `on_speak` (TTS)
  - `voice.speak.delta` → `on_speak_delta`
  - `voice.speak.flush` → `on_speak_flush`
  - `thoth.voice.speak` → `on_speak`
  - `voice.listen` → `on_listen` (STT)
  - `voice.stop` → `on_stop_sync`
  - `voice.set_voice` → `on_set_voice_sync`
  - `system.shutdown` → `on_shutdown_sync`

- When `event_bus.voice_speak_authority == "legacy"`, VoiceManager **skips** handling `voice.speak` so the legacy handler in `kingdom_ai_perfect` is the one that actually speaks (Windows pyttsx3 / PowerShell SAPI / XTTS). So there is a single effective TTS path; no double speech.

**kingdom_ai_perfect.py** (during voice init):

- Sets `event_bus.voice_speak_authority = "legacy"`.
- Subscribes `handle_voice_speak` to:
  - `thoth.voice.speak`
  - `voice.speak`
- `handle_voice_speak` runs TTS (pyttsx3 on Windows, PowerShell SAPI from WSL, or KingdomVoiceBrainService/XTTS).

Result: Every `voice.speak` / `thoth.voice.speak` is handled by either VoiceManager or the legacy handler; chat and unified AI both drive the same voice path.

---

## 3. Chat ↔ voice integration

| Direction | Mechanism |
|-----------|-----------|
| **Chat → Voice (AI reply)** | ThothQt subscribes to `ai.response.unified` → publishes `voice.speak` with response text. Greeting path publishes `voice.speak` for welcome. |
| **Voice → Chat (user input)** | User pushes mic → `voice.listen` → VoiceManager STT → publishes `voice.transcription` → ThothQt subscribes to `voice.transcription` and can auto-send to AI (same as typing in chat). |
| **Chat display** | ChatWidget subscribes to `ai.response.unified` and adds the assistant message; no duplicate add from ThothQtWidget (comment in code: "ChatWidget will display"). |

So: chat send and voice send both go through `ai.request`; AI replies go to both chat (display) and voice (speak).

---

## 4. Unified systems involved

- **BrainRouter** – registered as `brain_router`; handles brain-side routing.
- **UnifiedAIRouter** – `initialize_unified_router(event_bus)`; bridges `ai.request` to brain and produces deduplicated `ai.response.unified`.
- **VoiceManager** – registered as `voice_manager`; subscribes to `voice.speak`, `thoth.voice.speak`, `voice.listen`, `voice.stop` (and defers to legacy TTS when `voice_speak_authority == "legacy"`).
- **ThothQt / ChatWidget** – publish `ai.request`; subscribe to `ai.response.unified`, `chat.message.add`, `voice.transcription`; publish `voice.speak` for AI replies and greeting.

---

## 5. Confirmation summary

| Item | Status |
|------|--------|
| Voice system subscribes to `voice.speak` and `thoth.voice.speak` | Yes (VoiceManager + legacy handler; one active via authority) |
| Chat sends via `ai.request` | Yes (ThothQt send_message / voice → AI) |
| AI response → chat display | Yes (`ai.response.unified` → ChatWidget) |
| AI response → voice (TTS) | Yes (`ai.response.unified` → ThothQtWidget publishes `voice.speak`) |
| Unified pipeline (ai.request → brain → ai.response.unified) | Yes (UnifiedAIRouter, BrainRouter) |
| Voice input → chat/AI | Yes (`voice.listen` → VoiceManager → `voice.transcription` → ThothQt can send to AI) |

**The voice system is wired to work with chat and the unified systems.**  
Responses from the unified AI pipeline are shown in chat and spoken via `voice.speak`; voice input can be sent into the same chat/AI flow via `voice.transcription`.
