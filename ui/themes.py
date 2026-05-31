THEMES = {

    "Teal Clarity": {
        "display_name": "Teal Clarity",
        "description": "Composed and calm. The default.",
        "accent_light":           "#0d9488",
        "accent_hover_light":     "#0f766e",
        "accent_dark":            "#2dd4bf",
        "accent_hover_dark":      "#14b8a6",
        "accent_text":            "#ffffff",
        "nav_border_light":       "#5eead4",
        "nav_border_dark":        "#0d9488",
        "nav_active_bg_light":    "transparent",
        "nav_active_bg_dark":     "transparent",
        "nav_active_text_light":  "#1a1a1a",
        "nav_active_text_dark":   "#f0f0f0",
        "grad_start":             "#0d9488",
        "grad_end":               "#0891b2",
    },

    "Slate Mono": {
        "display_name": "Slate Mono",
        "description": "Pure black and white. No color.",
        "accent_light":           "#1a1a1a",
        "accent_hover_light":     "#333333",
        "accent_dark":            "#f0f0f0",
        "accent_hover_dark":      "#cccccc",
        "accent_text":            "#ffffff",
        "nav_border_light":       "#1a1a1a",
        "nav_border_dark":        "#f0f0f0",
        "nav_active_bg_light":    "transparent",
        "nav_active_bg_dark":     "transparent",
        "nav_active_text_light":  "#1a1a1a",
        "nav_active_text_dark":   "#f0f0f0",
        "grad_start":             "#1a1a1a",
        "grad_end":               "#3a3a3a",
    },

    "Indigo Focus": {
        "display_name": "Indigo Focus",
        "description": "Calm confidence. Feels like professional software.",
        "accent_light":           "#6366f1",
        "accent_hover_light":     "#4f46e5",
        "accent_dark":            "#818cf8",
        "accent_hover_dark":      "#6366f1",
        "accent_text":            "#ffffff",
        "nav_border_light":       "#a5b4fc",
        "nav_border_dark":        "#6366f1",
        "nav_active_bg_light":    "transparent",
        "nav_active_bg_dark":     "transparent",
        "nav_active_text_light":  "#1a1a1a",
        "nav_active_text_dark":   "#f0f0f0",
        "grad_start":             "#6366f1",
        "grad_end":               "#4f46e5",
    },

    "Amber Warmth": {
        "display_name": "Amber Warmth",
        "description": "Personal and warm. Feels handcrafted.",
        "accent_light":           "#d97706",
        "accent_hover_light":     "#b45309",
        "accent_dark":            "#f59e0b",
        "accent_hover_dark":      "#d97706",
        "accent_text":            "#ffffff",
        "nav_border_light":       "#fcd34d",
        "nav_border_dark":        "#d97706",
        "nav_active_bg_light":    "transparent",
        "nav_active_bg_dark":     "transparent",
        "nav_active_text_light":  "#1a1a1a",
        "nav_active_text_dark":   "#f0f0f0",
        "grad_start":             "#d97706",
        "grad_end":               "#b45309",
    },
}

DEFAULT_THEME = "Teal Clarity"


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def all_theme_names() -> list:
    return list(THEMES.keys())
