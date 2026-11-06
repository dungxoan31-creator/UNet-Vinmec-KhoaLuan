# Unified Form Validation and Dynamic CRUD Streamline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide full real-time validation across all clinical and intake form fields with complete CRUD (Create, Edit, Delete) capabilities for patient records, study metadata, and clinical finding tags, delivering a lightning-fast, uncluttered medical UI/UX.

**Architecture:** A lightweight, dependency-free validation module (`form-validator.js`) powers instant field-level verification and inline error micro-copy. In the data layer, `intake-session.js` is expanded with atomic `update` and `delete` primitives for persistent patient stores. In the presentation layer, `intake.js`, `viewer.js`, and `cdss-panel.js` leverage compact action buttons, non-intrusive modal editors, real-time age/phone formatters, dynamic tag additions/removals, and smooth inline feedback without layout shift.

**Tech Stack:** Vanilla ES2022 JavaScript, Web Components/HTML5 Dialog, CSS Custom Properties (Design Tokens), Node.js native test runner (`node:test`, `node:assert/strict`), Playwright browser tests.

**Spec:** [docs/architecture/form-validation-and-crud-spec.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/architecture/form-validation-and-crud-spec.md) (derived from project medical constraints in [AGENTS.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/AGENTS.md) and [DESIGN.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/DESIGN.md)).

## Global Constraints

- Preserve 9-digit ASCII PID constraint (`^[0-9]{9}$`) across all patient records and intake requests.
- Medical terminology and classifications must strictly adhere to ACR O-RADS US v2022, IOTA Simple Rules, and IOTA ADNEX.
- Zero layout shift: validation errors must appear in designated containers without causing jumpy UI or disrupting doctor workflow.
- Backward compatibility: existing DOM query selectors such as `[data-select]`, `[data-action=add-patient]`, `#startSegmentationBtn`, and `#modal form` must be preserved for existing test suites.
- Code style: clean ES modules, no heavy external libraries, resilient fallback for offline/synthetic demo modes.

## Review Focus

1. **Duplicate PID collision on edit vs. create**: When editing patient A, keeping A's own PID must not trigger a duplicate error, but changing PID to an existing patient B's PID must be caught immediately.
2. **Vietnamese phone number normalization**: Non-digit characters (spaces, dashes, dots, country code `+84`) must normalize to standard 10-digit format without rejecting legitimate inputs.
3. **Dynamic birth year to age synchronization**: Changing the birth year must instantly update the displayed age badge and CDSS age field without requiring a form blur or submit action.
4. **Non-blocking consistency warnings**: Medical rule discrepancies (e.g. O-RADS 1 selected while solid component or malignant features are checked) must show soft, actionable warnings instead of hard modal blocks.
5. **Accidental deletion prevention**: Patient and tag deletions must have quick, accessible confirmation (escape-key dismissible, zero-fuss 1-click confirmation) to protect clinical records.

---

### Task 1: Real-time Form Validation Engine (`form-validator.js`)

**Files:**
- Create: `frontend/app/form-validator.js`
- Test: `tests/test_form_validator.mjs`

**Interfaces:**
- Produces:
  - `validatePid(pid: string, options?: { existingPids?: string[], currentPid?: string | null }): { valid: boolean, error: string | null }`
  - `validateFullName(name: string): { valid: boolean, error: string | null }`
  - `validateBirthYear(year: number | string, currentYear?: number): { valid: boolean, error: string | null, age?: number }`
  - `validatePhone(phone: string): { valid: boolean, error: string | null, cleanPhone?: string }`
  - `validateGender(gender: string): { valid: boolean, error: string | null }`
  - `validateHometown(hometown: string): { valid: boolean, error: string | null }`
  - `validateStudyDate(dateStr: string): { valid: boolean, error: string | null }`
  - `validateMeasurement(val: number | string, min?: number, max?: number, label?: string): { valid: boolean, error: string | null }`
  - `attachInlineValidation(formElement: HTMLFormElement, rules: Record<string, Function>, options?: { onValidityChange?: (isValid: boolean) => void }): { validateAll: () => boolean, reset: () => void }`

- [ ] **Step 1: Write the failing test**

