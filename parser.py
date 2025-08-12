import re
from typing import List, Dict
import fitz  # PyMuPDF

HEADING_PATTERNS = [
    r'^\s*(chapter|part|schedule)\s+([ivx]+|\d+)\b.*$',
    r'^\s*(section|sec\.)\s+(\d+[A-Za-z\-]*)\b.*$',
    r'^\s*(\d+(\.\d+)*)\s+[\w\(\)]',
    r'^\s*[A-Z][A-Z \-\&\.\,]{5,}$',
]

compiled_patterns = [re.compile(p, re.IGNORECASE) for p in HEADING_PATTERNS]

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    return "\n".join(parts)

def normalize(text: str) -> str:
    text = re.sub(r'\xa0', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\r', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def split_sections(text: str) -> List[Dict]:
    text = normalize(text)
    lines = text.splitlines()
    sections = []
    current = {"id": None, "heading": None, "body": [], "level": 3, "start": 0}
    def flush(end_idx):
        if current["heading"] or current["body"]:
            body = "\n".join(current["body"]).strip()
            if body or current["heading"]:
                entry = {
                    "id": _make_id(current["heading"]),
                    "heading": current["heading"] or "",
                    "body": body,
                    "level": current["level"],
                    "start": current["start"],
                    "end": end_idx,
                }
                sections.append(entry)
    for i, line in enumerate(lines):
        is_heading = False
        detected_level = 3
        for pat in compiled_patterns:
            if pat.match(line.strip()):
                is_heading = True
                if line.strip().lower().startswith(("chapter", "part")):
                    detected_level = 1
                elif line.strip().lower().startswith(("section", "sec.")):
                    detected_level = 2
                else:
                    detected_level = 3
                break
        if is_heading:
            flush(i)
            current = {"id": None, "heading": line.strip(), "body": [], "level": detected_level, "start": i}
        else:
            current["body"].append(line)
    flush(len(lines))

    for s in sections:
        if not s["id"]:
            s["id"] = _make_id(s["heading"]) or f"auto_{s['start']}_{s['end']}"
    return sections

def _make_id(heading: str) -> str:
    if not heading:
        return ""
    m = re.search(r'(section|sec\.)\s+(\d+[A-Za-z\-]*)', heading, flags=re.IGNORECASE)
    if m:
        return f"section_{m.group(2).lower()}"
    m = re.match(r'^\s*(\d+(\.\d+)*)', heading)
    if m:
        return f"num_{m.group(1)}"
    m = re.match(r'^\s*(chapter|part)\s+([ivx]+|\d+)\b', heading, flags=re.IGNORECASE)
    if m:
        return f"{m.group(1).lower()}_{m.group(2).lower()}"
    slug = re.sub(r'[^a-z0-9]+', '_', heading.lower()).strip('_')
    return f"h_{slug[:60]}"
