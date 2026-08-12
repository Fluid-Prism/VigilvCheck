"""theme.py — design tokens and the stylesheet built from them.

Qt Style Sheets have no variables and no transitions, so tokens live here as
plain dicts and get interpolated into one QSS string per theme. Anything that
animates is driven from Python instead.

The identity is a night watch: deep indigo, warm gold, a serif for the
headline. Its siblings are cool blue-black/teal (Kevscope) and moss charcoal
with signal orange (Redactus), so the three share a layout language and
nothing else.
"""

SPACE = 4

PALETTES = {
    "dark": {
        "bg": "#0B0E1A", "chrome": "#111524", "surface": "#171B2E",
        "surface_alt": "#1C2038", "surface_raised": "#222741",
        "border": "#2B2F48", "border_strong": "#3A3F5C",
        "text": "#EDE9DD", "text_muted": "#9A96B0", "text_faint": "#6A6785",
        "accent": "#E7B84F", "accent_hover": "#F0C86A", "accent_ink": "#241505",
        "accent_wash": "#241E10",
        "pass": "#8CB369", "pass_wash": "#16200F",
        "fail": "#E2555A", "fail_wash": "#2A1417",
        "unknown": "#D9922E", "unknown_wash": "#261B0F",
        "na": "#6A6785", "na_wash": "#181B2B",
        "critical": "#E2555A", "high": "#D9722E", "medium": "#D9B23A", "low": "#8B87A3",
        "selection": "#242942",
        "shadow": (0, 0, 0, 150),
        "is_dark": True,
    },
    "light": {
        "bg": "#F4EFE2", "chrome": "#EDE6D4", "surface": "#FFFDF6",
        "surface_alt": "#F6F1E2", "surface_raised": "#FFFFFF",
        "border": "#E0D5BA", "border_strong": "#CBBE9C",
        "text": "#241C10", "text_muted": "#6B6048", "text_faint": "#918672",
        "accent": "#A9720F", "accent_hover": "#BC8218", "accent_ink": "#FFFFFF",
        "accent_wash": "#F6EBD5",
        "pass": "#4F7A3D", "pass_wash": "#EDF3E7",
        "fail": "#B8393A", "fail_wash": "#F9E9E7",
        "unknown": "#A85A1E", "unknown_wash": "#F8EFE2",
        "na": "#8A8069", "na_wash": "#F1ECE0",
        "critical": "#B8393A", "high": "#A85A1E", "medium": "#87701A", "low": "#7A6F58",
        "selection": "#EFE7D3",
        "shadow": (60, 45, 20, 40),
        "is_dark": False,
    },
}

MONO = "Menlo, 'SF Mono', Consolas, monospace"
SERIF = "'New York', Georgia, 'Times New Roman', serif"
# Qt's rich-text CSS parser is stricter than its stylesheet parser: a quoted
# family name makes it discard the whole declaration, silently dropping the
# size and weight along with the font. Rich text gets an unquoted list.
SERIF_RICH = "Georgia, serif"

STATUS_TOKEN = {"pass": "pass", "fail": "fail", "unknown": "unknown", "not_applicable": "na"}
STATUS_LABEL = {"pass": "PASS", "fail": "GAP", "unknown": "UNKNOWN", "not_applicable": "N/A"}


def rgba(hex_colour, alpha):
    h = hex_colour.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{alpha})"


def build_qss(c):
    return f"""
QWidget {{ background: transparent; color: {c['text']}; font-size: 13px; }}
QMainWindow, #Root {{ background: {c['bg']}; }}

#TopBar {{ background: {c['chrome']}; border-bottom: 1px solid {c['border']}; }}
#NavRail {{ background: {c['chrome']}; border-right: 1px solid {c['border']}; }}
#StatusBar {{ background: {c['chrome']}; border-top: 1px solid {c['border']}; }}
#BrandMark {{ font-family: {SERIF}; font-size: 11px; font-weight: 600; font-style: italic;
    letter-spacing: 1.6px; color: {c['accent']}; }}
#BrandName {{ font-family: {SERIF}; font-size: 15px; font-weight: 600; color: {c['text']}; }}

#Panel {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
#PanelHeader {{ background: {c['surface_alt']}; border-bottom: 1px solid {c['border']};
    border-top-left-radius: 8px; border-top-right-radius: 8px; }}
#SectionLabel {{ font-family: {MONO}; font-size: 9px; font-weight: 700;
    letter-spacing: 1.8px; color: {c['text_faint']}; }}
#PageTitle {{ font-family: {SERIF}; font-size: 21px; font-weight: 600; color: {c['text']}; }}
#PageSub {{ font-size: 12px; color: {c['text_muted']}; }}
#Meta {{ font-family: {MONO}; font-size: 11px; color: {c['text_muted']}; }}

QPushButton {{ background: {c['surface']}; color: {c['text']};
    border: 1px solid {c['border_strong']}; border-radius: 6px;
    padding: 6px 13px; font-size: 12px; font-weight: 500; }}
QPushButton:hover {{ background: {c['surface_raised']}; border-color: {c['text_faint']}; }}
QPushButton:pressed {{ background: {c['surface_alt']}; }}
QPushButton:disabled {{ color: {c['text_faint']}; border-color: {c['border']}; background: transparent; }}
QPushButton#Primary {{ background: {c['accent']}; color: {c['accent_ink']};
    border: 1px solid {c['accent']}; font-weight: 700;
    font-family: {MONO}; letter-spacing: 1.2px; font-size: 11px; padding: 7px 16px; }}
QPushButton#Primary:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton#Primary:disabled {{ background: {c['border']}; border-color: {c['border']};
    color: {c['text_faint']}; }}
QPushButton#Quiet {{ background: transparent; border: 1px solid transparent; padding: 6px 9px; }}
QPushButton#Quiet:hover {{ background: {c['surface']}; border-color: {c['border']}; }}
QPushButton#Quiet:checked {{ background: {c['accent_wash']}; border-color: {c['accent']};
    color: {c['accent']}; }}

QLineEdit, QComboBox {{ background: {c['surface']}; color: {c['text']};
    border: 1px solid {c['border_strong']}; border-radius: 6px;
    padding: 6px 10px; font-size: 12px; selection-background-color: {c['accent']};
    selection-color: {c['accent_ink']}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {c['surface_raised']}; color: {c['text']};
    border: 1px solid {c['border_strong']}; padding: 3px;
    selection-background-color: {c['selection']}; outline: none; }}
QCheckBox {{ spacing: 7px; }}

QTreeView {{ background: {c['surface']}; border: none; outline: none; }}
QTreeView::item {{ border: none; }}
QTreeView::item:selected {{ background: {c['selection']}; }}
QTreeView::branch {{ background: transparent; }}

#Drawer {{ background: {c['surface']}; border-left: 1px solid {c['border_strong']}; }}
#DrawerHeader {{ background: {c['surface_alt']}; border-bottom: 1px solid {c['border']}; }}
#Scrim {{ background: {rgba('#000000', 0.34 if c['is_dark'] else 0.16)}; }}

#Notice {{ background: {c['accent_wash']}; border: 1px solid {c['border']};
    border-left: 3px solid {c['accent']}; border-radius: 6px;
    padding: 10px 12px; color: {c['text_muted']}; font-size: 12px; }}
#Detail {{ background: transparent; font-size: 12px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['border_strong']}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {c['text_faint']}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 5px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {c['surface_raised']}; color: {c['text']};
    border: 1px solid {c['border_strong']}; padding: 5px 8px; }}
QSplitter::handle {{ background: {c['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
"""
