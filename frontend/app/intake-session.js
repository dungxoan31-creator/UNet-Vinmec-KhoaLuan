// A request belongs to one account, intake instance, side and exact file selection.
export function createIntakeSession(currentIdentity) {
  const identity = currentIdentity();
  const slots = new Map();
  let disposed = false;
  const active = () => !disposed && currentIdentity() === identity;
  return {
    active,
    select(side, file) {
      slots.get(side)?.controller.abort();
      const selection = { file, controller: new AbortController() };
      slots.set(side, selection);
      return {
        signal: selection.controller.signal,
        current: () => active() && slots.get(side) === selection && !selection.controller.signal.aborted,
      };
    },
    remove(side) {
      slots.get(side)?.controller.abort();
      slots.delete(side);
    },
    dispose() {
      disposed = true;
      for (const selection of slots.values()) selection.controller.abort();
      slots.clear();
    },
  };
}

export function planBilateralDrop(files, suggest) {
  const hints = files.map(file => suggest(file.name));
  const distinct = hints.length === 2 && hints.includes("L") && hints.includes("R");
  return files.map((file, index) => ({
    file,
    side: distinct ? hints[index] : index === 0 ? "L" : "R",
    needsConfirmation: !distinct,
  }));
}

export function intakeSidesReady(files, confirmed, unavailableStatus) {
  const sides = ["L", "R"];
  const imageSides = sides.filter((side) => Boolean(files?.[side]));
  if (imageSides.length === 0) return false;
  return sides.every((side) => {
    if (files?.[side]) return Boolean(confirmed?.[side]) && !unavailableStatus?.[side];
    return ["SURGICALLY_ABSENT", "NOT_VISUALIZED"].includes(unavailableStatus?.[side]);
  });
}
