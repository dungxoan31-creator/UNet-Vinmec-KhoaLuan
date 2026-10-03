# Kế Hoạch Thực Thi (Implementation Plan) Nâng Cấp Nền Tảng Siêu Âm Buồng Trứng AI (Human-in-the-Loop)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thiện toàn diện prototype web phân tích siêu âm buồng trứng AI phục vụ khóa luận tốt nghiệp theo chuẩn 3 lớp kiến trúc và 17 tiêu chí đặc thù (hai bên buồng trứng, tách biệt Ground Truth vs AI Mask vs Doctor Review, Medical Viewer đa tầng có tính Live Dice, và Cổng đánh giá học thuật phân tích Failure Cases).

**Architecture:** Mở rộng backend FastAPI + SQLAlchemy/SQLite an toàn (auto-migration không phá vỡ dữ liệu cũ) với trường vị trí giải phẫu (`ovary_side`, `contralateral_status`) và API tải mẫu thực nghiệm. Nâng cấp frontend Vanilla JS với cấu trúc 2 Tab buồng trứng song song, bộ chuyển lớp đa tầng (Layer Switcher) và tính Live Dice trên Canvas, cùng Tab Đánh giá Học thuật & Failure Cases Inspector trong Cổng Quản Trị.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, SQLite, HTML5 Canvas, Vanilla ES6 JavaScript, CSS3.

**Spec:** [docs/superpowers/specs/2026-10-03-ovarian-ultrasound-hitl-platform-design.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/superpowers/specs/2026-10-03-ovarian-ultrasound-hitl-platform-design.md)

## Global Constraints

* Phân định tuyệt đối giữa PID và Tên bệnh nhân: `PatientModel.anonymized_pid` là khóa chính duy nhất.
* Mặc định khi chỉ siêu âm 1 bên buồng trứng: buồng trứng đối bên phải mang trạng thái rõ ràng `NOT_VISUALIZED` (Không quan sát được), không mặc định là bình thường hoặc không có u.
* Thước đo chưa hiệu chuẩn pixel-to-mm bắt buộc hiển thị đơn vị `px` kèm huy hiệu cảnh báo `📐 Chưa hiệu chuẩn mm`.
* Độ tin cậy của mô hình AI (`confidence_score`) phải được gọi chính xác là "Độ tin cậy AI", tuyệt đối không gọi là "Độ chính xác" (Accuracy).
* Bảo toàn 100% 47 test case hiện có; mọi thay đổi code phải vượt qua bộ kiểm thử trước khi bàn giao.

## Review Focus

1. **Lệch kích thước Mask vs Ảnh**: Kiểm tra shape $[512, 512]$ của mask trước khi vẽ hoặc lưu; từ chối và báo lỗi nếu kích thước không khớp.
2. **Quên chọn buồng trứng đối bên**: Nếu form chỉ nạp ảnh 1 bên, tự động gán `contralateral_status = "NOT_VISUALIZED"`.
3. **Ghi đè Ground Truth bằng Prediction**: `PredictionModel` lưu `raw_mask_rle`, `ReviewModel` lưu `verified_mask_rle`, Ground Truth gốc giữ nguyên trong dataset/tệp ảnh.
4. **Chia cho 0 khi tính Live Dice**: Xử lý trường hợp cả 2 mặt nạ đều rỗng ($|A| + |B| = 0$) trả về Dice = 1.0 (hoặc N/A nếu cả hai không có tổn thương).
5. **Nạp ca từ Failure Cases**: Đảm bảo tệp ảnh và mask tương ứng trong `dataset/` tồn tại trước khi nạp vào Workstation; hiển thị thông báo lỗi rõ ràng nếu đường dẫn ảnh bị thiếu.

---

### Task 1: Backend Schemas & Database Models for Ovary Laterality

**Files:**
- Modify: `backend/schemas/schemas.py:185-207`
- Modify: `backend/db/database.py:45-75,145-165`
- Modify: `backend/app/routers/cases.py:25-60`
- Create: `tests/test_case_laterality.py`

