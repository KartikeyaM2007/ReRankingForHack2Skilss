from __future__ import annotations
import tempfile
from pathlib import Path
import streamlit as st
import pandas as pd

from rank import rank_candidates

st.set_page_config(page_title="Redrob Candidate Ranker", layout="wide")
st.title("Redrob Candidate Ranker Sandbox")
st.write("Upload a small candidates.jsonl sample. The demo runs the same CPU-only ranking code and returns a ranked CSV.")

uploaded = st.file_uploader("Upload candidates JSONL", type=["jsonl"])
top_n = st.slider("Rows to output", min_value=5, max_value=100, value=20)
shortlist_n = st.slider("Shortlist size", min_value=50, max_value=1000, value=300)

if uploaded and st.button("Rank candidates"):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        in_path = td / "candidates.jsonl"
        out_path = td / "ranked.csv"
        debug_path = td / "debug.jsonl"
        in_path.write_bytes(uploaded.read())
        rank_candidates(in_path, out_path, debug_path, top_n=top_n, shortlist_n=shortlist_n)
        df = pd.read_csv(out_path)
        st.dataframe(df, use_container_width=True)
        st.download_button("Download ranked CSV", out_path.read_bytes(), file_name="ranked_candidates.csv", mime="text/csv")
