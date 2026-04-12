"use client";

import React, { useEffect } from "react";
import { useFocusMode } from "@/lib/context/SystemContext";

/* ══════════════════════════════════════════════════════════════
   FOCUS MODE — Distraction-Free Deep Work Toggle
   
   Effects: hides sidebar, reduces gradients/grain to zero,
   expands content full-width, minimal SystemStateBar.
   Toggle: ⌘. (Cmd+Period) or via SystemStateBar icon.
   ══════════════════════════════════════════════════════════════ */

export function FocusModeController() {
  const [focusMode, toggleFocus] = useFocusMode();

  // Keyboard shortcut: ⌘. / Ctrl+.
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        e.preventDefault();
        toggleFocus();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleFocus]);

  // Apply focus mode classes to the root
  useEffect(() => {
    const root = document.documentElement;
    if (focusMode) {
      root.setAttribute("data-focus", "true");
    } else {
      root.removeAttribute("data-focus");
    }
    return () => root.removeAttribute("data-focus");
  }, [focusMode]);

  // No visual output — this is a controller
  return null;
}

/* CSS for focus mode (added to globals.css via data-focus attribute) */
// [data-focus="true"] is handled by the Sidebar and SystemStateBar
// components reading focusMode from context.
