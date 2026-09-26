# 🤖 Changayi — Chrome Extension

> Ask questions about any webpage you're reading, powered by a full Retrieval-Augmented Generation (RAG) pipeline.

A production-quality Chrome Extension that extracts content from the current webpage, stores it in a local vector database, and lets you have a contextual AI conversation about it — all grounded in what the page actually says.

Built as a portfolio-quality project demonstrating modern **GenAI engineering** and **full-stack product development**.

---

## ✨ Features

- **Page-aware AI** — answers are grounded in the webpage you're reading, not general knowledge
- **Streaming responses** — Gemini's answer appears token-by-token, like a human typing
- **Markdown rendering** — bold, italic, code blocks, bullet lists, and headings rendered natively
- **Dark mode** — one-click toggle with full theme support
- **SPA navigation detection** — automatically re-indexes when you navigate in single-page apps (React, Next.js, etc.)
- **Source cards** — see exactly which page chunks contributed to each answer
- **Starter prompts** — clickable suggestions when you first open the panel
- **Shadow DOM isolation** — the extension UI never interferes with the page's own styles
- **Floating assistant button** — stays accessible while you read, opens a polished chat panel

---

## 🏗️ Architecture

```
                    🌐 WEBPAGE
                       │
                       ▼
             Chrome Extension
             React + TypeScript
                       │
              Extract page text
              (content script)
                       │
                       ▼
                    FastAPI
                       │
          ┌────────────┴────────────┐
          │                         │
       Cleaning                  Chunking
    (remove noise)        (LangChain RecursiveCharacterTextSplitter)
          │                         │
          └────────────┬────────────┘
                       │
                       ▼
             HuggingFace Embeddings
          (sentence-transformers/all-MiniLM-L6-v2)
                       │
                       ▼
                    ChromaDB
               (temporary, per-page)
                       │
                 User Question
                       │
                       ▼
              Question Embedding
                       │
                       ▼
               Similarity Search
               (cosine distance)
                       │
                       ▼
              Relevant Page Chunks
               (top-k=4 results)
                       │
                       ▼
                  RAG Prompt
          (system + context + question)
                       │
                       ▼
              Gemini 1.5 Flash
           (streaming via SSE)
                       │
                       ▼
             FastAPI → React UI
          (token-by-token rendering)
```

