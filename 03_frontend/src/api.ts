import axios from 'axios'

export const api = axios.create({ baseURL: '/api', headers: { 'X-NPI-Request': '1' } })
export interface RuntimeStatus { mode: 'demo' | 'pilot'; authorization: string; identity: { actor: string; permission: 'RO' | 'RW'; authentication: string }; source_ready: boolean; review_ready: boolean; risk_status: string; source: {state: string; provider: string; detail: string; source_id?: string; revision_id?: string; snapshot_id?: string; extracted_at?: string; provenance?: string; freshness?: string } }
export const getRuntimeStatus = () => api.get<RuntimeStatus>('/runtime/status').then(r => r.data)

// ── programs ────────────────────────────────────────────────────────────────

export interface Program {
  program_id: string
  name: string
  vehicle_platform: string
  target_market: string | null
  stage: string
  gate_status: string
}

export interface Coverage {
  total: number
  traced: number
  gaps: string[]
  pct: number
}

export interface MatrixRow {
  req_id: string
  category: string
  spec_id: string | null
  test_id: string | null
  verdict: string | null
}

export interface Matrix {
  program_id: string
  rows: MatrixRow[]
}

export interface SharedMetrics { snapshot_id: string; revision_id: string; recommendation: string | null; prepared: boolean; missing_standards: string[]; definitions: Record<string, string>; tests_needing_attention: number; high_risk_requirements: number; observation_count: number; open_issues: number; unscored_requirements: number; bom_cost: number; bom_mass_kg: number; executed_coverage: Coverage; action_completion: {complete: number;total: number} }
export interface ProgramDetail {
  issues: {issue_id:string;title:string;status:string;corrective_action:string;owner:string;verification_test_id:string}[]
  history: {revision_id:string;change:string}[]
  metrics: SharedMetrics
  identity: { snapshot_id: string; revision_id: string }
  program: Program
  coverage: Coverage
  matrix: Matrix
}

export interface Requirement {
  req_id: string
  program_id: string
  category: string
  text: string
  target_value: number | null
  unit: string | null
  priority: string
  source: string
  status: string
}

export interface DesignSpec {
  spec_id: string
  program_id: string
  req_id: string
  parameter: string
  value: number | null
  unit: string | null
  rationale: string
  cell_chemistry: string | null
  version: string
}

export interface BomItem {
  part_id: string
  program_id: string
  spec_id: string
  name: string
  supplier_id: string
  qty: number
  unit_cost: number
  mass_kg: number
}

export interface TestPlan {
  test_id: string
  program_id: string
  req_id: string
  method: string
  standard: string
  pass_criteria: string
  target_value: number | null
  unit: string | null
}

export interface TestResult {
  result_id: string
  test_id: string
  program_id: string
  measured_value: number | null
  verdict: 'PASS' | 'MARGINAL' | 'FAIL'
  computed_by: string
  run_at: string
}

export interface RiskScore {
  program_id: string
  entity_type: string
  entity_id: string
  model_version: string
  risk_prob: number
  risk_band: 'LOW' | 'MEDIUM' | 'HIGH'
  top_features: string[]
  scored_at: string
}

export interface FeatureImportance {
  feature: string
  importance: number
}

export interface RiskResponse {
  scores: RiskScore[]
  explanation: FeatureImportance[]
}

export const getPrograms = () =>
  api.get<Program[]>('/programs').then(r => r.data)

export const getProgram = (pid: string) =>
  api.get<ProgramDetail>(`/programs/${pid}`).then(r => r.data)

export const getRequirements = (pid: string) =>
  api.get<Requirement[]>(`/programs/${pid}/requirements`).then(r => r.data)

export const getDesign = (pid: string) =>
  api.get<DesignSpec[]>(`/programs/${pid}/design`).then(r => r.data)

export const getBom = (pid: string) =>
  api.get<BomItem[]>(`/programs/${pid}/bom`).then(r => r.data)

