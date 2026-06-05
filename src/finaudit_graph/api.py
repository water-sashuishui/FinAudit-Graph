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

API_TAGS = [
    {
        "name": "系统状态",
        "description": "用于检查服务是否启动成功，以及关键外部配置是否已经就绪。",
    },
    {
        "name": "审计准则检索",
        "description": "用于重建审计准则向量库，以及基于自然语言查询审计依据。",
    },
    {
        "name": "财务审计执行",
        "description": "上传财务材料或指定本地文件路径，执行完整的智能审计流程。",
    },
]

app = FastAPI(
    title="FinAudit-Graph 财务助手接口",
    version="0.1.0",
    description=(
        "这是 FinAudit-Graph 的 FastAPI 服务入口。"
        "系统面向财务审计与合规分析场景，支持材料解析、审计准则 RAG 检索、"
        "风险识别、报告生成以及 N8N dry-run 自动化记录。"
    ),
    openapi_tags=API_TAGS,
)


class RagQueryRequest(BaseModel):
    """审计准则检索请求体。"""

    query: str = Field(
        ...,
        min_length=1,
        title="检索问题",
        description="请输入希望检索的审计问题，例如“收入增长异常需要关注什么风险”。",
    )
    limit: int = Field(
        5,
        ge=1,
        le=10,
        title="返回条数",
        description="最多返回多少条审计准则结果，范围为 1 到 10。",
    )


@app.get(
    "/api/health",
    tags=["系统状态"],
    summary="检查服务状态",
    description="用于确认 FastAPI 服务是否已经正常启动。",
)
def health() -> dict[str, str]:
    """返回最小健康状态，用于负载均衡或启动检查。"""
    return {"status": "ok"}


@app.get(
    "/api/config/status",
    tags=["系统状态"],
    summary="查看配置状态",
    description="返回 DeepSeek、Neo4j、N8N、飞书等关键配置是否已就绪。",
)
def config_status() -> dict[str, object]:
    """返回关键外部服务配置是否可用。"""
    return build_config_status()


@app.post(
    "/api/rag/query",
    tags=["审计准则检索"],
    summary="检索审计准则",
    description="根据自然语言问题查询本地 Chroma 向量库中的审计准则依据。",
)
def rag_query(payload: RagQueryRequest) -> dict[str, object]:
    """执行审计准则 RAG 检索。"""
    return query_audit_standards(payload.query, payload.limit)


@app.post(
    "/api/rag/rebuild",
    tags=["审计准则检索"],
    summary="重建审计准则向量库",
    description="从本地审计准则 JSON 数据源重新构建 Chroma 向量索引。",
)
def rag_rebuild() -> dict[str, object]:
    """重建本地审计准则向量索引。"""
    return rebuild_rag_index()


@app.post(
    "/api/audit/run",
    tags=["财务审计执行"],
    summary="执行财务审计",
    description=(
        "支持两种输入方式：上传财务材料文件，或直接提供本地文件路径。"
        "接口会依次执行材料解析、图谱线索检索、风险识别、报告生成和 N8N dry-run。"
    ),
)
async def audit_run(
    file: UploadFile | None = File(
        default=None,
        description="上传待审计的文件，支持 txt、pdf、docx、xlsx、xls、csv。",
    ),
    document_path: str | None = Form(
        default=None,
        description="如果不上传文件，可以直接填写项目内已有文件的本地路径。",
    ),
    save_report: bool = Form(
        default=False,
        description="是否将审计结果额外保存为 Markdown / DOCX 报告文件。",
    ),
) -> dict[str, object]:
    """接收上传文件或本地路径，触发完整审计流程。"""
    if file is None and not document_path:
        raise HTTPException(status_code=400, detail="请上传文件，或提供 document_path。")

    try:
        if file is not None:
            # 上传文件先落入 data/raw，再复用 document_path 模式的服务层逻辑。
            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="上传文件为空。")
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
        raise HTTPException(status_code=500, detail=f"审计执行失败：{exc}") from exc
