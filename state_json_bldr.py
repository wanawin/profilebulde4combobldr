# profile_builder_app.py
# GUI builder for positional_matrices_<STATE>_<mid|eve>.json
# Upload a text file of 5-digit draws -> builds 10x10 positional transition matrices (percent rows sum ~100)
# and lets you download the JSON in the exact format your profiler app expects.

from __future__ import annotations
import io
import json
import re
from typing import List, Optional, Tuple

import streamlit as st

st.set_page_config(page_title="Pick-5 Profile Builder (GUI)", layout="centered")
st.title("Pick-5 Profile Builder (GUI)")
st.caption("Upload a history .txt, pick State + Draw, and download the learned profile JSON.")

STATES = ["OH","DC","FL","GA","PA","LA","VA","DE"]
DRAWS  = ["mid","eve"]  # lower-case

DRAW_RE = re.compile(r'(\d)[^\d]*?(\d)[^\d]*?(\d)[^\d]*?(\d)[^\d]*?(\d)')

def extract_draw_from_line(line: str) -> Optional[List[int]]:
    """
    Find the first occurrence of 5 digits in order on the line (separators allowed).
    Returns [d1..d5] or None.
    """
    m = DRAW_RE.search(line)
    if not m:
        return None
    return [int(g) for g in m.groups()]

def load_draws_from_text(text: str) -> List[List[int]]:
    draws: List[List[int]] = []
    for raw in text.splitlines():
        digs = extract_draw_from_line(raw)
        if digs is not None:
            draws.append(digs)
    if len(draws) < 2:
        raise ValueError("Need at least 2 parsed draws in the file/text.")
    return draws

def coverage(draws: List[List[int]]) -> int:
    """Rough score: how many seed-digit bins (per position) are non-empty. Higher is better."""
    seen = 0
    for pos in range(5):
        bins = [0]*10
        for d in draws[:-1]:
            bins[d[pos]] += 1
        seen += sum(1 for b in bins if b > 0)
    return seen

def ensure_oldest_to_newest(draws: List[List[int]]) -> Tuple[List[List[int]], str]:
    """Decide whether to reverse by comparing coverage in both directions."""
    cov_a = coverage(draws)
    cov_b = coverage(list(reversed(draws)))
    if cov_b > cov_a:
        return list(reversed(draws)), "Input looked newest→oldest; reversed to oldest→newest."
    return draws, "Input already oldest→newest."

def build_transition_matrices(draws: List[List[int]]) -> dict:
    """
    Build counts then convert to percentage matrices per position (10x10 each).
    Returns dict {'P1': [[...],[...],...], ..., 'P5': [[...],[...],...]} in percentages.
    """
    counts = {pos: [[0]*10 for _ in range(10)] for pos in range(5)}
    for i in range(len(draws)-1):
        seed = draws[i]
        nxt  = draws[i+1]
        for pos in range(5):
            counts[pos][seed[pos]][nxt[pos]] += 1

    mats_pct = {}
    for pos in range(5):
        mat = counts[pos]
        pct = []
        for row in mat:
            s = sum(row)
            if s == 0:
                pct.append([0.0]*10)
            else:
                pct.append([round(100.0 * c / s, 6) for c in row])
        mats_pct[f"P{pos+1}"] = pct
    return mats_pct

def pretty_row_sums(mats: dict) -> List[str]:
    out = []
    for pos in range(1,6):
        sums = [round(sum(r), 3) for r in mats[f"P{pos}"]]
        out.append(f"P{pos} row sums: {sums}")
    return out

# ---------------- UI ----------------
colA, colB = st.columns(2)
with colA:
    state = st.selectbox("State", STATES, index=STATES.index("DC"))
with colB:
    draw  = st.selectbox("Draw", DRAWS, index=0)  # mid default

st.markdown("#### Upload history file (.txt)")
uploaded = st.file_uploader("One line per draw; mixed formats like '1-7-4-8-8' or '17488' are OK.", type=["txt"])

st.markdown("*(Optional)* Or paste raw text instead:")
raw_text = st.text_area("Paste text of draws here (will be used if no file is uploaded)", height=160, placeholder="Tue Aug 26... 1-7-4-8-8\n17488\n...")

recent = st.number_input("Use most recent N draws (0 = use all)", min_value=0, max_value=100000, value=0, step=50)
build_btn = st.button("Build profile")

if build_btn:
    # Load text
    try:
        if uploaded is not None:
            text = uploaded.read().decode("utf-8", errors="ignore")
        else:
            text = raw_text
        if not text.strip():
            st.error("Please upload a file or paste draw text.")
            st.stop()

        draws = load_draws_from_text(text)
        draws, note = ensure_oldest_to_newest(draws)
        total_parsed = len(draws)

        if recent and recent > 1:
            draws = draws[-recent:]
            recent_note = f"Using most recent {recent} draws."
        else:
            recent_note = "Using all parsed draws."

        mats = build_transition_matrices(draws)
        filename = f"positional_matrices_{state}_{draw}.json"

        # Prepare JSON bytes for download
        buf = io.BytesIO()
        buf.write(json.dumps(mats, indent=2).encode("utf-8"))
        buf.seek(0)

        st.success(f"Built profile for **{state} {draw.upper()}** → **{filename}**")
        st.caption(f"{note} Parsed draws: {total_parsed}. {recent_note}")

        with st.expander("Row-sum sanity (should be ~100 each row)"):
            for line in pretty_row_sums(mats):
                st.write(line)

        st.download_button(
            label=f"Download {filename}",
            data=buf,
            file_name=filename,
            mime="application/json"
        )

        with st.expander("Preview (first few rows of P1)"):
            st.code(json.dumps({"P1": mats["P1"][:3]}, indent=2))

        st.info("Place the downloaded JSON in the **same folder** as your prediction app. "
                "In the app, pick the matching State + Draw to use this profile.")

    except Exception as e:
        st.error(f"Error: {e}")
