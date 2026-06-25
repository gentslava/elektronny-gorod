// Выбор паттерна открытия двери по типу ввода (call-card-ux-spec.md §9).
// slide удобен на тач, неудобен мышью → на десктопе дефолт hold/tap.

export type OpenAction = "slide" | "hold" | "tap";

const EXPLICIT: ReadonlySet<string> = new Set(["slide", "hold", "tap"]);

/**
 * Разрешить open_action.
 * - явное значение (slide|hold|tap) — как задано;
 * - auto / не задано → тач (coarse pointer) = slide, мышь/десктоп = hold.
 */
export function resolveOpenAction(
  configured: string | undefined,
  coarsePointer: boolean,
): OpenAction {
  if (configured && EXPLICIT.has(configured)) {
    return configured as OpenAction;
  }
  return coarsePointer ? "slide" : "hold";
}

/** Тач-устройство (телефон/планшет/настенная панель)? Безопасно вне браузера. */
export function isCoarsePointer(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(pointer: coarse)").matches
  );
}
