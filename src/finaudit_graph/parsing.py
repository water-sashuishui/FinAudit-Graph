from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


DEMO_PARSED_FINANCIAL_DATA: dict[str, Any] = {
    "company_name": "华辰智能装备股份有限公司",
    "reporting_year": 2025,
    "revenue_growth_rate": 42.8,
    "operating_cashflow_growth_rate": -18.6,
    "gross_margin_rate": 61.5,
    "accounts_receivable_growth_rate": 55.2,
    "key_clues": [
        "营业收入高增长但经营现金流下降",
        "毛利率显著高于同行均值",
        "期末应收账款余额增长较快",
    ],
}

FIELD_ALIASES: dict[str, list[str]] = {
    "company_name": ["被审计企业", "被审计单位", "企业名称", "公司名称", "单位名称", "公司"],
    "reporting_year": ["报告年度", "会计年度", "年度", "年份", "报告年份"],
    "revenue_growth_rate": [
        "收入增长率",
        "营业收入增长率",
        "营业收入同比",
        "主营业务收入增长",
        "主营业务收入同比",
        "收入同比",
    ],
    "operating_cashflow_growth_rate": [
        "经营现金流增长率",
        "经营现金流量增长率",
        "经营现金流同比",
        "经营活动现金流同比",
        "经营活动现金流量同比",
    ],
    "gross_margin_rate": ["毛利率", "综合毛利率", "主营业务毛利率", "销售毛利率"],
    "accounts_receivable_growth_rate": [
        "应收账款增长率",
        "应收账款余额增长率",
        "应收账款同比",
        "应收款增长",
        "应收款同比",
    ],
}

PERCENT_FIELDS = {
    "revenue_growth_rate",
    "operating_cashflow_growth_rate",
    "gross_margin_rate",
    "accounts_receivable_growth_rate",
}

SPREADSHEET_SUFFIXES = {".csv", ".xlsx", ".xls"}


