import { t, tNode } from '../i18n'
import { CheckCircle2, CircleAlert, ShieldCheck } from 'lucide-react';
import type { ProgramDetail, TestResult } from '../api';
const OUTCOMES: Record<string, string> = {
    PASS: 'Ready for gate approval',
    CONDITIONAL: 'Release conditions need attention',
    FAIL: 'Release criteria are not met',
};
export function RuleBasedSummary({ program, results }: {
    program: ProgramDetail;
    results: TestResult[];
}) {
    const { metrics, coverage } = program;
    const recommendation = metrics.prepared ? metrics.recommendation : null;
    const failed = results.filter(result => result.verdict === 'FAIL').length;
    const marginal = results.filter(result => result.verdict === 'MARGINAL').length;
    const missing = metrics.missing_standards;
    const checks = [
        { label: 'Validation tests', clear: failed === 0 && marginal === 0,
            value: `${failed} failed · ${marginal} marginal`,
            detail: `${results.length} computed test results reviewed` },
        { label: 'Requirement coverage', clear: coverage.gaps.length === 0,
            value: `${Math.round(coverage.pct * 100)}% · ${coverage.traced} of ${coverage.total} covered`,
            detail: coverage.gaps.length ? `${coverage.gaps.length} requirements need design or test links` : 'Every requirement has design and test links' },
        { label: 'Required standards', clear: missing.length === 0,
            value: missing.length ? `${missing.length} standards missing from test plans` : 'All required standards linked',
            detail: missing.length ? missing.join(' · ') : 'No gaps in required test-plan standards' },
    ];
    return <section className="rule-summary" aria-labelledby="rule-summary-title" data-recommendation={recommendation || 'UNREADY'}>
    <header className="rule-summary-header">
      <div><p className="rule-summary-label"><ShieldCheck size={15}/>{t("Rule-based summary")}</p>
        <h2 id="rule-summary-title">{tNode(recommendation ? OUTCOMES[recommendation] || recommendation : 'Prepared results are required')}</h2>
        <p>{tNode(recommendation ? 'Computed from test results, requirement coverage, and required standards.' : 'Prepare current results for this revision before assessing release readiness.')}</p>
      </div>
      <span className="rule-summary-verdict">{tNode(recommendation || 'NOT PREPARED')}</span>
    </header>
    {tNode(recommendation && <ul className="rule-summary-checks" aria-label={t("Gate rule findings")}>{tNode(checks.map(check => <li key={check.label}>
      {tNode(check.clear ? <CheckCircle2 size={17} className="rule-check-clear"/> : <CircleAlert size={17} className="rule-check-attention"/>)}
      <div><span>{tNode(check.label)}</span><strong>{tNode(check.value)}</strong><p>{tNode(check.detail)}</p></div>
    </li>))}</ul>)}
    <footer className="rule-summary-footer">
      <details><summary>{t("How the recommendation is determined")}</summary>
        <p>{tNode(metrics.definitions.recommendation)}</p>
        <p>{t("ML risk and AI explanations provide additional review context. They do not enter the gate rule.")}</p>
      </details>
      <span>{tNode(metrics.observation_count)}{t("seeded observations \u00B7 Human approval required")}</span>
    </footer>
  </section>;
}
