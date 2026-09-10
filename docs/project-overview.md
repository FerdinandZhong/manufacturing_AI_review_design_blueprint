# Project Overview

## The problem this answers

Manufacturers running a New Product Introduction (NPI) program have single-point AI tools at every stage but **no platform that chains them with shared context, full traceability, requirement↔design↔test version linkage, and knowledge reuse**. That gap — the defining *agentic* value proposition — is what this blueprint demonstrates, grounded in a real connected-vehicle manufacturer's pain (`车联网AI研讨(1).md`).

## What it is

A presentation-grade, **deterministic** agentic NPI-lifecycle platform, concretized on a new EV battery-pack program. It mirrors the `../anti_money_laundry_blueprint` (AML) architecture and philosophy, swapping the domain to automotive/manufacturing.

One seeded showcase program (`PACK-ATLAS-01`) plus two historical programs (`PACK-ORION-00`, `PACK-VEGA-00`) drive a scripted lifecycle, a marquee agentic **Gate Review** with human-in-the-loop, and a Program Cockpit dashboard — all over real, versioned, traceable, partly-multimodal data.

## The lifecycle

```
REQUIREMENTS → DESIGN → ENGINEERING(BOM) → VALIDATION(DVP&R) → GATE_REVIEW → RELEASED
```
The showcase is pre-seeded through VALIDATION; the live action is the Gate Review. Stage progression is a scripted state machine (`agents/state_machine.py`) — legal transitions only, no LLM in the driver's seat.

## The headline moment

A traditional **ML design-risk model** flags the thermal requirement **HIGH**. Independently, the deterministic **test bench** computes one **MARGINAL** thermal DVP&R result. ML prediction corroborated by measured reality. Click **Run Gate Review** → a swarm of 5 read-only agents audits the program (the DesignRisk agent explains the ML score in plain language; the KnowledgeReuse agent retrieves a prior program's multimodal design image + test report from the Lance store, guided by the ontology). The supervisor produces a **code-computed CONDITIONAL** recommendation with a traceability matrix; a human makes the final gate call.

## Core principles

- **Code decides, LLM narrates** — deterministic outputs by construction; LLM confined to prose with a template fallback (runs offline).
- **Two-store split** — read-only CSV source (Iceberg-ready seam) / mutable SQLite ops / Lance multimodal+ontology KB.
- **Data is the demo** — the value is in seeded, linked, traceable, multimodal data, not in prompt cleverness.

## Scope (Phase 1 — shipped)

CSV source + SQLite ops + Lance KB; deterministic test bench + traceability + `decide()`; sklearn design-risk model; ontology layer; 5-agent SSE gate review; FastAPI backend; React Dashboard A; CAI AMP packaging.

**Explicitly out of Phase 1 (Phase 2+):** Iceberg-via-MCP source backend (seam present, raises "not configured"), Dashboard B (Engineering Ops), richer multimodal/CLIP embeddings, live lifecycle artifact generation. See [TODO.md](TODO.md).

## Tech stack

Python 3.11 · FastAPI · Uvicorn · pandas · numpy · scikit-learn (`GradientBoostingClassifier`, CPU-only) · pylance/Lance (multimodal store, precomputed hashing-fallback embeddings) · pyyaml · OpenAI-compatible LLM client (CAII/vLLM/Ollama) · React 19 · Vite · Tailwind 4.

## Related docs

[architecture.md](architecture.md) · [user-guide.md](user-guide.md) · [demo_storyline.md](demo_storyline.md) · [../AGENTS.md](../AGENTS.md)
