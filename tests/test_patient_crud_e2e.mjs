import assert from "node:assert/strict";
import test from "node:test";
import { startIsolatedBrowser } from "./helpers/isolated_browser.cjs";

test("patient directory CRUD persists across browser sessions without local PID or demographic cache", { timeout: 120000 }, async () => {
  const server = await startIsolatedBrowser();
  try {
    const first = await server.browser.newPage();
    const firstErrors = [];
    first.on("pageerror", error => firstErrors.push(error.message));
    await first.goto(server.base + "/#login");
    await first.locator("[name=username]").fill("doctor");
    await first.locator("[name=password]").fill(server.password);
    await first.locator("#authForm button[type=submit]").click();
    await first.waitForFunction(() => location.hash === "#dashboard");
    await first.evaluate(() => { location.hash = "#intake"; });
    await first.locator(".intake-patient-list").waitFor();
    assert.equal(await first.locator("[data-select]").count(), 0, "a new facility has an empty directory");
    assert.equal(await first.locator("[name=pid]").count(), 0, "intake does not ask for or generate a patient ID");

    await first.locator('[data-action="add-patient"]').click();
    assert.equal(await first.locator('#modal [name="birth_year"]').evaluate(input => input.required), false);
    assert.equal(await first.locator('#modal [name="phone"]').count(), 0);
    assert.equal(await first.locator('#modal [name="national_id"]').count(), 0);
    await first.locator('#modal [name="display_name"]').fill("Synthetic Directory Patient");
    await first.locator('#modal [name="birth_year"]').fill("1994");
    await first.locator('#modal button[type=submit]').click();
    await first.locator('#startSegmentationBtn').waitFor();
    assert.equal(await first.locator("[name=pid]").count(), 0);
    await first.locator('[name="patient-age"]').fill("34");
    const createCaseResponse = first.waitForResponse(response =>
      response.url().includes("/api/cases") && response.request().method() === "POST",
    );
    await first.locator('[data-action="create-visit"]').click();
    const createdCase = await (await createCaseResponse).json();
    assert.ok(createdCase.patient_directory_id);
    const createdDirectoryId = createdCase.patient_directory_id;
    assert.equal(createdCase.patient_name, "Synthetic Directory Patient");
    assert.equal(createdCase.patient_age, "34");
    const studyId = createdCase.study_id;
    await first.locator('[data-action="change-patient"]').click();
    await first.locator("[data-edit-patient]").waitFor();
    const patientId = await first.locator("[data-edit-patient]").getAttribute("data-edit-patient");
    assert.equal(patientId, createdDirectoryId);
    assert.ok(patientId);
    assert.equal(await first.evaluate(() => Object.values(localStorage).some(value => value.includes("Synthetic Directory Patient"))), false);

    const second = await server.browser.newPage();
    const secondErrors = [];
    second.on("pageerror", error => secondErrors.push(error.message));
    await second.goto(server.base + "/#login");
    await second.locator("[name=username]").fill("doctor");
    await second.locator("[name=password]").fill(server.password);
    await second.locator("#authForm button[type=submit]").click();
    await second.waitForFunction(() => location.hash === "#dashboard");
    await second.evaluate(() => { location.hash = "#intake"; });
    const patientRow = second.locator(".intake-patient-list tr").filter({ hasText: "Synthetic Directory Patient" });
    await patientRow.waitFor();
    await patientRow.locator("[data-edit-patient]").click();
    await second.locator('#modal [name="display_name"]').fill("Synthetic Directory Patient Updated");
    await second.locator('#modal button[type=submit]').click();
    await second.locator(".intake-patient-list").getByText("Synthetic Directory Patient Updated").waitFor();
    const updatedRow = second.locator(".intake-patient-list tr").filter({ hasText: "Synthetic Directory Patient Updated" });
    await updatedRow.locator("[data-delete-patient]").click();
    await second.locator('#modal button[type=submit]').click();
    await second.locator(".intake-patient-list").getByText("Chưa có hồ sơ trong danh bạ.").waitFor();
    const directLookup = await second.evaluate(async id => {
      const token = sessionStorage.getItem("ova.token");
      const response = await fetch(`/api/patient-directory/${encodeURIComponent(id)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.status;
    }, patientId);
    assert.equal(directLookup, 404, "deactivated directory records are absent from normal lookups");
    const preservedCase = await second.evaluate(async id => {
      const token = sessionStorage.getItem("ova.token");
      const response = await fetch(`/api/cases/${encodeURIComponent(id)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return { status: response.status, body: await response.json() };
    }, studyId);
    assert.equal(preservedCase.status, 200);
    assert.equal(preservedCase.body.patient_directory_id, patientId);
    assert.equal(preservedCase.body.patient_age, "34");
    const legacyKey = await second.evaluate(async () => {
      const token = sessionStorage.getItem("ova.token");
      const user = await fetch("/api/auth/current-user", { headers: { Authorization: `Bearer ${token}` } }).then(response => response.json());
      const key = `ova.demo-patients.v1.${encodeURIComponent(user.id)}`;
      localStorage.setItem(key, JSON.stringify([{ name: "Legacy synthetic record", national_id: "synthetic-only" }]));
      localStorage.setItem("ova.preference.audit-test", "keep");
      return key;
    });
    await second.locator("#accountMenu").click();
    await second.locator('[data-action="logout"]').click();
    await second.waitForFunction(() => location.hash === "#login");
    assert.equal(await second.evaluate(key => localStorage.getItem(key), legacyKey), null);
    assert.equal(await second.evaluate(() => localStorage.getItem("ova.preference.audit-test")), "keep");
    assert.deepEqual(firstErrors, []);
    assert.deepEqual(secondErrors, []);
  } finally {
    await server.close();
  }
});
