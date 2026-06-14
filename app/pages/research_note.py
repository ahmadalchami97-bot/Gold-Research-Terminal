"""Research Note — compiled institutional note with Markdown / HTML export."""
from __future__ import annotations

import streamlit as st

from app.narrative import get_narrative, get_news_digest
from app.reporting import research_note as report
from app.ui import components as C
from app.ui.data import get_data, get_snapshot


def render() -> None:
    snap = get_snapshot()
    data = get_data()
    blocks = get_narrative(snap)
    digest = get_news_digest(data, snap)

    C.header("Research Note", "Compiled, exportable institutional research note")

    stamp = snap.as_of.strftime("%Y%m%d")
    md = report.build_markdown(snap, blocks, digest)
    note_html = report.build_html(snap, blocks, digest)

    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        st.download_button("⬇ Markdown", md, file_name=f"gold_research_note_{stamp}.md",
                           mime="text/markdown", width="stretch")
    with c2:
        st.download_button("⬇ HTML (print → PDF)", note_html,
                           file_name=f"gold_research_note_{stamp}.html",
                           mime="text/html", width="stretch")
    with c3:
        C.note(f"Narrative engine: {blocks[0].source if blocks else 'deterministic'} · "
               f"News: {digest.generated_by} · HTML opens print-ready in any browser")

    st.divider()
    st.markdown(md)
    C.disclaimer()
