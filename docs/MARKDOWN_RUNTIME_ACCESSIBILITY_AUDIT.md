# Markdown Runtime Accessibility Audit - Kingdom AI

> **Date:** 2025-12-24  
> **Scope:** Runtime access paths for `docs/*.md` across GUI + core AI subsystems  
> **Goal:** Identify where markdown files are loaded, cached, referenced, or rendered at runtime so Thoth/ChatWidget/Ollama can access them reliably.

---

## 1) Authoritative Runtime Documentation Loaders

### 1.1 `core/system_knowledge_loader.py` (EventBus-driven doc service)

**Role:** Loads and caches documentation from `docs/` and exposes it over the EventBus.

**Runtime paths:**
- **Docs directory root**: `DOCS_PATH = Path(__file__).parent.parent / "docs"`
  - `core/system_knowledge_loader.py:18`
- **Preloaded docs**: `PRIORITY_DOCS = [...]`
  - `core/system_knowledge_loader.py:27-37`
- **Event subscriptions**:
  - `ai.knowledge.request` → `_handle_knowledge_request`
  - `ai.knowledge.list` → `_handle_list_request`
  - `core/system_knowledge_loader.py:47-50`
- **Runtime listing**:
  - `DOCS_PATH.glob("*.md")`
  - `core/system_knowledge_loader.py:145-148`

**How the AI/UI can retrieve docs:**
- Request full docs by name via `ai.knowledge.request` (payload key: `doc_name`).
- Request the doc list via `ai.knowledge.list`.

---

### 1.2 `core/system_context_provider.py` (AI self-awareness context)

**Role:** Injects internal system context into the AI prompt, including key documentation.

**Runtime loads:**
- **Changelog**:
  - `docs/SOTA_2026_CHANGELOG.md`
  - Read path: `core/system_context_provider.py:218-224`
- **Orchestrator docs**:
  - `docs/KINGDOM_BRAIN_ORCHESTRATOR.md`
  - Read path: `core/system_context_provider.py:239-245`

**Context keys populated:**
- `changelog_full`: loaded markdown content
- `orchestrator_docs`: loaded markdown content
  - `core/system_context_provider.py:48-53`

**Prompt references (explicit doc pointers):**
- `docs/SOTA_2026_CHANGELOG.md`
- `docs/KINGDOM_BRAIN_ORCHESTRATOR.md`
  - `core/system_context_provider.py:415-420`

---

### 1.3 `core/biometric_security_manager.py` (security doc access)

**Role:** Exposes biometric security documentation to the brain.

**Runtime load:**
- Doc path stored at init:
  - `self._docs_path = Path("docs/BIOMETRIC_SECURITY_SYSTEM.md")`
  - `core/biometric_security_manager.py:238`
- Read on demand:
  - `with open(self._docs_path, 'r', encoding='utf-8') as f: return f.read()`
  - `core/biometric_security_manager.py:1200-1202`

---

## 2) GUI / Chat Rendering & Local Doc Opening

### 2.1 `gui/qt_frames/chat_widget.py` (markdown rendering + doc context)

**Markdown-to-HTML rendering:**
- `ChatMessageWidget.set_message_content()` converts markdown to HTML:
  - `from markdown import markdown`
  - `from bs4 import BeautifulSoup`
  - `self.content.setHtml(...)`
  - `gui/qt_frames/chat_widget.py:320-331`

**Local file open buttons (open via OS):**
- `QDesktopServices.openUrl(QUrl.fromLocalFile(p))`
  - `gui/qt_frames/chat_widget.py:303-305`

**Changelog context injection for AI:**
- Loads `docs/SOTA_2026_CHANGELOG.md` and extracts the “Quick Reference” block
  - `gui/qt_frames/chat_widget.py:1956-1967`

**Command reference help:**
- When user message is `help`/`commands`, pulls command reference via `SystemKnowledgeLoader`:
  - `from core.system_knowledge_loader import get_command_reference`
  - `help_text = get_command_reference()`
  - `gui/qt_frames/chat_widget.py:1236-1243`

**In-chat doc listing + viewing (SystemKnowledgeLoader-backed):**
- `docs` / `list docs` → list `docs/*.md` files.
- `doc <name>` / `show doc <name>` / `open doc <name>` / `read doc <name>` → display markdown file content from `docs/`.
- `changelog` / `what changed` → display `docs/CHANGELOG_DEC_24_2025.md`.
  - `gui/qt_frames/chat_widget.py:1247-1333`

---

## 3) Prompt-Only Doc References (Not Directly Rendered)

### 3.1 `gui/qt_frames/thoth_qt.py`

**Role:** Adds a system-prompt reference pointing to voice/command docs.

- Mentions `docs/SOTA_2026_MCP_VOICE_COMMANDS.md` in system prompt:
  - `gui/qt_frames/thoth_qt.py:3342-3351`

### 3.2 `core/thoth_live_integration.py`

**Role:** The multi-model orchestration prompt includes a reference to the command doc.

- Mentions `docs/SOTA_2026_MCP_VOICE_COMMANDS.md`:
  - `core/thoth_live_integration.py:303-315`

---

## 4) BrainRouter Selective Documentation Injection

### `kingdom_ai/ai/brain_router.py`

**Role:** Conditionally injects relevant documentation into the AI context.

- If the user prompt indicates BRIO relevance, it loads:
  - `BRIO_VOICE_VISION_INTEGRATION.md`
- If the user prompt indicates “what changed”/changelog relevance, it loads:
  - `CHANGELOG_DEC_24_2025.md`
- If the user prompt explicitly requests documentation, it supports:
  - `doc <name>` / `show doc <name>` / `open doc <name>` / `read doc <name>`
  - `docs` (injects a docs index)
- Retrieval path:
  - `from core.system_knowledge_loader import get_knowledge_loader`
  - `get_full_documentation(...)`
  - `kingdom_ai/ai/brain_router.py` (documentation injection block in `_build_self_aware_prompt`)

---

## 5) Known In-App Documentation UI Gaps

### `gui/kingdom_main_window_qt.py`
- `show_documentation()` is currently log-only:
  - `gui/kingdom_main_window_qt.py:1340-1342`

---

## 6) Runtime Availability Summary (What’s Guaranteed)

- **Guaranteed doc directory discovery**: `SystemKnowledgeLoader.list_available_docs()` scans `docs/*.md`.
- **Guaranteed on-demand doc reads**: `SystemKnowledgeLoader.get_full_documentation(doc_name)` reads from disk if not cached.
- **Guaranteed always-loaded context docs** (via `SystemContextProvider`):
  - `docs/SOTA_2026_CHANGELOG.md`
  - `docs/KINGDOM_BRAIN_ORCHESTRATOR.md`

---

## 7) Docs Added/Updated During This Conversation

- `docs/CHANGELOG_DEC_24_2025.md` updated with additional runtime hotfix notes.
- `docs/TAB_08_APIKEYS_DATAFLOW.md` updated with Dec 2025 runtime fixes.
- `docs/BRIO_VOICE_VISION_INTEGRATION.md` updated with runtime doc accessibility wiring.
- `core/system_knowledge_loader.py` updated to preload key docs so ChatWidget/Ollama can retrieve them via `ai.knowledge.request`.
- `gui/qt_frames/chat_widget.py` updated to support `docs` / `doc <name>` / `changelog` in-chat commands.
- This audit file: `docs/MARKDOWN_RUNTIME_ACCESSIBILITY_AUDIT.md`.
