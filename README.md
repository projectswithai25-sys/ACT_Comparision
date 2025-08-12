# Act Compare — Streamlit + GitHub

Compare a **new Act** vs the **old Act** and generate:
- Section-wise change log (Added / Removed / Modified / Unchanged)
- Color-coded inline differences
- **Excel** (comparison table) + **Word** (narrative) downloads

## Quick Start (Local)

```bash
git clone https://github.com/<your-username>/act-compare-streamlit.git
cd act-compare-streamlit
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Community Cloud (Free)

1. Push this folder to a **public GitHub repo**.
2. Go to https://share.streamlit.io/ → **New app** → Select your repo & branch → `app.py`.
3. Click **Deploy**. (It builds automatically using `requirements.txt`.)

### Optional: Secrets
If you add any keys later, put them in `.streamlit/secrets.toml` locally (not committed). On Streamlit Cloud, add the same entries under **App → Settings → Secrets**.

## File Structure

```
.
├── app.py                  # Streamlit UI
├── parser.py               # PDF text extraction & section parsing
├── compare.py              # Matching & diff + Excel/Word exporters
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── .streamlit/
│   └── config.toml
└── .github/workflows/
    └── CI.yml
```

## Notes
- For **scanned PDFs**, run OCR first (e.g., Tesseract, Adobe) so we can extract text.
- The parser uses heuristics for headings like `Section 23`, `CHAPTER II`, `1. Short title`. Tweak patterns in `parser.py` for your format.
- Fuzzy matching (RapidFuzz) handles renumbered sections and returns a similarity score.

## License
MIT — see `LICENSE`.