export const getTests = (pid: string) =>
  api.get<TestPlan[]>(`/programs/${pid}/tests`).then(r => r.data)

export const getResults = (pid: string) =>
  api.get<TestResult[]>(`/programs/${pid}/results`).then(r => r.data)

export const getRisk = (pid: string) =>
  api.get<RiskResponse>(`/programs/${pid}/risk`).then(r => r.data)

export const getMatrix = (pid: string) =>
  api.get<Matrix>(`/programs/${pid}/matrix`).then(r => r.data)

// ── knowledge base / ontology ───────────────────────────────────────────────

export interface KbHit {
  evidence_kind?: string
  provenance?: string
  source_url?: string
  license_url?: string
  asset_id: string
  ontology_class: string
  modality: 'image' | 'pdf' | 'text'
  title: string
  caption_text: string
  program_ref: string
  linked_entity_type: string
  linked_entity_id: string
  score: number
  retrieval?: { method: string; matched_terms: string[]; chunks: { chunk_id: string; page: number; section: string; text: string; source_sha256: string; extraction_method: string; verification: string }[] }

}

export const searchKb = (q: string, cls?: string, k = 3, externalOnly = false, programId?: string, evidenceKind = 'all') =>
  api.get<KbHit[]>('/kb/search', { params: { q, cls, k, external_only: externalOnly, program_id: programId, evidence_kind: evidenceKind } }).then(r => r.data)

export const assetUrl = (id: string) => `/api/asset/${id}`

export interface Relation { from: string; rel: string; to: string }
export interface Ontology { classes: string[]; relations: Relation[] }

export const getOntology = () =>
  api.get<Ontology>('/ontology').then(r => r.data)

// ── gate review (agents, SSE) ───────────────────────────────────────────────

export interface GateReviewRow {
  review_id: string
  program_id: string
  state: string
  recommendation: string | null
  narrative: string | null
  decided_by: string | null
  decision: string | null
  created_at: string
}

export type ReviewDecision = 'APPROVED' | 'APPROVED_WITH_CONDITIONS' | 'REJECTED'

export const postDecision = (
  reviewId: string,
  body: { decision: ReviewDecision; rationale?: string; adjudicator?: string },
) => api.post<GateReviewRow>(`/review/${reviewId}/decision`, body).then(r => r.data)

/** Read a `data: {json}\n\n` SSE response and invoke onEvent per parsed event.
 *  Buffers across chunk boundaries so split lines don't drop events. */
export async function streamSSE(
  res: Response,
  onEvent: (e: Record<string, unknown>) => void,
) {
  if (!res.body) return
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''          // keep the trailing partial line
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (!raw || raw === '[DONE]') continue
      try { onEvent(JSON.parse(raw)) } catch { /* ignore malformed frame */ }
    }
  }
}

export const streamReview = (
  pid: string,
  reviewId: string,
  onEvent: (e: Record<string, unknown>) => void,
) =>
  fetch(`/api/review/${pid}/stream?review_id=${encodeURIComponent(reviewId)}`, { headers: { 'X-NPI-Request': '1' } })
    .then(res => { if (!res.ok) throw new Error(`Review failed (${res.status})`); return streamSSE(res, onEvent) })

export interface LlmModel {
  id: number
  alias: string
  provider: string
  model_identifier: string
  api_base: string | null
  api_key: string        // masked from the server
  is_active: number
}

export interface RegisterModelBody {
  alias: string
  provider: string
  model_identifier: string
  api_base?: string
  api_key?: string
}

export const getLlmModels = () =>
  api.get<{ models: LlmModel[] }>('/config/llm/models').then(r => r.data.models)

export const registerLlmModel = (body: RegisterModelBody) =>
  api.post('/config/llm/models', body).then(r => r.data)

export const activateLlmModel = (id: number) =>
  api.post(`/config/llm/models/${id}/activate`).then(r => r.data)

