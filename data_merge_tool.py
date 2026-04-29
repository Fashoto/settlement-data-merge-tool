import streamlit as st
import pandas as pd
import io
from difflib import SequenceMatcher

st.set_page_config(page_title="Data Merge Tool", layout="wide")
st.title("Settlement Data Merge Tool")
st.markdown("Merge latitude & longitude from source datasets into a target SOP file.")

# ── helpers ──────────────────────────────────────────────────────────────────

def normalize(s):
    if pd.isna(s):
        return ""
    return str(s).strip().lower()

def fuzzy_score(a, b):
    return SequenceMatcher(None, a, b).ratio()

def load_file(uploaded_file):
    if uploaded_file is None:
        return None
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    elif name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    st.error("Unsupported file type. Upload .xlsx, .xls, or .csv")
    return None

def do_merge(source_df, target_df, src_keys, tgt_keys, src_lat, src_lon, fuzzy=False, threshold=0.85):
    """
    Match target rows to source rows using a concatenated composite key.
    Adds lat, lon, and the matched source reference columns to the target.
    Returns (merged_df, match_report_df).
    """
    src = source_df.copy()
    src["_key"] = src[src_keys].apply(
        lambda r: "|".join(normalize(r[c]) for c in src_keys), axis=1
    )
    # keep lat, lon AND the original source key columns for reference
    src_lookup = src.drop_duplicates("_key").set_index("_key")[src_keys + [src_lat, src_lon]]

    tgt = target_df.copy()
    tgt["_key"] = tgt[tgt_keys].apply(
        lambda r: "|".join(normalize(r[c]) for c in tgt_keys), axis=1
    )

    matched_lat, matched_lon, match_type = [], [], []
    ref_cols = {k: [] for k in src_keys}   # ref_LGA, ref_ward, ref_settlement

    src_keys_list = list(src_lookup.index)

    def _append_match(row, mtype):
        matched_lat.append(row[src_lat])
        matched_lon.append(row[src_lon])
        match_type.append(mtype)
        for k in src_keys:
            ref_cols[k].append(row[k])

    def _append_no_match():
        matched_lat.append(None)
        matched_lon.append(None)
        match_type.append("no match")
        for k in src_keys:
            ref_cols[k].append(None)

    for key in tgt["_key"]:
        if key in src_lookup.index:
            _append_match(src_lookup.loc[key], "exact")
        elif fuzzy:
            best_score, best_key = 0, None
            for sk in src_keys_list:
                score = fuzzy_score(key, sk)
                if score > best_score:
                    best_score, best_key = score, sk
            if best_key and best_score >= threshold:
                _append_match(src_lookup.loc[best_key], f"fuzzy ({best_score:.0%})")
            else:
                _append_no_match()
        else:
            _append_no_match()

    # add ref columns named after source keys (prefixed with "ref_")
    for k in src_keys:
        tgt[f"ref_{k}"] = ref_cols[k]
    tgt["latitude"] = matched_lat
    tgt["longitude"] = matched_lon
    tgt["_match_type"] = match_type
    tgt.drop(columns=["_key"], inplace=True)

    ref_col_names = [f"ref_{k}" for k in src_keys]
    report = tgt[tgt_keys + ref_col_names + ["latitude", "longitude", "_match_type"]].copy()
    report.columns = (
        list(tgt_keys) + [f"ref_{k}" for k in src_keys] + ["latitude", "longitude", "match_type"]
    )

    return tgt.drop(columns=["_match_type"]), report


