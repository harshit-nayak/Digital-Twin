from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend_graph.chat_graph import run_chat
from app.schemas import ChatRequest, ChatResponse

app = FastAPI(title="Digital Twin Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return run_chat(request)