**Interfaces:**
- Consumes: `CreateCaseRequest`, `StudyModel`, `CaseItem`
- Produces: `active_ovary_side: Literal["RIGHT", "LEFT"]`, `contralateral_status: Literal["NOT_VISUALIZED", "NORMAL", "SUSPECTED"]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_case_laterality.py
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_create_case_with_ovary_laterality():
    payload = {
        "patient_id": "BN-TEST-LATERALITY-01",
        "study_code": "US-TEST-RO-001",
        "study_date": "2026-10-03",
        "patient_age": "30-39",
        "clinical_notes": "Khảo sát u nang bì buồng trứng phải",
        "active_ovary_side": "RIGHT",
        "contralateral_status": "NOT_VISUALIZED",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "BN-TEST-LATERALITY-01"
    assert data.get("ovary_side") == "RIGHT"
    assert data.get("contralateral_status") == "NOT_VISUALIZED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_case_laterality.py -v -p no:cacheprovider`
Expected: FAIL (missing fields in response/payload validation)

- [ ] **Step 3: Implement laterality in `schemas.py`, `database.py`, and `cases.py`**

- In `backend/schemas/schemas.py`: Add `active_ovary_side: Literal["RIGHT", "LEFT"] = "RIGHT"` and `contralateral_status: Literal["NOT_VISUALIZED", "NORMAL", "SUSPECTED"] = "NOT_VISUALIZED"` to `CreateCaseRequest`. Add `ovary_side: str | None = "RIGHT"` and `contralateral_status: str | None = "NOT_VISUALIZED"` to `CaseItem`.
- In `backend/db/database.py`: Add columns `ovary_side = Column(String(10), default="RIGHT")` and `contralateral_status = Column(String(30), default="NOT_VISUALIZED")` to `StudyModel`. Update `init_db()` to auto-migrate columns in SQLite:
  `cursor.execute("ALTER TABLE studies ADD COLUMN ovary_side VARCHAR(10) DEFAULT 'RIGHT';")`
  `cursor.execute("ALTER TABLE studies ADD COLUMN contralateral_status VARCHAR(30) DEFAULT 'NOT_VISUALIZED';")`
- In `backend/app/routers/cases.py`: Populate `ovary_side` and `contralateral_status` on `StudyModel` creation and return them in API response.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_case_laterality.py -v -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_case_laterality.py backend/schemas/schemas.py backend/db/database.py backend/app/routers/cases.py
git commit -m "feat(backend): add ovary laterality and contralateral status to study schema and db"
```

---

### Task 2: Academic Evaluation & Failure Cases API Endpoints

**Files:**
- Modify: `backend/schemas/schemas.py:240-258`
- Create: `backend/app/routers/evaluation.py`
- Modify: `backend/app/main.py:20-50`
- Create: `tests/test_evaluation_api.py`

**Interfaces:**
- Consumes: `evaluation/retrain_2d_2026-10-03/validation/summary.json`, `baseline_test_metrics.json`, `per_image.csv`
- Produces: `GET /api/evaluation/metrics`, `GET /api/evaluation/samples`, `GET /api/evaluation/samples/{case_id}/workstation-bundle`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evaluation_api.py
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_get_evaluation_metrics():
    resp = client.get("/api/evaluation/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "validation" in data
    assert "test" in data
    assert data["validation"]["dice_mean"] > 0.80
    assert data["validation"]["count"] == 123
    assert data["test"]["dice_mean"] > 0.50

def test_get_evaluation_samples():
    resp = client.get("/api/evaluation/samples?limit=10")
    assert resp.status_code == 200
    samples = resp.json()
    assert len(samples) > 0
    assert "case_id" in samples[0]
    assert "dice" in samples[0]
    assert "failure_category" in samples[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_evaluation_api.py -v -p no:cacheprovider`
Expected: FAIL with 404 Not Found

- [ ] **Step 3: Implement evaluation router in `backend/app/routers/evaluation.py`**

- Read metrics from `evaluation/retrain_2d_2026-10-03/validation/summary.json` and `evaluation/baseline_test_metrics.json`.
- Read per-image records from `evaluation/retrain_2d_2026-10-03/validation/per_image.csv`.
- Categorize each sample:
  - `dice < 0.70 and recall < 0.60` $\rightarrow$ `FALSE_NEGATIVE_DOMINANT`
  - `dice < 0.70 and precision < 0.60` $\rightarrow$ `FALSE_POSITIVE_DOMINANT`
  - `dice < 0.70` $\rightarrow$ `LOW_DICE`
  - `dice >= 0.90` $\rightarrow$ `EXCELLENT`
  - else $\rightarrow$ `GOOD`
