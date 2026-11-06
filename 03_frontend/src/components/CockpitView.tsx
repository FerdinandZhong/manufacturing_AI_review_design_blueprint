import { t, tNode } from '../i18n'
import { useEffect, useState } from 'react';
import { getProgram, getResults, getRisk } from '../api';
import type { ProgramDetail, RiskResponse, TestResult } from '../api';
import { StageTracker } from './StageTracker';
import { RequirementsTable } from './RequirementsTable';
import { RiskPanel } from './RiskPanel';
import { TraceabilityMatrix } from './TraceabilityMatrix';
import { GateReview } from './GateReview';
import { DecisionControl } from './DecisionControl';
import { RuleBasedSummary } from './RuleBasedSummary';
export function CockpitView({ programId, canWrite = true, reviewReady = true }: {
    programId: string;
    canWrite?: boolean;
    reviewReady?: boolean;
}) {
    const [data, setData] = useState<{
        program: ProgramDetail;
        results: TestResult[];
        risk: RiskResponse;
    } | null>(null);
    const [error, setError] = useState('');
    const [tab, setTab] = useState<'readiness' | 'records'>('readiness');
    const [refresh, setRefresh] = useState(0);
    const [reviewId, setReviewId] = useState<string | null>(null);
    useEffect(() => {
        let active = true;
        Promise.all([getProgram(programId), getResults(programId), getRisk(programId)]).then(([program, results, risk]) => { if (active)
            setData({ program, results, risk }); }).catch(() => { if (active)
            setError('Program summary is unavailable. Check the backend connection.'); });
        return () => { active = false; };
    }, [programId, refresh]);
    return <div className="cockpit-content">
    {tNode(!canWrite && <p className="reader-notice">{t("Workbench RO access permits inspection. RW permission is required to run reviews or record decisions.")}</p>)}
    {tNode(error && <p role="alert" className="reader-notice reader-error">{tNode(error)}</p>)}
    {tNode(data ? <RuleBasedSummary program={data.program} results={data.results}/> : <section className="rule-summary" aria-label={t("Rule-based summary")}><p role="status">{tNode(error ? 'Rule-based summary unavailable.' : 'Loading rule-based summary…')}</p></section>)}
    {tNode(data && <details className="reader-notice"><summary>{t("Engineering details \u00B7")}{tNode(data.program.metrics.open_issues)}{t("open")}{tNode(data.program.metrics.open_issues === 1 ? 'issue' : 'issues')}</summary><p>{t("Design-risk model:")}{tNode(data.program.metrics.high_risk_requirements)}{t("high-risk requirements \u00B7 Recorded workflow status:")}{tNode(data.program.program.gate_status.toLowerCase().replaceAll('_', ' '))}</p><p>{t("Executed coverage:")}{tNode(Math.round(data.program.metrics.executed_coverage.pct * 100))}{t("% \u00B7 Unscored requirements:")}{tNode(data.program.metrics.unscored_requirements)}</p><p>{t("Quantity-weighted BOM cost: $")}{tNode(data.program.metrics.bom_cost.toLocaleString())}{t("\u00B7 BOM mass:")}{tNode(data.program.metrics.bom_mass_kg.toLocaleString())}{t("kg")}</p><p>{t("Corrective actions verified:")}{tNode(data.program.metrics.action_completion.complete)}/{tNode(data.program.metrics.action_completion.total)}</p>{tNode(data.program.issues.map(issue => <p key={issue.issue_id}>{tNode(issue.issue_id)} · {tNode(issue.status)} · {tNode(issue.title)}. {tNode(issue.corrective_action)}{t(". Owner:")}{tNode(issue.owner)}{t(". Verification:")}{tNode(issue.verification_test_id)}.</p>))}<p>{t("Revision history:")}{tNode(data.program.history.map(r => `${r.revision_id}: ${r.change}`).join(' → '))}</p><a href={`/api/programs/${programId}/snapshot`} target="_blank" rel="noreferrer">{t("Inspect snapshot records and observation conditions")}</a></details>)}
    <StageTracker key={refresh} programId={programId}/>
    <nav className="section-tabs" aria-label={t("Program sections")}><button aria-pressed={tab === 'readiness'} onClick={() => setTab('readiness')}>{t("Readiness review")}</button><button aria-pressed={tab === 'records'} onClick={() => setTab('records')}>{t("Requirements & design")}</button><span>{tNode(programId)}{t("\u00B7 Synthetic engineering program")}</span></nav>
    <div hidden={tab !== 'readiness'} className="readiness-layout"><div className="min-w-0 space-y-4"><TraceabilityMatrix programId={programId}/><GateReview canWrite={canWrite && reviewReady} programId={programId} onReviewDone={id => { setReviewId(id); setRefresh(n => n + 1); }}/><DecisionControl key={reviewId} reviewId={canWrite ? reviewId : null} onDecision={() => setRefresh(n => n + 1)}/></div><aside className="min-w-0"><RiskPanel programId={programId}/></aside></div>
    <div hidden={tab !== 'records'}><RequirementsTable programId={programId}/></div>
  </div>;
}
