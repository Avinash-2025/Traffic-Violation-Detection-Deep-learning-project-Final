---
name: Sentinel Vanguard Design System
description: High-density mission-critical dark surveillance workstation UI
colors:
  bg-deep: "#0b0e14"
  bg-panel: "#10141d"
  bg-card: "#161c27"
  bg-elevated: "#1c2331"
  border-subtle: "rgba(255, 255, 255, 0.07)"
  border-focus: "rgba(16, 185, 129, 0.45)"
  primary-emerald: "#10b981"
  primary-emerald-hover: "#059669"
  accent-violet: "#8b5cf6"
  accent-violet-hover: "#7c3aed"
  alert-crimson: "#ef4444"
  text-primary: "#f1f5f9"
  text-secondary: "#94a3b8"
  text-muted: "#64748b"
typography:
  display:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: "JetBrains Mono, SF Mono, Menlo, monospace"
    fontSize: "0.75rem"
    fontWeight: 600
rounded:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "14px"
  xl: "18px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary-emerald}"
    textColor: "{colors.bg-deep}"
    rounded: "{rounded.pill}"
    padding: "9px 20px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.pill}"
    padding: "9px 20px"
---

# Design System & Visual Principles

## Aesthetics & Mode
- **Mode**: Operate (Mission-critical Command Center / Control Room).
- **Theme**: Obsidian Night with Emerald & Electric Violet highlights.
- **Tone**: Focused, restrained, high-density, authoritative. Avoid decorative glows, gratuitous animations, and AI-typical gradient text.
- **Contrast**: Strict adherence to WCAG AA standards with clear legibility against dark slate surfaces.

