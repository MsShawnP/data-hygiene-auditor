"""Lailara design system color palette — single source of truth.

All report generators (HTML, PDF, Excel) import from here so brand
tokens stay consistent across output formats.
"""

# --- Brand primaries ---
CHICAGO_20 = '#1f2e7a'
HONG_KONG_35 = '#158f75'
TOKYO_40 = '#b82d4a'
SINGAPORE_55 = '#ee8a2a'
RED_42 = '#cc100a'

# --- Tints ---
CHICAGO_85 = '#c5cbe6'
CHICAGO_95 = '#e8eaf4'
HONG_KONG_95 = '#e4f5f0'
SINGAPORE_95 = '#fdeee0'
RED_95 = '#fce8e7'

# --- London greyscale ---
INK = '#0d0d0d'
LONDON_20 = '#333333'
LONDON_35 = '#595959'
LONDON_85 = '#d9d9d9'
CANVAS = '#f5f3ee'

# --- Semantic aliases ---
SEV_HIGH = RED_42
SEV_MEDIUM = SINGAPORE_55
SEV_LOW = HONG_KONG_35
SEV_HIGH_BG = RED_95
SEV_MEDIUM_BG = SINGAPORE_95
SEV_LOW_BG = HONG_KONG_95

# --- Typography ---
FONT_SERIF = "'Playfair Display', Georgia, 'Times New Roman', serif"
FONT_SANS = "'Source Sans 3', 'Source Sans Pro', 'Helvetica Neue', Helvetica, Arial, sans-serif"
FONT_SANS_EXCEL = 'Source Sans Pro'
BORDER_RADIUS = '2px'


def xl(hex_color: str) -> str:
    """Strip leading '#' for openpyxl, which expects bare hex."""
    return hex_color.lstrip('#')
