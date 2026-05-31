LIGHT = {
    "bg_window":      "#f7f7f7",
    "bg_surface":     "#efefef",
    "bg_input":       "#f7f7f7",
    "bg_card":        "#fafafa",
    "bg_hover":       "#f0f0f0",
    "bg_active":      "#f0fdfa",
    "border":         "#e5e5e5",
    "border_focus":   "#5eead4",
    "text_primary":   "#2d2d2d",
    "text_secondary": "#636363",
    "text_tertiary":  "#a0a0a0",
    "text_on_accent": "#ffffff",
    "accent":         "#0d9488",
    "accent_hover":   "#0f766e",
    "success_bg":     "#f0fdf4",
    "success_text":   "#166534",
    "warning_bg":     "#fffbeb",
    "warning_text":   "#92400e",
    "error_bg":       "#fff1f2",
    "error_text":     "#9f1239",
    "progress_track": "#f0f0f0",
    "progress_fill":  "#0d9488",
    "scrollbar":      "#e0e0e0",
}

DARK = {
    "bg_window":      "#0f0f0f",
    "bg_surface":     "#141414",
    "bg_input":       "#1c1c1c",
    "bg_card":        "#1c1c1c",
    "bg_hover":       "#242424",
    "bg_active":      "#0a1f1e",
    "border":         "#2a2a2a",
    "border_focus":   "#0d9488",
    "text_primary":   "#d4d4d4",
    "text_secondary": "#888888",
    "text_tertiary":  "#555555",
    "text_on_accent": "#ffffff",
    "accent":         "#2dd4bf",
    "accent_hover":   "#14b8a6",
    "success_bg":     "#0d1f0d",
    "success_text":   "#4ade80",
    "warning_bg":     "#1a1500",
    "warning_text":   "#facc15",
    "error_bg":       "#1a0a0a",
    "error_text":     "#f87171",
    "progress_track": "#242424",
    "progress_fill":  "#2dd4bf",
    "scrollbar":      "#333333",
}