export const updateLlmModel = (id: number, body: RegisterModelBody) =>
  api.put(`/config/llm/models/${id}`, body).then(r => r.data)

export const testLlmModel = (id: number) =>
  api.post<{ ok: boolean; message: string }>(`/config/llm/models/${id}/test`).then(r => r.data)

export interface NifiSnapshot {
  mode: 'sample' | 'live'
  group_id: string
  name: string
  refreshed: string
  processors: { id: string; name: string; state: string; validation: string; type: string; threads: number | null }[]
  connections: { id: string; source: string; target: string; relationships: string[]; queued: number | null }[]
  bulletins: { id: string; source: string; level: string; timestamp: string; message: string }[]
  metrics: { queued: number | null; bytes_queued: number | null; active_threads: number | null; received: number | null }
  limitations: string[]
}
export const getNifiConfig = () => api.get<{ configured: boolean; group_id: string; read_only: boolean }>('/nifi/config').then(r => r.data)
export const getNifiSnapshot = (mode: 'sample' | 'live', signal?: AbortSignal) => api.get<NifiSnapshot>('/nifi/snapshot', { params: { mode }, signal }).then(r => r.data)

export interface SemanticAsset {
  id: string; title: string; modality: 'image' | 'pdf' | 'text'; caption: string
  locator: string; source_url: string; sha256: string; mime_type: string; experiment_ids: string[]; author?: string; license?: string; license_url?: string; applicability?: string; state?: string
}
export interface Experiment {
  source_id: string; experiment_id: string; method: string; chemistry: string
  peak_cell_temperature_c: number | null; total_gas_mol: number | null; initial_voltage_v: number | null; locator: string
}
export interface SemanticEdge { id: string; from: string; to: string; label: string; kind: string; rule: string }
export interface SemanticNode { id: string; label: string; kind: string; source: string; key: string; description: string; column: number; row: number; records: unknown; grain: string; origin: string }
export interface SemanticContext {
  model: { version: string; name: string; status: string; questions: { id: string; title: string; description: string; enabled: boolean; missing_source: string }[]; concepts: { id: string; label: string; definition: string; boundary: string; aliases: string[] }[]; metrics: { id: string; label: string; formula: string; unit: string; grain: string; boundary: string }[] }
  packet: { facts: { id: string; label: string; value: string; source: string; origin: string }[]; constraints: string[]; reference: { title: string; attribution: string; license_url: string; source_url: string; source_id: string }; [key: string]: unknown }
  context_sha256: string
  graph: { nodes: SemanticNode[]; edges: SemanticEdge[] }
  research_state: string
  source_states: { id: string; state: string }[]
  active_edges: string[]
  evidence: SemanticAsset[]
  measurements: Experiment[]
  steps: { label: string; detail: string }[]
}
export interface SemanticAnswer extends SemanticContext {
  answer: string; narration: string; note: string; image_inputs: string[]; prompt: unknown; answer_sha256: string
}
export const getSemanticContext = (questionId: string, signal?: AbortSignal, programId = 'PACK-ATLAS-01') => api.get<SemanticContext>('/semantic/context', { params: { question_id: questionId, program_id: programId }, signal }).then(r => r.data)
export const explainSemanticContext = (questionId: string, narration: 'template' | 'model', includeImages: boolean, signal?: AbortSignal, programId = 'PACK-ATLAS-01') => api.post<SemanticAnswer>('/semantic/explain', { question_id: questionId, narration, include_images: includeImages, program_id: programId }, { signal }).then(r => r.data)
export const semanticAssetUrl = (id: string) => `/api/semantic/assets/${encodeURIComponent(id)}`

export interface KnowledgeReadiness {
  index: { state: string; detail?: string }
  embedding: { version: string; model: string; dimension: number }
  ocr: { state: string; credential_validated: boolean; reason: string }
  image_similarity: { state: string; detail: string }
}
export const getKnowledgeReadiness = () => api.get<KnowledgeReadiness>('/kb/readiness').then(r => r.data)
