# Work Discovery Web Design System

## 0. Research Log

- Embedded refs: picked operational `taste-skill` because M1-M5 needs a dense task surface, not a marketing page.
- Lazyweb: skipped because the scope is an internal validation UI.
- Imagen drafts: skipped because no branded visual reference is required for M1/M2.

## 1. Atmosphere & Identity

A quiet interview workbench. The signature is a left-to-right operational flow: setup, questions, model, and audit stay visible enough that a tester can understand system state without decoration.

## 2. Color

| Role | Token | Light | Usage |
| --- | --- | --- | --- |
| Surface primary | `--surface-primary` | `#f6f7f9` | Page background |
| Surface panel | `--surface-panel` | `#ffffff` | Tool panels |
| Surface subtle | `--surface-subtle` | `#eef2f6` | Secondary controls |
| Text primary | `--text-primary` | `#17202a` | Main text |
| Text secondary | `--text-secondary` | `#5b6776` | Descriptions |
| Border default | `--border-default` | `#d7dee8` | Panel separators |
| Accent primary | `--accent-primary` | `#1f6feb` | Primary actions |
| Accent hover | `--accent-hover` | `#185abd` | Hover actions |
| Status success | `--status-success` | `#197a45` | Success state |
| Status warning | `--status-warning` | `#98620f` | Warning state |
| Status error | `--status-error` | `#b42318` | Errors |

## 3. Typography

- Primary: system UI stack.
- H1: 28px, 700, line-height 1.2.
- H2: 18px, 700, line-height 1.3.
- Body: 14px, 400, line-height 1.5.
- Caption: 12px, 600, line-height 1.4.

## 4. Spacing & Layout

- Base unit: 4px.
- Main shell: two-column grid above 980px, one-column stack below.
- Panel padding: 16px.
- Control gap: 8px.
- Section gap: 16px.
- Scroll owner: browser document for M1/M2; no nested scrolling.

## 5. Components

### Panel
- Structure: section with heading and body controls.
- States: default only.
- Accessibility: heading names the region.

### Button
- Variants: primary, secondary, danger.
- States: default, hover, disabled.
- Accessibility: native button with visible disabled state.

### Question Row
- Structure: question text, status select, answer textarea, submit action.
- States: unanswered, submitted through answered count, API error at page level.
- Accessibility: textarea labelled by nearby question title.

### JSON Viewer
- Structure: preformatted JSON inside a panel.
- States: empty and loaded.
- Accessibility: preserves readable text contrast and wraps long tokens.

### Metric/List Primitives
- Structure: bordered metric blocks, list blocks, and acceptance-test rows inside operational panels.
- States: empty, loaded, disabled action context.
- Accessibility: CJK copy uses short phrases and structured labels instead of raw JSON strings.

## 6. Motion & Interaction

No decorative animation. Hover changes use color only. Reduced motion has no special branch because there is no non-essential motion.

## 7. Depth & Surface

Strategy: borders-only. Panels use `--border-default`; no shadows.

## 8. Accessibility Constraints & Accepted Debt

- Target: WCAG 2.2 AA contrast for text and controls.
- Every action is a native button.
- Accepted debt: none for M1-M5.
