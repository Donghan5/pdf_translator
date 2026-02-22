# Easy PDF Translator — MVP Milestones

> Roadmap to transform the current local-model prototype into the Groq API + C++ VectorDB architecture described in `claude.md`.

---

## Current State Assessment

| Component | Status | Gap |
|---|---|---|
| PDF/TXT parsing (`parse.py`) | Exists | Chunking uses fixed char count — needs sentence-boundary rewrite |
| Translation (`translate.py`) | Exists | Uses local NLLB model — must switch to Groq API |
| Config (`config.py`) | Exists | Hardcoded for NLLB — needs `.env` + Groq config |
| Process (`process.py`) | Exists | No VectorDB integration, no RAG flow |
| CLI (`main.py`) | Exists | No progress bar, no ETA, no RAG QA mode |
| C++ VectorDB server | Missing | Entire `cpp_server/` directory not yet created |
| IPC client (`client.py`) | Missing | No Python ↔ C++ communication layer |
| RAG QA (`rag.py`) | Missing | No retrieval or QA logic |
| `.env` | Missing | No environment variable management |

---

## Milestone 0 — Project Scaffolding & Config Migration
**Goal**: Establish the new project structure and config system without breaking anything.

- [ ] Create `.env` file with all variables from claude.md Section 9
- [ ] Rewrite `config.py` to load from `.env` via `python-dotenv`
  - Groq API key, model names, server host/port, chunk settings, default languages
  - Remove NLLB-specific config (`MODEL_NAME`, `LOCAL_MODEL_PATH`, NLLB language codes)
  - Keep `SUPPORTED_LANGUAGES` as simple `{ "en": "English", "ko": "Korean", ... }` mapping
- [ ] Update `requirements.txt`: remove `transformers`, `torch`, `sentencepiece`; add `groq`, `nltk`
- [ ] Create empty directory structure: `cpp_server/`, `input/`, `output/`, `processed/`
- [ ] Add `.env` to `.gitignore`

**Deliverables**: Config loads from `.env`, old NLLB dependencies removed.

---

## Milestone 1 — Smart Chunking (parse.py rewrite)
**Goal**: Implement sentence-boundary-aware chunking per claude.md Section 4.

- [ ] Replace `split_into_chunks()` with sentence-boundary logic
  - Use `nltk.sent_tokenize()` for sentence detection
  - Paragraph-first splitting on `\n\n`
  - Target 1500 tokens per chunk (use word-count heuristic: ~1 token per 0.75 words)
  - 1–2 sentence overlap between consecutive chunks
  - Skip pages/sections with < 50 characters
- [ ] Generate chunk metadata dict per claude.md spec:
  ```
  chunk_id, doc_id, filename, page_start, page_end,
  chunk_index, total_chunks, char_count, original_text
  ```
- [ ] Refactor `extract_text_from_pdf()` to return per-page text (needed for page tracking in metadata)

**Deliverables**: `parse.py` produces metadata-enriched chunks. No fixed-char splitting.

---

## Milestone 2 — Groq API Translation (translate.py rewrite)
**Goal**: Replace local NLLB model with Groq API calls.

- [ ] Remove all `torch`/`transformers` imports and model loading logic
- [ ] Implement `translate_chunk()` using the `groq` Python SDK
  - Use prompt template from claude.md Section 5
  - `temperature=0`
  - Dynamic `max_tokens = input_tokens * 1.5`
  - Model: `llama-3.1-8b-instant` (from config)
- [ ] Implement rate-limit handling
  - 0.5s delay between requests
  - Exponential backoff on 429 (1s → 2s → 4s, max 3 retries)
  - Skip chunk on final failure, log it, continue
- [ ] Update `UsageTracker` for API token counting (input/output/cost)
- [ ] `translate_text()` returns list of `(chunk_metadata, translated_text)` pairs

**Deliverables**: Translation works end-to-end via Groq API. Failed chunks are skipped, not fatal.

---

## Milestone 3 — C++ VectorDB Server (cpp_server/)
**Goal**: Build a minimal C++ server that stores vectors and handles similarity search over Unix socket.

### 3a — Embedding & VectorDB Core
- [ ] `embedder.hpp/.cpp` — Lightweight text-to-vector embedding
  - Simple TF-IDF or bag-of-words for MVP (full model like MiniLM can come later)
  - `std::vector<float> embed(const std::string& text)`
- [ ] `vector_db.hpp/.cpp` — In-memory vector storage + cosine similarity search
  - `void store(chunk_id, doc_id, text, metadata, vector)`
  - `vector<Result> search(query_vector, top_k, doc_id_filter)`
  - Brute-force cosine similarity is fine for MVP

### 3b — IPC Socket Server
- [ ] `server.hpp/.cpp` — Unix socket JSON server
  - Listen on configurable port (default 50051)
  - Accept JSON requests matching claude.md Section 6 schema:
    - `"action": "store"` — vectorize text, store with metadata
    - `"action": "search"` — vectorize query, return top-k results
  - Return JSON responses: `{ "status": "ok", "results": [...] }`
