"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function moduleContext(name, globals) {
    const context = vm.createContext({console, ...globals});
    const source = fs.readFileSync(path.join(__dirname, "../frontend/js/modules", name), "utf8");
    vm.runInContext(source, context, {filename: name});
    return context;
}

async function testFailedCaseOpenPreservesActiveMask() {
    const active = {maskReady: true, image_id: "active-image", confirmed: true};
    const message = {textContent: ""};
    const context = moduleContext("cases.js", {
        currentCase: active,
        canReplaceCase: () => true,
        apiJson: async () => { throw new Error("Connection lost"); },
        $: id => id === "casesMessage" ? message : null,
        showToast: () => {},
    });
    await context.openCaseInWorkstation("another-study");
    assert.equal(active.maskReady, true, "A failed open cannot disable the current case");
    assert.match(message.textContent, /Connection lost/);
}

async function testReviewNeedsPersistedIdentity() {
    const rle = {shape: [512, 512], counts: [512 * 512], first_val: 0};
    const active = {maskReady: true, saving: false, study_id: "study", image_id: "image"};
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, {
            value: "", disabled: false, textContent: "", classList: {add() {}, remove() {}}, close() {},
        });
        return elements.get(id);
    };
    let savedMessage = "";
    const context = moduleContext("review.js", {
        currentCase: active, currentRole: "DOCTOR", currentUser: {username: "doctor"},
        currentPrediction: {rle_mask: rle, prediction_id: "prediction"},
        reviewStartedAt: null, performance: {now: () => 1},
        $: element, showError: (_id, message) => { savedMessage = message; }, showToast: () => {},
        apiJson: async () => ({status: "SUCCESS", image_id: "image"}),
    });
    context.encodeCurrentMask = () => rle;
    context.sameMask = () => true;
    context.getSurveyFeedback = () => null;
    context.syncReviewUI = () => {};
    await context.executeDoctorSignOff();
    assert.notEqual(active.confirmed, true, "Missing review_id cannot be shown as persisted");
    assert.match(savedMessage, /review|lưu/i);
}

async function testCanvasPointerStaysAlignedAfterWindowResize() {
    const nodes = new Map();
    const element = id => {
        if (!nodes.has(id)) nodes.set(id, {
            id, style: {}, hidden: false, clientWidth: 400, clientHeight: 400,
            listeners: {}, addEventListener(type, callback) { this.listeners[type] = callback; },
            append() {}, setAttribute() {}, setPointerCapture() {},
        });
        return nodes.get(id);
    };
    const canvas = element("editorCanvas");
    canvas.getContext = () => ({});
    canvas.getBoundingClientRect = () => {
        const side = parseFloat(canvas.style.width || "400") * 2;
        return {left: 20, top: 30, width: side, height: side};
    };
    const windowListeners = {};
    const context = moduleContext("viewer.js", {
        $: element, currentCase: {maskReady: true, sourceDimensions: [512, 512]},
        currentZoom: 2, panOffsetX: 0, panOffsetY: 0,
        currentTool: "brush", isSpacePressed: false, isPanning: false,
        isCalibratingTwoPoints: false, isDrawing: false,
        lastX: 0, lastY: 0,
        document: {createElement: () => element("curtainHandle"), querySelector: () => null},
        window: {addEventListener: (type, callback) => { windowListeners[type] = callback; }},
        ResizeObserver: class { observe() {} },
        setTimeout, clearTimeout,
    });
    context.clearMeasurements = () => {};
    context.syncReviewUI = () => {};
    let painted;
    context.paintOnMask = (x, y) => { painted = [x, y]; };
    context.setupCanvasEngine();
    element("editablePane").clientWidth = 200;
    element("editablePane").clientHeight = 200;
    assert.equal(typeof windowListeners.resize, "function", "Window resize must refresh canvas layout");
    windowListeners.resize();
    await new Promise(resolve => setTimeout(resolve, 180));
    assert.equal(canvas.style.width, "200px");
    assert.match(canvas.style.transform, /scale\(2\)/);
    canvas.listeners.pointerdown({button: 0, pointerId: 1, clientX: 220, clientY: 230,
        preventDefault() {}, shiftKey: false});
    assert.deepEqual(painted, [256, 256], "Brush coordinates must use the resized, zoomed rect");
}

async function testSpaceRespectsDialogAndSaving() {
    const listeners = {}, canvas = {style: {cursor: 'none'}};
    let dialogOpen = true, prevented = false;
    const context = moduleContext('navigation.js', {
        window: {location: {origin: 'http://localhost'},
            addEventListener: (type, callback) => { listeners[type] = callback; }},
        document: {querySelector: () => dialogOpen ? {} : null},
        activeRoute: 'results', currentCase: {saving: false, maskReady: true},
        isSpacePressed: false, isPanning: false, currentTool: 'brush', canvas,
    });
    vm.runInContext("activeRoute = 'results'", context);
    context.setupKeyboardShortcuts();
    const space = {code: 'Space', key: ' ', target: {closest: () => null},
        preventDefault: () => { prevented = true; }};
    listeners.keydown(space);
    assert.equal(prevented, false, 'Space must keep native button behavior inside a modal');
    assert.equal(context.isSpacePressed, false);
    dialogOpen = false;
    context.currentCase.saving = true;
    listeners.keydown(space);
    assert.equal(prevented, false, 'Saving must disable the pan shortcut');
    context.currentCase.saving = false;
    listeners.keydown(space);
    assert.equal(prevented, true);
    assert.equal(context.isSpacePressed, true, 'Space still enables pan in the active viewer');
    listeners.keyup(space);
    assert.equal(context.isSpacePressed, false);
}

(async () => {
    const failures = [];
    for (const test of [testFailedCaseOpenPreservesActiveMask, testReviewNeedsPersistedIdentity,
        testCanvasPointerStaysAlignedAfterWindowResize, testSpaceRespectsDialogAndSaving]) {
        try { await test(); }
        catch (error) { failures.push(error); console.error(error); }
    }
    if (failures.length) process.exitCode = 1;
    else console.log("PASS: frontend review state guards");
})().catch(error => { console.error(error); process.exitCode = 1; });
