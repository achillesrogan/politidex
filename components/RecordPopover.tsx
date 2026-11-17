"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { FOCUSABLE, moveCard, nextFocusIndex, placeCard } from "@/lib/record-popover.mjs";

type Point = { x: number; y: number };
type Box = { left: number; top: number; width: number; mode: string };

export default function RecordPopover({
  open,
  anchor,
  onClose,
  children,
  label = "Official record",
}: {
  open: boolean;
  anchor?: Point | null;
  onClose: () => void;
  children: React.ReactNode;
  label?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const [box, setBox] = useState<Box | null>(null);

  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (!open) {
      if (dialog.open) dialog.close();
      return;
    }
    if (!dialog.open) {
      trigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    }
    const sheet = window.innerWidth <= 800;
    dialog.classList.toggle("is-sheet", sheet);
    const rect = dialog.getBoundingClientRect();
    const placed = placeCard({
      anchor,
      card: { width: rect.width || 480, height: rect.height || 320 },
      viewport: { width: window.innerWidth, height: window.innerHeight },
    });
    setBox(placed);
  }, [open, anchor]);

  function restoreFocus() {
    const back = trigger.current;
    trigger.current = null;
    if (back && document.contains(back)) back.focus();
  }

  function onDialogClose() {
    restoreFocus();
    onClose();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;
    const dialog = ref.current;
    if (!dialog) return;
    const nodes = [...dialog.querySelectorAll(FOCUSABLE)].filter((node) => node instanceof HTMLElement) as HTMLElement[];
    event.preventDefault();
    const current = nodes.indexOf(document.activeElement as HTMLElement);
    const next = nextFocusIndex(nodes.length, current, event.shiftKey);
    nodes[next]?.focus();
  }

  function nudge(dx: number, dy: number) {
    const dialog = ref.current;
    if (!dialog || !box) return;
    const rect = dialog.getBoundingClientRect();
    setBox({
      ...box,
      ...moveCard({
        left: box.left,
        top: box.top,
        dx,
        dy,
        card: { width: rect.width, height: rect.height },
        viewport: { width: window.innerWidth, height: window.innerHeight },
      }),
    });
  }

  function onHandleKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    const step = event.shiftKey ? 48 : 16;
    if (event.key === "ArrowLeft") { event.preventDefault(); event.stopPropagation(); nudge(-step, 0); }
    if (event.key === "ArrowRight") { event.preventDefault(); event.stopPropagation(); nudge(step, 0); }
    if (event.key === "ArrowUp") { event.preventDefault(); event.stopPropagation(); nudge(0, -step); }
    if (event.key === "ArrowDown") { event.preventDefault(); event.stopPropagation(); nudge(0, step); }
  }

  function onPointerDown(event: React.PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0 || !box) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, left: box.left, top: box.top };
  }

  function onPointerMove(event: React.PointerEvent<HTMLButtonElement>) {
    const start = drag.current;
    const dialog = ref.current;
    if (!start || !dialog || !box) return;
    const rect = dialog.getBoundingClientRect();
    setBox({
      ...box,
      ...moveCard({
        left: start.left,
        top: start.top,
        dx: event.clientX - start.x,
        dy: event.clientY - start.y,
        card: { width: rect.width, height: rect.height },
        viewport: { width: window.innerWidth, height: window.innerHeight },
      }),
    });
  }

  function onPointerUp(event: React.PointerEvent<HTMLButtonElement>) {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  return (
    <dialog
      ref={ref}
      className={"record-popover newspaper-card" + (box?.mode === "sheet" ? " is-sheet" : "")}
      aria-label={label}
      style={box ? { left: box.left, top: box.top, width: box.width } : undefined}
      onClose={onDialogClose}
      onKeyDown={onKeyDown}
      onClick={(event) => {
        if (event.target === ref.current) ref.current?.close();
      }}
    >
      <div className="record-popover-bar">
        <button
          type="button"
          className="record-popover-handle"
          aria-label="Drag record card. Arrow keys move it."
          onKeyDown={onHandleKeyDown}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <span className="record-popover-grip" aria-hidden="true" />
          Drag
        </button>
        <form method="dialog">
          <button type="submit" className="record-popover-close">Close</button>
        </form>
      </div>
      <div className="record-popover-body">{children}</div>
    </dialog>
  );
}
