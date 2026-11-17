import assert from "node:assert/strict";
import test from "node:test";
import { moveCard, nextFocusIndex, placeCard } from "./record-popover.mjs";

test("a card opens near the click and not at the top-left", () => {
  const placed = placeCard({
    anchor: { x: 420, y: 260 },
    card: { width: 480, height: 320 },
    viewport: { width: 1440, height: 900 },
  });
  assert.equal(placed.mode, "popover");
  assert.ok(placed.left > 400 && placed.left < 460);
  assert.ok(placed.top > 250 && placed.top < 300);
  assert.notEqual(placed.left, 0);
  assert.notEqual(placed.top, 0);
});

test("a card is clamped inside the viewport", () => {
  const placed = placeCard({
    anchor: { x: 1400, y: 860 },
    card: { width: 480, height: 360 },
    viewport: { width: 1440, height: 900 },
    margin: 12,
  });
  assert.ok(placed.left >= 12);
  assert.ok(placed.top >= 12);
  assert.ok(placed.left + placed.width <= 1440 - 12);
  assert.ok(placed.top + 360 <= 900 - 12);
});

test("a narrow viewport uses a bottom sheet", () => {
  const placed = placeCard({
    anchor: { x: 40, y: 80 },
    card: { width: 480, height: 600 },
    viewport: { width: 390, height: 844 },
    margin: 12,
  });
  assert.equal(placed.mode, "sheet");
  assert.equal(placed.left, 12);
  const used = Math.min(600, Math.round(844 * 0.7));
  assert.equal(placed.top, 844 - used - 12);
  assert.ok(placed.top >= 12);
});

test("dragging stops at the viewport edge", () => {
  const moved = moveCard({
    left: 40,
    top: 40,
    dx: 5000,
    dy: -5000,
    card: { width: 480, height: 300 },
    viewport: { width: 1440, height: 900 },
    margin: 12,
  });
  assert.equal(moved.left, 1440 - 480 - 12);
  assert.equal(moved.top, 12);
});

test("tab wraps inside the card", () => {
  assert.equal(nextFocusIndex(3, 2, false), 0);
  assert.equal(nextFocusIndex(3, 0, true), 2);
  assert.equal(nextFocusIndex(3, -1, false), 0);
  assert.equal(nextFocusIndex(3, -1, true), 2);
});
