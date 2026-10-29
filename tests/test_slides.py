import os
import re
from html.parser import HTMLParser
from pathlib import Path


class SlideContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.slides = []
        self.current_slide = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "section" and "slide" in classes:
            self.current_slide = {
                "index": attributes.get("data-index"),
                "notes": attributes.get("data-notes", ""),
                "text": [],
            }

    def handle_data(self, data):
        if self.current_slide is not None:
            text = data.strip()
            if text:
                self.current_slide["text"].append(text)

    def handle_endtag(self, tag):
        if tag == "section" and self.current_slide is not None:
            self.slides.append(self.current_slide)
            self.current_slide = None


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


def test_slides_do_not_overstate_data_validation_or_release_readiness():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    slides_path = os.path.join(repo_root, "frontend", "slides.html")
    with open(slides_path, encoding="utf-8") as f:
        html = f.read()

    parser = SlideContentParser()
    parser.feed(html)
    assert len(parser.slides) == 10
    deck_text = "\n".join(
        " ".join([slide["notes"], *slide["text"]]) for slide in parser.slides
    ).casefold()

    unsupported_claims = [
        "bệnh viện đkqt vinmec times city",
        "patient-level split",
        "synthetic pid mapping",
        "395 automated tests",
        "100% pass rate",
        "-42%",
        "chữ ký số bác sĩ",
        "hệ thống sẵn sàng vận hành",
        "tập kiểm thử độc lập",
    ]
    for claim in unsupported_claims:
        assert claim not in deck_text, f"Unsupported claim reintroduced: {claim}"

    required_disclosures = [
        "prototype nghiên cứu ruo",
        "chưa xác thực lâm sàng",
        "không có ảnh/mặt nạ vinmec",
        "không báo cáo hiệu năng vinmec",
        "advanced hybrid loss",
        "threshold 0.40",
        "patient-level independence chưa được xác minh",
        "không tạo pid tổng hợp",
        "1.269 passed, 0 skipped",
        "118 passed",
        "541 ảnh",
        "demo-synthetic",
        "không chữ ký số",
    ]
    for disclosure in required_disclosures:
        assert disclosure in deck_text, f"Required scope disclosure missing: {disclosure}"

    assert 'href="/static/assets/brand/vinmec-logo.png' not in html
    assert "Prototype nghiên cứu RUO · chưa xác thực lâm sàng" in html


def test_repository_model_metrics_are_not_labeled_as_clinical_sensitivity():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(repo_root, "MODEL_CARD.md"), encoding="utf-8") as f:
        model_card = f.read().casefold()
    with open(os.path.join(repo_root, "README.md"), encoding="utf-8") as f:
        readme = f.read().casefold()
    with open(os.path.join(
        repo_root, "docs", "superpowers", "plans", "2026-10-27-max-accuracy-pipeline.md",
    ), encoding="utf-8") as f:
        plan = f.read().casefold()
    with open(os.path.join(repo_root, "evaluation", "selected_model.json"), encoding="utf-8") as f:
        selected_model = f.read().casefold()
    with open(os.path.join(repo_root, "frontend", "slides.html"), encoding="utf-8") as f:
        slides = f.read().casefold()

    unsupported_phrases = [
        (model_card, "clinical high-sensitivity configuration"),
        (model_card, "mean recall (sensitivity)"),
        (readme, "bộ đo lường phân đoạn lâm sàng"),
        (plan, "high clinical recall"),
        (plan, "for clinical safety"),
        (plan, "verified 100% pass rate"),
        (plan, "ensuring 100% pass rate"),
        (selected_model, '"clinical_profile"'),
    ]
    for source, phrase in unsupported_phrases:
        assert phrase not in source, f"Pixel-level validation evidence is framed as a clinical claim: {phrase}"

    assert "mean segmentation recall (pixel masks)" in model_card
    assert "validation image-level pixel recall" in selected_model
    assert "1.269 passed, 0 skipped" in slides
    assert "118 passed" in slides


def test_repository_does_not_claim_unverified_hospital_data_or_brand_endorsement():
    repo_root = Path(__file__).resolve().parents[1]
    readme = (repo_root / "README.md").read_text(encoding="utf-8").casefold()
    model_card = (repo_root / "MODEL_CARD.md").read_text(encoding="utf-8").casefold()
    user_surfaces = [
        "frontend/index.html",
        "frontend/app/auth.js",
        "frontend/app/navigation.js",
        "frontend/app/report-preview.js",
        "frontend/app/i18n.js",
    ]
    surface_text = {
        path: (repo_root / path).read_text(encoding="utf-8").casefold()
        for path in user_surfaces
    }

    assert "dữ liệu nghiên cứu thực nghiệm: bệnh viện đa khoa quốc tế vinmec times city" not in readme
    assert "workspace không có ảnh/mặt nạ vinmec" in readme
    assert "repository chưa có tài liệu xác nhận tài trợ, ủy quyền hoặc endorsement của vinmec" in readme
    assert "model card — vinmec ovarian ultrasound research prototype" not in model_card
    for path, source in surface_text.items():
        assert "vinmec-logo.png" not in source, f"Unverified institutional logo is still shown by {path}"
        assert "vinmec times city" not in source, f"Unverified hospital affiliation is still shown by {path}"
        assert "vinmec" not in source, f"Unverified institutional brand is still shown by {path}"
    assert "vinmec ·" not in surface_text["frontend/app/i18n.js"]

    slides = (repo_root / "frontend" / "slides.html").read_text(encoding="utf-8").casefold()
    assert "1.269 passed, 0 skipped" in slides
