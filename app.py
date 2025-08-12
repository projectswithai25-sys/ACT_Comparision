import streamlit as st
import pandas as pd
import io

from parser import extract_text_from_pdf, split_sections
from compare import match_sections, make_excel, make_word, make_csv, inline_diff

st.set_page_config(page_title="Act Compare", page_icon="📘", layout="wide")

st.title("📘 Act Compare — Topic ▸ SubTopic ▸ Section ▸ Subsection")
st.caption("Upload the OLD Act and the NEW Act. See structured changes with inline diffs in scrollable boxes and download Word/Excel/CSV.")

# ---------- Uploaders ----------
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        old_file = st.file_uploader("Upload OLD Act (PDF/TXT)", type=["pdf", "txt"], key="old")
    with col2:
        new_file = st.file_uploader("Upload NEW Act (PDF/TXT)", type=["pdf", "txt"], key="new")

def read_any(file):
    if file is None:
        return ""
    name = file.name.lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(file.read())
    elif name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    # fallback – try decode
    return file.read().decode("utf-8", errors="ignore")

# ---------- Action ----------
run = st.button("Compare", type="primary", use_container_width=True)

if run:
    if not old_file or not new_file:
        st.error("Please upload both files.")
        st.stop()

    with st.spinner("Extracting & parsing..."):
        old_text = read_any(old_file)
        new_text = read_any(new_file)
        old_units = split_sections(old_text)
        new_units = split_sections(new_text)

    st.success(f"Parsed units — Old: {len(old_units)} | New: {len(new_units)}")

    with st.spinner("Matching & diffing..."):
        matched = match_sections(old_units, new_units)

    df = pd.DataFrame(matched)

    # ---------- Layout: Filters (left) and Details (right) ----------
    left, right = st.columns([1.1, 1.9], gap="large")

    with left:
        st.subheader("Filters")
        status_sel = st.multiselect("Status", options=sorted(df["status"].unique()), default=None)

        # Build topic options from both old and new to be safe
        all_topics = set()
        all_topics.update(df["new_topic"].dropna().tolist())
        all_topics.update(df["old_topic"].dropna().tolist())
        topic_sel = st.multiselect("Topic", options=sorted([t for t in all_topics if t]), default=None)

        section_sel = st.text_input("Section contains (ref/heading)", "")

        # Apply filters
        df_view = df.copy()
        if status_sel:
            df_view = df_view[df_view["status"].isin(status_sel)]
        if topic_sel:
            df_view = df_view[(df_view["new_topic"].isin(topic_sel)) | (df_view["old_topic"].isin(topic_sel))]
        if section_sel.strip():
            mask = (
                df_view["old_section_ref"].fillna("").str.contains(section_sel, case=False)
                | df_view["new_section_ref"].fillna("").str.contains(section_sel, case=False)
                | df_view["old_section_heading"].fillna("").str.contains(section_sel, case=False)
                | df_view["new_section_heading"].fillna("").str.contains(section_sel, case=False)
            )
            df_view = df_view[mask]

        st.subheader("Summary")
        st.dataframe(df_view["status"].value_counts())

        st.subheader("Matched Units (preview)")
        preview_cols = [
            "status", "similarity",
            "old_topic", "old_subtopic", "old_section_ref", "old_subsection_ref",
            "new_topic", "new_subtopic", "new_section_ref", "new_subsection_ref",
        ]
        st.dataframe(
            df_view[preview_cols].reset_index(drop=True),
            use_container_width=True,
            height=320
        )

    with right:
        st.subheader("Details (scrollable diffs)")
        st.caption("Each block shows Old vs New with inline insertions/deletions. The text box is scrollable.")

        for _, r in df_view.iterrows():
            path = " > ".join(
                p for p in [
                    r.get("new_topic") or r.get("old_topic"),
                    r.get("new_subtopic") or r.get("old_subtopic"),
                    r.get("new_section_ref") or r.get("old_section_ref"),
                    r.get("new_subsection_ref") or r.get("old_subsection_ref"),
                ] if p
            )
            title = f"{path} — {r['status']} (Sim: {int(r['similarity'])}%)"

            with st.expander(title, expanded=False):
                if r["status"] == "Added":
                    st.markdown("<div style='font-weight:600'>New</div>", unsafe_allow_html=True)
                    safe_text = (r["new_text"] or "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    html_content = f"""
<div style='max-height:300px; overflow:auto; border:1px solid #eee; padding:12px; border-radius:8px'>
{safe_text}
</div>
"""
                    st.markdown(html_content, unsafe_allow_html=True)

                elif r["status"] == "Removed":
                    st.markdown("<div style='font-weight:600'>Removed from New</div>", unsafe_allow_html=True)
                    safe_text = (r["old_text"] or "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    html_content = f"""
<div style='max-height:300px; overflow:auto; border:1px solid #eee; padding:12px; border-radius:8px'>
{safe_text}
</div>
"""
                    st.markdown(html_content, unsafe_allow_html=True)

                else:
                    html_diff = inline_diff(r.get("old_text") or "", r.get("new_text") or "")
                    html_content = f"""
<div style='max-height:300px; overflow:auto; border:1px solid #eee; padding:12px; border-radius:8px; line-height:1.6'>
{html_diff}
</div>
"""
                    st.markdown(html_content, unsafe_allow_html=True)

    # ---------- Separate Downloads ----------
    st.markdown("---")
    st.header("⬇️ Downloads")

    c1, c2, c3 = st.columns(3)
    with c1:
        excel_bytes = io.BytesIO()
        make_excel(matched, excel_bytes)
        excel_bytes.seek(0)
        st.download_button(
            "Excel: Comparison Table",
            data=excel_bytes,
            file_name="act_comparison.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with c2:
        # CSV wants text (string) not bytes
        from io import StringIO
        csv_buf = StringIO()
        make_csv(matched, csv_buf)
        st.download_button(
            "CSV: Comparison Table",
            data=csv_buf.getvalue(),
            file_name="act_comparison.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with c3:
        docx_bytes = io.BytesIO()
        make_word(matched, docx_bytes, title="Act Comparison Report")
        docx_bytes.seek(0)
        st.download_button(
            "Word: Narrative Report",
            data=docx_bytes,
            file_name="act_comparison.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

st.info("Tip: Use the filters to narrow to a specific Topic/Section. Diffs are presented in a scrollable box for easy review.")
