"""Guard workstation control and clinical-state contrast in both themes."""

import re
from pathlib import Path

CSS_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "css"
FRONTEND_ROOT = Path(__file__).resolve().parents[1] / "frontend"
TOKENS = (CSS_ROOT / "workspace-tokens.css").read_text(encoding="utf-8")
WORKSPACE = (CSS_ROOT / "workspace.css").read_text(encoding="utf-8")
INTAKE = (FRONTEND_ROOT / "app" / "intake.js").read_text(encoding="utf-8")


def _rule(css, selector):
    normalized = re.sub(r"\s+", " ", css)
    match = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", normalized)
    assert match, f"Missing CSS rule: {selector}"
    return match.group(1)


def _variables(rule):
    return dict(re.findall(r"--([\w-]+):\s*(#[\da-fA-F]{6})", rule))


def _luminance(color):
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast(first, second):
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _themes():
    light = _variables(_rule(TOKENS, ":root"))
    dark = {**light, **_variables(_rule(TOKENS, '[data-theme="dark"]'))}
    return {"light": light, "dark": dark}


def test_form_button_and_chip_boundaries_have_nontext_contrast():
    for theme, variables in _themes().items():
        border = variables.get("control-border")
        assert border, f"{theme} theme is missing --control-border"
        for background in ("bg", "surface", "subtle", "hover"):
            assert _contrast(border, variables[background]) >= 3, (
                f"{theme} control border is below 3:1 against --{background}"
            )

    for selector in (".btn", "input, textarea, select", ".chip"):
        assert "var(--control-border)" in _rule(WORKSPACE, selector), selector


def test_laterality_letters_have_aa_contrast_on_solid_side_colors():
    for theme, variables in _themes().items():
        for side in ("left", "right"):
            foreground = variables.get(f"side-{side}-on")
            background = variables[f"side-{side}"]
            assert foreground, f"{theme} theme is missing --side-{side}-on"
            assert _contrast(foreground, background) >= 4.5, (
                f"{theme} {side} laterality text is below 4.5:1"
            )

    assert "var(--side-left-on)" in _rule(WORKSPACE, ".upload-card.side-L .side-letter")
    assert "var(--side-right-on)" in _rule(WORKSPACE, ".upload-card.side-R .side-letter")


def test_small_accent_text_uses_theme_aware_high_contrast_token():
    for selector in (
        ".brand-product",
        ".auth-card .text-link",
        ".side-letter",
        ".stepper .current",
        ".chip.selected",
    ):
        assert "var(--accent-text" in _rule(WORKSPACE, selector), selector


def test_clinical_badges_and_status_messages_have_aa_text_contrast_in_both_themes():
    for theme, variables in _themes().items():
        pairs = (
            ("warning", "warning-soft"),
            ("danger", "danger-soft"),
            ("success", "success-soft"),
            ("side-left-text", "side-left-soft"),
            ("side-right-text", "side-right-soft"),
        )
        for foreground, background in pairs:
            assert _contrast(variables[foreground], variables[background]) >= 4.5, (
                f"{theme} {foreground} on {background} is below 4.5:1"
            )

        for score in range(1, 6):
            foreground = variables[f"orads-{score}-text"]
            background = variables[f"orads-{score}-bg"]
            assert _contrast(foreground, background) >= 4.5, (
                f"{theme} O-RADS {score} text is below 4.5:1"
            )

    assert "var(--warning-soft)" in _rule(WORKSPACE, ".banner.warning")
    assert "var(--warning)" in _rule(WORKSPACE, ".banner.warning")
    assert "var(--danger-soft)" in _rule(WORKSPACE, ".banner.danger")
    assert "var(--danger)" in _rule(WORKSPACE, ".banner.danger")
    for score in range(1, 6):
        rule = _rule(WORKSPACE, f".orads-{score}")
        assert f"var(--orads-{score}-bg)" in rule
        assert f"var(--orads-{score}-text)" in rule


def test_intake_laterality_badges_use_theme_aware_side_styles():
    match = re.search(r'<span class="badge side-\$\{side\}">.*?</span>', INTAKE)
    assert match, "Intake laterality badges must use the theme-aware side badge classes"
    assert "style=" not in match.group(0), "Intake laterality badges must not override theme colors inline"

    for side in ("L", "R"):
        rule = _rule(WORKSPACE, f".badge.side-{side}")
        assert "background: var(--side-" in rule
        assert "color: var(--side-" in rule


def test_completed_stepper_state_has_aa_text_contrast_in_both_themes():
    for theme, variables in _themes().items():
        foreground = variables.get("on-success", variables["on-accent"])
        assert _contrast(foreground, variables["success"]) >= 4.5, (
            f"{theme} completed-step text on success color is below 4.5:1"
        )

    rule = _rule(WORKSPACE, ".stepper span.done b")
    assert "background: var(--success)" in rule
    assert "color: var(--on-success)" in rule
