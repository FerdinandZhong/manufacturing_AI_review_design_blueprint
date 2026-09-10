# Design System

Visual rules for the whole project. The frontend inherits the Cloudera Applied-ML-Prototype light theme; the source of truth is the `@theme` block in `03_frontend/src/index.css`.

## Brand chrome

- Deep-indigo header bar (`#1c0f43`) with a burnt-orange accent underline, "CLOUDERA" wordmark + app name ("Vehicle NPI Platform" / "Agentic NPI lifecycle · Cloudera AI Applied ML Prototype").
- Single accent color, locked page-wide: **burnt orange `#e35b1f`** (`accent-dim #c94e18`).
- One elevation only — `--shadow-soft` — used on cards/panels; no competing shadow scales.

## Color tokens (`--color-*`)

| Token | Hex | Use |
|-------|-----|-----|
| `header` | `#1c0f43` | header bar |
| `surface-0` | `#f4f5f7` | page canvas |
| `surface-1` | `#ffffff` | card / panel |
| `surface-2` | `#f7f8fa` | subtle inset |
| `surface-3` | `#e3e6ea` | hairline border |
| `surface-4` | `#d5d9e0` | input border / divider |
| `ink` | `#1a1a2e` | primary text |
| `ink-muted` | `#6b7280` | secondary text |
| `ink-faint` | `#9aa1ac` | placeholder / meta |
| `accent` / `accent-dim` | `#e35b1f` / `#c94e18` | the single brand accent |

## Status colors (semantic — verdicts, risk bands, recommendation)

| Token | Hex | Meaning |
|-------|-----|---------|
| `aml-red` | `#dc2626` | FAIL · HIGH risk · REJECTED |
| `aml-amber` | `#d97706` | MARGINAL · MEDIUM risk · CONDITIONAL · coverage gap |
| `aml-green` | `#059669` | PASS · LOW risk · APPROVED |

> Note: token names carry the `aml-` prefix inherited verbatim from the source AML scaffold. They are invisible to end users (never rendered as text); a rename is deferred Phase-1 debt. New code should use these existing tokens, not introduce parallel ones.

Map status → color consistently everywhere: test verdicts (TraceabilityMatrix cells, TestVerdict findings), ML risk bands (RiskPanel — HIGH must stand out red), and the gate recommendation badge (PASS green / CONDITIONAL amber / FAIL red). The `Badge`/`RiskBadge` component (`src/components/Badge.tsx`) is the canonical renderer.

## Typography

- Sans: **Inter** (`--font-sans`) — all UI text.
- Mono: **JetBrains Mono** (`--font-mono`) — IDs, evidence chips, code-like values (req_id, asset_id, test_id).
- Type scale adds `--text-2xs` (11px) for meta labels; otherwise Tailwind's default scale.

## Layout

Single-page "Program Cockpit": Cloudera header on top → StageTracker → a multi-column body (left: Requirements/Design + RiskPanel; center: TraceabilityMatrix + GateReview + DecisionControl; right: KnowledgeCards). Cards are `surface-1` on a `surface-0` canvas with `surface-3` hairlines and `shadow-soft`.

## Component visual conventions

- **Cards/panels:** `surface-1`, rounded, `shadow-soft`, `surface-3` hairline.
- **Chips (IDs/evidence):** mono, `surface-2` background, `ink-faint` text.
- **Phase stepper (`PipelineStream`):** active phase = accent fill; done = accent tint; pending = `surface-2`.
- **Gaps/warnings:** amber tint (`aml-amber`) — e.g. the uncovered `REQ-ATLAS-cost` matrix row.

Keep it restrained: one accent, one shadow, semantic status colors only where status is being communicated. Do not introduce new brand colors or a second elevation scale.
