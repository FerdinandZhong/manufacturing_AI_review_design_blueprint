# English and simplified Chinese

Select **EN** or **简体中文** in the header. The selection persists in the browser.
Switching languages preserves the selected revision, review results, and inspection state.
It does not run another review or model request.

The shared catalog covers application labels, tables, scenario descriptions, evidence captions,
NiFi sample inspections, worker findings, and gate narratives. The backend applies translation
**after** authorization, computation, and the existing narration validation.
Gate rules, risk scores, evidence IDs, measurements, and source files remain unchanged.
Proper names, technical identifiers, units, and original source images remain recognizable.
User-supplied names and arbitrary external source prose require catalog entries for translation;
there is no automatic paid translation call.

## API and MCP

Set `Accept-Language: zh-CN` (or `?lang=zh`) for Chinese JSON and SSE presentation text.
Use `en` for English. Machine keys and status enums remain stable in either language.
Translated objects include `_source_texts` for restoring canonical prose without another request.
Chinese free-text queries select Chinese output when no language is explicitly requested.

- Knowledge search accepts Chinese domain terms, for example `q=热隔离`.
- Engineering record search accepts Chinese labels and domain terms.
- `POST /api/semantic/explain` accepts `{"question":"外部证据是否适用？"}`.
  Supported topics remain thermal risk, packaging, venting, and evidence applicability.
- `POST /api/nifi/ask` accepts `{"question":"哪些处理器无效或已停止？","mode":"sample"}`.
  Live mode uses the same GET-only source reader. Commands and historical-log requests are rejected.
- The MCP server accepts optional `NPI_LANGUAGE=zh`. Chinese search arguments also work without it.
  `CDSW_APIV2_KEY` remains the only authentication credential.

## Translation maintenance

`shared/locales/zh.json` holds labels and complete prose.
`patterns.json` holds variable report sentences. `claims.json` covers the existing accepted AI claim grammar.
Python and TypeScript use the same files. Add new application text to the catalog with its implementation.
Do not translate identifiers or alter source records to change their display language.

Run `python -m pytest 02_backend/tests mcp_server/tests -q` and `npm run build --prefix 03_frontend`.
Use the AMP preparation tasks from a clean checkout to check packaging.

## Verified release

The implementation passed 273 backend and MCP tests and the production frontend build.
Browser checks covered every workspace page, table details, streamed review reports,
semantic explanations, all four NiFi inspection types, and persistent language switching.
Switching languages did not submit another review.

A clean Python 3.11 checkout passed generation, preparation, and the AMP smoke test.
A separate private Workbench AMP installation also completed and started its application.
Its health, identity, test results, risk scores, knowledge search, and Chinese NiFi endpoint passed.
The test application was stopped after verification; its project retains the evidence.
The original vehicle application remains deployed with the bilingual build.

Live API and stdio MCP checks used only `CDSW_APIV2_KEY` for authentication.
Chinese domain queries returned Chinese presentation text with unchanged identifiers and scores.
Missing credentials returned the Workbench login redirect; invalid credentials were rejected.
