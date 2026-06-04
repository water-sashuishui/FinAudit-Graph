from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .service import (
    build_config_status,
    execute_audit,
    query_audit_standards,
    rebuild_rag_index,
    save_uploaded_document,
)

app = FastAPI(
    title="FinAudit-Graph API",
    version="0.1.0",
    description="FastAPI service entry for the FinAudit-Graph audit workflow.",
)


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language query for audit standards.")
    limit: int = Field(5, ge=1, le=10, description="Maximum number of standards to return.")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config/status")
def config_status() -> dict[str, object]:
    return build_config_status()


@app.post("/api/rag/query")
def rag_query(payload: RagQueryRequest) -> dict[str, object]:
    return query_audit_standards(payload.query, payload.limit)


@app.post("/api/rag/rebuild")
def rag_rebuild() -> dict[str, object]:
    return rebuild_rag_index()


@app.post("/api/audit/run")
async def audit_run(
    file: UploadFile | None = File(default=None),
    document_path: str | None = Form(default=None),
    save_report: bool = Form(default=False),
) -> dict[str, object]:
    if file is None and not document_path:
        raise HTTPException(status_code=400, detail="Provide either an uploaded file or a document_path.")

    try:
        if file is not None:
            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            target_path = save_uploaded_document(file.filename or "uploaded_document", file_bytes)
        else:
            target_path = Path(document_path or "")
        return execute_audit(target_path, save_report=save_report)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit execution failed: {exc}") from exc
