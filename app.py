import streamlit as st
import pandas as pd
from parser import extract_text_from_pdf, split_sections
from compare import match_sections, make_excel, make_word, inline_diff
import io

st.set_page_config(page_title="Act Compare", page_icon="📘", layout="wide")

st.title("📘 Act Compare — New vs Old")
st.caption("Upload the **Old Act** and the **New Act** (PDF/TXT). Get a section-wise, color-coded comparison with downloadable Excel and Word reports.")

col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("Upload OLD Act (PDF/TXT)", type=["pdf", "txt"])
with col2:
    new_file = st.file_uploader("Upload NEW Act (PDF/TXT)", type=["pdf", "txt"])

def read_any(file):
    if file is None:
        return ""
    name = file.name.lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(file.read())
    elif name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    else:
        return file.read().decode("utf-8", errors="ignore")

if st.button("Compare", type="primary"):
    if not old_file or not new_file:
        st.error("Please upload both files.")
        st.stop()

    with st.spinner("Extracting & parsing..."):
        old_text = read_any(old_file)
        new_text = read_any(new_file)
        old_sections = split_sections(old_text)
        new_sections = split_sections(new_text)

    st.success(f"Parsed Old sections: {len(old_sections)} | New sections: {len(new_sections)}")

    with st.spinner("Matching & diffing..."):
        matched = match_sections(old_sections, new_sections)

    df = pd.DataFrame(matched)
    st.subheader("Summary")
    st.dataframe(df["status"].value_counts())

    st.subheader("Details")
    for r in matched:
        heading = r["new_heading"] or r["old_heading"] or "(Untitled)"
        status = r["status"]
        color = {"Added":"#0a7f2e","Removed":"#b00020","Unchanged":"#444","Minor edit":"#b08000","Modified":"#b08000","Substantially modified":"#b00020"}.get(status, "#333")
        with st.expander(f"{heading}  —  {status}"):
            if status == "Added":
                st.markdown(f"<div style='color:{color};font-weight:600'>New</div>", unsafe_allow_html=True)
                st.write(r["new_body"] or "")
            elif status == "Removed":
                st.markdown(f"<div style='color:{color};font-weight:600'>Removed from New</div>", unsafe_allow_html=True)
                st.write(r["old_body"] or "")
            else:
                st.markdown(f"<div style='color:{color};font-weight:600'>Old vs New (inline highlights)</div>", unsafe_allow_html=True)
                html = inline_diff(r["old_body"] or "", r["new_body"] or "")
                st.markdown(f"<div style='line-height:1.6'>{html}</div>", unsafe_allow_html=True)

    st.subheader("Downloads")
    excel_bytes = io.BytesIO()
    make_excel(matched, excel_bytes)
    excel_bytes.seek(0)
    st.download_button("Download Excel (Comparison Table)", data=excel_bytes, file_name="act_comparison.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    docx_bytes = io.BytesIO()
    make_word(matched, docx_bytes, title="Act Comparison Report")
    docx_bytes.seek(0)
    st.download_button("Download Word (Narrative Report)", data=docx_bytes, file_name="act_comparison.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

st.info("Tip: If your PDFs are scanned images, run OCR first (Tesseract/Adobe) so text can be extracted.")
