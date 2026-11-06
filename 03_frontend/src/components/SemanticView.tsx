import { t, tNode, formatDetails } from '../i18n'
import { useEffect, useRef, useState } from 'react';
import { Sparkles, X } from 'lucide-react';
import { getSemanticContext, explainSemanticContext } from '../api';
import type { SemanticContext, SemanticAnswer } from '../api';
function ContextGraph({ data, selected, onSelect }: {
    data: SemanticContext;
    selected: string;
    onSelect: (id: string) => void;
}) {
    const positions = Object.fromEntries(data.graph.nodes.map(n => [n.id, [25 + n.column * 222, 35 + n.row * 140]]));
    return <div className="semantic-graph-scroll"><svg viewBox="0 0 910 405" className="semantic-graph" aria-label={t("Semantic relationships between program records and external multimodal evidence")}>
    <defs><marker id="semantic-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>
    {tNode(data.graph.edges.map(e => {
            const [x, y] = positions[e.from], [tx, ty] = positions[e.to];
            const active = data.active_edges.includes(e.id);
            const d = y === ty ? `M${x + 180},${y + 38} H${tx}` : `M${x + 90},${y + 76} C${x + 90},${y + 110} ${tx + 90},${ty - 30} ${tx + 90},${ty}`;
            return <path key={e.id} d={d} fill="none" stroke={active ? '#1670c5' : '#d5d9e0'} strokeWidth={active ? 2 : 1} strokeDasharray={e.kind === 'curated_reference' ? '6 5' : undefined} markerEnd="url(#semantic-arrow)"><title>{tNode(e.label)}: {tNode(e.rule)}</title></path>;
        }))}
    {tNode(data.graph.nodes.map(n => {
            const [x, y] = positions[n.id];
            return <g key={n.id} transform={`translate(${x},${y})`} role="button" tabIndex={0} aria-label={t(`Inspect ${n.label}`)} aria-pressed={selected === n.id} onClick={() => onSelect(n.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect(n.id);
            } }} className="semantic-node">
        <rect width="180" height="76" rx="10" fill={selected === n.id ? '#edf5ff' : 'white'} stroke={selected === n.id ? '#1670c5' : '#dce2ec'} strokeWidth={selected === n.id ? 2 : 1}/>
        <text x="13" y="23" fill="#667085" fontSize="9" letterSpacing=".7">{tNode(n.kind.toUpperCase())}</text><text x="13" y="45" fill="#292f3d" fontSize="12" fontWeight="600">{tNode(n.label)}</text><text x="13" y="63" fill="#748096" fontSize="9">{tNode(n.key)}</text>
      </g>;
        }))}
  </svg></div>;
}
export function SemanticView({ programId }: {
    programId: string;
}) {
    const [question, setQuestion] = useState('thermal');
    const [data, setData] = useState<SemanticContext | null>(null);
    const [answer, setAnswer] = useState<SemanticAnswer | null>(null);
    const [selected, setSelected] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [vision, setVision] = useState(false);
    const pending = useRef<AbortController | null>(null);
    useEffect(() => {
        const controller = new AbortController();
        getSemanticContext(question, controller.signal, programId).then(setData).catch(e => { if (!controller.signal.aborted)
            setError(e?.response?.data?.detail || 'Could not load semantic context.'); });
        return () => controller.abort();
    }, [question, programId]);
    useEffect(() => () => pending.current?.abort(), []);
    const choose = (id: string) => { pending.current?.abort(); setBusy(false); setAnswer(null); setError(''); setData(null); setQuestion(id); };
    const run = async (narration: 'template' | 'model') => {
        const controller = new AbortController();
        pending.current?.abort();
        pending.current = controller;
        setBusy(true);
        setError('');
        setAnswer(null);
        try {
            const result = await explainSemanticContext(question, narration, narration === 'model' && vision, controller.signal, programId);
            if (!controller.signal.aborted) {
                setAnswer(result);
                setData(result);
            }
        }
        catch (e: unknown) {
            if (!controller.signal.aborted)
                setError((e as {
                    response?: {
                        data?: {
                            detail?: string;
                        };
                    };
                })?.response?.data?.detail || 'Explanation failed. Try again.');
        }
        finally {
            if (!controller.signal.aborted)
                setBusy(false);
        }
    };
    const node = data?.graph.nodes.find(n => n.id === selected);
    return <section aria-label={t("Semantic context explorer")}>
    {tNode(error && <p role="alert" className="reader-notice reader-error">{tNode(error)}</p>)}
    {tNode(!data && !error && <p role="status" className="reader-notice">{t("Loading predefined semantic context\u2026")}</p>)}
    {tNode(data && <>
      <section className="reader-panel semantic-canvas-panel">
        <div className="semantic-canvas-toolbar">
          <label htmlFor="semantic-focus">{t("Explore")}</label>
          <select id="semantic-focus" value={question} onChange={e => choose(e.target.value)}>
            {tNode(data.model.questions.map(q => <option key={q.id} value={q.id} disabled={!q.enabled} title={q.missing_source || q.title}>{tNode(({ thermal: 'Thermal risk', packaging: 'Battery packaging', venting: 'Thermal response and venting', applicability: 'Evidence applicability' } as Record<string, string>)[q.id] || q.title)}{tNode(!q.enabled ? ' (unavailable)' : '')}</option>))}
          </select>
          <span>{t("Click a node to explore its context")}</span>
        </div>
        <div className={`semantic-map-layout${node ? " has-selection" : ""}`}><ContextGraph data={data} selected={selected} onSelect={id => setSelected(current => current === id ? '' : id)}/>{tNode(node && <aside className="semantic-inspector" aria-label={t("Selected node details")}><button className="semantic-inspector-close quiet-button" aria-label={t("Close node details")} onClick={() => setSelected('')}><X size={16}/></button><span className="eyebrow">{tNode(node.kind)}</span><h3>{tNode(node.label)}</h3><p>{tNode(node.description)}</p><dl><dt>{t("Physical source")}</dt><dd>{tNode(node.source)}</dd><dt>{t("Identity / join key")}</dt><dd><code>{tNode(node.key)}</code></dd></dl><dl><dt>{t("Grain")}</dt><dd>{tNode(node.grain)}</dd><dt>{t("Origin")}</dt><dd>{tNode(node.origin)}</dd></dl><details><summary>{t("Inspect resolved records")}</summary><pre>{formatDetails(node.records)}</pre></details></aside>)}</div>
        <p className="semantic-canvas-legend">{t("Solid lines: record joins \u00B7 Dashed lines: reference associations \u00B7 Program records are synthetic; external references are real.")}</p>
        <details className="reader-body semantic-rules"><summary>{t("View the join rules used for this question")}</summary>{tNode(data.graph.edges.filter(e => data.active_edges.includes(e.id)).map(e => <div key={e.id}><strong>{tNode(e.label)}</strong><code>{tNode(e.rule)}</code></div>))}</details>
      <details className="semantic-ai-details"><summary><Sparkles size={14}/>{t("Explore how AI uses this context")}</summary><div className="reader-body"><details className="semantic-selection"><summary>{t("How context is selected")}</summary><ol className="semantic-steps">{tNode(data.steps.map((s, i) => <li key={s.label}><span>{tNode(i + 1)}</span><div><strong>{tNode(s.label)}</strong><p>{tNode(s.detail)}</p></div></li>))}</ol></details><div className="semantic-actions"><button className="primary-button" disabled={busy} onClick={() => void run('model')}><Sparkles size={14}/>{tNode(busy ? 'Preparing explanation…' : 'Explain with configured AI')}</button><button className="quiet-button" disabled={busy} onClick={() => void run('template')}>{t("Show offline explanation")}</button><label><input type="checkbox" checked={vision} onChange={e => setVision(e.target.checked)} disabled={busy}/>{t("Include source images (vision model required)")}</label></div><details className="semantic-rules"><summary>{t("Inspect selected facts, definitions, relationships and citations")}</summary><pre>{formatDetails(data.packet)}</pre></details><p className="reader-caption mt-3">{t("Without image input, AI receives structured records and curated figure descriptions. Model errors and unsupported citation references fall back to a labelled offline explanation.")}</p>
          {tNode(answer && <div className="semantic-answer" aria-live="polite"><span className="context-chip">{tNode(answer.narration)}</span><p>{tNode(answer.answer)}</p><small>{tNode(answer.note)}</small><details><summary>{t("Inspect the exact prompt and evidence packet")}</summary><pre>{formatDetails(answer.prompt)}</pre><small>{t("Context SHA-256:")}{tNode(answer.context_sha256)}</small></details></div>)}
        </div></details>
      </section>
    </>)}

  </section>;
}
