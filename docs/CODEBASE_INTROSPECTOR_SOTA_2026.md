# CODEBASE INTROSPECTOR - SOTA 2026

## 🎯 OVERVIEW

The Codebase Introspector provides **full codebase access** to the Kingdom AI Chat Widget and Ollama brain, enabling:

- **Source file reading** - Access any `.py`, `.json`, `.md` file
- **AST-based symbol extraction** - Functions, classes, methods with signatures
- **Text search** - Grep-like search across the entire codebase
- **Safe runtime code editing** - Apply edits with automatic backups
- **Repository context generation** - Context packing for LLM consumption

---

## 📚 ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                      KINGDOM AI BRAIN                           │
│                                                                 │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Chat Widget │───▶│ SystemKnowledge  │───▶│  Codebase     │  │
│  │             │    │ Loader           │    │  Introspector │  │
│  └─────────────┘    └──────────────────┘    └───────────────┘  │
│         │                   │                       │          │
│         │                   │                       ▼          │
│         │                   │              ┌───────────────┐   │
│         │                   │              │ File Index    │   │
│         │                   │              │ Symbol Index  │   │
│         ▼                   ▼              │ Edit History  │   │
│  ┌─────────────┐    ┌──────────────────┐  └───────────────┘   │
│  │ Code Gen Tab│    │   EventBus       │          │           │
│  │             │───▶│   Topics         │◀─────────┘           │
│  └─────────────┘    └──────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔌 EVENTBUS TOPICS

### File Access
| Topic | Direction | Payload | Response Topic |
|-------|-----------|---------|----------------|
| `codebase.file.read` | Request | `{file_path, line_start?, line_end?}` | `codebase.file.read.response` |
| `codebase.file.write` | Request | `{file_path, content, create_backup?}` | `codebase.file.write.response` |
| `codebase.file.list` | Request | `{pattern?}` | `codebase.file.list.response` |

### Search
| Topic | Direction | Payload | Response Topic |
|-------|-----------|---------|----------------|
| `codebase.search.text` | Request | `{query, file_pattern?, case_sensitive?}` | `codebase.search.text.response` |
| `codebase.search.symbol` | Request | `{name, symbol_type?}` | `codebase.search.symbol.response` |
| `codebase.search.file` | Request | `{pattern}` | `codebase.search.file.response` |

### Introspection
| Topic | Direction | Payload | Response Topic |
|-------|-----------|---------|----------------|
| `codebase.symbols.get` | Request | `{file_path}` | `codebase.symbols.response` |
| `codebase.context.get` | Request | `{file_path?, focus_files?}` | `codebase.context.response` |
| `codebase.ast.analyze` | Request | `{file_path}` | `codebase.ast.analyze.response` |

### Editing
| Topic | Direction | Payload | Response Topic |
|-------|-----------|---------|----------------|
| `codebase.edit.apply` | Request | `{file_path, old_text, new_text}` | `codebase.edit.apply.response` |
| `codebase.edit.preview` | Request | `{file_path, old_text, new_text}` | `codebase.edit.preview.response` |
| `codebase.edit.rollback` | Request | `{backup_path}` | `codebase.edit.rollback.response` |

### AI Integration (via SystemKnowledgeLoader)
| Topic | Direction | Payload | Response Topic |
|-------|-----------|---------|----------------|
| `ai.source.request` | Request | `{file_path, line_start?, line_end?}` | `ai.source.response` |
| `ai.source.search` | Request | `{query, search_type, file_pattern?}` | `ai.source.search.response` |
| `ai.source.edit` | Request | `{file_path, old_text, new_text, preview_only?}` | `ai.source.edit.response` |
| `ai.context.full` | Request | `{focus_files?}` | `ai.context.full.response` |

---

## 💬 CHAT WIDGET COMMANDS

Users can access the codebase directly via the Chat Widget:

### File Listing
```
list files
list source
source files
codebase files
```

### Status Check
```
codebase status
index status
codebase info
```

### File Reading
```
read file core/event_bus.py
show file gui/tab_manager.py
cat config/settings.json
view file docs/README.md
```

### Text Search
```
search EventBus
grep def __init__
find code async def
search code publish
```

### Symbol Search
```
find function get_knowledge_loader
find class CodebaseIntrospector
find method apply_edit
find symbol PRIORITY_DOCS
```

### Full Context
```
codebase context
repo context
full context
repository context
```

---

## 🛠️ CODE GENERATOR INTEGRATION

