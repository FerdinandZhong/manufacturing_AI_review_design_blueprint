import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

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

export interface ProgramDetail {
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
  asset_id: string
  ontology_class: string
  modality: 'image' | 'pdf' | 'text'
  title: string
  caption_text: string
  program_ref: string
  linked_entity_type: string
  linked_entity_id: string
  score: number
}

export const searchKb = (q: string, cls?: string, k = 3) =>
  api.get<KbHit[]>('/kb/search', { params: { q, cls, k } }).then(r => r.data)

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
  fetch(`/api/review/${pid}/stream?review_id=${encodeURIComponent(reviewId)}`)
    .then(res => streamSSE(res, onEvent))