- Implement `/api/evaluation/samples/{case_id}/workstation-bundle` returning base64 image, base64 ground truth mask, and base64 AI prediction mask.
- Mount router in `backend/app/main.py`: `app.include_router(evaluation.router, prefix="/api/evaluation", tags=["Evaluation"])`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_evaluation_api.py -v -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_evaluation_api.py backend/app/routers/evaluation.py backend/app/main.py backend/schemas/schemas.py
git commit -m "feat(api): add evaluation metrics and failure cases benchmark endpoints"
```

---

### Task 3: Frontend Case Intake UI with 2-Tab Ovary Laterality

**Files:**
- Modify: `frontend/index.html:280-335,530-580`
- Modify: `frontend/js/modules/cases.js:90-135,170-220`
- Modify: `frontend/js/modules/viewer.js:65-95`
- Test: `node --check frontend/js/modules/cases.js && node --check frontend/js/modules/viewer.js`

**Interfaces:**
- Consumes: `CreateCaseRequest` with `active_ovary_side`, `contralateral_status`
- Produces: UI elements `#tabOvaryRight`, `#tabOvaryLeft`, `#selectContralateralStatus`, `#viewerOvarySideBadge`

- [ ] **Step 1: Write UI markup in `frontend/index.html`**

In `screenCreateCase`:
- Add 2-Tab laterality toggle:
  ```html
  <div class="ovary-tabs-container" style="display: flex; gap: 8px; margin-bottom: 14px;">
      <button type="button" class="btn btn-tab active" id="tabOvaryRight" onclick="selectOvarySide('RIGHT')">
          🩺 Buồng Trứng Phải (Right Ovary)
      </button>
      <button type="button" class="btn btn-tab" id="tabOvaryLeft" onclick="selectOvarySide('LEFT')">
          🩺 Buồng Trứng Trái (Left Ovary)
      </button>
  </div>
  ```
- Add Contralateral Status selector:
  ```html
  <div class="form-group">
      <label for="selectContralateralStatus" class="form-label">Tình trạng buồng trứng đối bên</label>
      <select id="selectContralateralStatus" class="form-select">
          <option value="NOT_VISUALIZED" selected>⚠️ Không quan sát được (Not visualized)</option>
          <option value="NORMAL">✓ Bình thường (Normal)</option>
          <option value="SUSPECTED">⚡ Nghi ngờ có tổn thương riêng</option>
      </select>
  </div>
  ```
- In `.viewer-case-summary-strip`, add `#viewerOvarySideBadge` and `#viewerContralateralBadge`.

- [ ] **Step 2: Update `frontend/js/modules/cases.js`**

- In `handleCreateCaseSubmit(e)`: extract `active_ovary_side` and `contralateral_status` from form inputs. Include them in POST `/api/cases` payload and store in `window.currentCase`.
- Add `selectOvarySide(side)` helper to toggle active class on tabs.
- In `renderRecentCasesTable` and `renderHistoryTable`: include Ovary side badge (e.g., `<span class="badge badge-cyan">Phải (RO)</span>`).

- [ ] **Step 3: Update `frontend/js/modules/viewer.js`**

- In `initResultsWorkspace(data)`: update `#viewerOvarySideBadge` with `currentCase.ovary_side === 'LEFT' ? 'Buồng Trứng Trái (LO)' : 'Buồng Trứng Phải (RO)'`.
- Update `#viewerContralateralBadge` with contralateral status text.

- [ ] **Step 4: Verify syntax**

Run: `node --check frontend/js/modules/cases.js; node --check frontend/js/modules/viewer.js`
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/js/modules/cases.js frontend/js/modules/viewer.js
git commit -m "feat(ui): add 2-tab ovary laterality selector and display in case strip"
```

---

### Task 4: Medical Viewer Multi-Layer Engine & Live Dice / IoU

**Files:**
- Modify: `frontend/index.html:560-630`
- Modify: `frontend/css/viewer.css:120-190`
- Modify: `frontend/js/modules/viewer.js:140-280`
- Test: `node --check frontend/js/modules/viewer.js`

**Interfaces:**
- Consumes: Ground Truth RLE/Mask (when available), AI predicted mask, Doctor canvas mask
- Produces: Live Dice and IoU calculation: `calculateLiveMetrics()`, Layer Switcher toggles (`#toggleLayerGT`, `#toggleLayerAI`, `#toggleLayerDoc`)

- [ ] **Step 1: Add Layer Switcher markup in `frontend/index.html`**

