# Project Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep only the files required to run, test, and demonstrate FinAudit-Graph in the project root, and move all process artifacts into `archive/project_cleanup_2026-06-04/`.

**Architecture:** Preserve the runnable Python package, Streamlit entrypoint, minimal data fixtures, LoRA adapter artifact, README, dependency files, and tests. Move generated outputs, planning/defense docs, Label Studio process data, old configs, helper scripts, and evidence files into a dated archive subtree. No files are deleted.

**Tech Stack:** PowerShell `Move-Item`, Python CLI validation, `unittest`, Streamlit app source, FinAudit-Graph package.

---

## File Classification

### Keep In Root

These files and directories are required for local running, testing, or basic project explanation:

- `.env`
- `.env.example`
- `.gitignore`
- `README.md`
- `pyproject.toml`
- `requirements.txt`
- `apps/streamlit_app.py`
- `src/finaudit_graph/**`
- `tests/test_workflow.py`
- `data/raw/.gitkeep`
- `data/raw/test_audit.txt`
- `data/raw/sample_financial_data.xlsx`
- `data/raw/sample_financial_data.csv`
- `data/graph/related_parties.json`
- `data/graph/init_neo4j.cypher`
- `data/rag/audit_standards.json`
- `data/rag/vector_store.json`
- `model_artifacts/lora_adapter/adapter_config.json`
- `model_artifacts/lora_adapter/adapter_model.safetensors`
- `model_artifacts/lora_adapter/artifact_summary.json`
- `outputs/.gitkeep`

### Move To Archive

These are useful evidence or process files, but not required for the app to run:

- `docs/architecture.md`
- `docs/day2_labeling_and_finetune.md`
- `docs/day4_graph_and_rag.md`
- `docs/day5_streamlit_n8n.md`
- `docs/day6_reporting_and_integration.md`
- `docs/day7_defense_package.md`
- `docs/defense_package/**`
- `docs/label_studio_import.md`
- `docs/labelstudio_to_sft.md`
- `docs/mvp_usage.md`
- `docs/project_status.md`
- `configs/llama_factory/finaudit_lora_demo.yaml`
- `scripts/convert_labelstudio_to_sft.py`
- `scripts/generate_audit_samples.py`
- `data/labeling/**`
- `data/processed/**`
- `model_artifacts/lora_adapter/audit_risk_sft_from_labelstudio_80.jsonl`
- `model_artifacts/lora_adapter/cloud_training_notes.md`
- `model_artifacts/lora_adapter/dataset_info.json`
- `model_artifacts/lora_adapter/finaudit_lora_demo.yaml`
- `model_artifacts/lora_adapter/trainer_log.jsonl`
- `model_artifacts/lora_adapter/train_results.json`
- `model_artifacts/lora_adapter/training_loss.png`
- `outputs/*.md`
- `outputs/*.docx`
- `outputs/defense_presentation/**`
- Existing `archive/legacy_*`, `archive/labelstudio_exports`, and `archive/planning_docs` stay inside `archive/`.

---

### Task 1: Create Archive Structure

**Files:**
- Create directories under `archive/project_cleanup_2026-06-04/`

- [ ] **Step 1: Create archive directories**

Run:

```powershell
New-Item -ItemType Directory -Force -Path `
  archive/project_cleanup_2026-06-04/docs,`
  archive/project_cleanup_2026-06-04/outputs,`
  archive/project_cleanup_2026-06-04/training_materials,`
  archive/project_cleanup_2026-06-04/scripts,`
  archive/project_cleanup_2026-06-04/configs,`
  archive/project_cleanup_2026-06-04/data | Out-Null
```

Expected: directories exist and no files are moved yet.

### Task 2: Move Non-Runtime Docs

**Files:**
- Move selected docs from `docs/` to `archive/project_cleanup_2026-06-04/docs/`
- Keep `docs/superpowers/plans/2026-06-04-project-cleanup.md` until cleanup is complete

- [ ] **Step 1: Move documentation artifacts**

Run:

```powershell
$target = "archive/project_cleanup_2026-06-04/docs"
$paths = @(
  "docs/architecture.md",
  "docs/day2_labeling_and_finetune.md",
  "docs/day4_graph_and_rag.md",
  "docs/day5_streamlit_n8n.md",
  "docs/day6_reporting_and_integration.md",
  "docs/day7_defense_package.md",
  "docs/defense_package",
  "docs/label_studio_import.md",
  "docs/labelstudio_to_sft.md",
  "docs/mvp_usage.md",
  "docs/project_status.md"
)
foreach ($path in $paths) {
  if (Test-Path $path) {
    Move-Item -LiteralPath $path -Destination $target
  }
}
```

Expected: root `docs/` contains only `docs/superpowers/plans/2026-06-04-project-cleanup.md`, or can be archived at the final step if the user wants an ultra-minimal root.

### Task 3: Move Training And Labeling Materials

**Files:**
- Move non-runtime Label Studio data and LoRA training logs to `archive/project_cleanup_2026-06-04/training_materials/`

- [ ] **Step 1: Move Label Studio and processed datasets**

Run:

