# Backend

FastAPI application with a LangGraph-compatible staged flow:

Domain Check -> Memory -> Retrieval -> Rerank -> Context -> Generate -> Memory Save.

The first stable endpoint is `POST /chat`.

