LIGHT = {
    "bg_window":       "#f5f5f5",
    "bg_surface":      "#efefef",
    "bg_input":        "#f7f7f7",
    "bg_card":         "#ffffff",
    "bg_hover":        "#f0f0f0",
    "bg_active":       "#ffffff",
    "border":          "#e5e5e5",
    "border_focus":    "#a0a0a0",
    "text_primary":    "#1a1a1a",
    "text_secondary":  "#6b6b6b",
    "text_tertiary":   "#a0a0a0",
    "text_on_accent":  "#ffffff",
    "accent":          "#3a3a3a",
    "accent_hover":    "#555555",
    "success_bg":      "#f0fdf4",
    "success_text":    "#166534",
    "warning_bg":      "#fffbeb",
    "warning_text":    "#92400e",
    "error_bg":        "#fff1f2",
    "error_text":      "#9f1239",
    "progress_track":  "#f0f0f0",
    "progress_fill":   "#1a1a1a",
    "scrollbar":       "#e0e0e0",
}

DARK = {
    "bg_window":      "#0f0f0f",
    "bg_surface":     "#141414",
    "bg_input":       "#141414",
    "bg_card":        "#1c1c1c",
    "bg_hover":       "#242424",
    "bg_active":      "#242424",
    "border":         "#272727",
    "border_focus":   "#444444",
    "text_primary":   "#f5f5f5",
    "text_secondary": "#a0a0a0",
    "text_tertiary":  "#5a5a5a",
    "text_on_accent": "#0f0f0f",
    "accent":         "#d4d4d4",
    "accent_hover":   "#bbbbbb",
    "success_bg":     "#0d1f0d",
    "success_text":   "#4ade80",
    "warning_bg":     "#1a1500",
    "warning_text":   "#facc15",
    "error_bg":       "#1a0a0a",
    "error_text":     "#f87171",
    "progress_track": "#242424",
    "progress_fill":  "#d4d4d4",
    "scrollbar":      "#333333",
}


def build_stylesheet(t: dict) -> str:
    template = """
QMainWindow, QWidget {{
    color: {text_primary};
    font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
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
    background: transparent;
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
    background: {bg_surface};
    border: 1px solid {border_focus};
    border-radius: 6px;
    padding: 7px 10px;
    text-align: left;
    color: {text_secondary};
    font-size: 12px;
}}

QPushButton#NavButton:hover {{
    background: {bg_hover};
    color: {text_primary};
    border: 1px solid {accent};
}}

QPushButton#NavButton[active="true"] {{
    background: {bg_active};
    border: 1px solid {accent};
    color: {text_primary};
    font-weight: 500;
}}

QPushButton#NavButton QLabel {{
    color: {text_secondary};
}}

QPushButton#NavButton:hover QLabel {{
    color: {text_primary};
}}

QPushButton#NavButton[active="true"] QLabel {{
    color: {text_primary};
    font-weight: 500;
}}

QLineEdit {{
    background: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 10px;
    color: {text_primary};
    font-size: 12px;
    selection-background-color: {accent};
}}

QLineEdit:focus {{
    border: 1px solid {border_focus};
}}

QPushButton#PrimaryButton {{
    background: {accent};
    color: {text_on_accent};
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton#PrimaryButton:hover {{
    background: {accent_hover};
}}

QPushButton#PrimaryButton:disabled {{
    background: {bg_hover};
    color: {text_tertiary};
}}

QPushButton#DownloadButton {{
    background: {accent};
    color: {text_on_accent};
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
}}

QPushButton#DownloadButton:hover {{
    background: {accent_hover};
}}

QPushButton#DownloadButton:disabled {{
    background: {bg_hover};
    color: {text_tertiary};
}}

QPushButton#GhostButton {{
    background: {bg_card};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
}}

QPushButton#GhostButton:hover {{
    background: {bg_hover};
}}

QPushButton#PillButton {{
    background: transparent;
    border: none;
    border-radius: 20px;
    padding: 3px 10px;
    font-size: 11px;
    color: {text_tertiary};
}}

QPushButton#PillButton[active="true"] {{
    background: {bg_surface};
    border: 1px solid {border};
    color: {text_primary};
    font-weight: 500;
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
    font-size: 13px;
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
    font-size: 12px;
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
    font-size: 12px;
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
    font-size: 10px;
    font-weight: 500;
}}

QLabel#BadgeWarning {{
    background: {warning_bg};
    color: {warning_text};
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#BadgeError {{
    background: {error_bg};
    color: {error_text};
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#BadgeNeutral {{
    background: {bg_surface};
    color: {text_secondary};
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#NavCounter {{
    background: {bg_surface};
    border: 1px solid {border};
    border-radius: 20px;
    padding: 1px 6px;
    font-size: 10px;
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
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.08em;
    color: {text_tertiary};
}}

/* Styled label types to fix dark mode contrast issues */
QLabel#PageSubtitle {{
    color: {text_secondary};
    font-size: 12px;
}}

QLabel#MetaLabel {{
    color: {text_secondary};
    font-size: 11px;
}}

QLabel#SettingSubLabel, QLabel#InfoSubtle, QLabel#ToggleLabel {{
    color: {text_secondary};
}}

QLabel#TaskTitle, QLabel#InfoTitle {{
    color: {text_primary};
}}

/* Flat dialog styling */
QDialog {{
    background: {bg_window};
    border-radius: 12px;
}}

QDialog QLabel {{
    color: {text_primary};
    font-size: 12px;
    background: transparent;
}}

QDialog QTextEdit, QDialog QPlainTextEdit {{
    background: {bg_surface};
    border: 1px solid {border};
    border-radius: 8px;
    color: {text_primary};
    font-size: 12px;
    padding: 10px;
}}

QDialog QPushButton {{
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 18px;
    color: {text_primary};
    font-size: 12px;
}}

QDialog QPushButton:hover {{
    background: {bg_hover};
}}
"""
    return template.format(**t)


style = build_stylesheet(LIGHT)
dark_style = build_stylesheet(DARK)
