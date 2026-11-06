import { t, tNode } from '../i18n'
import React from 'react';
import { Loader2, CheckCircle2, MinusCircle, AlertTriangle } from 'lucide-react';
import { WorkflowGraph, type WorkflowNode } from './WorkflowGraph';
import { assetUrl } from '../api';
export type WorkerAssessment = {
    kind: 'model_risk';
    score: number | null;
    entity_id: string | null;
    risk_band: string | null;
    model_version: string | null;
    scored_requirements: number;
    high_risk_requirements: number;
    calibration: string;
    note: string;
    feature_basis: string;
} | {
    kind: 'retrieval';
    query: string;
    method: string;
    note: string;
    hits: {
        asset_id: string;
        title: string;
        score: number;
        lexical_score: number;
        vector_score: number;
        evidence_kind: string;
        support: string;
        ocr_unverified: boolean;
    }[];
};
export function AssessmentDetails({ assessment }: {
    assessment: WorkerAssessment;
}) {
    if (assessment.kind === 'model_risk')
        return <div className="assessment-panel" aria-label={t("Traditional ML score")}>
    <div className="assessment-score"><span>{t("Model predicted risk")}</span><strong>{tNode(assessment.score == null ? 'Unavailable' : `${(assessment.score * 100).toFixed(1)}%`)}</strong><span>{tNode(assessment.risk_band ? `${assessment.risk_band} risk` : 'No score')}</span></div>
    <p>{tNode(assessment.entity_id)} · {tNode(assessment.high_risk_requirements)}{t("HIGH /")}{tNode(assessment.scored_requirements)}{t("scored requirements")}</p>
    <p className="assessment-note">{tNode(assessment.note)}</p>
    <details><summary>{t("Model and score interpretation")}</summary><p>{t("Model version:")}{tNode(assessment.model_version || 'Unavailable')}</p><p>{tNode(assessment.feature_basis)}</p><p>{t("Model confidence calibration: not validated.")}</p></details>
  </div>;
    return <div className="assessment-panel" aria-label={t("Retrieval relevance scores")}>
    <p className="assessment-note">{t("Relevance score \u00B7 0\u20131 scale.")}{tNode(assessment.note)}</p>
    {tNode(assessment.hits.length ? <ol className="retrieval-score-list">{tNode(assessment.hits.map(hit => <li key={hit.asset_id}>
      <div><a href={assetUrl(hit.asset_id)} target="_blank" rel="noreferrer">{tNode(hit.title)}</a><small>{tNode(hit.evidence_kind.replaceAll('_', ' '))} · {tNode(hit.support)}{tNode(hit.ocr_unverified ? ' · Unverified OCR' : '')}</small></div><strong aria-label={`Relevance ${hit.score.toFixed(3)}`}>{tNode(hit.score.toFixed(3))}</strong>
    </li>))}</ol> : <p>{t("No relevant evidence found. No retrieval confidence score is assigned.")}</p>)}
    <details><summary>{t("Query and score calculation")}</summary><p>{tNode(assessment.query)}</p><p>{tNode(assessment.method)}</p>{tNode(assessment.hits.map(hit => <p key={hit.asset_id}>{tNode(hit.asset_id)}{t(": lexical")}{tNode(hit.lexical_score.toFixed(3))}{t("\u00B7 vector")}{tNode(hit.vector_score.toFixed(3))}</p>))}</details>
  </div>;
}
/** One row in a streamed pipeline — a worker (investigation) or a step (retrain). */
export interface PipelineItem {
    key: string;
    label: string;
    status: 'running' | 'ok' | 'skip' | 'error';
    detail?: string; // worker findings (bullet lines) or step detail
    chips?: string[]; // evidence ids
    assessment?: WorkerAssessment;
    mono?: boolean; // render label mono (console character)
}
/** One verification verdict for a factual claim (from the MCP verification worker). */
export interface Verdict {
    claim: string;
    verdict: 'confirmed' | 'refuted' | 'unverified' | string;
    sources: string[];
}
interface Props {
    phases: string[]; // ordered phase names for the stepper
    activePhase: string | null;
    items: PipelineItem[];
    narrative?: string;
    narrativeTitle?: string;
    running?: boolean;
    idle?: React.ReactNode; // shown before the first run
    graphNodes?: WorkflowNode[]; // optional live DAG rendered above the phase stepper
    verdicts?: Verdict[]; // verification verdicts, rendered as a card before the narrative
}
/** Minimal markdown renderer: **bold**, numbered section headers, bullet lines. No deps. */
export const Md: React.FC<{
    text: string;
    running?: boolean;
}> = ({ text, running }) => {
    const bold = (s: string): React.ReactNode[] => s.split(/\*\*(.+?)\*\*/g).map((p, i) => i % 2 === 1 ? <strong key={i}>{tNode(p)}</strong> : p as React.ReactNode);
    return (<div className="text-xs text-ink leading-relaxed space-y-0.5">
      {tNode(text.split('\n').map((line, i, arr) => {
            const cursor = running && i === arr.length - 1
                ? <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-accent/70 align-middle animate-pulse"/>
                : null;
            if (line === '')
                return <div key={i} className="h-1"/>;
            if (/^\d+\.\s/.test(line))
                return <p key={i} className="font-semibold text-ink mt-2 first:mt-0">{tNode(bold(line))}{tNode(cursor)}</p>;
            if (line.startsWith('- '))
                return <p key={i} className="pl-3">{tNode(bold(line.slice(2)))}{tNode(cursor)}</p>;
            return <p key={i}>{tNode(bold(line))}{tNode(cursor)}</p>;
        }))}
    </div>);
};
const VERDICT_STYLE: Record<string, string> = {
    confirmed: 'text-aml-green bg-aml-green/10',
    refuted: 'text-aml-red bg-aml-red/10',
    unverified: 'text-amber-600 bg-amber-500/10',
};
const STATUS: Record<PipelineItem['status'], {
    cls: string;
    icon: React.ReactNode;
}> = {
    running: { cls: 'text-accent', icon: <Loader2 className="w-3.5 h-3.5 animate-spin"/> },
    ok: { cls: 'text-aml-green', icon: <CheckCircle2 className="w-3.5 h-3.5"/> },
    skip: { cls: 'text-ink-faint', icon: <MinusCircle className="w-3.5 h-3.5"/> },
    error: { cls: 'text-aml-red', icon: <AlertTriangle className="w-3.5 h-3.5"/> },
};
/** Presentational renderer for an SSE pipeline: a phase stepper, per-item status
 *  cards with evidence chips, and a streamed narrative. Callers reduce their own
 *  events (worker_* or step) into `items` — this component stays vocabulary-free. */
