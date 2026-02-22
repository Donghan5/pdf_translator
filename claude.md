# Easy PDF Translator — claude.md

> This file is the project context document for AI-assisted refactoring.
> Always follow the principles in this document when generating, modifying, or reviewing code.

---

## 1. Project Overview

A CLI application that parses PDF/TXT files → chunks → translates them via Groq API, and stores all data in a C++ VectorDB server.
Beyond translation, the system supports RAG-based QA over stored documents.

### Two Core Flows

```
[Flow 1] Translator Flow (Data Ingestion)
  Parse File → C++ Service (Vectorize & Store) → Groq API (Translation) → Result Formatting → Final Result
                     ↓ Fail                            ↓ Fail
              Vectorize Error (Log & Continue)    API Error (Retry / Skip)
                     ↓
               Vector DB (Storage)

[Flow 2] RAG Flow (Retrieval & QA)
  User Query → C++ Service (Vectorize & Search) → Context Injection (Prompt) → Groq API → AI Response
                     ↓ Fail
              Search Error (Ask Rephrase)
```

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| CLI / Orchestration | Python 3.11+ | Main entry point, UX handling |
| PDF Parsing | Python (`pdfplumber`) | Text extraction only |
| Translation / QA Model | Groq API | `llama-3.1-8b-instant` or `mixtral-8x7b` |
| Vectorization & Search | C++ (`cpp_server`) | Embedding, VectorDB management, IPC |
| VectorDB | Built-in C++ | Stores and retrieves all chunk data |
| IPC Communication | Unix Socket or gRPC | Python ↔ C++ server |

---

## 3. Project Directory Structure

```
PDF_Translator_App/
├── claude.md                  # This file
├── main.py                    # CLI entry point
├── config.py                  # Environment variables and constants
├── parse.py                   # PDF/TXT parsing and chunking
├── translate.py               # Groq API translation logic
├── rag.py                     # RAG QA logic
├── client.py                  # Python client for C++ server communication
├── process.py                 # Flow 1 & 2 orchestration
├── requirements.txt
├── .env                       # GROQ_API_KEY etc.
│
├── cpp_server/                # C++ VectorDB server
│   ├── main.cpp
│   ├── vector_db.hpp/.cpp     # VectorDB implementation
│   ├── embedder.hpp/.cpp      # Text embedding
│   ├── server.hpp/.cpp        # IPC socket server
│   └── CMakeLists.txt
│
├── input/                     # Source files to translate
├── output/                    # Translation results
└── processed/                 # Completed originals
```

---

## 4. Chunking Strategy (Critical)

> Must handle PDFs with 100+ pages reliably. Semantically meaningful chunking with minimal token waste is the top priority.

### Chunking Principles

1. **Paragraph-first splitting**: Split on `\n\n` boundaries first
2. **Sentence boundary preservation**: Never cut a chunk mid-sentence
3. **Overlap**: Include the last 1–2 sentences of the previous chunk at the start of the next to preserve context
4. **Chunk size**: Target `1500 tokens` (balanced for Groq API quality vs. cost)
5. **Skip empty / image pages**: Exclude pages with fewer than 50 characters from chunking

### Chunk Metadata (Required when storing to VectorDB)

```python
{
    "chunk_id": "doc_abc123_chunk_0042",
    "doc_id": "doc_abc123",
    "filename": "report.pdf",
    "page_start": 10,
    "page_end": 11,
    "chunk_index": 42,
    "total_chunks": 210,
    "char_count": 1200,
    "original_text": "...",
    "translated_text": "..."  # Updated after translation
}
```

### Forbidden Approaches

- Splitting purely by fixed character count (`len()`) → **Prohibited**
- Splitting by page boundary directly → **Prohibited** (page breaks often fall mid-sentence)

---

## 5. Groq API Usage Principles (Token Efficiency)

### Translation Prompt Template

```
Translate the following text from {source_lang} to {target_lang}.
Output only the translated text, no explanations.

Text:
{chunk_text}
```

> - Keep system prompts minimal to save tokens
> - "Output only the translated text" must be explicit — eliminates unnecessary preamble
> - Fix `temperature=0` (translation requires no creativity)
> - Set `max_tokens` dynamically: `input_tokens * 1.5`

### RAG QA Prompt Template

```
Answer the question based only on the provided context.
If the answer is not in the context, say "I don't know."

Context:
{retrieved_chunks}

Question: {user_query}
```

### Model Selection

| Use Case | Model | Reason |
|---|---|---|
| Translation (speed priority) | `llama-3.1-8b-instant` | Fast and cheap |
| RAG QA (quality priority) | `llama-3.3-70b-versatile` | Better reasoning |
| Fallback | `mixtral-8x7b-32768` | Large context window |

### Rate Limit Handling

