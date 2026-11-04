# Design System

Visual rules for the whole project. The frontend inherits the UOB workspace light theme; the source of truth is the `@theme` block in `03_frontend/src/index.css`.

## Brand chrome

- Pale sidebar and compact header, aligned with the UOB AI Data & Operations Workspace layout.
- Use the local Cloudera wordmark in the sidebar and the orange Cloudera mark for the browser tab.
- Navigation contains Program Cockpit, Knowledge base, Semantic context, NiFi reader, and Models. Search finds these workspace pages.
- Single accent color, locked page-wide: **blue `#2d62df`** (`accent-dim #2356cb`).
- Panels use thin borders without shadows. Only the NiFi composer uses a soft shadow.

## Color tokens (`--color-*`)

| Token | Hex | Use |
|-------|-----|-----|
| `header` | `#152c65` | header bar |
| `surface-0` | `#f7f8fc` | page canvas |
| `surface-1` | `#ffffff` | card / panel |
| `surface-2` | `#f7f8fa` | subtle inset |
| `surface-3` | `#e9edf4` | hairline border |
| `surface-4` | `#d5d9e0` | input border / divider |
| `ink` | `#292f3d` | primary text |
| `ink-muted` | `#667085` | secondary text |
| `ink-faint` | `#748096` | placeholder / meta |
| `accent` / `accent-dim` | `#2d62df` / `#2356cb` | the single brand accent |

## Status colors (semantic — verdicts, risk bands, recommendation)

| Token | Hex | Meaning |
|-------|-----|---------|
| `aml-red` | `#dc2626` | FAIL · HIGH risk · REJECTED |
| `aml-amber` | `#d97706` | MARGINAL · MEDIUM risk · CONDITIONAL · coverage gap |
| `aml-green` | `#059669` | PASS · LOW risk · APPROVED |

> Note: token names carry the `aml-` prefix inherited verbatim from the source AML scaffold. They are invisible to end users (never rendered as text); a rename is deferred Phase-1 debt. New code should use these existing tokens, not introduce parallel ones.

Map status → color consistently everywhere: test verdicts (TraceabilityMatrix cells, TestVerdict findings), ML risk bands (RiskPanel — HIGH must stand out red), and the gate recommendation badge (PASS green / CONDITIONAL amber / FAIL red). The `Badge`/`RiskBadge` component (`src/components/Badge.tsx`) is the canonical renderer.

## Typography

- Sans: **system UI** (`-apple-system`, `BlinkMacSystemFont`, Segoe UI, Arial) (`--font-sans`) — all UI text.
- Mono: **SFMono-Regular / Consolas / Liberation Mono** (`--font-mono`) — IDs, evidence chips, code-like values (req_id, asset_id, test_id).
- Type scale adds `--text-2xs` (11px) for meta labels; otherwise Tailwind's default scale.

## Layout

The workspace uses a sticky sidebar, search header, breadcrumbs, page heading, and bordered white panels.
The cockpit uses a revision/source toolbar, one compact rule-based summary, a lifecycle strip, and underline tabs. The summary contains coverage and test metrics without duplicate metric cards. Engineering details retain workflow status and supplementary metrics. Readiness panels sit beside a narrow risk panel.
Lead the cockpit with a visible Rule-based summary: the backend recommendation, test findings, coverage, and missing test-plan standards. Show the selected revision's scope and human-approval boundary. Keep the rule explanation collapsed. This follows UOB's result/source/scope hierarchy and AML's recommendation-first report with supporting findings. ML risk and AI explanation remain review context outside the gate rule.
Knowledge base is a standalone list of attributed external sources. Synthetic fixtures and duplicate copies are excluded.
At 980 pixels, engineering panels stack. At 600 pixels, navigation becomes a top tab row.
Tables and flow inventories scroll within their panels. The page must not scroll horizontally.

NiFi reader follows UOB’s centered starter questions, compact heading, and bottom composer.
NiFi reader keeps Sample preview and Live NiFi separate. Show loading, empty, and error states explicitly.
Selecting a processor filters its connection list. Label unexpanded endpoints and unknown metrics.
Use semantic status colors for processor health. Never imply that sample flow data supplies engineering decisions.

## Component visual conventions

- **Cards/panels:** `surface-1`, 10px corners, no shadow, `surface-3` hairline.
- **Chips (IDs/evidence):** mono, `surface-2` background, `ink-faint` text.
- **Phase stepper (`PipelineStream`):** active phase = accent fill; done = accent tint; pending = `surface-2`.
- **Gaps/warnings:** amber tint (`aml-amber`) — e.g. the uncovered `REQ-ATLAS-cost` matrix row.

Keep it restrained: one blue interaction accent, semantic status colors only where status is being communicated. Do not introduce new brand colors or a second elevation scale.