- [ ] `main.cpp` — Server entry point, parse args, start listener
- [ ] `CMakeLists.txt` — Build configuration (C++17, nlohmann/json dependency)

**Deliverables**: `cpp_server` binary that accepts store/search over Unix socket. Can be tested with `socat` or `nc`.

---

## Milestone 4 — Python ↔ C++ IPC Client (client.py)
**Goal**: Python client that communicates with the C++ server.

- [ ] Implement `CppClient` class
  - `connect()` — Connect to Unix socket, verify server is alive
  - `store_chunk(chunk_id, doc_id, text, metadata)` → send store request, handle response
  - `search(query, top_k, doc_id)` → send search request, return results
  - `is_alive()` → health check
- [ ] Handle connection errors gracefully
  - Detect server not running at startup
  - Print clear instructions: "Start cpp_server first: `./cpp_server/build/server`"
- [ ] JSON serialization/deserialization matching claude.md Section 6 schema

**Deliverables**: `client.py` can store and retrieve chunks from the running C++ server.

---

## Milestone 5 — Pipeline Integration (process.py rewrite)
**Goal**: Wire together parse → vectorize/store → translate → update in VectorDB.

- [ ] Rewrite `process_pdf()` and `process_txt()` to follow Flow 1:
  1. Parse file → chunks with metadata
  2. Store each chunk in C++ VectorDB (original text + metadata)
  3. Translate each chunk via Groq API
  4. Update VectorDB with translated text
  5. Save final output file
- [ ] Non-blocking errors: vectorize failure logs & continues, translation failure skips & continues
- [ ] Track per-file stats: chunks total, translated, skipped, elapsed time

**Deliverables**: Full Flow 1 works end-to-end. Data lives in both output files and VectorDB.

---

## Milestone 6 — RAG QA Mode (rag.py)
**Goal**: Implement Flow 2 — retrieval-augmented QA over stored documents.

- [ ] Implement `ask_question(query, doc_id, client)`:
  1. Send search request to C++ server (top 5 chunks)
  2. Build RAG prompt from claude.md Section 5 template
  3. Call Groq API with `llama-3.3-70b-versatile` model
  4. Return answer + source page numbers
- [ ] Handle edge cases:
  - No search results → "No relevant content found. Please rephrase your question."
  - Empty query → re-prompt
  - `q` / `quit` → exit RAG mode

**Deliverables**: `rag.py` provides working QA over previously translated documents.

---

## Milestone 7 — CLI Polish (main.py rewrite)
**Goal**: Implement the full CLI UX from claude.md Section 7.

- [ ] Startup banner with version, model info, server status
- [ ] Server connection check at startup (fail fast with instructions)
- [ ] Language selection with defaults (Enter to accept)
- [ ] File discovery with page counts displayed
- [ ] Real-time progress bar with ETA per file
- [ ] ANSI color output (green=success, red=error, yellow=warning)
- [ ] Summary report after all files: success/fail counts, token usage, elapsed time
- [ ] Post-translation prompt: "Enter RAG QA mode? [Y/n]"
- [ ] RAG QA interactive loop (from Milestone 6)

**Deliverables**: CLI matches the UX spec in claude.md Section 7. Full interactive experience.

---

## MVP Definition of Done

All of the following must work in sequence:

```
1. Start cpp_server          → Server listening on port 50051
2. python main.py            → Banner shows, server connected
3. Select languages          → en → ko (or any pair)
4. Drop PDF in input/        → File detected, pages counted
5. Translation runs          → Progress bar, chunks translated via Groq API
6. Output saved              → Translated file in output/, original moved to processed/
7. Data stored in VectorDB   → Chunks retrievable via search
8. Enter RAG QA mode         → Ask questions about the translated document
9. Get AI answers            → Answers cite source pages
```

---

## Milestone Dependency Graph

```
M0 (Scaffolding)
 ├── M1 (Chunking)
 │    └── M2 (Groq Translation)
 │         └── M5 (Pipeline Integration) ← requires M4
 │              └── M7 (CLI Polish) ← requires M6
 ├── M3 (C++ Server)
 │    └── M4 (IPC Client)
 │         └── M5 (Pipeline Integration)
 └── M6 (RAG QA) ← requires M4
      └── M7 (CLI Polish)
```

**Parallel tracks after M0:**
- Track A: M1 → M2 (Python-side translation pipeline)
- Track B: M3 → M4 (C++ server + IPC client)
- Merge at M5, then M6 and M7 sequentially.

---

## Estimated Complexity

| Milestone | Files Touched | New Files | Complexity |
|---|---|---|---|
| M0 — Scaffolding | `config.py`, `requirements.txt`, `.gitignore` | `.env` | Low |
| M1 — Chunking | `parse.py` | — | Medium |
| M2 — Groq Translation | `translate.py` | — | Medium |
| M3 — C++ Server | — | 7 files in `cpp_server/` | High |
| M4 — IPC Client | — | `client.py` | Medium |
| M5 — Pipeline Integration | `process.py` | — | Medium |
| M6 — RAG QA | — | `rag.py` | Medium |
| M7 — CLI Polish | `main.py` | — | Medium |
