// Svelte action for a whitespace-nowrap span inside an overflow:hidden parent.
// Waits two frames so flex layout has settled before measuring.
export function marquee(node) {
  let frame;

  function check() {
    const parent = node.parentElement;
    if (!parent) return;
    const overflow = node.scrollWidth - parent.clientWidth;
    if (overflow > 2) {
      node.style.setProperty('--marquee-px', `-${overflow}px`);
      node.classList.add('marquee-active');
    } else {
      node.style.removeProperty('--marquee-px');
      node.classList.remove('marquee-active');
    }
  }

  function schedule() {
    cancelAnimationFrame(frame);
    // Nest two rAF calls. The first frame starts paint and the second runs after layout settles.
    frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(check);
    });
  }

  schedule();
  window.addEventListener('resize', schedule);

  return {
    destroy() {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', schedule);
    },
  };
}
