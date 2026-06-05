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

REQUIRED_FINANCIAL_FIELDS = {
    "company_name",
    "reporting_year",
    "revenue_growth_rate",
    "operating_cashflow_growth_rate",
    "gross_margin_rate",
    "accounts_receivable_growth_rate",
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
        # 表格文件先展开为单元格，再转成统一文本视图，便于后面的规则复用。
        return spreadsheet_cells_to_text(read_spreadsheet_cells(document_path))

    return ""


def _extract_percent(text: str, labels: list[str]) -> float | None:
    """按标签名从文本中提取百分比数值。"""
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[：:]\s*(-?\d+(?:\.\d+)?)\s*%?"
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def _extract_year(text: str) -> int | None:
    """从常见年度标签后提取 20xx 年份。"""
    match = re.search(r"(?:报告年度|会计年度|年度|年份|报告年份)\s*[：:]\s*(20\d{2})", text)
    if match:
        return int(match.group(1))
    return None


def _extract_company(text: str) -> str | None:
    """从文本中识别被审计企业名称。"""
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
    """把 CSV/XLSX/XLS 统一读取成 sheet、row、col、value 单元格列表。"""
    # 不同表格格式统一转成 sheet / row / col / value 四元组，后面语义对齐只关心这一层。
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
    """把单元格列表展开为带位置标识的文本，供正则解析复用。"""
    return "\n".join(
        f"{cell['sheet']}!{column_name(cell['col'])}{cell['row']}: {cell['value']}" for cell in cells if cell["value"]
    )


def _read_csv_cells(path: Path) -> list[dict[str, Any]]:
    """读取 CSV 非空单元格。"""
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
    """用标准 xlsx zip/xml 结构读取非空单元格，减少额外依赖。"""
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
    """读取旧版 xls 文件；pandas/xlrd 不可用时返回空列表。"""
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
    """读取 xlsx sharedStrings.xml 中的共享字符串表。"""
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(".//{*}si"):
        text_parts = [node.text or "" for node in item.findall(".//{*}t")]
        strings.append("".join(text_parts))
    return strings


def _read_workbook_sheet_names(archive: zipfile.ZipFile) -> list[str]:
    """读取 xlsx 工作簿里的 sheet 名称。"""
    if "xl/workbook.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    return [sheet.attrib.get("name", "Sheet") for sheet in root.findall(".//{*}sheet")]


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    """解析 xlsx 单元格真实文本，兼容 inlineStr 和 shared string。"""
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
    """把 A1/B2 这类引用转换成 1-based 行列坐标。"""
    match = re.match(r"([A-Z]+)(\d+)", reference)
    if not match:
        return 0, 0
    col = 0
    for character in match.group(1):
        col = col * 26 + (ord(character) - ord("A") + 1)
    return int(match.group(2)), col


def column_name(index: int) -> str:
    """把 1-based 列号转换成 Excel 列名。"""
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name or "A"


def semantically_align_financial_fields(cells: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """根据字段别名在表格中定位标签，并抽取相邻或同格的财务指标值。"""
    cell_map = {(cell["sheet"], cell["row"], cell["col"]): cell for cell in cells}
    parsed: dict[str, Any] = {}
    evidence: dict[str, Any] = {}

    for field, aliases in FIELD_ALIASES.items():
        for cell in cells:
            label = str(cell["value"])
            if not label_matches_alias(label, aliases):
                continue
            # 先尝试从当前单元格直接抽值；抽不到再向右/向下找相邻单元格。
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


def analyze_financial_statement_tables(cells: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """从多 sheet 财务报表中识别本期/上期金额，并计算关键风险指标。"""
    parsed: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    rows_by_sheet: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for cell in cells:
        rows_by_sheet.setdefault(cell["sheet"], {}).setdefault(cell["row"], []).append(cell)

    for sheet, rows in rows_by_sheet.items():
        header_map = locate_amount_headers(rows)
        if not header_map:
            continue

        for row_index, row_cells in rows.items():
            labels = " ".join(str(cell["value"]) for cell in row_cells)
            normalized = normalize_label(labels)
            current_cell = find_cell_in_row(row_cells, header_map["current"])
            previous_cell = find_cell_in_row(row_cells, header_map["previous"])
            if current_cell is None or previous_cell is None:
                continue
            current = parse_amount(current_cell["value"])
            previous = parse_amount(previous_cell["value"])
            if current is None or previous in (None, 0):
                continue

            if "营业收入" in normalized or "主营业务收入" in normalized:
                parsed["revenue_growth_rate"] = percent_change(current, previous)
                evidence["revenue_growth_rate"] = build_statement_evidence(
                    sheet,
                    row_cells,
                    current_cell,
                    previous_cell,
                    "营业收入本期/上期金额",
                )
            elif "经营活动产生的现金流量净额" in normalized or "经营现金流" in normalized:
                parsed["operating_cashflow_growth_rate"] = percent_change(current, previous)
                evidence["operating_cashflow_growth_rate"] = build_statement_evidence(
                    sheet,
                    row_cells,
                    current_cell,
                    previous_cell,
                    "经营活动现金流本期/上期金额",
                )
            elif "应收账款" in normalized or "应收款项" in normalized:
                parsed["accounts_receivable_growth_rate"] = percent_change(current, previous)
                evidence["accounts_receivable_growth_rate"] = build_statement_evidence(
                    sheet,
                    row_cells,
                    current_cell,
                    previous_cell,
                    "应收账款期末/期初余额",
                )

        revenue = find_statement_amount(rows, header_map, ["营业收入", "主营业务收入"])
        cost = find_statement_amount(rows, header_map, ["营业成本", "主营业务成本"])
        if revenue and cost and revenue[0] != 0:
            parsed["gross_margin_rate"] = round((revenue[0] - cost[0]) / revenue[0] * 100, 2)
            evidence["gross_margin_rate"] = {
                "sheet": sheet,
                "cell": revenue[1],
                "matched_label": "营业收入 / 营业成本",
                "raw_value": f"revenue={revenue[0]}, cost={cost[0]}",
                "calculation": "(revenue - cost) / revenue",
            }

    return parsed, evidence


def locate_amount_headers(rows: dict[int, list[dict[str, Any]]]) -> dict[str, int] | None:
    """定位本期/上期或期末/期初金额所在列。"""
    for row_cells in rows.values():
        current_col = None
        previous_col = None
        for cell in row_cells:
            label = normalize_label(str(cell["value"]))
            if any(term in label for term in ("本期金额", "本期数", "期末余额", "期末数")):
                current_col = cell["col"]
            elif any(term in label for term in ("上期金额", "上期数", "期初余额", "期初数")):
                previous_col = cell["col"]
        if current_col and previous_col:
            return {"current": current_col, "previous": previous_col}
    return None


def find_statement_amount(
    rows: dict[int, list[dict[str, Any]]],
    header_map: dict[str, int],
    labels: list[str],
) -> tuple[float, str] | None:
    """按项目名称查找本期金额。"""
    for row_cells in rows.values():
        normalized = normalize_label(" ".join(str(cell["value"]) for cell in row_cells))
        if not any(normalize_label(label) in normalized for label in labels):
            continue
        current_cell = find_cell_in_row(row_cells, header_map["current"])
        if current_cell is None:
            continue
        amount = parse_amount(current_cell["value"])
        if amount is not None:
            return amount, f"{column_name(current_cell['col'])}{current_cell['row']}"
    return None


def find_cell_in_row(row_cells: list[dict[str, Any]], col: int) -> dict[str, Any] | None:
    """在一行中按列号取单元格。"""
    for cell in row_cells:
        if cell["col"] == col:
            return cell
    return None


def parse_amount(value: Any) -> float | None:
    """解析财务报表金额，兼容逗号、括号负数和百分号。"""
    text = str(value).strip()
    if not text or text in {"-", "--", "—"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[,\s人民币元万元千元%（）()]", "", text)
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    amount = float(match.group(0))
    return -abs(amount) if negative else amount


def percent_change(current: float, previous: float) -> float:
    """计算增长率百分比。"""
    return round((current - previous) / abs(previous) * 100, 2)


def build_statement_evidence(
    sheet: str,
    row_cells: list[dict[str, Any]],
    current_cell: dict[str, Any],
    previous_cell: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    """记录计算型指标的来源。"""
    return {
        "sheet": sheet,
        "cell": f"{column_name(current_cell['col'])}{current_cell['row']}",
        "matched_label": label,
        "raw_value": f"current={current_cell['value']}, previous={previous_cell['value']}",
        "row_values": [str(cell["value"]) for cell in row_cells],
        "calculation": "(current - previous) / abs(previous)",
    }


def label_matches_alias(label: str, aliases: list[str]) -> bool:
    """判断表格标签是否命中任一字段别名。"""
    normalized_label = normalize_label(label)
    return any(normalize_label(alias) in normalized_label for alias in aliases)


def normalize_label(value: str) -> str:
    """去除空格、括号、分隔符等噪声，提升标签匹配容错率。"""
    return re.sub(r"[\s：:（）()\[\]【】_\-/%]+", "", value.lower())


def find_neighbor_value(
    field: str,
    label_cell: dict[str, Any],
    cell_map: dict[tuple[str, int, int], dict[str, Any]],
) -> tuple[Any | None, dict[str, Any]]:
    """在标签右侧、下方等常见财务表布局位置寻找字段值。"""
    # 这里优先搜索“右侧一格、下方一格”等常见财务表布局，避免做过重的表格推理。
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
    """按字段类型把原始文本转换为公司名、年度或百分比数值。"""
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


def empty_parse_result(document_path: Path, text: str = "") -> dict[str, Any]:
    """创建不会伪装成 demo 成功结果的解析骨架。"""
    return {
        "company_name": None,
        "reporting_year": None,
        "revenue_growth_rate": None,
        "operating_cashflow_growth_rate": None,
        "gross_margin_rate": None,
        "accounts_receivable_growth_rate": None,
        "key_clues": [],
        "source_file": document_path.name,
        "raw_text_excerpt": text[:1200],
        "extraction_method": "unreadable_or_empty",
        "extraction_evidence": {},
        "extraction_complete": False,
        "extraction_warnings": [],
    }


def mark_extraction_status(parsed: dict[str, Any]) -> dict[str, Any]:
    """补充解析完整性和缺失字段提示。"""
    missing_fields = [field for field in REQUIRED_FINANCIAL_FIELDS if parsed.get(field) in (None, "")]
    parsed["extraction_complete"] = not missing_fields
    parsed["extraction_warnings"] = [
        warning for warning in parsed.get("extraction_warnings", []) if warning
    ]
    if missing_fields:
        parsed["extraction_warnings"].append("missing_fields:" + ",".join(sorted(missing_fields)))
    parsed["key_clues"] = build_key_clues(parsed)
    return parsed


def build_key_clues(parsed: dict[str, Any]) -> list[str]:
    """根据真实提取出的指标生成核心线索，避免固定 demo 文案。"""
    clues: list[str] = []
    revenue_growth = parsed.get("revenue_growth_rate")
    cashflow_growth = parsed.get("operating_cashflow_growth_rate")
    receivable_growth = parsed.get("accounts_receivable_growth_rate")
    gross_margin = parsed.get("gross_margin_rate")
    if isinstance(revenue_growth, (int, float)) and isinstance(cashflow_growth, (int, float)):
        if revenue_growth > 20 and cashflow_growth < 0:
            clues.append("营业收入增长但经营现金流下降")
    if isinstance(receivable_growth, (int, float)) and receivable_growth > 30:
        clues.append("应收账款增长较快")
    if isinstance(gross_margin, (int, float)) and gross_margin > 55:
        clues.append("毛利率处于较高水平")
    return clues


def parse_financial_document(path: str | Path) -> dict[str, Any]:
    """Parse key audit fields from a source document without masking failures."""
    document_path = Path(path)
    suffix = document_path.suffix.lower()
    cells: list[dict[str, Any]] = []
    if suffix in SPREADSHEET_SUFFIXES:
        cells = read_spreadsheet_cells(document_path)
        text = spreadsheet_cells_to_text(cells)
    else:
        text = read_document_text(document_path)

    parsed = empty_parse_result(document_path, text)

    if not text.strip():
        if suffix in SPREADSHEET_SUFFIXES:
            parsed["extraction_warnings"].append("spreadsheet_no_cells_read")
        return mark_extraction_status(parsed)

    if suffix in SPREADSHEET_SUFFIXES:
        # Excel / CSV 优先走语义对齐，比纯文本正则更适合真实财务表。
        statement_fields, statement_evidence = analyze_financial_statement_tables(cells)
        if statement_fields:
            parsed.update(statement_fields)
            parsed["extraction_method"] = "financial_statement_analysis"
            parsed["extraction_evidence"].update(statement_evidence)

        aligned, evidence = semantically_align_financial_fields(cells)
        if aligned:
            method = parsed["extraction_method"]
            parsed.update(aligned)
            parsed["extraction_method"] = method if method == "financial_statement_analysis" else "semantic_table_alignment"
            parsed["extraction_evidence"].update(evidence)
    else:
        parsed["extraction_method"] = "text_regex"

    parsed["company_name"] = _extract_company(text) or parsed["company_name"]
    parsed["reporting_year"] = _extract_year(text) or parsed["reporting_year"]
    parsed["revenue_growth_rate"] = _extract_percent(text, ["收入增长率", "营业收入增长率"]) or parsed.get(
        "revenue_growth_rate"
    )
    parsed["operating_cashflow_growth_rate"] = _extract_percent(
        text, ["经营现金流增长率", "经营现金流量增长率"]
    ) or parsed.get("operating_cashflow_growth_rate")
    parsed["gross_margin_rate"] = _extract_percent(text, ["毛利率"]) or parsed.get("gross_margin_rate")
    parsed["accounts_receivable_growth_rate"] = _extract_percent(
        text, ["应收账款增长率", "应收账款余额增长率"]
    ) or parsed.get("accounts_receivable_growth_rate")

    return mark_extraction_status(parsed)
