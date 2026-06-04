from __future__ import annotations

import json
from pathlib import Path

import requests
import streamlit as st

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_DOCUMENT_PATH = "showcase/demo_inputs/test_audit.txt"
SUPPORTED_TYPES = ["pdf", "docx", "txt", "xlsx", "xls", "csv"]


def build_api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


st.set_page_config(page_title="FinAudit-Graph Demo", page_icon="FA", layout="wide")
st.title("FinAudit-Graph 智能审计演示")
st.caption("当前页面作为演示前端，所有审计能力由 FastAPI 提供。")

api_base_url = st.text_input("FastAPI 地址", value=DEFAULT_API_BASE_URL)
uploaded_file = st.file_uploader("上传财报、合同或问询函材料", type=SUPPORTED_TYPES)
document_path = st.text_input("或填写本地文件路径", value=DEFAULT_DOCUMENT_PATH)
save_report = st.checkbox("同时保存报告到 outputs/", value=False)

if st.button("开始审计分析", type="primary"):
    try:
        with st.spinner("正在调用 FastAPI 审计服务..."):
            if uploaded_file is not None:
                response = requests.post(
                    build_api_url(api_base_url, "/api/audit/run"),
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type or "application/octet-stream",
                        )
                    },
                    data={"save_report": str(save_report).lower()},
                    timeout=120,
                )
            else:
                response = requests.post(
                    build_api_url(api_base_url, "/api/audit/run"),
                    data={
                        "document_path": document_path,
                        "save_report": str(save_report).lower(),
                    },
                    timeout=120,
                )

        if response.status_code != 200:
            st.error(f"请求失败：HTTP {response.status_code}")
            try:
                st.json(response.json())
            except ValueError:
                st.code(response.text)
        else:
            payload = response.json()
            left, right = st.columns([2, 1])
            with left:
                st.subheader("审计报告")
                st.markdown(payload.get("final_report_markdown", ""))
            with right:
                st.subheader("自动化记录")
                st.json(payload.get("n8n_result", {}))

            st.subheader("结构化结果")
            st.json(
                {
                    "request_id": payload.get("request_id"),
                    "status": payload.get("status"),
                    "parsed_financial_data": payload.get("parsed_financial_data", {}),
                    "related_parties": payload.get("related_parties", []),
                    "audit_risks": payload.get("audit_risks", []),
                    "warnings": payload.get("warnings", []),
                    "report_paths": payload.get("report_paths"),
                }
            )

            report_text = payload.get("final_report_markdown", "")
            st.download_button(
                "下载 Markdown 审计报告",
                data=report_text,
                file_name="finaudit_report.md",
                mime="text/markdown",
            )
            st.download_button(
                "下载完整 API 返回",
                data=json.dumps(payload, ensure_ascii=False, indent=2),
                file_name="finaudit_api_response.json",
                mime="application/json",
            )
    except requests.RequestException as exc:
        st.error(f"无法连接 FastAPI 服务：{exc}")


if st.checkbox("查看 API 健康状态"):
    try:
        health_response = requests.get(build_api_url(api_base_url, "/api/health"), timeout=10)
        config_response = requests.get(build_api_url(api_base_url, "/api/config/status"), timeout=10)
        st.write("健康检查：", health_response.status_code, health_response.json())
        st.write("配置状态：")
        st.json(config_response.json())
    except requests.RequestException as exc:
        st.warning(f"健康检查失败：{exc}")


st.caption(
    "建议先启动 FastAPI：`python -m uvicorn finaudit_graph.api:app --reload`，"
    "再运行本页面：`python -m streamlit run apps/streamlit_app.py`。"
)
