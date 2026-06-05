from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_if_present(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE pairs without overriding existing environment values."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ProjectSettings:
    """Runtime configuration loaded from environment variables."""

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"
    n8n_webhook_url: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    audit_llm_model: str = "deepseek-chat"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_base_app_token: str = ""
    feishu_table_id: str = ""

    @classmethod
    def from_env(cls) -> "ProjectSettings":
        """从 .env 和系统环境变量创建运行配置。"""
        _load_dotenv_if_present()
        return cls(
            neo4j_uri=os.getenv("NEO4J_URI", cls.neo4j_uri),
            neo4j_username=os.getenv("NEO4J_USERNAME", cls.neo4j_username),
            neo4j_password=os.getenv("NEO4J_PASSWORD", cls.neo4j_password),
            n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL", cls.n8n_webhook_url),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", cls.deepseek_api_key),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", cls.deepseek_base_url),
            audit_llm_model=os.getenv("AUDIT_LLM_MODEL", cls.audit_llm_model),
            feishu_app_id=os.getenv("FEISHU_APP_ID", cls.feishu_app_id),
            feishu_app_secret=os.getenv("FEISHU_APP_SECRET", cls.feishu_app_secret),
            feishu_base_app_token=os.getenv("FEISHU_BASE_APP_TOKEN", cls.feishu_base_app_token),
            feishu_table_id=os.getenv("FEISHU_TABLE_ID", cls.feishu_table_id),
        )