Create `tests/test_form_validator.mjs`:
```javascript
import assert from "node:assert/strict";
import test from "node:test";
import {
  validatePid,
  validateFullName,
  validateBirthYear,
  validatePhone,
  validateGender,
  validateHometown,
  validateStudyDate,
  validateMeasurement,
} from "../frontend/app/form-validator.js";

test("validatePid enforces 9 digits and unicity", () => {
  assert.equal(validatePid("100000001", { existingPids: ["100000001"] }).valid, false);
  assert.equal(validatePid("100000001", { existingPids: ["100000001"], currentPid: "100000001" }).valid, true);
  assert.equal(validatePid("12345678", { existingPids: [] }).valid, false);
  assert.equal(validatePid("1234567890", { existingPids: [] }).valid, false);
  assert.equal(validatePid("100000005", { existingPids: ["100000001"] }).valid, true);
});

test("validateBirthYear calculates correct age", () => {
  const res = validateBirthYear(1994, 2026);
  assert.equal(res.valid, true);
  assert.equal(res.age, 32);
  assert.equal(validateBirthYear(1890, 2026).valid, false);
  assert.equal(validateBirthYear(2030, 2026).valid, false);
});

test("validatePhone cleans Vietnamese numbers", () => {
  const res = validatePhone("0912 345 678");
  assert.equal(res.valid, true);
  assert.equal(res.cleanPhone, "0912345678");
  assert.equal(validatePhone("123").valid, false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/test_form_validator.mjs`
Expected: FAIL with "Cannot find module '../frontend/app/form-validator.js'"

- [ ] **Step 3: Implement `frontend/app/form-validator.js`**

Implement deterministic field validators with Vietnamese error messages, inline DOM error injection (`.field-error`), and `aria-invalid` attribute handling.

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/test_form_validator.mjs`
Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/form-validator.js tests/test_form_validator.mjs
git commit -m "feat(validation): implement unified form validator module"
```

---

### Task 2: Patient Store CRUD Operations (`intake-session.js`)

**Files:**
- Modify: `frontend/app/intake-session.js:51-82`
- Test: `tests/test_patient_store_crud.mjs`

**Interfaces:**
- Consumes: `createDemoPatientStore` in `frontend/app/intake-session.js`
- Produces:
  - `store.update(key: string, pid: string, updates: Partial<Patient>): Patient[]`
  - `store.remove(key: string, pid: string): Patient[]`
  - `store.add(key: string, patient: Patient): Patient[]`
  - `store.get(key: string, pid: string): Patient | undefined`

- [ ] **Step 1: Write the failing test**

Create `tests/test_patient_store_crud.mjs`:
```javascript
import assert from "node:assert/strict";
import test from "node:test";
import { createDemoPatientStore } from "../frontend/app/intake-session.js";

function mockStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

test("demo patient store supports update and delete operations", () => {
  const storage = mockStorage();
  const store = createDemoPatientStore(
    [{ pid: "100000001", name: "Nguyễn Minh Anh", age: 32 }],
    () => storage
  );
  const key = "test-patients";

  // Add
  store.add(key, { pid: "100000002", name: "Trần Thu Hà", age: 41 });
  assert.equal(store.read(key).length, 2);

  // Update
  store.update(key, "100000001", { name: "Nguyễn Minh Anh (Đã sửa)", age: 33 });
  const updated = store.get(key, "100000001");
  assert.equal(updated.name, "Nguyễn Minh Anh (Đã sửa)");
  assert.equal(updated.age, 33);

  // Remove
  store.remove(key, "100000002");
  assert.equal(store.read(key).length, 1);
  assert.equal(store.get(key, "100000002"), undefined);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/test_patient_store_crud.mjs`
Expected: FAIL with "store.add is not a function"

- [ ] **Step 3: Implement CRUD operations in `createDemoPatientStore`**

In `frontend/app/intake-session.js`, extend the returned object with `add`, `update`, `remove`, and `get` methods ensuring immutable state updates and storage synchronization.

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/test_patient_store_crud.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/intake-session.js tests/test_patient_store_crud.mjs
git commit -m "feat(store): add atomic add, update, remove methods to patient store"
```

---

### Task 3: UI Icons and Uncluttered Styling (`ui.js`, `workspace.css`)

**Files:**
- Modify: `frontend/app/ui.js:12-45`
- Modify: `frontend/css/workspace.css:555-570`
- Modify: `frontend/css/workstation-premium.css`
- Test: `tests/test_ui_icons.mjs`

**Interfaces:**
- Consumes: SVG paths in `ui.js`
- Produces:
  - `icon("edit")`: SVG path for pencil edit action
  - `icon("trash")`: SVG path for garbage bin delete action
  - CSS classes: `.table-actions-compact`, `.field-error`, `input[aria-invalid="true"]`, `.age-badge-preview`, `.btn.icon-only`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ui_icons.mjs`:
```javascript
import assert from "node:assert/strict";
import test from "node:test";
import { icon } from "../frontend/app/ui.js";

test("ui.js contains edit and trash SVG icons", () => {
  const editSvg = icon("edit");
  const trashSvg = icon("trash");
  assert.match(editSvg, /<svg.*<path/);
  assert.notEqual(editSvg, icon("file"), "edit icon must not fallback to file icon");
  assert.match(trashSvg, /<svg.*<path/);
  assert.notEqual(trashSvg, icon("file"), "trash icon must not fallback to file icon");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/test_ui_icons.mjs`
