# Settlement Data Merge Tool

A Streamlit web app for merging latitude and longitude coordinates from OBR (Outbreak Response) datasets into SOP (Settlement Operational Plan) files.

## What it does

Matches settlements across two datasets using a **concatenated LGA + Ward + Settlement name key**, transfers the coordinates, and adds reference columns showing exactly what was matched from the source.

### Output columns added to the SOP
| Column | Description |
|---|---|
| `ref_LGA` | LGA as it appears in the source (OBR) |
| `ref_ward` | Ward as it appears in the source (OBR) |
| `ref_settlement` | Settlement as it appears in the source (OBR) |
| `latitude` | Latitude pulled from the source |
| `longitude` | Longitude pulled from the source |

Match types are colour-coded in the report:
- **Green** — exact match
- **Yellow** — fuzzy match (configurable threshold)
- **Red** — no match found

## Tabs

### Tab 1 — Quick Merge (Zamfara OBR → SOP)
Pre-configured for the Zamfara April OBR and SOP files. Upload both files and run — no column mapping needed.

- Source keys: `LGA`, `ward`, `settlement`
- Target keys: `LGA name`, `Wardname`, `Settlementname`

### Tab 2 — Custom Upload Merge
For any two datasets. You choose:
- How many key columns to match on
- Which source column maps to which target column
- Which columns hold latitude and longitude

## Getting started

```bash
pip install -r requirements.txt
streamlit run data_merge_tool.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Requirements

- Python 3.8+
- streamlit
- pandas
- openpyxl

## Notes

- Matching is case-insensitive and whitespace-trimmed
- Fuzzy matching uses Python's `difflib.SequenceMatcher` — adjust the threshold slider (default 85%) to control strictness
- Data files (`.xlsx`, `.csv`) are excluded from this repo via `.gitignore`
