# Knowledge retrieval and OCR v3

The knowledge index uses a fixed offline encoder. It never discovers or downloads an embedding model.

The `token-hash-v2` contract specifies SHA-256 token hashing, 128 dimensions, Unicode word tokens, float32 values, and L2 normalization. Each Lance row stores this contract. Search rejects missing or different contracts. The API returns HTTP 503 with `incompatible_knowledge_index`. Run `python 02_backend/scripts/prepare.py` to rebuild older indexes. Existing configurations without `knowledge` use the offline default.

Build-time extraction reads source bytes. UTF-8 text, JSON sections, PDF pages, and SVG text elements produce stable chunks. Each chunk contains its asset ID, source SHA-256, page, section, offset, and extraction method. Indexed OCR metadata retains its model, prompt, schema, preprocessing, cache identity, and structured transcription. Extraction status distinguishes missing cache, invalid cache, no visible text, and unsupported PDF pages. PDF extraction accepts at most 20 MB and 100 pages. Pages without text report a scanned or partial state. PDF raster OCR remains unsupported. SVG text is markup extraction, not pixel evidence. Raster images produce chunks only from a validated OCR cache. Captions remain searchable metadata. Captions never substitute for extracted image text.

Search applies program, revision, evidence type, and requirement scope before ranking. It combines lexical overlap and offline token-hash similarity. Hash collisions alone cannot produce a hit. Punctuation, stopwords, and absent terms return no hits. Metadata matches can return an asset without supporting extracted text. Returned chunks must share substantive query terms. Asset-level search remains compatible with existing MCP callers.

```text
Source bytes -> build-time extraction -> stable chunks -> Lance assets
                                                       |
Query -> scope filter -> lexical + vector ranking ------+
                                                       |
                                      cited source text + applicability
```

The knowledge worker derives queries from the highest-risk requirements. Retrieval adds context to the semantic packet. It never changes test verdicts, risk scores, coverage, or gate recommendations. Image similarity is unavailable because no image encoder is configured.

Semantic model prose uses a bounded cited-claim grammar. Each sentence binds one fact citation to its subject, property, exact value, and unit. Supported claims cover the Atlas thermal result, risk band, thermal target, and external experiment count. Source claims use an approved caption or a generic reference label. Unknown prose, negation, new quantities, and mismatched citations cause deterministic fallback. The server appends a deterministic applicability boundary to accepted prose. This conservative grammar does not claim general natural-language entailment.

Review workers may select or reorder complete authoritative statements. The gate narrator buffers the response before validation. Invalid partial model output never reaches the event stream. These guards intentionally restrict free-form narration.

## Optional build-time image OCR

OpenAI OCR uses exactly `gpt-6-luna` through the official Responses endpoint. Requests use strict structured output, `store=false`, reasoning effort `none`, a bounded image, bounded output, a timeout, and zero retries. A live one-image smoke test passed on 2026-11-03 using the official endpoint and a credential loaded from the user-selected local file. The test made one request, returned HTTP 200, validated the structured output, replayed the cache without a key, and indexed the transcription. All six visible panel headings in `RES-experiment-7` matched. Visual review also found a numeric error: the top-left legend prints `500°C`, while OCR returned `90°C`. The API/cache integration passed, but the transcription is not verified and must not supply engineering measurements.

1. Set `OPENAI_API_KEY` in the process environment.
2. Select one local source image.
3. Run `python 02_backend/scripts/build_image_ocr.py IMAGE --allow-paid-openai-ocr`.
4. Run `python 02_backend/scripts/prepare.py` to index the cached transcription.

For keyless offline replay, run `python 02_backend/scripts/build_image_ocr.py IMAGE` without the paid flag. A cache miss exits with a clear error and makes no network request. Missing files and missing credentials also produce CLI errors without tracebacks.

Only step 3 authorizes a paid request. It sends at most one image request. A valid cache replays without a key. Normal preparation and runtime search never call paid OCR. The program never stores or prints the key. SDK failures return redacted errors.

The cache identity covers source bytes, exact model, prompt, schema, preprocessing, and request bounds. Cache validation checks the identity, digest, structured result, dimensions, and flattened text. Atomic publication prevents partial cache files. Corrupt caches fail closed. No automatic paid replacement occurs. `no_visible_text` forbids text and tables, including hidden table titles.

OCR remains an unverified transcription. It cannot establish measurements, source authenticity, acceptance, compliance, or a gate decision. External research retains its original applicability limits. The OCR cache is a build artifact under `data/kb/ocr_cache` by default.

The API exposes `/api/kb/readiness`. The knowledge UI shows retrieval support, chunk locators, extraction methods, source hashes, and OCR limits.

Official OpenAI documentation: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).


## Review score interpretation and final report

Gate Review exposes two independent score signals. The traditional model's `risk_prob` is displayed as a predicted risk percentage, with its risk band, requirement, model version, and scoring completeness. It is an uncalibrated output from the small synthetic training cohort. A score of 100% does not establish 100% confidence in correctness. Feature rankings are global model importance, not local causal attributions.

Knowledge Reuse displays the top retrieved assets, their relevance on a 0–1 scale, their source applicability, and unverified OCR status. Relevance is `0.7 × lexical overlap + 0.3 × token-hash cosine similarity`. It measures query matching rather than evidence truth. Each hit retains the component scores. No-hit and missing-model states display unavailable values rather than manufactured confidence. Neither score signal changes the gate decision.

These assessments accompany `worker_done` SSE events and persist in `gate_reviews.worker_results` with evidence IDs. The completed UI leads with the review summary and score overview; supporting findings and score calculations are expandable. The final narrative covers the recommendation, its computed reasons, model/evidence context, and the source-defined corrective action and verification test. It remains useful offline. Model output is checked before display and must preserve every authoritative statement.