Expected: FAIL with "edit icon must not fallback to file icon"

- [ ] **Step 3: Implement SVG paths in `ui.js` and styling in `workspace.css`**

1. Add `edit` and `trash` path strings to `paths` dictionary in `frontend/app/ui.js`.
2. Add `.table-actions-compact` (horizontal flex row, gap 6px, vertically centered).
3. Add `.field-error` styling (`color: var(--danger, #ef4444); font-size: 11px; margin-top: 3px; min-height: 16px; display: block;`).
4. Add `input[aria-invalid="true"], select[aria-invalid="true"]` highlight styling.
5. Add `.age-badge-preview` styling (`font-size: 12px; color: var(--muted, #64748b); margin-left: 8px; font-weight: normal;`).

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/test_ui_icons.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/ui.js frontend/css/workspace.css tests/test_ui_icons.mjs
git commit -m "feat(ui): add edit and trash icons with uncluttered form error styles"
```

---

### Task 4: Complete Patient Management (Add, Edit, Delete) & Inline Validation in Intake (`intake.js`)

**Files:**
- Modify: `frontend/app/intake.js:40-100`
- Test: `tests/test_intake_patient_crud.mjs`

**Interfaces:**
- Consumes: `form-validator.js`, `createDemoPatientStore`, `icon`
- Produces:
  - Table action cell with `[data-select]`, `[data-edit-patient]`, and `[data-delete-patient]`
  - Unified Patient Modal for Add and Edit with real-time validation and live age calculation
  - Quick confirmation modal for deletion

- [ ] **Step 1: Write the failing test**

Create `tests/test_intake_patient_crud.mjs`:
```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("intake.js implements edit and delete buttons in patient table", () => {
  const code = fs.readFileSync(path.join(rootDir, "frontend/app/intake.js"), "utf8");
  assert.match(code, /data-edit-patient/, "intake.js must have data-edit-patient buttons");
  assert.match(code, /data-delete-patient/, "intake.js must have data-delete-patient buttons");
  assert.match(code, /validatePid/, "intake.js must import or use validatePid");
  assert.match(code, /form-validator\.js/, "intake.js must import form-validator.js");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/test_intake_patient_crud.mjs`
Expected: FAIL with "intake.js must have data-edit-patient buttons"

- [ ] **Step 3: Implement Edit and Delete in `frontend/app/intake.js`**

1. Import validators from `./form-validator.js`.
2. In `renderList()`, update the table row to include a `.table-actions-compact` cell containing:
   - Primary `Chọn bệnh nhân` button (`data-select="${i}"`)
   - Edit button (`data-edit-patient="${p.pid}"`, title: "Sửa thông tin", icon "edit")
   - Delete button (`data-delete-patient="${p.pid}"`, title: "Xóa hồ sơ", icon "trash")
3. Wire `data-edit-patient`:
   - Fetch patient data, open modal with pre-filled inputs.
   - Attach real-time inline validation (`input` & `blur`).
   - Dynamically compute age as birth year changes.
   - On submit, call `patientsStore.update()` and show toast "Đã cập nhật thông tin bệnh nhân."
4. Wire `data-delete-patient`:
   - Open quick confirmation modal: "Xóa hồ sơ bệnh nhân {name} (PID: {pid})?".
   - On confirm, call `patientsStore.remove()` and show toast "Đã xóa hồ sơ bệnh nhân."
5. Upgrade "Tạo bệnh nhân":
   - Wire `attachInlineValidation()` to check PID (9 digits, unique), full name (2-120 chars), birth year (1900-now), phone, hometown in real-time.

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/test_intake_patient_crud.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/intake.js tests/test_intake_patient_crud.mjs
git commit -m "feat(intake): implement patient edit, delete, and real-time field validation"
```

---

### Task 5: Dynamic Clinical Finding Tags & Non-Blocking Consistency Validation in Workstation Viewer (`viewer.js`)

**Files:**
- Modify: `frontend/app/viewer.js:300-350`
- Test: `tests/test_viewer_custom_chips.mjs`

**Interfaces:**
- Consumes: `state.case`, `icon`
- Produces:
  - Custom tag input (+ Thêm đặc điểm lâm sàng)
  - Removable custom tags (`.chip.custom` with remove button)
  - Non-blocking consistency warning between O-RADS score and morphology chips

- [ ] **Step 1: Write the failing test**

Create `tests/test_viewer_custom_chips.mjs`:
```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("viewer.js provides custom clinical tag management and consistency check", () => {
  const code = fs.readFileSync(path.join(rootDir, "frontend/app/viewer.js"), "utf8");
  assert.match(code, /add-custom-chip|data-action="add-chip"/, "viewer must allow adding custom chips");
  assert.match(code, /remove-custom-chip|data-remove-chip/, "viewer must allow removing custom chips");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/test_viewer_custom_chips.mjs`
Expected: FAIL with "viewer must allow adding custom chips"

- [ ] **Step 3: Implement dynamic custom chips and consistency helper in `viewer.js`**

1. In `viewer.js`, render an inline "+ Thêm đặc điểm" pill input that appends custom tags to `image.customChips`.
2. Allow doctors to click custom chips to toggle active/inactive, or click the small `×` to delete them.
3. Add a lightweight consistency watcher that verifies:
   - If `oradsScore === "O-RADS 1"` and "Dạng đặc" is selected -> display gentle inline warning banner: "Lưu ý: O-RADS 1 thường dành cho tổn thương nang thuần nhất. Vui lòng kiểm tra lại nếu có thành phần đặc."
4. Add a "Làm mới / Đặt lại" button to restore AI default values in one click.

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/test_viewer_custom_chips.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/viewer.js tests/test_viewer_custom_chips.mjs
git commit -m "feat(viewer): support custom clinical finding chips and smart consistency hints"
```

---

### Task 6: CDSS & ADNEX Numeric Boundary Validation & Reset Flow (`cdss-panel.js`, `adnex.js`)

**Files:**
- Modify: `frontend/app/cdss-panel.js:80-120`
- Modify: `frontend/app/adnex.js:55-110`
- Test: `tests/test_cdss_validation_flow.mjs`

**Interfaces:**
- Consumes: `form-validator.js`
- Produces:
  - Real-time range validation: CA-125 (0-100,000), Age (0-130), Diameter (0-500 mm)
  - Logical constraint: `solid_diameter <= max_diameter`
  - "Khôi phục từ AI" (Reset to AI measurements) action button

- [ ] **Step 1: Write the failing test**

Create `tests/test_cdss_validation_flow.mjs`:
```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("adnex and cdss panels enforce numeric ranges and reset capability", () => {
  const adnexCode = fs.readFileSync(path.join(rootDir, "frontend/app/adnex.js"), "utf8");
  const cdssCode = fs.readFileSync(path.join(rootDir, "frontend/app/cdss-panel.js"), "utf8");
  assert.match(adnexCode, /reset-adnex|data-action="reset-adnex"/, "adnex must support reset action");
  assert.match(cdssCode, /validateMeasurement|form-validator/, "cdss must validate numeric boundaries");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/test_cdss_validation_flow.mjs`
Expected: FAIL with "adnex must support reset action"

- [ ] **Step 3: Implement boundary checks and reset actions in `cdss-panel.js` and `adnex.js`**

1. In `adnex.js`, add boundary checks on `ca125_u_ml` and `age_years` with inline helper text.
2. In `cdss-panel.js`, add validation ensuring `solid_component_diameter` does not exceed `max_diameter`.
3. Provide a compact "Đặt lại dữ liệu ban đầu" button to clear user overrides and re-sync with U-Net segmented caliper outputs.

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/test_cdss_validation_flow.mjs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/cdss-panel.js frontend/app/adnex.js tests/test_cdss_validation_flow.mjs
git commit -m "feat(cdss): add numeric boundary validation and reset flow in CDSS and ADNEX panels"
```

---

### Task 7: Full Regression and End-to-End Test Suite Verification

**Files:**
- Modify: `tests/test_frontend_intake_patient_id.mjs` (synchronize test assertion with 9-digit requirement)
- Create: `tests/test_patient_crud_e2e.mjs`

**Interfaces:**
- Verifies: Full end-to-end workflow across intake, patient CRUD, workstation tags, and CDSS validation.

- [ ] **Step 1: Write the end-to-end regression test**

Create `tests/test_patient_crud_e2e.mjs` to simulate adding a new patient, validating inputs, editing patient details, deleting a patient, and selecting a patient to advance to intake.

- [ ] **Step 2: Run all unit and integration tests to ensure zero regression**

Run:
```bash
node tests/test_form_validator.mjs
node tests/test_patient_store_crud.mjs
node tests/test_ui_icons.mjs
node tests/test_intake_patient_crud.mjs
node tests/test_viewer_custom_chips.mjs
node tests/test_cdss_validation_flow.mjs
node tests/test_patient_crud_e2e.mjs
pytest tests/test_pid_nine_digits.py -v
```
Expected: All tests PASS with exit code 0.

- [ ] **Step 3: Fix existing stale assertion in `tests/test_frontend_intake_patient_id.mjs`**

Update `test_frontend_intake_patient_id.mjs` line 52 to align with current 9-digit PID placeholder contract.

- [ ] **Step 4: Run the updated test to verify PASS**

Run: `node tests/test_frontend_intake_patient_id.mjs`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_frontend_intake_patient_id.mjs tests/test_patient_crud_e2e.mjs
git commit -m "test(e2e): verify end-to-end form validation and patient CRUD workflows"
```