In workstation toolbar above `#canvasContainer`:
```html
<div class="layer-switcher-bar" style="display: flex; gap: 6px; align-items: center; background: #0f172a; padding: 4px 8px; border-radius: var(--radius-sm); margin-bottom: 6px;">
    <span style="font-size: 11px; font-weight: 700; color: #94a3b8; margin-right: 4px;">LỚP LÂM SÀNG:</span>
    <button type="button" class="btn-layer active" id="btnLayerOriginal" onclick="toggleLayer('ORIGINAL')">📷 Ảnh Gốc</button>
    <button type="button" class="btn-layer" id="btnLayerGT" onclick="toggleLayer('GT')" style="display: none;">🟢 Ground Truth</button>
    <button type="button" class="btn-layer active" id="btnLayerAI" onclick="toggleLayer('AI')">🟣 AI Mask</button>
    <button type="button" class="btn-layer active" id="btnLayerDoc" onclick="toggleLayer('DOC')">🖌️ Bác Sĩ Sửa</button>
    <div id="liveMetricsPill" style="display: none; margin-left: auto; font-family: var(--font-mono, monospace); font-size: 11px; color: #34d399; background: rgba(16, 185, 129, 0.15); padding: 2px 8px; border-radius: 12px; border: 1px solid #059669;">
        Dice: <strong id="liveDiceVal">0.000</strong> | IoU: <strong id="liveIouVal">0.000</strong>
    </div>
</div>
```

- [ ] **Step 2: Add styles in `frontend/css/viewer.css`**

Add styles for `.btn-layer`:
```css
.btn-layer {
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.2);
    cursor: pointer;
    transition: all 0.15s ease;
}
.btn-layer.active {
    background: var(--vm-blue);
    color: #ffffff;
    border-color: #38bdf8;
}
```

- [ ] **Step 3: Implement Layer rendering & Live Dice in `frontend/js/modules/viewer.js`**

- Add state variables: `window.activeLayers = { original: true, gt: false, ai: true, doc: true }`, `window.currentGTBitmap = null`.
- In `redrawCanvas()`: compose layers according to active toggles. If `activeLayers.gt` is true, render ground truth mask in emerald green outline/fill.
- Implement `calculateLiveMetrics()`:
  - If `window.currentGTBitmap` is loaded, compare active editor canvas mask pixels against ground truth mask pixels:
    - Count TP (both == 1), FP (editor == 1, GT == 0), FN (editor == 0, GT == 1).
    - $\text{Dice} = \frac{2 \times \text{TP}}{2 \times \text{TP} + \text{FP} + \text{FN}}$, $\text{IoU} = \frac{\text{TP}}{\text{TP} + \text{FP} + \text{FN}}$.
    - Update `#liveDiceVal` and `#liveIouVal`. Show `#liveMetricsPill`.

- [ ] **Step 4: Verify syntax**

Run: `node --check frontend/js/modules/viewer.js`
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/css/viewer.css frontend/js/modules/viewer.js
git commit -m "feat(viewer): implement multi-layer engine and live dice calculation"
```

---

### Task 5: Academic Evaluation Dashboard & Failure Cases Inspector on Admin Portal

**Files:**
- Modify: `frontend/index.html:1095-1150`
- Modify: `frontend/js/modules/admin.js:1-120`
- Test: `node --check frontend/js/modules/admin.js`

**Interfaces:**
- Consumes: `GET /api/evaluation/metrics`, `GET /api/evaluation/samples`
- Produces: Sub-tab `adminTabEvaluation` with 3-split cards, metrics grid, Failure Cases table, and `loadBenchmarkSampleIntoWorkstation(caseId)`

- [ ] **Step 1: Add Tab 6 in `frontend/index.html`**

In `.admin-subnav-bar`:
```html
<button class="admin-subnav-btn" id="btnAdminTabEvaluation" onclick="switchAdminSubTab('evaluation')">
    🔬 Đánh Giá Học Thuật & Failure Cases
