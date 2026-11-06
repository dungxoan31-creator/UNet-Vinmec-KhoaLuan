export function getReportShortcutHash(event, studyId) {
  if (
    !event ||
    typeof studyId !== "string" ||
    !studyId ||
    String(event.key).toLowerCase() !== "p" ||
    !(event.ctrlKey || event.metaKey) ||
    event.shiftKey ||
    event.altKey ||
    event.isComposing
  )
    return null;

  const target = event.target;
  if (
    target?.isContentEditable ||
    target?.closest?.("input, textarea, select, [contenteditable]")
  )
    return null;

  return `#report/${encodeURIComponent(studyId)}?print=1`;
}

export function isOverlayToggleShortcut(event) {
  if (
    !event ||
    String(event.key).toLowerCase() !== "o" ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.isComposing
  )
    return false;

  const target = event.target;
  if (
    target?.isContentEditable ||
    target?.closest?.("input, textarea, select, [contenteditable]")
  )
    return false;

  return true;
}

export function isFastAdvanceShortcut(event) {
  if (
    !event ||
    String(event.key).toLowerCase() !== "enter" ||
    !event.shiftKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.isComposing
  )
    return false;

  const target = event.target;
  if (
    target?.isContentEditable ||
    target?.closest?.("input, textarea, select, [contenteditable]")
  )
    return false;

  return true;
}

export function isHelpShortcut(event) {
  if (
    !event ||
    event.key !== "?" ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.isComposing
  )
    return false;

  const target = event.target;
  if (
    target?.isContentEditable ||
    target?.closest?.("input, textarea, select, [contenteditable]")
  )
    return false;

  return true;
}



export function getOradsShortcutValue(event) {
  if (!event || event.isComposing) return null;
  const target = event.target;
  if (
    target?.isContentEditable ||
    target?.closest?.("input, textarea, select, [contenteditable]")
  )
    return null;

  const key = String(event.key);
  if (event.altKey && ["0", "1", "2", "3", "4", "5"].includes(key)) {
    return `O-RADS ${key}`;
  }
  if (!event.ctrlKey && !event.metaKey && ["1", "2", "3", "4", "5"].includes(key)) {
    return `O-RADS ${key}`;
  }
  return null;
}

export function isAutoZoomShortcut(event) {
  if (
    !event ||
    String(event.key).toLowerCase() !== "a" ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.isComposing
  )
    return false;

  const target = event.target;
  if (
    target?.isContentEditable ||
    target?.closest?.("input, textarea, select, [contenteditable]")
  )
    return false;

  return true;
}

export function isUndoShortcut(event) {
  if (
    !event ||
    String(event.key).toLowerCase() !== "z" ||
    event.isComposing ||
    event.altKey
  )
    return false;

  const target = event.target;
  if (
    target?.isContentEditable ||
    target?.closest?.("input, textarea, select, [contenteditable]")
  )
    return false;

  return true;
}
