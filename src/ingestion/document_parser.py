"""
Enterprise Document Parser & Deterministic Metadata Extractor.
Parses PDF, DOCX, XLSX, and XML enterprise documents while preserving tables,
and applies deterministic regex/heuristic rules to extract business metadata:
- contract_code / document_id
- tenant_id
- department
- security_acl (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED)
- effective_date, expiration_date
- SLA commitments (delivery hours, penalty percentage)
- return policy terms
"""

import re
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional
import pypdf
import docx
import openpyxl


class DocumentParser:
    def __init__(self):
        # Regex patterns for deterministic extraction
        self.patterns = {
            "contract_code": [
                r"(?:HỢP ĐỒNG SỐ|HĐ SỐ|MÃ HỢP ĐỒNG|CONTRACT NO|DOC ID)[:\s]+([A-Z0-9\-_/]+)",
                r"\b(CTR-[A-Z0-9\-_]+)\b",
                r"\b(POL-[A-Z0-9\-_]+)\b",
                r"\b(SOP-[A-Z0-9\-_]+)\b",
                r"\b(AUD-[A-Z0-9\-_]+)\b",
            ],
            "tenant_id": [
                r"(?:TENANT ID|MÃ ĐỐI TÁC|MÃ DOANH NGHIỆP|TENANT)[:\s]+([A-Z0-9_]+)",
                r"\b(TENANT_[A-Z0-9]+)\b",
                r"\b(VN_DIST_[A-Z0-9]+)\b"
            ],
            "department": [
                r"(?:PHÒNG BAN|BỘ PHẬN|DEPARTMENT)[:\s]+(SALES|FINANCE|LOGISTICS|WAREHOUSE|LEGAL|HR|OPERATIONS|EXECUTIVE)",
            ],
            "security_acl": [
                r"(?:PHÂN LOẠI BẢO MẬT|BẢO MẬT|CLASSIFICATION|SECURITY ACL)[:\s]+(PUBLIC|INTERNAL|CONFIDENTIAL|RESTRICTED)",
                r"\b(CONFIDENTIAL|RESTRICTED|INTERNAL|PUBLIC)\b"
            ],
            "effective_date": [
                r"(?:NGÀY HIỆU LỰC|EFFECTIVE DATE)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})",
            ],
            "sla_delivery_hours": [
                r"(?:GIAO HÀNG TRONG VÒNG|THỜI GIAN GIAO HÀNG|DELIVERY SLA)[:\s]+(\d+)\s*(?:GIỜ|HOURS|H)",
                r"(\d+)\s*(?:giờ|hours)\s*(?:kể từ khi xác nhận đơn|from confirmation)",
            ],
            "sla_penalty_percent": [
                r"(?:PHẠT CHẬM GIAO HÀNG|MỨC PHẠT|PENALTY RATE)[:\s]+(\d+(?:\.\d+)?)\s*%",
                r"phạt\s+(\d+(?:\.\d+)?)\s*%\s*(?:giá trị đơn|per day)",
            ],
            "return_window_days": [
                r"(?:THỜI HẠN ĐỔI TRẢ|RETURN WINDOW)[:\s]+(\d+)\s*(?:NGÀY|DAYS)",
            ]
        }

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parses document file based on extension and extracts text & metadata.
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            raw_text, tables, pages = self._parse_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            raw_text, tables, pages = self._parse_docx(file_path)
        elif ext in [".xlsx", ".xls"]:
            raw_text, tables, pages = self._parse_xlsx(file_path)
        elif ext in [".xml"]:
            raw_text, tables, pages = self._parse_xml(file_path)
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
            tables = []
            pages = [{"page_no": 1, "text": raw_text}]

        metadata = self.extract_metadata_heuristics(raw_text, path.name)

        return {
            "file_name": path.name,
            "file_path": str(path.resolve()),
            "file_type": ext.lstrip("."),
            "text": raw_text,
            "tables": tables,
            "pages": pages,
            "metadata": metadata
        }

    def _parse_pdf(self, file_path: str):
        reader = pypdf.PdfReader(file_path)
        pages = []
        full_text = []
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            pages.append({"page_no": idx + 1, "text": txt})
            full_text.append(f"--- [Page {idx + 1}] ---\n{txt}")
        return "\n\n".join(full_text), [], pages

    def _parse_docx(self, file_path: str):
        doc = docx.Document(file_path)
        full_text = []
        pages = []
        page_no = 1

        for p in doc.paragraphs:
            if p.text.strip():
                full_text.append(p.text)

        tables = []
        for t_idx, table in enumerate(doc.tables):
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(" | ".join(row_data))
            table_md = "\n".join(table_data)
            tables.append(table_md)
            full_text.append(f"\n[TABLE {t_idx + 1}]\n{table_md}\n")

        joined = "\n".join(full_text)
        pages.append({"page_no": 1, "text": joined})
        return joined, tables, pages

    def _parse_xlsx(self, file_path: str):
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheets_text = []
        tables = []
        pages = []

        for sheet_idx, sheet_name in enumerate(wb.sheetnames):
            ws = wb[sheet_name]
            sheet_rows = []
            for row in ws.iter_rows(values_only=True):
                if any(v is not None for v in row):
                    row_str = " | ".join([str(v) if v is not None else "" for v in row])
                    sheet_rows.append(row_str)
            table_md = f"Sheet: {sheet_name}\n" + "\n".join(sheet_rows)
            tables.append(table_md)
            sheets_text.append(table_md)
            pages.append({"page_no": sheet_idx + 1, "text": table_md})

        joined = "\n\n".join(sheets_text)
        return joined, tables, pages

    def _parse_xml(self, file_path: str):
        tree = ET.parse(file_path)
        root = tree.getroot()
        text_elements = []

        for elem in root.iter():
            if elem.text and elem.text.strip():
                text_elements.append(f"<{elem.tag}>: {elem.text.strip()}")

        joined = "\n".join(text_elements)
        pages = [{"page_no": 1, "text": joined}]
        return joined, [], pages

    def extract_metadata_heuristics(self, text: str, file_name: str) -> Dict[str, Any]:
        """
        Deterministic regex/heuristic metadata extraction.
        """
        metadata: Dict[str, Any] = {
            "contract_code": None,
            "tenant_id": "GLOBAL_TENANT",
            "department": "GENERAL",
            "security_acl": "INTERNAL",
            "effective_date": None,
            "sla_delivery_hours": None,
            "sla_penalty_percent": None,
            "return_window_days": None,
        }

        # Check in text and filename
        combined = f"{file_name}\n{text[:4000]}"

        # Contract Code
        for p in self.patterns["contract_code"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["contract_code"] = m.group(1).strip()
                break

        # Tenant ID
        for p in self.patterns["tenant_id"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["tenant_id"] = m.group(1).strip()
                break

        # Department
        for p in self.patterns["department"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["department"] = m.group(1).upper()
                break

        # Security ACL
        for p in self.patterns["security_acl"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["security_acl"] = m.group(1).upper()
                break

        # Effective date
        for p in self.patterns["effective_date"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["effective_date"] = m.group(1).strip()
                break

        # SLA delivery hours
        for p in self.patterns["sla_delivery_hours"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["sla_delivery_hours"] = int(m.group(1))
                break

        # SLA penalty percent
        for p in self.patterns["sla_penalty_percent"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["sla_penalty_percent"] = float(m.group(1))
                break

        # Return window days
        for p in self.patterns["return_window_days"]:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                metadata["return_window_days"] = int(m.group(1))
                break

        # Fallback security rules based on filename/document type
        fn_upper = file_name.upper()
        if "CONFIDENTIAL" in fn_upper or "VIP" in fn_upper or "CONTRACT" in fn_upper:
            if metadata["security_acl"] == "INTERNAL":
                metadata["security_acl"] = "CONFIDENTIAL"
        if "AUDIT" in fn_upper or "FINANCE" in fn_upper:
            if metadata["security_acl"] in ["INTERNAL", "CONFIDENTIAL"]:
                metadata["security_acl"] = "RESTRICTED"
        if "PUBLIC" in fn_upper or "POLICY" in fn_upper:
            if metadata["security_acl"] != "CONFIDENTIAL":
                metadata["security_acl"] = "PUBLIC"

        return metadata
