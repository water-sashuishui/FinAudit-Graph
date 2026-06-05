from __future__ import annotations

import json

import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000"
SUPPORTED_TYPES = ["pdf", "docx", "txt", "xlsx", "xls", "csv"]


def build_api_url(path: str) -> str:
    """拼接后端 API 地址，避免页面代码到处重复处理斜杠。"""
    return f"{API_BASE_URL.rstrip('/')}{path}"


st.set_page_config(
    page_title="FinAudit-Graph 财务助手",
    page_icon="FA",
    layout="wide",
)

st.title("FinAudit-Graph 财务助手")
st.caption("上传财务材料后，系统会自动完成解析、风险识别、报告生成和自动化记录。")

uploaded_file = st.file_uploader(
    "上传待审计材料",
    type=SUPPORTED_TYPES,
    help="支持 txt、pdf、docx、xlsx、xls、csv 格式。",
)

run_disabled = uploaded_file is None

if st.button("开始审计分析", type="primary", use_container_width=True, disabled=run_disabled):
    try:
        with st.spinner("正在分析材料，请稍候..."):
            # Streamlit 只负责上传和展示，实际审计流程统一交给 FastAPI 服务层。
            response = requests.post(
                build_api_url("/api/audit/run"),
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type or "application/octet-stream",
                    )
                },
                data={"save_report": "true"},
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

            if payload.get("status") == "blocked_for_review":
                st.warning("材料触发安全拦截，系统已转为人工复核。")
                st.json(payload)
            else:
                left, right = st.columns([2, 1])
                with left:
                    # 报告正文直接使用后端生成的 Markdown，保持 CLI/API/前端展示一致。
                    st.subheader("审计报告")
                    st.markdown(payload.get("final_report_markdown", ""))

                with right:
                    # 右侧保留结构化摘要，便于演示时快速检查状态和报告落盘路径。
                    st.subheader("处理结果")
                    st.json(
                        {
                            "状态": payload.get("status"),
                            "请求编号": payload.get("request_id"),
                            "告警信息": payload.get("warnings", []),
                            "报告文件": payload.get("report_paths"),
                        }
                    )

                st.subheader("风险识别结果")
                st.json(payload.get("audit_risks", []))

                report_text = payload.get("final_report_markdown", "")
                st.download_button(
                    "下载 Markdown 报告",
                    data=report_text,
                    file_name="finaudit_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

                st.download_button(
                    "下载完整结果 JSON",
                    data=json.dumps(payload, ensure_ascii=False, indent=2),
                    file_name="finaudit_result.json",
                    mime="application/json",
                    use_container_width=True,
                )
    except requests.RequestException as exc:
        st.error(f"无法连接到审计服务：{exc}")


if uploaded_file is None:
    st.info("请先上传一份财务材料，再开始审计分析。")
