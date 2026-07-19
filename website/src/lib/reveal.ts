// Появление секций при скролле. Уважает prefers-reduced-motion:
// в этом случае всё видно сразу, без переходов.

export function initReveal(): void {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const targets = document.querySelectorAll<HTMLElement>("[data-reveal]");
  if (reduced || !("IntersectionObserver" in window)) {
    targets.forEach((el) => el.classList.add("in"));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          (e.target as HTMLElement).classList.add("in");
          io.unobserve(e.target);
        }
      }
    },
    { rootMargin: "0px 0px -10% 0px", threshold: 0.08 },
  );
  targets.forEach((el) => io.observe(el));
}