# ── tabs ─────────────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["Quick Merge (Zamfara OBR → SOP)", "Custom Upload Merge"])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — pre-configured Zamfara merge
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Zamfara April OBR → SOP Lat/Long Transfer")
    st.info(
        "Matches on a **concatenated LGA + Ward + Settlement key** (exact, then optional fuzzy). "
        "Adds `latitude`, `longitude`, and the matched OBR reference columns (`ref_LGA`, `ref_ward`, `ref_settlement`) to the SOP."
    )

    col1, col2 = st.columns(2)
    with col1:
        obr_file = st.file_uploader("Upload OBR file (source)", type=["xlsx", "xls", "csv"], key="obr")
    with col2:
        sop_file = st.file_uploader("Upload SOP file (target)", type=["xlsx", "xls", "csv"], key="sop")

    fuzzy_on = st.checkbox("Enable fuzzy matching for unmatched rows", value=True, key="fz1")
    if fuzzy_on:
        threshold = st.slider("Fuzzy match threshold", 0.5, 1.0, 0.85, 0.01, key="th1")
    else:
        threshold = 0.85

    if obr_file and sop_file:
        obr_df = load_file(obr_file)
        sop_df = load_file(sop_file)

        if obr_df is not None and sop_df is not None:
            st.write(f"OBR: **{len(obr_df):,} rows** | SOP: **{len(sop_df):,} rows**")

            # fixed key mapping
            SRC_KEYS = ["LGA", "ward", "settlement"]
            TGT_KEYS = ["LGA name", "Wardname", "Settlementname"]
            SRC_LAT, SRC_LON = "latitude", "longitude"

            missing = [c for c in SRC_KEYS if c not in obr_df.columns]
            missing += [c for c in TGT_KEYS if c not in sop_df.columns]
            if missing:
                st.error(f"Missing expected columns: {missing}")
            else:
                if st.button("Run Merge", key="run1"):
                    with st.spinner("Merging…"):
                        merged, report = do_merge(
                            obr_df, sop_df,
                            SRC_KEYS, TGT_KEYS,
                            SRC_LAT, SRC_LON,
                            fuzzy=fuzzy_on,
                            threshold=threshold,
                        )

                    exact = (report["match_type"] == "exact").sum()
                    fuzzy_matched = report["match_type"].str.startswith("fuzzy").sum()
                    unmatched = (report["match_type"] == "no match").sum()

                    st.success(
                        f"Done — **{exact}** exact | **{fuzzy_matched}** fuzzy | **{unmatched}** unmatched"
                    )

                    st.subheader("Match Report")
                    color_map = {
                        "exact": "background-color: #d4edda",
                        "no match": "background-color: #f8d7da",
                    }
                    def highlight(row):
                        mt = row["match_type"]
                        if mt == "exact":
                            return ["background-color: #d4edda"] * len(row)
                        elif mt == "no match":
                            return ["background-color: #f8d7da"] * len(row)
                        return ["background-color: #fff3cd"] * len(row)

                    st.dataframe(report.style.apply(highlight, axis=1), use_container_width=True)

                    st.subheader("Merged SOP (preview)")
                    st.dataframe(merged.head(50), use_container_width=True)

                    # download
                    buf = io.BytesIO()
                    merged.to_excel(buf, index=False)
                    st.download_button(
                        "Download Merged SOP (.xlsx)",
                        data=buf.getvalue(),
                        file_name="SOP_Zamfara_with_coordinates.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                    buf2 = io.BytesIO()
                    report.to_excel(buf2, index=False)
                    st.download_button(
                        "Download Match Report (.xlsx)",
                        data=buf2.getvalue(),
                        file_name="match_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — custom upload / flexible merge
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Custom Dataset Merge")
    st.info(
        "Upload any two files, choose which columns to match on, "
        "and which columns to transfer from the source into the target."
    )

    col1, col2 = st.columns(2)
    with col1:
        src_file = st.file_uploader("Source file (has lat/long)", type=["xlsx", "xls", "csv"], key="src")
    with col2:
        tgt_file = st.file_uploader("Target file (receives lat/long)", type=["xlsx", "xls", "csv"], key="tgt")

    if src_file and tgt_file:
        src_df = load_file(src_file)
        tgt_df = load_file(tgt_file)

        if src_df is not None and tgt_df is not None:
            st.write(f"Source: **{len(src_df):,} rows, {len(src_df.columns)} cols** | Target: **{len(tgt_df):,} rows, {len(tgt_df.columns)} cols**")

            st.markdown("### Harmonization Settings")
            st.caption("Select the columns to match on (must be in the same order across both files).")

            n_keys = st.number_input("Number of key columns to match on", 1, 5, 2, key="nk")

            src_key_cols, tgt_key_cols = [], []
            cols_src = list(src_df.columns)
            cols_tgt = list(tgt_df.columns)

            for i in range(int(n_keys)):
                c1, c2 = st.columns(2)
                with c1:
                    sc = st.selectbox(f"Source key column {i+1}", cols_src, key=f"sk{i}")
                    src_key_cols.append(sc)
                with c2:
                    tc = st.selectbox(f"Target key column {i+1}", cols_tgt, key=f"tk{i}")
                    tgt_key_cols.append(tc)

            st.markdown("### Columns to Transfer")
            src_lat2 = st.selectbox("Source latitude column", cols_src, key="slat")
            src_lon2 = st.selectbox("Source longitude column", cols_src, key="slon")

            fuzzy_on2 = st.checkbox("Enable fuzzy matching", value=True, key="fz2")
            if fuzzy_on2:
                threshold2 = st.slider("Fuzzy threshold", 0.5, 1.0, 0.85, 0.01, key="th2")
            else:
                threshold2 = 0.85

            if st.button("Run Merge", key="run2"):
                with st.spinner("Merging…"):
                    merged2, report2 = do_merge(
                        src_df, tgt_df,
                        src_key_cols, tgt_key_cols,
                        src_lat2, src_lon2,
                        fuzzy=fuzzy_on2,
                        threshold=threshold2,
                    )

                exact2 = (report2["match_type"] == "exact").sum()
                fuzzy2 = report2["match_type"].str.startswith("fuzzy").sum()
                unmatched2 = (report2["match_type"] == "no match").sum()

                st.success(f"Done — **{exact2}** exact | **{fuzzy2}** fuzzy | **{unmatched2}** unmatched")

                st.subheader("Match Report")
                def highlight2(row):
                    mt = row["match_type"]
                    if mt == "exact":
                        return ["background-color: #d4edda"] * len(row)
                    elif mt == "no match":
                        return ["background-color: #f8d7da"] * len(row)
                    return ["background-color: #fff3cd"] * len(row)

                st.dataframe(report2.style.apply(highlight2, axis=1), use_container_width=True)

                st.subheader("Merged Target (preview)")
                st.dataframe(merged2.head(50), use_container_width=True)

                buf3 = io.BytesIO()
                merged2.to_excel(buf3, index=False)
                st.download_button(
                    "Download Merged File (.xlsx)",
                    data=buf3.getvalue(),
                    file_name="merged_output.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                buf4 = io.BytesIO()
                report2.to_excel(buf4, index=False)
                st.download_button(
                    "Download Match Report (.xlsx)",
                    data=buf4.getvalue(),
                    file_name="match_report_custom.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