```powershell
$target = "archive/project_cleanup_2026-06-04/training_materials"
$paths = @(
  "data/labeling",
  "data/processed",
  "model_artifacts/lora_adapter/audit_risk_sft_from_labelstudio_80.jsonl",
  "model_artifacts/lora_adapter/cloud_training_notes.md",
  "model_artifacts/lora_adapter/dataset_info.json",
  "model_artifacts/lora_adapter/finaudit_lora_demo.yaml",
  "model_artifacts/lora_adapter/trainer_log.jsonl",
  "model_artifacts/lora_adapter/train_results.json",
  "model_artifacts/lora_adapter/training_loss.png"
)
foreach ($path in $paths) {
  if (Test-Path $path) {
    Move-Item -LiteralPath $path -Destination $target
  }
}
```

Expected: `model_artifacts/lora_adapter/` keeps only the adapter files and summary needed by `--lora-summary`.

### Task 4: Move Scripts And Configs

**Files:**
- Move generation/conversion scripts and LLaMA Factory config to archive

- [ ] **Step 1: Move helper scripts and old config**

Run:

```powershell
if (Test-Path "scripts") {
  Move-Item -LiteralPath "scripts" -Destination "archive/project_cleanup_2026-06-04/scripts"
}
if (Test-Path "configs") {
  Move-Item -LiteralPath "configs" -Destination "archive/project_cleanup_2026-06-04/configs"
}
```

Expected: root no longer has `scripts/` or `configs/`.

### Task 5: Move Generated Outputs

**Files:**
- Move generated reports and PPT output to `archive/project_cleanup_2026-06-04/outputs/`
- Recreate `outputs/.gitkeep`

- [ ] **Step 1: Move generated output files**

Run:

```powershell
$target = "archive/project_cleanup_2026-06-04/outputs"
Get-ChildItem -Path outputs -Force | Where-Object { $_.Name -ne ".gitkeep" } | ForEach-Object {
  Move-Item -LiteralPath $_.FullName -Destination $target
}
if (-not (Test-Path "outputs/.gitkeep")) {
  New-Item -ItemType File -Force -Path "outputs/.gitkeep" | Out-Null
}
```

Expected: root `outputs/` contains only `.gitkeep`.

### Task 6: Update README Structure Section

**Files:**
- Modify `README.md`

- [ ] **Step 1: Update README project tree**

Replace the tree section with:

```text
FinAudit-Graph/
├─ apps/
│  └─ streamlit_app.py
├─ archive/
│  └─ project_cleanup_2026-06-04/
├─ data/
│  ├─ graph/
│  ├─ rag/
│  └─ raw/
├─ model_artifacts/
│  └─ lora_adapter/
├─ outputs/
├─ src/
│  └─ finaudit_graph/
├─ tests/
│  └─ test_workflow.py
├─ README.md
├─ pyproject.toml
└─ requirements.txt
```

Also add a short note:

```markdown
过程材料、旧报告、训练日志、Label Studio 导出、答辩包装材料和辅助脚本已统一移动到 `archive/project_cleanup_2026-06-04/`。
```

Expected: README matches the cleaned root layout.

### Task 7: Verify Runtime

**Files:**
- No edits unless verification exposes missing runtime files

- [ ] **Step 1: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe tests\test_workflow.py
```

Expected:

```text
Ran 19 tests
OK
```

- [ ] **Step 2: Verify CLI demo with Excel sample**

Run:

```powershell
$env:DEEPSEEK_API_KEY=""
$env:NEO4J_PASSWORD="password"
.\.venv\Scripts\python.exe -m finaudit_graph --demo --document data/raw/sample_financial_data.xlsx --save-report
```

Expected:

```text
企业名称：星河智能制造有限公司
Saved Markdown report: outputs\sample_financial_data_audit_report.md
```

If the command generates reports, move those generated reports back into `archive/project_cleanup_2026-06-04/outputs/` and leave `outputs/.gitkeep`.

- [ ] **Step 3: Verify Streamlit source imports**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile apps\streamlit_app.py src\finaudit_graph\*.py
```

Expected: command exits with code 0.

### Task 8: Final Root Audit

**Files:**
- No edits unless unexpected generated files remain

- [ ] **Step 1: Inspect final root**

Run:

```powershell
Get-ChildItem -Force | Select-Object Mode,Name
```

Expected root entries:

```text
.git
.venv
apps
archive
data
model_artifacts
outputs
src
tests
.env
.env.example
.gitignore
README.md
pyproject.toml
requirements.txt
```

- [ ] **Step 2: Inspect runtime data**

Run:

```powershell
Get-ChildItem data -Recurse -File | Select-Object FullName
Get-ChildItem model_artifacts/lora_adapter -File | Select-Object Name
```

Expected runtime data remains:

```text
data/raw/test_audit.txt
data/raw/sample_financial_data.xlsx
data/raw/sample_financial_data.csv
data/graph/related_parties.json
data/graph/init_neo4j.cypher
data/rag/audit_standards.json
data/rag/vector_store.json
model_artifacts/lora_adapter/adapter_config.json
model_artifacts/lora_adapter/adapter_model.safetensors
model_artifacts/lora_adapter/artifact_summary.json
```

---

## Self-Review

Spec coverage: The plan keeps all runtime code, dependency files, environment templates, test files, demo inputs, graph/RAG data, and LoRA adapter files. It moves all non-runtime documents, generated outputs, training logs, helper scripts, labels, and configs into archive.

Placeholder scan: No placeholder steps remain; every move command names exact paths and destinations.

Risk note: `docs/superpowers/plans/2026-06-04-project-cleanup.md` itself is a planning artifact. Keep it until execution completes; then either leave it as the cleanup record or move `docs/superpowers/` into `archive/project_cleanup_2026-06-04/docs/`.