</button>
```
Add tab container `#adminTabEvaluation`:
- 3 Split Cards: Train (991), Validation (123), Test (46).
- Scientific Metrics Table: Dice, IoU, Recall, Precision, Specificity.
- Failure Cases Filter Chips:
  `<button class="btn btn-sm active" onclick="filterFailureCases('ALL')">Tất cả (123)</button>`
  `<button class="btn btn-sm" onclick="filterFailureCases('LOW_DICE')">⚠️ Dice < 0.70 (28 ca)</button>`
  `<button class="btn btn-sm" onclick="filterFailureCases('FALSE_NEGATIVE')">🔴 Bỏ sót u (Recall thấp)</button>`
  `<button class="btn btn-sm" onclick="filterFailureCases('FALSE_POSITIVE')">🟡 Nhận nhầm nhiễu (Precision thấp)</button>`
  `<button class="btn btn-sm" onclick="filterFailureCases('EXCELLENT')">🟢 Xuất sắc (Dice ≥ 0.90)</button>`
- Table `#tableEvaluationSamples` with columns: Mã mẫu, Dice, IoU, Recall, Precision, Đặc trưng sai số, Thao tác.

- [ ] **Step 2: Implement logic in `frontend/js/modules/admin.js`**

- In `switchAdminSubTab(tabName)`: handle `'evaluation'` by calling `loadEvaluationData()`.
- Implement `loadEvaluationData()`: fetch `/api/evaluation/metrics` and render metrics cards; fetch `/api/evaluation/samples` and render samples table.
- Implement `filterFailureCases(category)`: filter and re-render table rows.
- Implement `loadBenchmarkSampleIntoWorkstation(caseId)`:
  - Fetch `/api/evaluation/samples/${caseId}/workstation-bundle`.
  - Set `window.currentCase` with PID `SAMPLE-${caseId}`.
  - Set `window.currentPrediction` with sample data and AI predicted mask.
  - Set `window.currentGTBitmap` with Ground Truth mask.
  - Enable Ground Truth layer button (`#btnLayerGT.style.display = 'inline-block'`).
  - Call `initResultsWorkspace(window.currentPrediction)`.
  - Navigate to `'results'` screen: `navigateTo('results')`.
  - Show toast: `✓ Đã nạp ca kiểm thử #${caseId}. Đang hiển thị đối chiếu Ground Truth vs U-Net!`

- [ ] **Step 3: Verify syntax**

Run: `node --check frontend/js/modules/admin.js`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html frontend/js/modules/admin.js
git commit -m "feat(admin): add academic evaluation dashboard and failure cases inspector"
```

---

### Task 6: Clinical Report A4 Presentation of Both Ovaries

**Files:**
- Modify: `frontend/index.html:850-950`
- Modify: `frontend/js/modules/review.js:30-80`
- Test: `node --check frontend/js/modules/review.js`

**Interfaces:**
- Consumes: `window.currentCase.ovary_side`, `window.currentCase.contralateral_status`, `window.currentPrediction`
- Produces: Report table lines for Right Ovary and Left Ovary

- [ ] **Step 1: Update report template in `frontend/index.html`**

In `#reportPrintSheet`, update the findings section:
- Row 1: **Buồng trứng phải (Right Ovary)**:
  - Display lesion dimensions, volume, area, and segmentation confirmation status (if `ovary_side === 'RIGHT'`), or status `Không quan sát được (Not visualized)` (if contralateral).
- Row 2: **Buồng trứng trái (Left Ovary)**:
  - Display lesion dimensions (if `ovary_side === 'LEFT'`), or status `Không quan sát được (Not visualized)` / `Bình thường (Normal)`.

- [ ] **Step 2: Update `frontend/js/modules/review.js`**

In `fillReportData(data)`:
- Bind `#field_ovary_right_finding` and `#field_ovary_left_finding` dynamically based on `window.currentCase.ovary_side` and `window.currentCase.contralateral_status`.

- [ ] **Step 3: Verify syntax**

Run: `node --check frontend/js/modules/review.js`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html frontend/js/modules/review.js
git commit -m "feat(report): format A4 print sheet with explicit two-ovary findings"
```

---

### Task 7: Comprehensive Integration Verification

**Files:**
- Execute: Test suite and server health checks

- [ ] **Step 1: Run all unit and integration tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider`
Expected: All tests PASS (>49 passed, 0 failed).

- [ ] **Step 2: Run syntax verification on all JS files**

Run: `Get-ChildItem -Path frontend/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }`
Expected: 0 errors across all modules.

- [ ] **Step 3: Verify server response**

Run: `(Invoke-WebRequest -Uri "http://localhost:8000/" -UseBasicParsing).StatusCode`
Expected: 200

- [ ] **Step 4: Final Git Status check and commit**

```bash
git status -s
git commit -am "chore(release): complete milestone prototype compliant with 17 clinical thesis criteria"
```
