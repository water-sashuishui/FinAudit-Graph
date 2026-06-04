from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_LORA_FILES = {
    "adapter_model.safetensors",
    "adapter_config.json",
    "artifact_summary.json",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig") as handle:
        return sum(1 for line in handle if line.strip())


def inspect_lora_artifact(artifact_dir: str | Path = "model_artifacts/lora_adapter") -> dict[str, Any]:
    """Summarize the exported LoRA adapter in a presentation-friendly shape."""
    artifact_path = Path(artifact_dir)
    if not artifact_path.exists():
        raise FileNotFoundError(f"LoRA artifact directory not found: {artifact_path}")

    files = sorted(item.name for item in artifact_path.iterdir() if item.is_file())
    missing = sorted(REQUIRED_LORA_FILES.difference(files))
    train_results_path = artifact_path / "train_results.json"
    train_results = _read_json(train_results_path) if train_results_path.exists() else {}

    summary_path = artifact_path / "artifact_summary.json"
    metadata = _read_json(summary_path) if summary_path.exists() else {}

    sft_path = artifact_path / "audit_risk_sft_from_labelstudio_80.jsonl"
    train_samples = int(metadata.get("train_samples") or _count_jsonl(sft_path))
    train_loss = train_results.get("train_loss")

    return {
        "artifact_type": metadata.get("artifact_type", "LoRA adapter"),
        "base_model": metadata.get("base_model", "Qwen2.5-1.5B-Instruct"),
        "finetuning_type": metadata.get("finetuning_type", "LoRA"),
        "train_samples": train_samples,
        "epoch": train_results.get("epoch"),
        "train_loss": round(float(train_loss), 4) if train_loss is not None else None,
        "train_runtime_seconds": train_results.get("train_runtime"),
        "files": files,
        "missing_required_files": missing,
        "path": str(artifact_path),
        "usage_note": (
            "This directory contains a LoRA adapter only. Load it together with "
            "the base model before inference."
        ),
    }