- Apply a `0.5s` delay between chunk requests by default
- On 429 error: exponential backoff (1s → 2s → 4s, max 3 retries)
- If all retries fail: skip the chunk, log it, and continue with the rest

---

## 6. C++ Server (cpp_server) Interface

### Python → C++ Communication Spec (JSON over Unix Socket)

**Store chunk request**
```json
{
  "action": "store",
  "chunk_id": "doc_abc123_chunk_0042",
  "doc_id": "doc_abc123",
  "text": "...",
  "metadata": { "page_start": 10, "filename": "report.pdf" }
}
```

**Similarity search request**
```json
{
  "action": "search",
  "query": "...",
  "top_k": 5,
  "doc_id": "doc_abc123"
}
```

**Response format**
```json
{
  "status": "ok",
  "results": [
    { "chunk_id": "...", "score": 0.92, "text": "..." }
  ]
}
```

### C++ Server Responsibilities

- Generate text embeddings (lightweight model recommended, e.g., `all-MiniLM-L6-v2` level)
- Index vectors and perform cosine similarity search
- Store original text, translated text, and chunk metadata
- Handle IPC requests from the Python client

---

## 7. CLI UX Design

### Default Execution Flow

```
$ python main.py

============================================================
   Easy PDF Translator v2.0
   Model: Groq API (llama-3.1-8b-instant)
============================================================
✓ cpp_server connected (port: 50051)
✓ Directories ready: input/ output/ processed/

📋 Supported Languages: en, ko, ja, zh, fr, de, es, ...
🌐 Source [en] → Target [ko]  (Press Enter for defaults)
   Source:
   Target:

📚 Found 3 file(s):
   [1] annual_report_2024.pdf  (142 pages)
   [2] manual_en.pdf           (38 pages)
   [3] notes.txt

▶ Start translation? [Y/n]:

------------------------------------------------------------
[1/3] annual_report_2024.pdf
   Extracting... 142 pages, 284,300 chars
   Chunking...   198 chunks created
   Progress: ████████████░░░░░░░░  62/198 chunks  [ETA: 2m 14s]
------------------------------------------------------------
```

### UX Rules

1. **Real-time progress**: Show per-chunk progress bar + ETA
2. **Non-blocking errors**: Mark failed chunks as `[SKIP]` and continue
3. **Mode selection**: After translation, ask whether to enter RAG QA mode
4. **RAG QA mode**: Exit with `q` or `quit`; re-prompt on empty input
5. **Color output**: Use ANSI codes — green for success, red for errors, yellow for warnings
6. **Summary report**: Print success/failure count, token usage, and elapsed time after all files are processed

### RAG QA Interface

```
============================================================
   RAG QA Mode
   Document: annual_report_2024.pdf
   Type 'q' to quit
============================================================

❓ Question: What was the revenue growth rate in 2024?

   🔍 Searching relevant chunks... (top 5)
   💬 Generating answer...

   📄 Answer:
   Revenue grew by 12.3% year-over-year in 2024, driven by...

   📌 Source pages: 23, 47, 89

❓ Question:
```

---

## 8. Error Handling Strategy

| Situation | Response |
|---|---|
| C++ server connection failure | Detect at startup, print instructions to start server, then exit |
| Vectorize failure | Log the error, skip the chunk, continue translation |
| Groq API error (4xx) | Exponential backoff with 3 retries, skip on final failure |
| Groq API rate limit (429) | Auto-wait and retry |
| PDF image-only page | Skip if text < 50 chars, log page numbers |
| No search results | Print: "No relevant content found. Please rephrase your question." |

---

## 9. Environment Variables (.env)

```env
GROQ_API_KEY=gsk_...
GROQ_MODEL_TRANSLATE=llama-3.1-8b-instant
GROQ_MODEL_QA=llama-3.3-70b-versatile
CPP_SERVER_HOST=localhost
CPP_SERVER_PORT=50051
CHUNK_TOKEN_SIZE=1500
CHUNK_OVERLAP_SENTENCES=2
DEFAULT_SOURCE_LANG=en
DEFAULT_TARGET_LANG=ko
```

---

## 10. Sub-Agent Routing Rules

> Claude Code uses this section to decide which sub-agent handles each task.
> The Lead Agent reads CLAUDE.md, interprets the task, and delegates automatically.
> Do NOT spawn a sub-agent for tasks that can be done in a single file edit.

---

### Agent Roster

| Agent | Alias | Owns |
|---|---|---|
| Lead Agent | `@lead` | Architecture decisions, interface contracts, cross-domain coordination |
| Python Agent | `@python` | All `.py` files in project root |
| C++ Agent | `@cpp` | Everything inside `cpp_server/` |

---

### Routing Decision Tree

