# Demo Storyline

Scripted presenter narrative for the marquee Gate Review demonstration. Estimated run time: 8–12 minutes for the full flow; 4–5 minutes for the accelerated version (skip §3 and §5).

---

## Setup (before the audience arrives)

```bash
python 02_backend/scripts/prepare.py   # one-time; idempotent
python start_app.py                    # keeps running; http://localhost:8100
```

Open the browser to **http://localhost:8100**. The cockpit loads `PACK-ATLAS-01` automatically. No login, no state to reset — the page is always in the pre-gate-review state on first load (gate review has not been run yet).

---

## §1 — Set the scene (1 min)

> "We're looking at a new EV battery-pack program — PACK-ATLAS-01. The engineering team has completed requirements, design, and validation. The program is now at its release gate. As program manager, I need to decide: do we release, hold, or reject?"

Point at the **Stage Tracker** across the top:

> "The lifecycle runs requirements → design → engineering → validation → gate review → released. PACK-ATLAS-01 has been pre-seeded through validation. The live step is the gate review."

---

## §2 — Show the data story (2 min)

**Left panel — Requirements and Design.**

> "Five requirements: range, energy density, thermal management, safety, and cost. Each has a design spec linked to it. The BOM tab shows the bill of materials — 17 line items, supplier quality ratings included."

**Left panel — Design Risk (ML signal).**

> "Now here's something interesting. We trained a traditional ML model on two historical programs. It's a gradient-boosted classifier — trained on features like spec margin, BOM cost, thermal flag, and safety flag. It scored every requirement for PACK-ATLAS-01."

Point at the risk list. The thermal row is at the top, highlighted red.

> "Thermal management scores HIGH risk. The model is saying: based on everything we've seen before, this requirement is the one most likely to fail at validation. The feature importance bars below explain why — the 'is_thermal' flag and the spec margin dominate."

**Center panel — Traceability Matrix.**

> "Independent of the ML model, our deterministic test bench computed the DVP&R results from the design specs. Look at the thermal row — verdict is MARGINAL. The measured thermal margin came in at +3%, which is above zero but below our 10% threshold."

Pause for effect.

> "The ML model predicted HIGH risk. The actual test came back MARGINAL. Two entirely separate computations — one predictive, one measured — agree. That's the corroboration story."

**Make the two signals explicit (use when the audience asks how they relate).**

> "For this prototype, the DVP&R result is a deterministic simulation of a lab result. The test bench takes the seeded measured value — 103 degC for Atlas thermal — and compares it with the 100 degC target. That gives a +3% margin. Our engineering rule calls margins from zero up to, but not including, 10% MARGINAL. This is the factual test signal in the demo; in production, the same interface would read an actual lab or validation-system result."

> "The ML model does not receive the test verdict as an input. It predicts risk from the requirement, design, BOM, and supplier feature vector: target value, design value, margin, cost, mass, supplier quality, and thermal and safety flags. It was trained only on the historical Orion and Vega programs, where the thermal requirements failed. Atlas is held out as the demo program, so its HIGH score is a prediction rather than a replay of its own test outcome."

> "That separation matters. The model provides an early-warning signal; the test bench computes the validation fact. The gate function then reads the deterministic evidence, including coverage and standards, to recommend CONDITIONAL. The LLM explains the result but cannot change any of those values."

Point at the cost row (amber highlight):

> "There's also a coverage gap — the cost requirement has a design spec but no test plan. Four of five requirements have test coverage; cost does not."

---

## §3 — Knowledge reuse panel (1 min, skip in accelerated run)

**Right panel — Knowledge Cards.**

> "Before we run the gate review, notice the knowledge panel on the right. It's queried for assets related to thermal requirements — and it found two assets from a prior program: a design image and a test report. The ontology tells the system what each asset *is* and how it *links* — that DesignImage illustrates a thermal requirement; that TestReport evidences a thermal test plan. This is knowledge reuse: the team can see how a past program handled the same risk before making their call."

---

## §4 — Run the Gate Review (3 min)

> "Now let's run the gate review."

Click **Run Gate Review**.

Five agent worker cards appear and begin streaming:

> "Five specialist agents fan out in parallel. Each one reads the program data, logs a hashed evidence record for audit traceability, calls an LLM to articulate its finding, and reports back."

Walk through each card as it completes:

- **coverage** — "The coverage agent found that four of five requirements trace all the way through to a test. One gap: the cost requirement."
- **testverdict** — "The test-verdict agent summarized the DVP&R results. It flagged the thermal test as MARGINAL — it passed, but only barely."
- **compliance** — "The compliance agent checked our required EV-battery standards: UN 38.3, GB 38031, IEC 62660. It reports which are covered."
- **designrisk** — "The design-risk agent explained the ML score in plain language — HIGH probability on thermal, citing the is_thermal feature and the thin margin."
- **knowledgereuse** — "The knowledge-reuse agent retrieved that prior thermal asset from the Lance multimodal store and cited it by ontology class and ID."

When the **CONDITIONAL** badge appears:

> "The recommendation is CONDITIONAL — not a FAIL, because no test actually failed and coverage is at 80%. But the MARGINAL thermal test, the coverage gap, and the missing standard hold it back from a clean PASS. Critically: this value is computed by code, not generated by the LLM. Same data, same answer, every single run."

The narrative streams beneath:

> "The LLM's job is only to write the prose summary — it narrates, it doesn't decide."

---

## §5 — Human gate decision (1 min, skip in accelerated run)

> "The platform puts a human in the loop. The decision control activates once the review completes."

Select **APPROVED_WITH_CONDITIONS**, add a short rationale ("Close thermal margin — re-test after thermal interface material swap"), enter a name, and click **Submit**.

> "The decision is persisted. The gate review is finalized. The program state advances to RELEASED. The annotation — who decided, when, and why — is part of the permanent audit trail."

---

## §6 — Wrap (30 sec)

> "What you just saw: a traditional ML model and an independent deterministic test bench independently flagging the same risk. A five-agent swarm that explains, retrieves, and audits — but never decides. A human making the final call with full traceability. That's the agentic NPI lifecycle platform."

---

## Common questions

**"What if the LLM is down?"** — The gate review still runs. Each agent has a deterministic template fallback. The recommendation, verdicts, and risk scores are unaffected (they're computed, not generated). The narrative falls back to a template paragraph. The ~80s stream time collapses to a few seconds.

**"Can you change the outcome?"** — Yes, by changing the data. Edit `data_generation/generate_synthetic_data.py` to make the thermal test PASS (margin ≥ 0.10) and re-run `prepare.py`. The recommendation becomes PASS. The ML model will also re-score if the historical programs' data changes. The formula and the model are not touched — only the data.

**"Where does the LLM run?"** — Configured in `config/config.yaml`: CAII endpoint, vLLM, or Ollama. Offline mode uses templates automatically.

**"Is this real manufacturing data?"** — No. Everything is synthetic, seeded, and deterministic. The use case (EV battery-pack NPI, APQP gates, DVP&R, thermal margin) is real; the specific numbers are designed so the demo tells a clean story every time.
