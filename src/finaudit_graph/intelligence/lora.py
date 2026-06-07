from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..settings import ProjectSettings

REQUIRED_LORA_FILES = {
    "adapter_model.safetensors",
    "adapter_config.json",
    "artifact_summary.json",
}


def _read_json(path: Path) -> dict[str, Any]:
    """读取 LoRA 产物元数据，兼容带 BOM 的 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _module_available(name: str) -> bool:
    """检查可选推理依赖是否安装，用于解释 LoRA 当前不可用原因。"""
    return importlib.util.find_spec(name) is not None


def inspect_lora_artifact(artifact_dir: str | Path = "data/lora_adapter") -> dict[str, Any]:
    """Summarize the exported LoRA adapter in a presentation-friendly shape."""
    artifact_path = Path(artifact_dir)
    if not artifact_path.exists():
        raise FileNotFoundError(f"LoRA artifact directory not found: {artifact_path}")

    files = sorted(item.name for item in artifact_path.iterdir() if item.is_file())
    missing = sorted(REQUIRED_LORA_FILES.difference(files))
    metadata = _read_json(artifact_path / "artifact_summary.json") if (artifact_path / "artifact_summary.json").exists() else {}

    return {
        "artifact_type": metadata.get("artifact_type", "LoRA adapter"),
        "base_model": metadata.get("base_model", "Qwen2.5-1.5B-Instruct"),
        "finetuning_type": metadata.get("finetuning_type", "LoRA"),
        "train_samples": int(metadata.get("train_samples", 0) or 0),
        "files": files,
        "missing_required_files": missing,
        "path": str(artifact_path),
        "usage_note": (
            "This directory contains a LoRA adapter only. Load it together with "
            "the base model before inference."
        ),
    }


def get_lora_runtime_status(
    settings: ProjectSettings | None = None,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """检查 LoRA 风险助手的开关、产物文件、基础模型和依赖是否齐备。"""
    current = settings or ProjectSettings.from_env()
    target_dir = Path(artifact_dir or getattr(current, "lora_artifact_dir", "data/lora_adapter"))

    artifact_exists = target_dir.exists()
    missing_required_files: list[str] = []
    if artifact_exists:
        files = sorted(item.name for item in target_dir.iterdir() if item.is_file())
        missing_required_files = sorted(REQUIRED_LORA_FILES.difference(files))

    torch_available = _module_available("torch")
    transformers_available = _module_available("transformers")
    peft_available = _module_available("peft")
    base_model_path = getattr(current, "lora_base_model_path", "")
    enabled = bool(getattr(current, "enable_lora_risk_assist", False))
    base_model_configured = bool(base_model_path)
    runtime_ready = (
        enabled
        and artifact_exists
        and not missing_required_files
        and torch_available
        and transformers_available
        and peft_available
        and base_model_configured
    )

    if not enabled:
        reason = "LoRA risk assist is disabled."
    elif not artifact_exists:
        reason = f"LoRA artifact directory not found: {target_dir}"
    elif missing_required_files:
        reason = f"Missing required LoRA files: {', '.join(missing_required_files)}"
    elif not base_model_configured:
        reason = "LORA_BASE_MODEL_PATH is not configured."
    elif not torch_available:
        reason = "torch is not installed."
    elif not transformers_available:
        reason = "transformers is not installed."
    elif not peft_available:
        reason = "peft is not installed."
    else:
        reason = "LoRA risk assist is ready."

    return {
        "enabled": enabled,
        "artifact_dir": str(target_dir),
        "artifact_exists": artifact_exists,
        "missing_required_files": missing_required_files,
        "base_model_path": base_model_path,
        "base_model_configured": base_model_configured,
        "torch_available": torch_available,
        "transformers_available": transformers_available,
        "peft_available": peft_available,
        "runtime_ready": runtime_ready,
        "reason": reason,
    }


@lru_cache(maxsize=1)
def _load_lora_generator(base_model_path: str, artifact_dir: str) -> tuple[Any, Any]:
    """加载基础模型和 LoRA adapter；缓存后避免每次请求重复载入大模型。"""
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(base_model_path, trust_remote_code=True)
    model = PeftModel.from_pretrained(model, artifact_dir)
    model.eval()
    return tokenizer, model


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """从模型输出中截取第一个 JSON 对象，兼容模型夹带说明文字的情况。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def run_lora_risk_assistant(
    parsed: dict[str, Any],
    related_parties: list[dict[str, Any]],
    standards: list[dict[str, Any]],
    *,
    settings: ProjectSettings | None = None,
) -> dict[str, Any]:
    """使用 LoRA adapter 做可选的首轮风险识别，失败时返回可解释状态。

    该函数不会抛出推理环境缺失错误，而是把 disabled/failed 状态写入结果，
    方便主审计流程继续走 DeepSeek、LangChain 或本地规则兜底。
    """
    current = settings or ProjectSettings.from_env()
    status = get_lora_runtime_status(current)
    if not status["runtime_ready"]:
        return {"used": False, "provider": "lora_disabled", "risks": [], "status": status}

    try:
        tokenizer, model = _load_lora_generator(
            getattr(current, "lora_base_model_path", ""),
            getattr(current, "lora_artifact_dir", "data/lora_adapter"),
        )
        prompt = (
            "你是财务审计风险分类助手。请根据财务指标、关联方线索和审计准则，"
            "识别 2 到 4 个风险点，并只返回 JSON。"
            '格式必须是 {"risks":[{"risk_type":str,"severity":str,"evidence":str,'
            '"audit_basis":str,"recommendation":str}]}\n\n'
            f"财务指标：{json.dumps(parsed, ensure_ascii=False)}\n"
            f"关联方线索：{json.dumps(related_parties, ensure_ascii=False)}\n"
            f"审计准则：{json.dumps(standards, ensure_ascii=False)}"
        )
        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        data = _extract_json_object(text)
        risks = data.get("risks", []) if isinstance(data, dict) else []
        valid_risks = []
        for risk in risks:
            if not isinstance(risk, dict):
                continue
            if {"risk_type", "severity", "evidence", "audit_basis", "recommendation"}.issubset(risk):
                valid_risks.append(risk)
        return {
            "used": bool(valid_risks),
            "provider": "lora_qwen_risk_assistant",
            "risks": valid_risks,
            "status": status,
        }
    except Exception as exc:
        failure_status = {**status, "runtime_ready": False, "reason": f"LoRA inference failed: {exc}"}
        return {"used": False, "provider": "lora_failed", "risks": [], "status": failure_status}