```
Is the task cross-domain (touches both Python and C++)?
    YES → @lead handles interface contract first, then delegates to @python and @cpp in parallel
    NO  → route directly to the owning agent (see Domain Ownership below)

Is it a pure read/analysis task (no file edits)?
    YES → @lead handles it alone, no sub-agent needed (saves tokens)

Is it a single-file edit under 50 lines?
    YES → @lead handles it directly, no sub-agent needed (saves tokens)
```

---

### Domain Ownership (Hard Rules)

**@python agent owns — never touch these in @cpp:**
```
main.py
config.py
parse.py
translate.py
rag.py
client.py
process.py
requirements.txt
.env
```

**@cpp agent owns — never touch these in @python:**
```
cpp_server/main.cpp
cpp_server/vector_db.hpp
cpp_server/vector_db.cpp
cpp_server/embedder.hpp
cpp_server/embedder.cpp
cpp_server/server.hpp
cpp_server/server.cpp
cpp_server/CMakeLists.txt
```

**@lead owns — interface contracts between the two domains:**
```
IPC message schema (JSON spec in Section 6)
claude.md (this file)
Directory structure decisions
```

---

### Spawn Conditions (When to Use Sub-Agents)

Spawn `@python` when:
- Modifying chunking logic in `parse.py`
- Changing Groq API call patterns in `translate.py`
- Updating RAG retrieval logic in `rag.py`
- Refactoring CLI UX in `main.py`
- Adding new language support in `config.py`

Spawn `@cpp` when:
- Modifying VectorDB storage or indexing logic
- Changing embedding generation
- Updating IPC socket server behavior
- Optimizing cosine similarity search
- Modifying CMakeLists.txt build config

Spawn **both in parallel** when:
- Changing the IPC JSON schema (both sides must update simultaneously)
- Adding a new action type to the Python ↔ C++ interface
- Performance profiling across the full pipeline

---

### Sub-Agent Invocation Protocol

Every sub-agent dispatch from @lead MUST include these four components:

```
1. SCOPE      — Exact files the agent is allowed to touch
2. TASK       — Specific, unambiguous description of what to implement
3. CONSTRAINT — Rules from CLAUDE.md the agent must follow (link the section)
4. OUTPUT     — Expected deliverable (file changed, function added, etc.)
```

**Example — spawning @python for chunking refactor:**
```
SCOPE:      parse.py only
TASK:       Refactor split_into_chunks() to use sentence-boundary detection
            instead of fixed character count. Use nltk.sent_tokenize().
CONSTRAINT: See CLAUDE.md Section 4 — chunk size target 1500 tokens,
            overlap of 1-2 sentences, never split mid-sentence.
OUTPUT:     Updated split_into_chunks() with unit test stubs in parse.py
```

**Example — spawning @cpp for VectorDB store action:**
```
SCOPE:      cpp_server/vector_db.cpp, cpp_server/vector_db.hpp only
TASK:       Implement store() method that accepts chunk_id, text, and
            metadata JSON, generates embedding, and indexes the vector.
CONSTRAINT: See CLAUDE.md Section 6 — input JSON schema must match exactly.
            No external dependencies beyond what's in CMakeLists.txt.
OUTPUT:     store() method implemented and callable from server.cpp
```

---

### Parallel vs Sequential Rules

| Situation | Execution |
|---|---|
| @python and @cpp tasks are independent | Spawn in **parallel** |
| @cpp must finish before @python calls it | Spawn **sequentially** (@cpp first) |
| Interface contract is ambiguous | @lead resolves first, then parallel spawn |
| Single domain, single file | No sub-agent, @lead handles directly |

---

### Token Efficiency Rules for Sub-Agents

- Pass only the **relevant file contents** to each sub-agent, not the entire codebase
- Sub-agents must **not re-read CLAUDE.md** — @lead extracts only the relevant sections and passes them inline
- If a sub-agent task can be completed in under 20 lines of code, @lead does it directly
- After each sub-agent completes, @lead discards the sub-agent context immediately

---

## 11. Anti-Patterns (Never Do These)

- Including unnecessary explanations, examples, or greetings in prompts → **Token waste**
- Splitting chunks by fixed character count only → **Destroys sentence and semantic boundaries**
- Aborting the entire process on a single chunk failure → **Fatal for 100+ page PDFs**
- Running translation without the C++ server → **RAG becomes unavailable, data is lost**
- Saving translation results only to file, not to VectorDB → **Violates the architecture**
- Using a fixed `max_tokens` value → **Wastes tokens on short chunks**
- Spawning a sub-agent for a single-file, small edit → **Unnecessary token overhead**
- Passing the entire codebase to a sub-agent → **Token waste; pass only relevant files**
- Letting @python touch `cpp_server/` or @cpp touch `.py` files → **Domain boundary violation**
- Spawning sub-agents without all 4 components (scope, task, constraint, output) → **Leads to wasted work**
- Running @python and @cpp sequentially when they can go in parallel → **Slower with no benefit**