**Technology stack:**

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| Chrome Extension | Manifest V3, Content Scripts, Shadow DOM |
| Backend | Python, FastAPI, Pydantic |
| RAG Framework | LangChain |
| Embeddings | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` |
| Vector Database | ChromaDB (in-memory, temporary) |
| LLM | Google Gemini 1.5 Flash |
| Streaming | Server-Sent Events (SSE) |

---

## 📁 Project Structure

```
RAG/
├── backend/
│   ├── .env                        # API keys (never committed)
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 # FastAPI app, CORS, route registration
│       ├── config.py               # Settings loaded from .env
│       ├── models/
│       │   └── schemas.py          # Pydantic request/response models
│       ├── api/routes/
│       │   ├── health.py           # GET  /api/health
│       │   ├── page.py             # POST /api/page/index
│       │   └── chat.py             # POST /api/chat  +  POST /api/chat/stream
│       └── services/
│           ├── cleaner.py          # Strip scripts, ads, nav, boilerplate
│           ├── chunker.py          # LangChain RecursiveCharacterTextSplitter
│           ├── embedder.py         # HuggingFace sentence-transformer
│           ├── vector_store.py     # ChromaDB read/write
│           ├── rag_service.py      # index_page() + retrieve()
│           ├── llm_service.py      # generate_answer() + generate_answer_stream()
│           └── chat_service.py     # Orchestrates retrieve → generate
│
├── extension/
│   ├── manifest.json               # Chrome Extension Manifest V3
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── content.tsx             # Content script: mounts React, extracts page, handles SPA nav
│       ├── App.tsx                 # Floating ✨ Ask AI button with status states
│       ├── components/
│       │   └── ChatPanel.tsx       # Full chat UI (dark mode, markdown, streaming)
│       ├── services/
│       │   └── api.ts              # All FastAPI communication (fetch + SSE stream)
│       ├── store/
│       │   └── indexingState.ts    # Pub/sub state: idle → indexing → ready → error
│       ├── types/
│       │   └── index.ts            # TypeScript interfaces for all data shapes
│       └── utils/
│           ├── extractor.ts        # DOM-based text extraction
│           └── session.ts          # URL → stable session ID (hash of origin+pathname)
│
├── .env.example                    # Template for required environment variables
└── .gitignore
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **Google Chrome** (or any Chromium browser)
- A free **Gemini API key** from [Google AI Studio](https://aistudio.google.com/app/apikey)

---

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd RAG
```

---

### 2. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate       # macOS/Linux
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt
```

Create your `.env` file (copy from the example):

```bash
cp ../.env.example .env
```

Open `.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your_actual_key_here
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`. Visit `http://127.0.0.1:8000/docs` to see the interactive Swagger documentation.

> **First run note:** HuggingFace will download the embedding model (`all-MiniLM-L6-v2`, ~90 MB) on first startup. This is cached locally — subsequent starts are instant.

---

### 3. Chrome Extension setup

```bash
cd extension

# Install dependencies
npm install

# Build the extension
npm run build
```

This produces a `dist/` folder.

**Load the extension in Chrome:**

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** (toggle, top-right)
3. Click **Load unpacked**
4. Select the `extension/dist/` folder
5. The **✨ Ask AI** button should now appear on any webpage

> After making code changes, run `npm run build` again, then click the ↺ refresh icon on the extension card at `chrome://extensions`.

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Your Google Gemini API key |
| `CHROMA_PERSIST_DIR` | ❌ | Path for ChromaDB storage (defaults to in-memory) |
| `EMBEDDING_MODEL` | ❌ | HuggingFace model name (default: `all-MiniLM-L6-v2`) |
| `CHUNK_SIZE` | ❌ | Characters per chunk (default: `800`) |
| `CHUNK_OVERLAP` | ❌ | Overlap between chunks (default: `100`) |

**Security rule:** API keys live exclusively in `backend/.env`. They are never in any frontend code, browser storage, or version control.

---

## 🔌 API Reference

All endpoints are prefixed with `/api`.

### `GET /api/health`

Verifies the backend is running.

```json
{ "status": "ok", "version": "0.8.0" }
```

---

### `POST /api/page/index`

Receives webpage content, runs the full indexing pipeline (clean → chunk → embed → store), and returns the session ID.

**Request:**
```json
{
  "session_id": "page-a3f8c2",
  "url": "https://example.com/article",
  "title": "My Article",
  "content": "The raw extracted page text..."
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "page-a3f8c2",
  "chunks_created": 14,
  "message": "Indexed 14 chunks",
  "url": "https://example.com/article"
}
```

---

### `POST /api/chat`

Runs the full RAG pipeline and returns the complete answer as one JSON response (non-streaming).

**Request:**
```json
{
  "session_id": "page-a3f8c2",
  "question": "What is the main argument of this article?"
}
```

**Response:**
```json
{
  "session_id": "page-a3f8c2",
  "question": "What is the main argument of this article?",
  "answer": "The article argues that...",
  "sources": [
    { "content": "...chunk text...", "chunk_index": 2 },
    { "content": "...chunk text...", "chunk_index": 7 }
  ]
}
```

---

### `POST /api/chat/stream`

Same as `/api/chat` but streams the response via **Server-Sent Events (SSE)**.

**Request:** Same as `/api/chat`

**Response stream** (`Content-Type: text/event-stream`):

```
data: {"type":"sources","sources":[{"content":"...","chunk_index":2}]}

data: {"type":"chunk","text":"The article "}

data: {"type":"chunk","text":"argues that "}

data: {"type":"chunk","text":"retrieval-augmented generation..."}

data: {"type":"done"}
```

---

## 🧠 How RAG Works

### The core problem

Large language models have a training cutoff and no knowledge of the specific webpage you're reading. Asking Gemini "what does this page say?" without context will produce a hallucinated answer.

### The RAG solution

Instead of asking Gemini to know the answer, we retrieve the relevant parts of the page and show them to Gemini as part of the question.

```
User asks: "What are the installation steps?"
              │
              ▼
Embed the question → [0.12, -0.43, 0.77, ...]
              │
              ▼
Search ChromaDB for similar vectors
(finds chunks about "installation", "setup", "steps")
              │
              ▼
Build prompt:
  "You are a helpful assistant. Answer using only this context:
   [Chunk 3: Installation requires Python 3.10...]
   [Chunk 7: Run pip install -r requirements.txt...]
   Question: What are the installation steps?"
              │
              ▼
Gemini generates a grounded, accurate answer
```

### Why chunking?

A typical webpage contains 5,000–50,000 characters. Embedding the whole page as one vector loses specificity — a question about "installation steps" would match equally against all page content. Splitting into ~800-character chunks with 100-character overlap gives the vector search precision: it finds the *specific sections* that are relevant to the question.

### Why embeddings?

Embeddings convert text into numerical vectors where semantic similarity corresponds to geometric proximity. "How do I install?" and "Installation steps" produce vectors that are close together in embedding space, even though they share no words. This is what makes the retrieval step work across paraphrasing and synonyms.

---

## 🔄 Development Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Foundation — project structure, Vite + FastAPI scaffold | ✅ |
| 2 | RAG Backend — cleaning, chunking, HuggingFace embeddings, ChromaDB | ✅ |
| 3 | Gemini — RAG prompt, answer generation, error handling | ✅ |
| 4 | Chrome Extension — Manifest V3, content script, Shadow DOM isolation | ✅ |
| 5 | Chat UI — floating button, chat panel, starter prompts, source cards | ✅ |
| 6 | Full Integration — end-to-end pipeline, SPA navigation detection | ✅ |
| 7 | UI/UX Polish — dark mode, markdown rendering, animations | ✅ |
| 8 | Streaming — SSE backend, client-side stream reader, progressive rendering | ✅ |

---

## 🛠️ Common Issues

**The ✨ Ask AI button doesn't appear**
- Make sure the backend is running at `http://127.0.0.1:8000`
- Check the extension is loaded at `chrome://extensions` with no errors
- Some pages (Chrome Web Store, `chrome://` pages) block content scripts by design

**Extension shows "Analyzing…" indefinitely**
- Open DevTools → Console (on the page, not the extension popup) and look for errors
- The backend health check at `/api/health` should return `200 OK`

**"Page hasn't been analyzed yet" response**
- The `session_id` in the chat request must match the one used during indexing
- This usually means the page changed URL since indexing — refresh the page

**Streaming gives a `RuntimeError: StopIteration` error**
- Fixed in the codebase. If you see it, ensure you have the latest `chat.py` with the `_DONE` sentinel pattern

**HuggingFace model download is slow**
- The `all-MiniLM-L6-v2` model (~90 MB) is downloaded once on first startup
- Set `SENTENCE_TRANSFORMERS_HOME` in your environment to cache it in a preferred directory

**CORS errors in the browser console**
- The backend has `allow_origins=["*"]` for local development
- If deploying, restrict this to your extension's origin

---

## 🔐 Security Notes

- **API keys never touch the frontend.** The Gemini key lives only in `backend/.env`.
- **`.env` is in `.gitignore`** — it will never be committed.
- **ChromaDB is temporary and local.** No page content leaves your machine (except to Gemini's API).
- For production deployment, add authentication to the FastAPI endpoints and restrict CORS.

---

## 🚧 Potential Enhancements

- **OpenAI as an alternative LLM** — the LLM service is isolated; swapping providers means editing one file
- **Persistent sessions** — store ChromaDB collections on disk to survive backend restarts
- **Multi-tab awareness** — track multiple pages simultaneously across browser tabs
- **Conversation history** — include previous turns in the RAG prompt for follow-up questions
- **PDF and file support** — extend extraction beyond webpages to uploaded documents
- **WebSocket streaming** — upgrade from SSE to WebSocket for bidirectional communication

---

## 📄 License

MIT — free to use, modify, and distribute.

---

*Built with React + TypeScript + Vite · FastAPI · LangChain · HuggingFace · ChromaDB · Gemini*

