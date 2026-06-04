from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from finaudit_graph.automation import build_n8n_payload, send_to_n8n
from finaudit_graph.reporting import build_full_report_markdown
from finaudit_graph.workflow import run_demo


st.set_page_config(page_title="FinAudit-Graph", page_icon="FA", layout="wide")

st.title("FinAudit-Graph 智能审计演示")

uploaded_file = st.file_uploader("上传财报、合同或问询函材料", type=["pdf", "docx", "txt", "xlsx", "xls", "csv"])
document_path = "data/raw/demo_annual_report.pdf"

if uploaded_file is not None:
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    save_path = raw_dir / uploaded_file.name
    save_path.write_bytes(uploaded_file.getbuffer())
    document_path = str(save_path)
    st.success(f"已保存上传文件：{uploaded_file.name}")

if st.button("开始审计分析", type="primary"):
    with st.spinner("LangGraph 多智能体正在分析..."):
        result = run_demo(document_path)
        report = build_full_report_markdown(result)
        payload = build_n8n_payload(result)
        n8n_result = send_to_n8n(payload)

    left, right = st.columns([2, 1])
    with left:
        st.subheader("审计报告")
        st.markdown(report)
    with right:
        st.subheader("自动化记录")
        st.json(n8n_result)

    st.download_button(
        "下载 Markdown 审计报告",
        data=report,
        file_name="finaudit_report.md",
        mime="text/markdown",
    )
    st.download_button(
        "下载 N8N Payload",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name="n8n_audit_payload.json",
        mime="application/json",
    )
