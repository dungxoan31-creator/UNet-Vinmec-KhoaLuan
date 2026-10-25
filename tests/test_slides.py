import os
import re


def test_slides_security_and_script_compliance():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    slides_path = os.path.join(repo_root, "frontend", "slides.html")
    js_path = os.path.join(repo_root, "frontend", "js", "slides.js")

    assert os.path.exists(slides_path), "frontend/slides.html must exist"
    assert os.path.exists(js_path), "frontend/js/slides.js must exist"

    with open(slides_path, encoding="utf-8") as f:
        html = f.read()

    # Rule 1: No inline <script> blocks (blocked by CSP script-src 'self')
    inline_scripts = re.findall(r"<script(?![^>]*src=)[^>]*>(.+?)</script>", html, re.DOTALL | re.IGNORECASE)
    assert not inline_scripts, "Inline scripts in slides.html violate CSP script-src 'self'"

    # Rule 2: Script must reference external file
    assert re.search(r'<script\s+src="[^"]*slides\.js"', html), "slides.html must load slides.js externally"

    # Rule 3: No external Google Fonts CDN links (blocked by CSP style-src 'self' font-src 'self')
    assert "fonts.googleapis.com" not in html, "External font CDN violates CSP style-src"
    assert "fonts.gstatic.com" not in html, "External font CDN violates CSP font-src"


def test_slides_dom_elements_present():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    slides_path = os.path.join(repo_root, "frontend", "slides.html")

    with open(slides_path, encoding="utf-8") as f:
        html = f.read()

    required_ids = [
        'id="progress-bar"',
        'id="slideCounter"',
        'id="prevBtn"',
        'id="nextBtn"',
        'id="fsBtn"',
        'id="timerBadge"',
        'id="timerDisplay"',
        'id="timerToggle"',
        'id="qaBtn"',
        'id="closeQa"',
        'id="qa-modal"',
        'id="notesBtn"',
        'id="closeNotes"',
        'id="notes-drawer"',
        'id="notesContent"',
    ]
    for dom_id in required_ids:
        assert dom_id in html, f"Missing required element: {dom_id}"