def build_stylesheet(t: dict, theme: dict, dark: bool) -> str:
    t_copy = dict(t)
    t_copy["nav_color"] = "#b0b0b0" if dark else "#3a3a3a"
    
    accent         = theme["accent_dark"]        if dark else theme["accent_light"]
    accent_hover   = theme["accent_hover_dark"]  if dark else theme["accent_hover_light"]
    nav_border     = theme["nav_border_dark"]     if dark else theme["nav_border_light"]
    accent_text    = theme["accent_text"]
    
    t_copy["accent"] = accent
    t_copy["accent_hover"] = accent_hover
    t_copy["nav_border"] = nav_border
    t_copy["text_on_accent"] = accent_text
    
    t_copy["progress_fill"] = accent
    t_copy["border_focus"] = accent
    template = """
QMainWindow, QWidget {{
    color: {text_primary};
    font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
}}

QMainWindow, QMainWindow > QWidget, QWidget#centralWidget {{
    background-color: {bg_window};
}}

/* Set transparent backgrounds for containers so they do not hide cards/sidebar */
QFrame, QAbstractButton, QLineEdit, QComboBox, QProgressBar, QScrollBar, QLabel,
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QScrollArea#GlassScroll > QWidget {{
    background: transparent;
}}

QFrame#Sidebar {{
    background: {bg_surface};
    border: none;
    border-right: 1px solid {border};
}}

QFrame#BrandIconContainer {{
    background: {text_primary};
    border-radius: 6px;
}}

QLabel#BrandIconLabel {{
    color: {bg_window};
    font-size: 12px;
    font-weight: 500;
}}

QLabel#BrandName {{
    font-size: 13px;
    font-weight: 500;
    color: {text_primary};
}}

QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 7px 10px;
    text-align: left;
    color: {nav_color};
    font-size: 14px;
}}

QPushButton#NavButton:hover {{
    background: {bg_hover};
    color: {text_primary};
}}

QPushButton#NavButton[active="true"] {{
    background: transparent;
    border-color: {nav_border};
    color: {text_primary};
    font-weight: 500;
}}

QPushButton#NavButton[active="true"]:hover {{
    background: transparent;
}}

QLineEdit {{
    background: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 10px;
    color: {text_primary};
    font-size: 14px;
    selection-background-color: {accent};
}}

QLineEdit:focus {{
    border: 1px solid {border_focus};
}}

QPushButton {{
    padding-left: 12px;
    padding-right: 12px;
}}

QPushButton#PrimaryButton {{
    background: {accent};
    color: {text_on_accent};
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 14px;
    font-weight: 500;
}}

QPushButton#PrimaryButton:hover {{
    background: {accent_hover};
}}

QPushButton#DownloadButton {{
    color: {text_on_accent};
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 700;
}}

QPushButton#GhostButton {{
    background: {bg_surface};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 14px;
    font-weight: 400;
    min-width: 0px;
}}

QPushButton#GhostButton:hover {{
    background: {bg_hover};
    border-color: {border_focus};
}}

QPushButton#GhostButton:pressed {{
    background: {bg_active};
}}

QPushButton#PillButton {{
    background: transparent;
    border: none;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 11px;
    color: {text_tertiary};
}}

QPushButton#PillButton[active="true"] {{
    background: {bg_surface};
    border: 1px solid {border};
    color: {text_primary};
    font-weight: 500;
}}

QPushButton#PasteButton, QToolButton#PasteButton {{
    background: {bg_surface};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 14px;
    font-weight: 400;
    min-width: 0px;
}}
QPushButton#PasteButton:hover, QToolButton#PasteButton:hover {{
    background: {bg_hover};
    border-color: {border_focus};
}}
QPushButton#PasteButton:pressed, QToolButton#PasteButton:pressed {{
    background: {bg_active};
}}

QFrame#Card, QFrame#OptionsCard {{
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 12px;
}}

QFrame#LibraryCard {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {border};
    border-radius: 0px;
}}

QFrame#Card QLabel {{
    color: {text_primary};
    background: transparent;
}}

QFrame#Card QLabel#SettingLabel {{
    color: {text_primary};
    font-size: 14px;
    background: transparent;
}}

QFrame#ConfigCell {{
    background: {bg_surface};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 10px;
}}

QFrame#ConfigCell:hover {{
    border: 1px solid {border_focus};
}}

QFrame#ConfigCell QLabel {{
    font-size: 15px;
}}

QFrame#ConfigCell QLabel#SectionLabel {{
    font-size: 11px;
}}

QProgressBar {{
    background: {progress_track};
    border: none;
    border-radius: 2px;
    height: 4px;
    qproperty-textVisible: false;
}}

QProgressBar::chunk {{
    background: {progress_fill};
    border-radius: 2px;
}}

QProgressBar#FetchBar {{
    background: transparent;
    border: none;
    border-radius: 0px;
    height: 2px;
}}

QProgressBar#FetchBar::chunk {{
    background: {accent};
    border-radius: 0px;
}}

QScrollBar:vertical {{
    width: 8px;
    background: transparent;
    border: none;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {scrollbar};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QComboBox {{
    background: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
    color: {text_primary};
    font-size: 14px;
}}

QComboBox:focus {{
    border: 1px solid {border_focus};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {text_secondary};
    width: 0;
    height: 0;
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 8px;
    color: {text_primary};
    selection-background-color: {bg_hover};
    selection-color: {text_primary};
    padding: 4px;
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 28px;
}}

QComboBox QAbstractItemView::item:hover {{
    background: {bg_hover};
}}

QComboBox QAbstractItemView::item:selected {{
    background: {bg_hover};
    color: {text_primary};
}}

QSpinBox {{
    background: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 10px;
    color: {text_primary};
    font-size: 14px;
    selection-background-color: {accent};
}}

QSpinBox:focus {{
    border: 1px solid {border_focus};
}}

QLabel#BadgeSuccess {{
    background: {success_bg};
    color: {success_text};
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
}}

QLabel#BadgeWarning {{
    background: {warning_bg};
    color: {warning_text};
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
}}

QLabel#BadgeError {{
    background: {error_bg};
    color: {error_text};
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
}}

QLabel#BadgeNeutral {{
    background: {bg_surface};
    color: {text_secondary};
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
}}

QLabel#NavCounter {{
    background: {bg_surface};
    border: 1px solid {border};
    border-radius: 20px;
    padding: 1px 6px;
    font-size: 11px;
    color: {text_secondary};
}}

QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 30px;
    height: 16px;
    border-radius: 9px;
    border: 1px solid {border};
    background: {bg_input};
}}

QCheckBox::indicator:unchecked {{
    background: {bg_input};
}}

QCheckBox::indicator:checked {{
    background: {accent};
}}

QLabel#SectionLabel {{
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.08em;
    color: {text_tertiary};
}}

/* Styled label types to fix dark mode contrast issues */
QLabel#PageTitle {{
    font-size: 18px;
}}

QLabel#PageSubtitle {{
    color: {text_secondary};
    font-size: 14px;
}}

QLabel#MetaLabel {{
    color: {text_secondary};
    font-size: 12px;
}}

QLabel#SettingSubLabel, QLabel#InfoSubtle, QLabel#ToggleLabel {{
    color: {text_secondary};
}}

QLabel#SettingSubLabel {{
    font-size: 12px;
}}

QLabel#TaskTitle, QLabel#InfoTitle {{
    color: {text_primary};
    font-size: 13px;
}}

/* Flat dialog styling */
QDialog {{
    background: {bg_window};
    border-radius: 12px;
}}

QDialog QLabel {{
    color: {text_primary};
    font-size: 13px;
    background: transparent;
}}

QDialog QTextEdit, QDialog QPlainTextEdit {{
    background: {bg_surface};
    border: 1px solid {border};
    border-radius: 8px;
    color: {text_primary};
    font-size: 13px;
    padding: 10px;
}}

QDialog QPushButton {{
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 18px;
    color: {text_primary};
    font-size: 14px;
}}

QDialog QPushButton:hover {{
    background: {bg_hover};
}}
"""
    return template.format(**t_copy)


from ui.themes import get_theme, DEFAULT_THEME

def get_stylesheet(dark: bool = False, theme_name: str = DEFAULT_THEME) -> str:
    t = DARK if dark else LIGHT
    theme = get_theme(theme_name)
    return build_stylesheet(t, theme, dark)

# Keep these for backward compatibility
style = get_stylesheet(dark=False)
dark_style = get_stylesheet(dark=True)
