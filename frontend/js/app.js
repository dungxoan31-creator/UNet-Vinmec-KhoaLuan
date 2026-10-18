/** Initialize only the segmentation and human-review workflow. */
document.addEventListener('DOMContentLoaded', async () => {
    setupDragAndDrop();
    setupCanvasEngine();
    setupKeyboardShortcuts();
    $('confirmSignoffModal').addEventListener('cancel', e => { if (currentCase.saving) e.preventDefault(); });
    await loadCurrentUser();
    navigateTo(location.hash.slice(1) || 'home');
});
