# Digital Twin 3

Scientist classroom digital twin built in phases:

1. Scientist registry
2. RAG engine
3. LLM gateway
4. Memory
5. Context builder
6. FastAPI + LangGraph backend
7. Frontend connection layer
8. React classroom
9. Debate engine
10. Evaluation

## Quick Start

Backend:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn app.main:app --reload
```

From the project root, use offline/backend verification when local installs are blocked:

```powershell
$py = "C:\Users\nayak\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$env:PYTHONDONTWRITEBYTECODE = "1"
& $py scripts\verify_backend.py
```

Frontend:

```powershell
cd frontend
npm install
npm run build
npm run dev
```

From the project root, use static frontend verification when `npm install` is blocked:

```powershell
$py = "C:\Users\nayak\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $py scripts\verify_frontend_static.py
```

Copy `.env.example` to `.env` and add Gemini keys for real model calls. Without keys, the backend returns a grounded local fallback response so the app remains testable.

The frontend uses the Vite proxy by default. Set `VITE_API_BASE_URL=http://127.0.0.1:8000` when serving the built frontend from a different origin.
