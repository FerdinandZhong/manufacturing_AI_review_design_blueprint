# Iceberg source and Lance knowledge-lakehouse enhancement plan

## Goal

Replace the prototype CSV source with governed Iceberg tables in the Cloudera
lakehouse, expose bounded read-only engineering queries through the Cloudera
Iceberg MCP server, and move the Lance knowledge base to durable object
storage with optional Hive Metastore registration. Preserve the rule that code
decides every score, verdict, and gate recommendation; an LLM may request or
summarize evidence but cannot select an uncontrolled query that changes a
decision.

## Target architecture

```text
Engineering systems / approved batch extracts
  → Iceberg tables through Impala
      npi_ref.programs, requirements, design_specs, bom_items,
      suppliers, test_plans, standards_coverage
  → immutable Iceberg snapshot IDs

Vehicle NPI Application
  deterministic source repository
    → fixed, typed Iceberg queries through an MCP bridge
  gate-review workers
    → bounded, allow-listed Iceberg MCP evidence queries
  → SQLite operations store: results, risk scores, reviews, evidence snapshots

Knowledge ingestion
  documents/images → object storage + extracted text/metadata
    → Lance dataset: vectors, multimodal bytes or object URIs, Lance indexes
    → npi_ref.knowledge_assets Iceberg table: searchable metadata, lineage,
      content hash, object URI, Lance asset ID and dataset version
    → optional Hive Metastore external Lance-table registration
```

The Cloudera Iceberg MCP server is an Impala-backed read-only service with
`get_schema()` and `execute_query()` tools. Use it for bounded evidence access
to Iceberg tables, never for writes or ad-hoc database administration.

## Data ownership and table design

Create an Iceberg namespace such as `npi_ref` and ingest these source tables:

| Table | Natural key | Partition / evolution guidance |
| --- | --- | --- |
| `programs` | `program_id` | No partition at demo scale; add program lifecycle/date when volume warrants it. |
| `requirements` | `requirement_id` | Partition only by stable program or release dimensions if selective queries need it. |
| `design_specs` | `spec_id` | Maintain requirement/program foreign keys as data-quality checks. |
| `bom_items` | `bom_item_id` | Partition by program or effective release only after measuring query patterns. |
| `suppliers` | `supplier_id` | Slowly changing supplier attributes need `valid_from`, `valid_to`, and source version. |
| `test_plans` | `test_id` | Include standard IDs and requirement/spec links. |
| `standards_coverage` | `program_id`, `standard_id` | Make compliance coverage explicit rather than inferred from prose. |
| `knowledge_assets` | `asset_id` | Metadata-only Iceberg discovery table; includes object URI, MIME type, checksum, Lance dataset/version, ontology links, and access classification. |

Every ingestion batch records source system, ingestion ID, schema version, and
Iceberg snapshot ID. A gate review stores the snapshot IDs used for source
queries beside its existing evidence payloads. Replaying a review must read
its recorded snapshot, not silently use a later engineering revision.

## Implementation phases

### 1. Lakehouse foundation and contracts

1. Confirm the Impala catalog, Iceberg warehouse location, object-storage
   permissions, encryption, retention, and the service identity used by CAI.
2. Version explicit SQL DDL and data-quality contracts in
   `lakehouse/ddl/`; add primary-key uniqueness, referential integrity,
   allowed-value, and source-freshness checks to the ingestion pipeline.
3. Build an idempotent CSV-to-Iceberg demo loader for the six current source
   tables. It is a bootstrap fixture, not a runtime write path.
4. Add a production ingestion interface for approved extracts or upstream
   CDC/batch feeds. Reject partial loads; publish only a fully validated
   snapshot for a release.
5. Define two data classes: source/reference data in Iceberg is read-only to
   the app; runtime review/decision data remains in the operations store until
   a separate operational-history design is approved.

**Acceptance:** all current CSV rows load to Iceberg without type loss; source
quality checks pass; a recorded snapshot can reproduce the Atlas source views.

### 2. Typed application source repository

1. Replace the current `common/source.py` `iceberg` placeholder with an
   `IcebergSourceRepository`. Keep `csv` as explicit offline/demo fallback and
   `auto` only when a checked configuration selects a healthy backend.
2. Implement typed methods matching the existing source contract:
   `list_programs`, `get_program`, `list_requirements`, `list_design_specs`,
   `list_bom`, `list_test_plans`, and `historical_requirements`.
3. Use fixed SQL templates with validated bound values and explicit projected
   columns. Do not pass user or LLM SQL to the source repository.
4. Capture query identity, parameter values, table versions/snapshot IDs, row
   count, and a canonical payload hash in evidence. Continue converting nulls
   consistently and preserve CSV/Iceberg parity tests.
5. Add a configuration section such as `source.iceberg` for database,
   warehouse, and non-secret connection references. Load passwords/tokens only
   from Workbench secrets or environment variables; never YAML, GitHub logs,
   evidence, or prompts.

**Acceptance:** the deterministic test bench, risk scoring, coverage, and
CONDITIONAL recommendation are identical for CSV and the same Iceberg
snapshot.

### 3. Iceberg MCP bridge for evidence queries

