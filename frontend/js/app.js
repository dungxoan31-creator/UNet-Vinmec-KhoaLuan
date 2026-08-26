/**
 * VINMEC OVARIAN ULTRASOUND AI SYSTEM - MAIN APPLICATION ENTRY POINT
 * Orchestrates modules, event listeners, and initial lifecycle loading.
 */

document.addEventListener('DOMContentLoaded', async () => {
    console.log('[Vinmec AI] Application Initializing...');

    // 1. Check & Prompt for Local Draft Recovery
    if (typeof checkDraftOnLoad === 'function') {
        checkDraftOnLoad();
    }

    // 2. Load User Profile & Header Info
    if (typeof loadCurrentUser === 'function') {
        await loadCurrentUser();
    }

    // 3. Load Dashboard Statistics & Recent Clinical Cases
    if (typeof loadDashboardStats === 'function') {
        loadDashboardStats();
    }
    if (typeof loadDashboardCases === 'function') {
        loadDashboardCases();
    }

    // 4. Initialize Drag & Drop Handlers
    if (typeof setupDragAndDrop === 'function') {
        setupDragAndDrop();
    }

    // 5. Initialize Canvas Interactive Engine
    if (typeof setupCanvasEngine === 'function') {
        setupCanvasEngine();
    }

    // 6. Register Global Keyboard Shortcuts (Ctrl+Z, Ctrl+Y, 1-4, etc.)
    if (typeof setupKeyboardShortcuts === 'function') {
        setupKeyboardShortcuts();
    }

    // 7. Handle Initial URL Hash Routing (e.g. #admin, #history, #workspace)
    const initialHash = window.location.hash.replace('#', '') || (window.location.pathname === '/admin' ? 'admin' : 'dashboard');
    if (typeof navigateTo === 'function') {
        navigateTo(initialHash);
    }

    console.log('[Vinmec AI] System Ready.');
});