The Code Generator tab (`gui/frames/code_generator_qt.py`) has built-in methods for codebase editing:

### Load File
```python
# Load a file from the codebase into the editor
self.load_codebase_file("core/event_bus.py")
self.load_codebase_file("core/event_bus.py", line_start=100, line_end=200)
```

### Apply Edit
```python
# Apply a safe edit with automatic backup
self.apply_codebase_edit(
    file_path="core/event_bus.py",
    old_text="def old_method():",
    new_text="def new_method():"
)
```

### Preview Edit
```python
# Preview edit without applying
diff = self.preview_codebase_edit(
    file_path="core/event_bus.py",
    old_text="old code",
    new_text="new code"
)
print(diff)  # Shows unified diff
```

### Search Codebase
```python
# Search for text
results = self.search_codebase("EventBus", file_pattern="*.py")
for r in results:
    print(f"{r['file_path']}:{r['line_number']}: {r['line_content']}")
```

### Get Context
```python
# Get repository context for LLM
context = self.get_codebase_context(focus_files=["core/event_bus.py"])
```

### Save to Codebase
```python
# Save editor content to codebase with backup
self.save_to_codebase("core/new_module.py")
```

---

## 🔒 SAFETY FEATURES

### Automatic Backups
- Every edit creates a backup in `.kingdom_backups/`
- Backup format: `filename.ext.YYYYMMDD_HHMMSS.bak`
- Rollback available via `codebase.edit.rollback` topic

### Safe Edit Pattern
- **Unique Match Required**: `old_text` must appear exactly once
- **Rejected if**: Multiple matches found (prevents unintended changes)
- **Atomic Operations**: Either succeeds completely or fails with no changes

### Excluded Directories
The introspector automatically excludes:
- `__pycache__`, `.git`, `.venv`, `venv`
- `node_modules`, `.idea`, `.vscode`
- `build`, `dist`, `eggs`, `*.egg-info`
- `backup`, `corrupted_files_backup`
- External projects (Unity Hub, GPT-SoVITS, etc.)

### File Size Limit
- Maximum 10MB per file to prevent memory issues
- Large files are skipped during indexing

---

## 📊 INDEX STRUCTURE

### FileIndex
```python
@dataclass
class FileIndex:
    file_path: str
    relative_path: str
    size_bytes: int
    last_modified: float
    content_hash: str
    language: str  # 'python', 'config', 'text'
    symbols: List[CodeSymbol]
    imports: List[str]
    line_count: int
```

### CodeSymbol
```python
@dataclass
class CodeSymbol:
    name: str
    symbol_type: str  # 'function', 'class', 'method', 'variable'
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str]
    signature: Optional[str]
    parent_class: Optional[str]
    decorators: List[str]
```

---

## 🚀 USAGE EXAMPLES

### From Ollama Brain (via EventBus)
```python
# Request file content
event_bus.publish('ai.source.request', {
    'file_path': 'core/event_bus.py',
    'request_id': 'req_123'
})

# Handle response
def on_source_response(payload):
    if payload['request_id'] == 'req_123':
        content = payload['content']
        # Use content for code generation context
```

### From Code Generator
```python
# Load, edit, and save a file
code_gen.load_codebase_file("core/utils.py")
# ... make changes in editor ...
code_gen.save_to_codebase()  # Saves with backup
```

### From Chat Widget
```
User: search def publish
Thoth AI: ## Search Results for 'def publish'
- core/event_bus.py:145: def publish(self, topic, payload):
- kingdom/event_bus.py:89: def publish(self, event_name, data=None):
...
```

---

## 📁 FILES

| File | Purpose |
|------|---------|
| `core/codebase_introspector.py` | Main introspector implementation |
| `core/system_knowledge_loader.py` | AI integration layer |
| `gui/frames/code_generator_qt.py` | Code Generator with editing methods |
| `gui/qt_frames/chat_widget.py` | Chat commands for codebase access |
| `.kingdom_backups/` | Automatic edit backups |

---

## ✅ STATUS

**Implementation Complete:** December 2025
**SOTA 2026 Features:**
- ✅ Full source file indexing
- ✅ AST-based symbol extraction
- ✅ Text and symbol search
- ✅ Safe runtime code editing with backups
- ✅ Repository context generation for LLMs
- ✅ EventBus integration for AI access
- ✅ Chat Widget commands
- ✅ Code Generator integration

---

**Created:** December 24, 2025
**Version:** 1.0
**Based on:** SOTA 2026 LLM Code Agent Research
