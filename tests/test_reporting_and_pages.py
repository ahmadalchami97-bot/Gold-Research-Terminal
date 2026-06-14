"""Reporting builders and a render smoke test for every page."""
import pytest

from app.narrative import templates
from app.reporting import research_note as report


def test_markdown_and_html(snap):
    blocks = templates.build_blocks(snap)
    md = report.build_markdown(snap, blocks, None)
    assert "Executive summary" in md and "Outlook" in md
    html = report.build_html(snap, blocks, None)
    assert html.startswith("<!DOCTYPE") and "Research Note" in html


PAGES = ["overview", "market_state", "drivers", "regime", "levels", "outlook",
         "indicator_consensus", "probability", "risk", "news", "research_note"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(f"import app.pages.{page} as m\nm.render()",
                             default_timeout=90).run()
    assert not at.exception, f"{page}: {[str(e.value) for e in at.exception]}"
