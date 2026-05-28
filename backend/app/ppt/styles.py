"""Design tokens for each PPT theme."""
from dataclasses import dataclass

Rgb = tuple[int, int, int]

SLIDE_WIDTH_EMU  = 12192000
SLIDE_HEIGHT_EMU = 6858000


@dataclass
class Theme:
    id: str
    name: str
    description: str
    preview_colors: list[str]   # hex CSS colors for UI preview swatches
    title_bg: Rgb
    slide_bg: Rgb
    accent: Rgb
    accent2: Rgb
    title_text: Rgb
    heading_text: Rgb
    body_text: Rgb
    table_header_bg: Rgb
    table_header_fg: Rgb
    table_alt_row: Rgb
    chart_colors: list[Rgb]


THEMES: dict[str, Theme] = {
    "corporate": Theme(
        id="corporate", name="Corporate Blue",
        description="Professional navy blue — ideal for business & finance reports.",
        preview_colors=["#002f6c", "#0072bd", "#e8f1fb", "#ffffff"],
        title_bg=(0, 47, 108), slide_bg=(255, 255, 255),
        accent=(0, 114, 189), accent2=(0, 163, 224),
        title_text=(255, 255, 255), heading_text=(0, 47, 108), body_text=(51, 51, 51),
        table_header_bg=(0, 47, 108), table_header_fg=(255, 255, 255),
        table_alt_row=(232, 241, 251),
        chart_colors=[(0,114,189),(0,163,224),(0,47,108),(255,153,0),(64,176,166),(178,24,43)],
    ),
    "modern_dark": Theme(
        id="modern_dark", name="Modern Dark",
        description="Sleek dark theme with cyan accents — great for tech presentations.",
        preview_colors=["#12121e", "#00d4c8", "#8155ff", "#1a1a2a"],
        title_bg=(18, 18, 30), slide_bg=(24, 26, 42),
        accent=(0, 212, 200), accent2=(129, 85, 255),
        title_text=(255, 255, 255), heading_text=(0, 212, 200), body_text=(210, 215, 235),
        table_header_bg=(0, 150, 180), table_header_fg=(255, 255, 255),
        table_alt_row=(35, 38, 60),
        chart_colors=[(0,212,200),(129,85,255),(255,107,107),(255,230,109),(107,203,119),(255,159,67)],
    ),
    "dashboard": Theme(
        id="dashboard", name="Data Dashboard",
        description="Clean teal theme — optimised for KPIs, tables and charts.",
        preview_colors=["#14b8a6", "#06b6d4", "#f0fdf9", "#f8fafc"],
        title_bg=(20, 184, 166), slide_bg=(248, 250, 252),
        accent=(6, 182, 212), accent2=(99, 102, 241),
        title_text=(255, 255, 255), heading_text=(15, 118, 110), body_text=(30, 41, 59),
        table_header_bg=(20, 184, 166), table_header_fg=(255, 255, 255),
        table_alt_row=(240, 253, 250),
        chart_colors=[(20,184,166),(6,182,212),(99,102,241),(245,158,11),(239,68,68),(34,197,94)],
    ),
    "minimal": Theme(
        id="minimal", name="Minimal Clean",
        description="Light minimal with indigo accents — elegant and readable.",
        preview_colors=["#f9fafb", "#6366f1", "#14b8a6", "#ffffff"],
        title_bg=(249, 250, 251), slide_bg=(255, 255, 255),
        accent=(99, 102, 241), accent2=(20, 184, 166),
        title_text=(30, 41, 59), heading_text=(49, 46, 129), body_text=(51, 65, 85),
        table_header_bg=(99, 102, 241), table_header_fg=(255, 255, 255),
        table_alt_row=(238, 242, 255),
        chart_colors=[(99,102,241),(20,184,166),(245,158,11),(239,68,68),(34,197,94),(6,182,212)],
    ),
}

DEFAULT_THEME_ID = "corporate"

FONT_FAMILY   = "Calibri"
FONT_TITLE    = 38
FONT_SUBTITLE = 20
FONT_HEADING  = 22
FONT_BODY     = 15
FONT_SMALL    = 11
FONT_TABLE    = 10
