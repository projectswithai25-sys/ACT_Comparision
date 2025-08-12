from typing import List, Dict, Tuple
from rapidfuzz import fuzz, process
import pandas as pd
from docx import Document
import difflib

def match_sections(old_sections: List[Dict], new_sections: List[Dict]) -> List[Dict]:
    old_map = {s["id"]: s for s in old_sections}
    new_map = {s["id"]: s for s in new_sections}
    matched = []
    used_new = set()

    for oid, osec in old_map.items():
        if oid in new_map:
            nsec = new_map[oid]
            used_new.add(oid)
            status, sim = _status(osec["body"], nsec["body"])
            matched.append(_row(osec, nsec, status, sim, "exact_id"))
        else:
            matched.append(_row(osec, None, "Removed", 0.0, "unmatched_old"))

    removed_rows = [r for r in matched if r["status"] == "Removed"]
    remaining_new = [n for nid, n in new_map.items() if nid not in used_new]
    for r in removed_rows:
        if not remaining_new:
            break
        best_by_heading = process.extractOne(r["old_heading"], [n["heading"] for n in remaining_new], scorer=fuzz.token_set_ratio)
        if best_by_heading and best_by_heading[1] >= 80:
            idx = [n["heading"] for n in remaining_new].index(best_by_heading[0])
            nsec = remaining_new.pop(idx)
            status, sim = _status(r["old_body"], nsec["body"])
            r.update(_row_updates_from_new(nsec, status, sim, "fuzzy_heading"))
    for nsec in remaining_new:
        matched.append(_row(None, nsec, "Added", 0.0, "new_only"))
    return matched

def _status(old_text: str, new_text: str) -> Tuple[str, float]:
    if old_text.strip() == new_text.strip():
        return "Unchanged", 100.0
    sim = fuzz.token_set_ratio(old_text, new_text)
    if sim >= 90:
        return "Minor edit", float(sim)
    elif sim >= 65:
        return "Modified", float(sim)
    else:
        return "Substantially modified", float(sim)

def _row(osec, nsec, status, sim, how):
    return {
        "old_id": osec["id"] if osec else None,
        "old_heading": osec["heading"] if osec else None,
        "old_body": osec["body"] if osec else None,
        "new_id": nsec["id"] if nsec else None,
        "new_heading": nsec["heading"] if nsec else None,
        "new_body": nsec["body"] if nsec else None,
        "status": status,
        "similarity": sim,
        "match_method": how,
        "level_old": osec["level"] if osec else None,
        "level_new": nsec["level"] if nsec else None,
    }

def _row_updates_from_new(nsec, status, sim, how):
    return {
        "new_id": nsec["id"],
        "new_heading": nsec["heading"],
        "new_body": nsec["body"],
        "status": status if status != "Removed" else "Modified",
        "similarity": sim,
        "match_method": how,
        "level_new": nsec["level"],
    }

def make_excel(matched: List[Dict], path_or_buf):
    df = pd.DataFrame(matched)
    cols = ["status", "similarity", "match_method",
            "old_id", "old_heading", "old_body",
            "new_id", "new_heading", "new_body",
            "level_old", "level_new"]
    df = df[cols]
    with pd.ExcelWriter(path_or_buf, engine="XlsxWriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Comparison")
        ws = writer.sheets["Comparison"]
        ws.autofilter(0, 0, len(df), len(cols)-1)
        ws.set_column(0, 0, 16)
        ws.set_column(1, 1, 12)
        ws.set_column(4, 4, 30)
        ws.set_column(6, 6, 16)
        ws.set_column(7, 7, 30)
        ws.set_column(5, 5, 60)
        ws.set_column(8, 8, 60)

def make_word(matched: List[Dict], path_or_buf, title="Comparison Report"):
    doc = Document()
    doc.add_heading(title, 0)
    doc.add_paragraph("This report summarizes the differences between the Old Act and the New Act, organized by sections.")
    total = len(matched)
    added = sum(1 for r in matched if r["status"] == "Added")
    removed = sum(1 for r in matched if r["status"] == "Removed")
    modified = sum(1 for r in matched if "Modified" in r["status"] or "Minor" in r["status"] or r["status"] == "Substantially modified")
    unchanged = sum(1 for r in matched if r["status"] == "Unchanged")
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(f"Total compared units: {total}")
    doc.add_paragraph(f"Added: {added}, Removed: {removed}, Modified: {modified}, Unchanged: {unchanged}")
    doc.add_heading("Section-wise Narrative", level=1)
    for r in matched:
        heading = r["new_heading"] or r["old_heading"] or "(Untitled)"
        p = doc.add_paragraph()
        p.add_run(f"{heading} — {r['status']} (Similarity: {int(r['similarity'])}%)").bold = True
        if r["status"] == "Added":
            doc.add_paragraph(r["new_body"] or "")
        elif r["status"] == "Removed":
            doc.add_paragraph(r["old_body"] or "")
        else:
            doc.add_paragraph("Old:")
            doc.add_paragraph(r["old_body"] or "")
            doc.add_paragraph("New:")
            doc.add_paragraph(r["new_body"] or "")
        doc.add_paragraph("")
    doc.save(path_or_buf)

def inline_diff(old: str, new: str) -> str:
    sm = difflib.SequenceMatcher(None, old.split(), new.split())
    out = []
    old_words = old.split()
    new_words = new.split()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            out.extend(old_words[i1:i2])
        elif tag == 'replace':
            out.append('<del>' + ' '.join(old_words[i1:i2]) + '</del>')
            out.append('<ins>' + ' '.join(new_words[j1:j2]) + '</ins>')
        elif tag == 'delete':
            out.append('<del>' + ' '.join(old_words[i1:i2]) + '</del>')
        elif tag == 'insert':
            out.append('<ins>' + ' '.join(new_words[j1:j2]) + '</ins>')
    return ' '.join(out)