def read_document_text(path: str | Path) -> str:
    """Extract text from txt, pdf, docx, csv, or xlsx files."""
    document_path = Path(path)
    if not document_path.exists():
        return ""

    suffix = document_path.suffix.lower()
    if suffix == ".txt":
        return document_path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            return ""
        with pdfplumber.open(str(document_path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError:
            return ""
        document = Document(str(document_path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    if suffix in SPREADSHEET_SUFFIXES:
        return spreadsheet_cells_to_text(read_spreadsheet_cells(document_path))

    return ""


def _extract_percent(text: str, labels: list[str]) -> float | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[：:]\s*(-?\d+(?:\.\d+)?)\s*%?"
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def _extract_year(text: str) -> int | None:
    match = re.search(r"(?:报告年度|年度|年份)\s*[：:]\s*(20\d{2})", text)
    if match:
        return int(match.group(1))
    return None


def _extract_company(text: str) -> str | None:
    patterns = [
        r"(?:被审计企业|企业名称|公司名称)\s*[：:]\s*([^\n\r，,。]+)",
        r"([\u4e00-\u9fa5A-Za-z0-9（）()]{4,40}(?:股份有限公司|有限公司|集团有限公司))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def read_spreadsheet_cells(path: str | Path) -> list[dict[str, Any]]:
    spreadsheet_path = Path(path)
    suffix = spreadsheet_path.suffix.lower()
    if suffix == ".csv":
        return _read_csv_cells(spreadsheet_path)
    if suffix == ".xlsx":
        return _read_xlsx_cells(spreadsheet_path)
    if suffix == ".xls":
        return _read_legacy_excel_cells(spreadsheet_path)
    return []


def spreadsheet_cells_to_text(cells: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{cell['sheet']}!{column_name(cell['col'])}{cell['row']}: {cell['value']}" for cell in cells if cell["value"]
    )


def _read_csv_cells(path: Path) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for row_index, row in enumerate(reader, start=1):
            for col_index, value in enumerate(row, start=1):
                text = str(value).strip()
                if text:
                    cells.append(
                        {
                            "sheet": path.stem,
                            "row": row_index,
                            "col": col_index,
                            "value": text,
                        }
                    )
    return cells


def _read_xlsx_cells(path: Path) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _read_shared_strings(archive)
            sheet_names = _read_workbook_sheet_names(archive)
            sheet_paths = sorted(
                name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
            for sheet_index, sheet_path in enumerate(sheet_paths):
                sheet_name = sheet_names[sheet_index] if sheet_index < len(sheet_names) else f"Sheet{sheet_index + 1}"
                root = ElementTree.fromstring(archive.read(sheet_path))
                for cell in root.findall(".//{*}c"):
                    ref = cell.attrib.get("r", "")
                    row, col = parse_cell_reference(ref)
                    value = _xlsx_cell_value(cell, shared_strings)
                    if value:
                        cells.append({"sheet": sheet_name, "row": row, "col": col, "value": value})
    except Exception:
        return []
    return cells


def _read_legacy_excel_cells(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except ImportError:
        return []

    cells: list[dict[str, Any]] = []
    try:
        workbook = pd.read_excel(path, sheet_name=None, header=None)
    except Exception:
        return []

    for sheet_name, frame in workbook.items():
        for row_index, row in frame.iterrows():
            for col_index, value in enumerate(row.tolist()):
                if pd.isna(value):
                    continue
                text = str(value).strip()
                if text:
                    cells.append(
                        {
                            "sheet": str(sheet_name),
                            "row": int(row_index) + 1,
                            "col": int(col_index) + 1,
                            "value": text,
                        }
                    )
    return cells


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(".//{*}si"):
        text_parts = [node.text or "" for node in item.findall(".//{*}t")]
        strings.append("".join(text_parts))
    return strings


def _read_workbook_sheet_names(archive: zipfile.ZipFile) -> list[str]:
    if "xl/workbook.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    return [sheet.attrib.get("name", "Sheet") for sheet in root.findall(".//{*}sheet")]


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//{*}t")).strip()

    value_node = cell.find("{*}v")
    if value_node is None or value_node.text is None:
        return ""
    raw_value = value_node.text.strip()
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)].strip()
        except (IndexError, ValueError):
            return ""
    return raw_value


def parse_cell_reference(reference: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)", reference)
    if not match:
        return 0, 0
    col = 0
    for character in match.group(1):
        col = col * 26 + (ord(character) - ord("A") + 1)
    return int(match.group(2)), col


def column_name(index: int) -> str:
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name or "A"


def semantically_align_financial_fields(cells: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    cell_map = {(cell["sheet"], cell["row"], cell["col"]): cell for cell in cells}
    parsed: dict[str, Any] = {}
    evidence: dict[str, Any] = {}

    for field, aliases in FIELD_ALIASES.items():
        for cell in cells:
            label = str(cell["value"])
            if not label_matches_alias(label, aliases):
                continue
            candidate = extract_value_for_field(field, label)
            source_cell = cell
            if candidate is None:
                candidate, source_cell = find_neighbor_value(field, cell, cell_map)
            if candidate is None:
                continue
            parsed[field] = candidate
            evidence[field] = {
                "sheet": source_cell["sheet"],
                "cell": f"{column_name(source_cell['col'])}{source_cell['row']}",
                "matched_label": label,
                "raw_value": source_cell["value"],
            }
            break

    return parsed, evidence


def label_matches_alias(label: str, aliases: list[str]) -> bool:
    normalized_label = normalize_label(label)
    return any(normalize_label(alias) in normalized_label for alias in aliases)


def normalize_label(value: str) -> str:
    return re.sub(r"[\s：:（）()\[\]【】_\-/%]+", "", value.lower())


def find_neighbor_value(
    field: str,
    label_cell: dict[str, Any],
    cell_map: dict[tuple[str, int, int], dict[str, Any]],
) -> tuple[Any | None, dict[str, Any]]:
    offsets = [(0, 1), (1, 0), (0, 2), (2, 0), (0, 3), (3, 0), (1, 1)]
    for row_delta, col_delta in offsets:
        candidate_cell = cell_map.get(
            (
                label_cell["sheet"],
                label_cell["row"] + row_delta,
                label_cell["col"] + col_delta,
            )
        )
        if not candidate_cell:
            continue
        value = extract_value_for_field(field, str(candidate_cell["value"]))
        if value is not None:
            return value, candidate_cell
    return None, label_cell


def extract_value_for_field(field: str, raw_value: str) -> Any | None:
    if field == "company_name":
        company = _extract_company(raw_value)
        if company:
            return company
        cleaned = raw_value.strip()
        if cleaned and not label_matches_alias(cleaned, FIELD_ALIASES[field]) and not _extract_percent(cleaned, [""]):
            return cleaned
        return None

    if field == "reporting_year":
        year = _extract_year(raw_value)
        if year:
            return year
        match = re.search(r"\b(20\d{2})\b", raw_value)
        return int(match.group(1)) if match else None

    if field in PERCENT_FIELDS:
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*%?", raw_value)
        return float(match.group(1)) if match else None

    return None


def parse_financial_document(path: str | Path) -> dict[str, Any]:
    """Parse key audit demo fields from a source document.

    If extraction is incomplete, return the stable demo values for missing fields.
    """
    document_path = Path(path)
    text = read_document_text(document_path)
    parsed = dict(DEMO_PARSED_FINANCIAL_DATA)
    parsed["source_file"] = document_path.name
    parsed["raw_text_excerpt"] = text[:1200]
    parsed["extraction_method"] = "text_regex"
    parsed["extraction_evidence"] = {}

    if not text.strip():
        return parsed

    if document_path.suffix.lower() in SPREADSHEET_SUFFIXES:
        aligned, evidence = semantically_align_financial_fields(read_spreadsheet_cells(document_path))
        if aligned:
            parsed.update(aligned)
            parsed["extraction_method"] = "semantic_table_alignment"
            parsed["extraction_evidence"] = evidence

    parsed["company_name"] = _extract_company(text) or parsed["company_name"]
    parsed["reporting_year"] = _extract_year(text) or parsed["reporting_year"]
    parsed["revenue_growth_rate"] = _extract_percent(text, ["收入增长率", "营业收入增长率"]) or parsed[
        "revenue_growth_rate"
    ]
    parsed["operating_cashflow_growth_rate"] = _extract_percent(
        text, ["经营现金流增长率", "经营现金流量增长率"]
    ) or parsed["operating_cashflow_growth_rate"]
    parsed["gross_margin_rate"] = _extract_percent(text, ["毛利率"]) or parsed["gross_margin_rate"]
    parsed["accounts_receivable_growth_rate"] = _extract_percent(
        text, ["应收账款增长率", "应收账款余额增长率"]
    ) or parsed["accounts_receivable_growth_rate"]

    return parsed
