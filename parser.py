import re
from typing import List, Dict
import fitz  # PyMuPDF

# Heuristic patterns
PAT_CHAPTER_PART = re.compile(r'^\s*(chapter|part|schedule)\s+([ivx]+|\d+)\b.*$', re.I)
PAT_SECTION = re.compile(r'^\s*(section|sec\.)\s+(\d+[A-Za-z\-]*)\b(.*)$', re.I)
PAT_SHOUTY = re.compile(r'^\s*[A-Z][A-Z \-\&\.\,]{5,}$')
PAT_NUM_HEADING = re.compile(r'^\s*(\d+(\.\d+)*)\s+[\w\(\)]')

# Subsection markers within a section body (very common legal formats)
PAT_SUBSEC_MAIN = re.compile(r'^\s*\(\s*(\d+)\s*\)\s+(.*)')      # (1) ...
PAT_SUBSEC_ALPHA = re.compile(r'^\s*\(\s*([a-z])\s*\)\s+(.*)')   # (a) ...
PAT_SUBSEC_ROMAN = re.compile(r'^\s*\(\s*([ivx]+)\s*\)\s+(.*)', re.I)  # (i) ...

def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    parts = []
    for page in doc:
        parts.append(page.get_text(\"text\"))
    return \"\n\".join(parts)

def normalize(text: str) -> str:
    text = re.sub(r'\xa0', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def split_sections(text: str) -> List[Dict]:
    \"\"\"Return a list of hierarchical units (Topic/SubTopic/Section/Subsection).\"\"\"
    text = normalize(text)
    lines = text.splitlines()

    topic = None
    subtopic = None
    current_section_id = None
    current_section_heading = None
    current_section_body = []

    units: List[Dict] = []

    def flush_section():
        nonlocal current_section_id, current_section_heading, current_section_body
        if current_section_heading is None and not current_section_body:
            return
        body = \"\n\".join(current_section_body).strip()
        if body == \"\" and not current_section_heading:
            # nothing to flush
            current_section_id = None
            current_section_heading = None
            current_section_body = []
            return
        # Break into subsections; if none detected, emit one generic subsection
        subsections = _split_subsections(body)
        if not subsections:
            units.append({
                \"topic\": topic or \"\",
                \"subtopic\": subtopic or \"\",
                \"section_ref\": current_section_id or _make_section_ref(current_section_heading),
                \"section_heading\": current_section_heading or \"\",
                \"subsection_ref\": \"\",
                \"text\": body
            })
        else:
            for ref, text_part in subsections:
                units.append({
                    \"topic\": topic or \"\",
                    \"subtopic\": subtopic or \"\",
                    \"section_ref\": current_section_id or _make_section_ref(current_section_heading),
                    \"section_heading\": current_section_heading or \"\",
                    \"subsection_ref\": ref,
                    \"text\": text_part.strip()
                })
        current_section_id = None
        current_section_heading = None
        current_section_body = []

    for raw in lines:
        line = raw.strip()
        if not line:
            current_section_body.append(raw)
            continue

        # Chapter/Part/Schedule -> Topic
        m = PAT_CHAPTER_PART.match(line)
        if m:
            flush_section()
            topic = line
            subtopic = None
            continue

        # SHOUTY headings -> SubTopic (e.g., short-titles or block headings)
        if PAT_SHOUTY.match(line) and not PAT_SECTION.match(line):
            flush_section()
            subtopic = line
            continue

        # Section heading
        sm = PAT_SECTION.match(line)
        if sm:
            # new section begins
            flush_section()
            current_section_id = f\"section_{sm.group(2).lower()}\"
            # include any trailing heading text in heading (sm.group(3))
            current_section_heading = line
            continue

        # Numeric heading can be treated as SubTopic or Section if no explicit 'Section'
        if PAT_NUM_HEADING.match(line) and current_section_heading is None:
            flush_section()
            subtopic = line if subtopic is None else subtopic
            # not changing section here; wait for SECTION marker
            current_section_body.append(raw)
            continue

        # otherwise accumulate into current section body
        current_section_body.append(raw)

    flush_section()
    # backfill refs
    for u in units:
        if not u[\"section_ref\"]:
            u[\"section_ref\"] = _make_section_ref(u[\"section_heading\"]) or \"auto_section\"
    return units

def _make_section_ref(heading: str) -> str:
    if not heading:
        return \"\"
    m = re.search(r'(section|sec\.)\\s+(\\d+[A-Za-z\\-]*)', heading, flags=re.I)
    if m:
        return f\"section_{m.group(2).lower()}\"
    m = re.match(r'^\\s*(\\d+(\\.\\d+)*)', heading)
    if m:
        return f\"num_{m.group(1)}\"
    m = re.match(r'^\\s*(chapter|part)\\s+([ivx]+|\\d+)\\b', heading, flags=re.I)
    if m:
        return f\"{m.group(1).lower()}_{m.group(2).lower()}\"
    slug = re.sub(r'[^a-z0-9]+', '_', heading.lower()).strip('_')
    return f\"h_{slug[:40]}\"

def _split_subsections(body: str):
    \"\"\"Split a section body into [(ref, text)] subsections using common markers.\"\"\"
    lines = body.splitlines()
    out = []
    current_ref = None
    current_buf = []

    def flush():
        nonlocal current_ref, current_buf
        if current_buf:
            out.append((current_ref or \"\", \"\\n\".join(current_buf).strip()))
            current_ref = None
            current_buf = []

    for ln in lines:
        m1 = PAT_SUBSEC_MAIN.match(ln)
        m2 = PAT_SUBSEC_ALPHA.match(ln) if not m1 else None
        m3 = PAT_SUBSEC_ROMAN.match(ln) if not (m1 or m2) else None
        if m1:
            flush()
            current_ref = f\"({m1.group(1)})\"
            current_buf.append(m1.group(2))
        elif m2:
            flush()
            current_ref = f\"({m2.group(1)})\"
            current_buf.append(m2.group(2))
        elif m3:
            flush()
            current_ref = f\"({m3.group(1)})\"
            current_buf.append(m3.group(2))
        else:
            current_buf.append(ln)
    flush()
    return [t for t in out if t[1].strip()]
