"""Tests that report outputs use the Lailara design system palette."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from audit import generate_excel, generate_html, generate_pdf, run_audit
from data_hygiene_auditor.reporting import palette as P

SAMPLE_PATH = Path(__file__).parent.parent / "samples" / "input" / "sample_messy_data.xlsx"


def _audit_results() -> dict:
    return run_audit(str(SAMPLE_PATH))


class TestHTMLBranding:
    def test_css_uses_palette_canvas(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_html(results, os.path.join(tmpdir, "r.html"))
            html = Path(path).read_text(encoding="utf-8")
            assert P.CANVAS in html
            assert P.CHICAGO_20 in html
            assert P.HONG_KONG_35 in html
            assert P.SINGAPORE_55 in html
            assert P.RED_42 in html

    def test_css_uses_serif_font(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_html(results, os.path.join(tmpdir, "r.html"))
            html = Path(path).read_text(encoding="utf-8")
            assert "Playfair Display" in html
            assert "Source Sans 3" in html

    def test_css_uses_2px_radius(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_html(results, os.path.join(tmpdir, "r.html"))
            html = Path(path).read_text(encoding="utf-8")
            assert P.BORDER_RADIUS in html

    def test_no_old_dark_theme_colors(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_html(results, os.path.join(tmpdir, "r.html"))
            html = Path(path).read_text(encoding="utf-8")
            assert '#1a1a2e' not in html
            assert '#16213e' not in html
            assert '#e94560' not in html


class TestExcelBranding:
    def test_header_fill_is_chicago(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_excel(results, os.path.join(tmpdir, "f.xlsx"))
            wb = load_workbook(path)
            ws = wb["Findings"]
            fill_color = ws.cell(row=1, column=1).fill.fgColor.rgb
            assert fill_color.lower().endswith(P.xl(P.CHICAGO_20))

    def test_header_font_is_source_sans(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_excel(results, os.path.join(tmpdir, "f.xlsx"))
            wb = load_workbook(path)
            ws = wb["Findings"]
            assert ws.cell(row=1, column=1).font.name == P.FONT_SANS_EXCEL

    def test_severity_fills_match_palette(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_excel(results, os.path.join(tmpdir, "f.xlsx"))
            wb = load_workbook(path)
            ws = wb["Findings"]
            sev_colors = set()
            for row in ws.iter_rows(min_row=2, min_col=5, max_col=5):
                cell = row[0]
                if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb:
                    sev_colors.add(cell.fill.fgColor.rgb[-6:])
            expected = {P.xl(P.SEV_HIGH_BG), P.xl(P.SEV_MEDIUM_BG), P.xl(P.SEV_LOW_BG)}
            assert sev_colors.issubset(expected | {'000000'})

    def test_no_arial_font(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_excel(results, os.path.join(tmpdir, "f.xlsx"))
            wb = load_workbook(path)
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for cell in row:
                        if cell.font and cell.font.name:
                            assert cell.font.name != "Arial", (
                                f"Cell {cell.coordinate} in '{ws.title}' "
                                f"still uses Arial"
                            )


class TestPDFBranding:
    def test_pdf_generates_successfully(self):
        results = _audit_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_pdf(results, os.path.join(tmpdir, "r.pdf"))
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0


class TestPaletteModule:
    def test_severity_aliases_match(self):
        assert P.SEV_HIGH == P.RED_42
        assert P.SEV_MEDIUM == P.SINGAPORE_55
        assert P.SEV_LOW == P.HONG_KONG_35

    def test_xl_strips_hash(self):
        assert P.xl('#1f2e7a') == '1f2e7a'
        assert P.xl('1f2e7a') == '1f2e7a'

    def test_all_colors_are_valid_hex(self):
        import re
        hex_pattern = re.compile(r'^#[0-9a-f]{6}$')
        color_attrs = [
            a for a in dir(P)
            if a.isupper() and not a.startswith('FONT') and not a.startswith('BORDER')
        ]
        for attr in color_attrs:
            val = getattr(P, attr)
            if isinstance(val, str) and val.startswith('#'):
                assert hex_pattern.match(val), f"{attr} = {val!r} is not valid hex"
