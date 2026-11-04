import { useEffect, useState } from 'react'
import { getProgram, getResults, getRisk } from '../api'
import type { ProgramDetail, RiskResponse, TestResult } from '../api'
import { StageTracker } from './StageTracker'
import { RequirementsTable } from './RequirementsTable'
import { RiskPanel } from './RiskPanel'
import { TraceabilityMatrix } from './TraceabilityMatrix'
import { GateReview } from './GateReview'
import { DecisionControl } from './DecisionControl'
import { RuleBasedSummary } from './RuleBasedSummary'

export function CockpitView({ programId, canWrite = true, reviewReady = true }: { programId: string; canWrite?: boolean; reviewReady?: boolean }) {
  const [data, setData] = useState<{ program: ProgramDetail; results: TestResult[]; risk: RiskResponse } | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'readiness' | 'records'>('readiness')
  const [refresh, setRefresh] = useState(0)
  const [reviewId, setReviewId] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    Promise.all([getProgram(programId), getResults(programId), getRisk(programId)]).then(([program, results, risk]) => { if (active) setData({ program, results, risk }) }).catch(() => { if (active) setError('Program summary is unavailable. Check the backend connection.') })
    return () => { active = false }
  }, [programId, refresh])
  return <div className="cockpit-content">
    {!canWrite && <p className="reader-notice">Workbench RO access permits inspection. RW permission is required to run reviews or record decisions.</p>}
    {error && <p role="alert" className="reader-notice reader-error">{error}</p>}
    {data ? <RuleBasedSummary program={data.program} results={data.results} /> : <section className="rule-summary" aria-label="Rule-based summary"><p role="status">{error ? 'Rule-based summary unavailable.' : 'Loading rule-based summary…'}</p></section>}
    {data && <details className="reader-notice"><summary>Engineering details · {data.program.metrics.open_issues} open {data.program.metrics.open_issues === 1 ? 'issue' : 'issues'}</summary><p>Design-risk model: {data.program.metrics.high_risk_requirements} high-risk requirements · Recorded workflow status: {data.program.program.gate_status.toLowerCase().replaceAll('_', ' ')}</p><p>Executed coverage: {Math.round(data.program.metrics.executed_coverage.pct * 100)}% · Unscored requirements: {data.program.metrics.unscored_requirements}</p><p>Quantity-weighted BOM cost: ${data.program.metrics.bom_cost.toLocaleString()} · BOM mass: {data.program.metrics.bom_mass_kg.toLocaleString()} kg</p><p>Corrective actions verified: {data.program.metrics.action_completion.complete}/{data.program.metrics.action_completion.total}</p>{data.program.issues.map(issue => <p key={issue.issue_id}>{issue.issue_id} · {issue.status} · {issue.title}. {issue.corrective_action}. Owner: {issue.owner}. Verification: {issue.verification_test_id}.</p>)}<p>Revision history: {data.program.history.map(r => `${r.revision_id}: ${r.change}`).join(' → ')}</p><a href={`/api/programs/${programId}/snapshot`} target="_blank" rel="noreferrer">Inspect snapshot records and observation conditions</a></details>}
    <StageTracker key={refresh} programId={programId} />
    <nav className="section-tabs" aria-label="Program sections"><button aria-pressed={tab === 'readiness'} onClick={() => setTab('readiness')}>Readiness review</button><button aria-pressed={tab === 'records'} onClick={() => setTab('records')}>Requirements & design</button><span>{programId} · Synthetic engineering program</span></nav>
    <div hidden={tab !== 'readiness'} className="readiness-layout"><div className="min-w-0 space-y-4"><TraceabilityMatrix programId={programId} /><GateReview canWrite={canWrite && reviewReady} programId={programId} onReviewDone={id => { setReviewId(id); setRefresh(n => n + 1) }} /><DecisionControl key={reviewId} reviewId={canWrite ? reviewId : null} onDecision={() => setRefresh(n => n + 1)} /></div><aside className="min-w-0"><RiskPanel programId={programId} /></aside></div>
    <div hidden={tab !== 'records'}><RequirementsTable programId={programId} /></div>
  </div>
}