1. Run the official `iceberg-mcp-server` as a client-side stdio process for
   local/CAI Studio use, or use its supported HTTP/SSE transport only after a
   network and authentication review. Pin a tested commit or release rather
   than tracking `main`.
2. Configure `IMPALA_HOST`, `IMPALA_PORT`, `IMPALA_USER`,
   `IMPALA_PASSWORD`, and `IMPALA_DATABASE` through the supported secret
   mechanism. The MCP process receives a least-privilege Impala identity with
   SELECT only on `npi_ref`.
3. Add an internal MCP bridge with a small allow-list of named operations,
   each rendering one fixed query template. Example operations: program
   context, requirement/design join, test-plan coverage, supplier context, and
   historical thermal precedent. Enforce program-ID format, page limits,
   selected columns, timeouts, and result byte limits.
4. Give the agent workers only these named operations. The supervisor's
   decision inputs come from the same typed repository/snapshot, not from
   model-generated SQL or agent prose. MCP results are supplementary evidence
   and must include SQL-template ID and snapshot lineage.
5. Do not expose the Iceberg MCP server's general `execute_query` tool through
   the public NPI MCP adapter. Keep the external adapter's NPI business tools
   bounded and read-only, apart from review creation.

**Acceptance:** a configured agent can inspect schema and retrieve approved
evidence; attempted DDL/DML, cross-namespace reads, oversized results, and
unapproved query templates are rejected. A missing MCP server falls back to
the typed Iceberg repository or offline CSV mode, with an explicit evidence
status rather than fabricated results.

### 4. Lance knowledge base on durable storage and Hive metadata

1. Store Lance dataset roots in governed object storage, for example
   `s3a://<warehouse>/npi_knowledge/lance/assets.lance`, rather than the CAI
   project filesystem. Configure CAI workload identity for that storage.
2. Split metadata from heavy content. Put discovery/lineage fields in
   `npi_ref.knowledge_assets` Iceberg and retain vectors, Lance manifests,
   vector/full-text indexes, and either bytes or object URIs in Lance. For
   large files, keep original binaries in governed object storage and retain
   immutable URI plus checksum in both stores.
3. Evaluate the Lance Hive Namespace implementation against the target Hive
   Metastore version. If compatible, register the Lance root as an
   `EXTERNAL_TABLE` marked `table_type=lance`; HMS then provides namespace,
   discovery, owner, and location metadata for Lance-aware clients.
4. Treat that HMS registration as **catalog metadata**, not an Impala table
   conversion. Impala and the Iceberg MCP server query Iceberg tables; they do
   not perform Lance vector search merely because HMS lists a Lance table.
5. Keep the application KB service on the Lance API for vector retrieval.
   Add a metadata fallback path through Iceberg for catalog filtering and
   governed asset discovery. Return signed/authenticated asset links rather
   than base64 blobs to agents.
6. Add an ingestion manifest that writes an asset only after ontology
   validation, malware/content scan where required, text extraction, embedding
   versioning, Lance write/index completion, and Iceberg metadata publication.
   Never publish Iceberg metadata pointing to an incomplete Lance version.

**Acceptance:** a known Atlas asset resolves from Iceberg metadata to a Lance
dataset/version and original object; vector results remain stable for a pinned
embedding and Lance version; a Hive catalog client can discover the Lance
external table when the namespace integration is enabled.

### 5. Migration, rollout, and operations

1. Run dual-read parity checks (`csv` and pinned Iceberg snapshot) for every
   existing test and the Atlas storyline. Run dual-write only in the build
   loader, never from the application runtime.
2. Gate `source.backend=iceberg` behind an environment-specific feature flag.
   Start with read-only shadow comparisons and record mismatches before using
   Iceberg for the dashboard or gate review.
3. Version and retain Iceberg snapshots, Lance datasets/indexes, embedding
   model IDs, ontology revisions, and review evidence for the required audit
   period. Define legal hold/deletion policy before adding real engineering
   documents.
4. Monitor ingestion freshness, Iceberg query latency/errors, MCP process
   availability, query-denial counts, Lance index freshness, retrieval quality,
   and source/evidence version mismatch. Alert on lineage gaps.
5. Retain the CSV/Lance local fixture mode for workshops and offline tests. A
   rollback from Iceberg returns to the last validated CSV fixture or prior
   pinned Iceberg snapshot; it does not rewrite source data.

## Implementation backlog

1. `lakehouse/ddl/` and a synthetic Iceberg loader with snapshot/parity tests.
2. `common/source_iceberg.py` plus a repository interface and configuration.
3. Internal allow-listed Iceberg MCP bridge and mocked MCP contract tests.
4. Evidence schema extension for source/Lance snapshot lineage.
5. Object-storage Lance configuration, `knowledge_assets` publisher, and
   Hive Namespace proof of concept.
6. CAI secret/environment templates, AMP tasks, CI integration tests, and
   operations runbook.

## Answer: can Lance data go into Hive?

Yes, **as a Lance external table registered in Hive Metastore**, provided the
target environment supports the Lance Hive Namespace implementation. Hive then
stores catalog metadata and the Lance dataset location; it does not transform
Lance into Iceberg/Parquet or make it queryable by Impala SQL. Keep Lance for
vectors and multimodal retrieval, and publish a companion Iceberg metadata
table for Impala, the Iceberg MCP server, governance, and SQL discovery.
