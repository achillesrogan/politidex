export const SHEET_MAX_WIDTH: number;
export const FOCUSABLE: string;
export function placeCard(input: {
  anchor?: { x?: number; y?: number } | null;
  card?: { width?: number; height?: number } | null;
  viewport?: { width?: number; height?: number } | null;
  margin?: number;
}): { left: number; top: number; width: number; mode: "sheet" | "popover" };
export function moveCard(input: {
  left: number;
  top: number;
  dx: number;
  dy: number;
  card?: { width?: number; height?: number } | null;
  viewport?: { width?: number; height?: number } | null;
  margin?: number;
}): { left: number; top: number };
export function nextFocusIndex(count: number, current: number, shift: boolean): number;
