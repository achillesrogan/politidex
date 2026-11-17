/**
 * Placement for the shared record card.
 * Tailwind preflight sets margin: 0 on every element, which overrides the
 * browser's margin: auto centering of a modal dialog. A dialog then sits at
 * the top-left. These helpers place it from the click and keep it on screen.
 */
export const SHEET_MAX_WIDTH = 800;
export const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function clamp(value, min, max) {
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

export function placeCard({ anchor, card, viewport, margin = 12 }) {
  const vw = Math.max(0, viewport?.width || 0);
  const vh = Math.max(0, viewport?.height || 0);
  const cw = Math.min(Math.max(card?.width || 320, 0), Math.max(0, vw - margin * 2));
  const fullHeight = Math.max(card?.height || 240, 0);
  if (vw > 0 && vw <= SHEET_MAX_WIDTH) {
    const height = Math.min(fullHeight, Math.round(vh * 0.7) || fullHeight);
    return {
      left: margin,
      top: Math.max(margin, vh - height - margin),
      width: Math.max(0, vw - margin * 2),
      mode: "sheet",
    };
  }
  const ax = Number.isFinite(anchor?.x) ? anchor.x : vw / 2;
  const ay = Number.isFinite(anchor?.y) ? anchor.y : vh / 2;
  const left = clamp(ax + 8, margin, vw - cw - margin);
  const top = clamp(ay + 8, margin, vh - fullHeight - margin);
  return { left, top, width: cw, mode: "popover" };
}

export function moveCard({ left, top, dx, dy, card, viewport, margin = 12 }) {
  const vw = Math.max(0, viewport?.width || 0);
  const vh = Math.max(0, viewport?.height || 0);
  const cw = Math.min(Math.max(card?.width || 0, 0), Math.max(0, vw - margin * 2));
  const ch = Math.min(Math.max(card?.height || 0, 0), Math.max(0, vh - margin * 2));
  return {
    left: clamp((Number(left) || 0) + (Number(dx) || 0), margin, vw - cw - margin),
    top: clamp((Number(top) || 0) + (Number(dy) || 0), margin, vh - ch - margin),
  };
}

export function nextFocusIndex(count, current, shift) {
  if (count <= 0) return 0;
  const index = current < 0 || current >= count ? (shift ? 0 : -1) : current;
  if (shift) return index <= 0 ? count - 1 : index - 1;
  return index >= count - 1 ? 0 : index + 1;
}