export const PipelineStream: React.FC<Props> = ({ phases, activePhase, items, narrative, narrativeTitle = 'Narrative', running, idle, graphNodes, verdicts, }) => {
    const activeIdx = activePhase ? phases.indexOf(activePhase) : -1;
    const started = items.length > 0 || activeIdx >= 0 || running;
    if (!started && idle) {
        return <div className="border-l-2 border-surface-3 pl-4 py-3 text-2xs text-ink-faint font-mono">{tNode(idle)}</div>;
    }
    return (<div className="border-l-2 border-accent/60 pl-4 space-y-3">
      {/* Live DAG */}
      {tNode(graphNodes && graphNodes.length > 0 && (<WorkflowGraph nodes={graphNodes} running={running}/>))}

      {/* Phase stepper */}
      {tNode(phases.length > 0 && (<div className="flex flex-wrap items-center gap-1.5">
          {tNode(phases.map((p, i) => {
                const done = activeIdx > i;
                const active = activeIdx === i;
                return (<span key={p} className={`text-2xs font-semibold px-2 py-0.5 rounded-full tracking-wide transition-colors
                  ${active ? 'bg-accent text-white'
                        : done ? 'bg-accent/10 text-accent'
                            : 'bg-surface-2 text-ink-faint'}`}>
                {tNode(p)}
              </span>);
            }))}
        </div>))}

      {/* Item cards */}
      <div className="space-y-2">
        {tNode(items.map(it => {
            const s = STATUS[it.status];
            return (<div key={it.key} className="bg-surface-1 rounded-lg shadow-soft p-3 animate-fade-in">
              <div className={`flex items-center gap-2 ${s.cls}`}>
                {tNode(s.icon)}
                <span className={`text-xs font-semibold text-ink ${it.mono ? 'font-mono' : ''}`}>
                  {tNode(it.label)}
                </span>
              </div>
              {tNode(it.detail && (<p className="text-2xs text-ink-muted mt-1.5 whitespace-pre-wrap leading-relaxed">
                  {tNode(it.detail)}
                </p>))}
              {tNode(it.assessment && <AssessmentDetails assessment={it.assessment}/>)}
              {tNode(it.chips && it.chips.length > 0 && (<div className="flex flex-wrap gap-1 mt-2">
                  {tNode(it.chips.map(c => (<span key={c} className="text-2xs font-mono text-ink-faint bg-surface-2 rounded-lg px-1.5 py-0.5">
                      {tNode(c)}
                    </span>)))}
                </div>))}
            </div>);
        }))}
      </div>

      {/* Verification verdicts */}
      {tNode(verdicts && verdicts.length > 0 && (<div className="bg-surface-1 rounded-lg shadow-soft p-4 animate-fade-in">
          <p className="text-2xs uppercase tracking-wider text-ink-faint mb-2">{t("Verification verdicts")}</p>
          <div className="space-y-2">
            {tNode(verdicts.map((v, i) => (<div key={i} className="text-xs">
                <div className="flex items-start gap-2">
                  <span className={`text-2xs font-semibold px-1.5 py-0.5 rounded-full uppercase tracking-wide shrink-0
                    ${VERDICT_STYLE[v.verdict] ?? 'text-ink-faint bg-surface-2'}`}>
                    {tNode(v.verdict)}
                  </span>
                  <span className="text-ink leading-snug">{tNode(v.claim)}</span>
                </div>
                {tNode(v.sources.length > 0 && (<div className="flex flex-wrap gap-1 mt-1 ml-1">
                    {tNode(v.sources.map((s, j) => {
                        const isUrl = /^https?:\/\//.test(s);
                        return isUrl ? (<a key={j} href={s} target="_blank" rel="noreferrer" className="text-2xs text-accent hover:underline break-all">{tNode(s)}</a>) : (<span key={j} className="text-2xs text-ink-faint bg-surface-2 rounded px-1.5 py-0.5 break-all">{tNode(s)}</span>);
                    }))}
                  </div>))}
              </div>)))}
          </div>
        </div>))}

      {/* Streamed narrative */}
      {tNode(narrative && (<div className="bg-surface-1 rounded-lg shadow-soft p-4">
          <p className="text-2xs uppercase tracking-wider text-ink-faint mb-1.5">{tNode(narrativeTitle)}</p>
          <Md text={narrative} running={running}/>
        </div>))}
    </div>);
};
