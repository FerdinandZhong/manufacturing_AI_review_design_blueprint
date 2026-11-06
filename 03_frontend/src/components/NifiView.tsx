import { t, tNode } from '../i18n'
import { useEffect, useRef, useState } from 'react';
import { ArrowUp, History, Plus, Settings2, X, SlidersHorizontal, ChevronRight, Network } from 'lucide-react';
import { getNifiConfig, askNifi } from '../api';
import type { NifiSnapshot } from '../api';
const STARTERS = ['Summarize the current pipeline running situation', 'Show the pipeline topology', 'Which processors are invalid or stopped?', 'Show recent pipeline bulletins'];
const display = (value: number | null) => value == null ? 'Unknown' : value.toLocaleString();
const State = ({ value }: {
    value: string;
}) => <span className={`state-chip ${['RUNNING', 'VALID'].includes(value) ? 'good' : ['STOPPED', 'INVALID', 'WARN', 'ERROR'].includes(value) ? 'warn' : ''}`}>{tNode(value)}</span>;
type Intent = 'status' | 'topology' | 'health' | 'bulletins';
function Topology({ snapshot }: {
    snapshot: NifiSnapshot;
}) {
    const [selected, setSelected] = useState<string | null>(null);
    const nodes = snapshot.processors;
    const endpoints = [...new Set(snapshot.connections.flatMap(c => [c.source, c.target]))].filter(id => id && !nodes.some(p => p.id === id));
    const allNodes = [...nodes, ...endpoints.map(id => ({ id, name: 'Unexpanded endpoint', state: 'UNKNOWN', validation: 'UNKNOWN', type: id, threads: null }))];
    const positions = Object.fromEntries(allNodes.map((n, i) => [n.id, { x: 24 + (i % 3) * 230, y: 34 + Math.floor(i / 3) * 145 }]));
    const linked = new Set(snapshot.connections.filter(c => !selected || c.source === selected || c.target === selected).flatMap(c => [c.source, c.target]));
    const selectedNode = allNodes.find(n => n.id === selected);
    const name = (id: string) => allNodes.find(n => n.id === id)?.name ?? id;
    return <section className="pipeline-topology"><div className="pipeline-canvas-heading"><h3>{t("Pipeline topology")}</h3><span>{t("Direct children \u00B7")}{tNode(allNodes.length)}{t("visible components")}</span></div><div className="pipeline-canvas-controls"><span><Network size={14}/>{tNode(snapshot.name)}</span>{tNode(selected && <button className="quiet-button" onClick={() => setSelected(null)}>{t("Clear selection")}</button>)}</div><div className="pipeline-canvas-scroll"><svg width="720" height={Math.max(240, Math.ceil(allNodes.length / 3) * 145 + 30)} role="img" aria-label={t("NiFi processors and directed connections")}><defs><marker id="nifi-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10" fill="#64748b"/></marker></defs>{tNode(snapshot.connections.map(c => { const from = positions[c.source], to = positions[c.target]; if (!from || !to)
        return null; const focus = !selected || c.source === selected || c.target === selected; return <g key={c.id} opacity={focus ? 1 : .25}><path d={from.y === to.y ? `M${from.x + 190},${from.y + 42} L${to.x},${to.y + 42}` : `M${from.x + 95},${from.y + 84} C${from.x + 95},${from.y + 115} ${to.x + 95},${to.y - 30} ${to.x + 95},${to.y}`} fill="none" stroke={selected && focus ? '#2d62df' : '#64748b'} strokeWidth="1.5" markerEnd="url(#nifi-arrow)"/><title>{tNode(c.relationships.join(', '))} · {tNode(display(c.queued))}{t("queued")}</title></g>; }))}{tNode(allNodes.map(n => <g key={n.id} transform={`translate(${positions[n.id].x},${positions[n.id].y})`} className="pipeline-canvas-node" role="button" tabIndex={0} aria-label={t(`Inspect ${n.name}`)} aria-pressed={selected === n.id} opacity={!selected || selected === n.id || linked.has(n.id) ? 1 : .3} onClick={() => setSelected(n.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setSelected(n.id);
    } }}><rect width="190" height="84" rx="6" fill="white" stroke={selected === n.id ? '#2d62df' : '#8396bc'} strokeWidth={selected === n.id ? 2 : 1}/><text x="12" y="22" fill="#667085" fontSize="10">{tNode(n.state)}</text><text x="12" y="44" fill="#292f3d" fontSize="12" fontWeight="500">{tNode(n.name.length > 25 ? n.name.slice(0, 24) + '…' : n.name)}</text><text x="12" y="65" fill="#667085" fontSize="10">{tNode(n.validation)} · {tNode(display(n.threads))}{t("threads")}</text><title>{tNode(n.name)} · {tNode(n.id)}</title></g>))}</svg></div>{tNode(selectedNode && <div className="pipeline-inspector"><strong>{tNode(selectedNode.name)}</strong><p>{tNode(selectedNode.type)}</p><p>{tNode(selectedNode.id)}</p></div>)}<div className="reader-table-wrap"><table className="reader-table"><thead><tr><th>{t("From")}</th><th>{t("To")}</th><th>{t("Relationship")}</th><th>{t("Queued")}</th></tr></thead><tbody>{tNode(snapshot.connections.filter(c => !selected || c.source === selected || c.target === selected).map(c => <tr key={c.id}><td>{tNode(name(c.source))}</td><td>{tNode(name(c.target))}</td><td>{tNode(c.relationships.join(', ') || 'Not supplied')}</td><td>{tNode(display(c.queued))}</td></tr>))}</tbody></table></div></section>;
}
export function NifiView({ pilot = false }: {
    pilot?: boolean;
}) {
    const [mode, setMode] = useState<'sample' | 'live'>(pilot ? 'live' : 'sample');
    const [config, setConfig] = useState<{
        configured: boolean;
        group_id: string;
    } | null>(null);
    const [question, setQuestion] = useState('');
    const [turn, setTurn] = useState<{
        question: string;
        intent: Intent;
        snapshot: NifiSnapshot;
    } | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [submitted, setSubmitted] = useState('');
    const [recent, setRecent] = useState<string[]>([]);
    const [history, setHistory] = useState(false);
    const request = useRef<AbortController | null>(null);
    const settings = useRef<HTMLDialogElement>(null);
    const input = useRef<HTMLTextAreaElement>(null);
    useEffect(() => { let active = true; getNifiConfig().then(c => { if (active)
        setConfig(c); }).catch(() => { }); return () => { active = false; request.current?.abort(); }; }, []);
    const reset = () => { request.current?.abort(); setTurn(null); setError(''); setBusy(false); setSubmitted(''); setQuestion(''); input.current?.focus(); };
    const changeMode = (next: 'sample' | 'live') => { if (next !== mode) {
        reset();
        setMode(next);
        setRecent([]);
        setHistory(false);
    } };
    const run = async (text: string) => {
        const q = text.trim();
        if (!q || busy)
            return;

        setSubmitted(q);
        setQuestion('');
        setError('');
        setTurn(null);
        setHistory(false);
        const controller = new AbortController();
        request.current?.abort();
        request.current = controller;
        setBusy(true);
        try {
            const {snapshot, intent} = await askNifi(q, mode, controller.signal);
            if (!controller.signal.aborted) {
                setTurn({ question: q, intent, snapshot });
                setRecent(prev => [q, ...prev.filter(x => x !== q)].slice(0, 8));
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
                })?.response?.data?.detail || 'The source could not be read. Check the connection and try again.');
        }
        finally {
            if (!controller.signal.aborted)
                setBusy(false);
        }
    };
    const snap = turn?.snapshot;
    const problemProcessors = snap?.processors.filter(p => p.state !== 'RUNNING' || p.validation === 'INVALID') ?? [];
    return <section className="nifi-workspace" aria-label={t("NiFi reader")}>
    <header className="nifi-heading"><div><h1>{t("Pipeline control")}</h1><div className="obs-status"><span className="obs-mode-pill" data-mode={mode}>{tNode(mode === 'sample' ? 'Sample preview' : 'Live NiFi')}</span><span>{t("Read-only")}</span><span>{tNode(mode === 'sample' ? 'Fixture data' : config?.configured ? `Group ${config.group_id}` : 'Connection not configured')}</span></div></div><div className="nifi-header-actions"><button className="icon-button" onClick={reset} aria-label={t("New inspection")} title={t("New inspection")}><Plus size={18}/></button><button className="icon-button" onClick={() => setHistory(!history)} aria-label={t("Recent questions")} title={t("Recent questions")} aria-expanded={history}><History size={18}/></button><button className="icon-button" onClick={() => settings.current?.showModal()} aria-label={t("Connection settings")} title={t("Connection settings")}><SlidersHorizontal size={18}/></button></div></header>
    {tNode(history && <div className="nifi-history"><strong>{t("Recent questions \u00B7 this session")}</strong>{tNode(recent.length ? recent.map(q => <button key={q} onClick={() => void run(t(q))}>{tNode(q)}<ChevronRight size={14}/></button>) : <p>{t("No questions yet.")}</p>)}</div>)}
    <div className="query-chat-workbench"><div className="obs-chat-layout">
      {tNode(!submitted && <div className="obs-empty"><h2>{t("What should we check in the pipeline?")}</h2><p>{t("Inspect current flow state, processor health, and connections. Every answer shows the snapshot it used.")}</p><div className="obs-starters">{tNode(STARTERS.map(q => <button className="obs-starter" key={q} onClick={() => void run(t(q))}>{tNode(q)}<ChevronRight size={15}/></button>))}</div></div>)}
      {tNode(submitted && <div className="nifi-result"><div className="obs-chat-user"><p>{tNode(submitted)}</p></div><div className="obs-chat-assistant"><div className="tiny-label"><span className="assistant-mark"><Network size={15}/></span>{t("Pipeline reader")}</div>{tNode(busy && <p role="status" className="obs-working">{t("Reading")}{tNode(mode === 'sample' ? 'sample' : 'NiFi')}{t("evidence\u2026")}</p>)}{tNode(error && <div role="alert" className="reader-notice reader-error">{tNode(error)}</div>)}{tNode(snap && <div className="obs-chat-answer"><details className="nifi-work"><summary>{t("Read three source views \u00B7 inspect evidence scope")}</summary><p>{t("Process-group flow \u00B7 group status \u00B7 scoped bulletin board")}</p><p>{t("Group:")}{tNode(snap.group_id)}{t("\u00B7 Source refreshed:")}{tNode(snap.refreshed)}</p>{tNode(snap.limitations.map(l => <p key={l}>{tNode(l)}</p>))}</details><p className="nifi-answer-lead">{tNode(turn.intent === 'bulletins' ? `${snap.bulletins.length} retained bulletins were returned for ${snap.name}.` : turn.intent === 'health' ? `${problemProcessors.length} direct child processors are not running or report invalid configuration.` : turn.intent === 'topology' ? `The current flow contains ${snap.processors.length} visible direct child processors and ${snap.connections.length} connections.` : `${snap.processors.filter(p => p.state === 'RUNNING').length} of ${snap.processors.length} visible processors are running, with ${display(snap.metrics.queued)} FlowFiles queued.`)}</p><p className="nifi-answer-note">{tNode(mode === 'sample' ? 'Synthetic fixture snapshot. No NiFi service was queried.' : 'Current NiFi REST snapshot. No operational changes were made.')}</p>
      {tNode(turn.intent === 'status' && <div className="nifi-inline-metrics"><div><span>{t("Queued FlowFiles")}</span><strong>{tNode(display(snap.metrics.queued))}</strong></div><div><span>{t("Active threads")}</span><strong>{tNode(display(snap.metrics.active_threads))}</strong></div><div><span>{t("Recent bulletins")}</span><strong>{tNode(snap.bulletins.length)}</strong></div></div>)}
      {tNode((turn.intent === 'health' || turn.intent === 'status') && <section className="nifi-table-section"><h3>{t("Processor states")}</h3><div className="reader-table-wrap"><table className="reader-table"><thead><tr><th>{t("Processor")}</th><th>{t("State")}</th><th>{t("Validation")}</th><th>{t("Threads")}</th></tr></thead><tbody>{tNode((turn.intent === 'health' ? problemProcessors : snap.processors).map(p => <tr key={p.id}><td>{tNode(p.name)}</td><td><State value={p.state}/></td><td><State value={p.validation}/></td><td>{tNode(display(p.threads))}</td></tr>))}{tNode(turn.intent === 'health' && !problemProcessors.length && <tr><td colSpan={4}>{t("No visible processors match these conditions.")}</td></tr>)}</tbody></table></div></section>)}
      {tNode((turn.intent === 'topology' || turn.intent === 'status') && <Topology snapshot={snap}/>)}
      {tNode(turn.intent === 'bulletins' && <section className="nifi-table-section"><h3>{t("Recent bulletins")}</h3><div className="reader-table-wrap"><table className="reader-table"><thead><tr><th>{t("Source timestamp")}</th><th>{t("Processor")}</th><th>{t("Level")}</th></tr></thead><tbody>{tNode(snap.bulletins.map(b => <tr key={b.id}><td>{tNode(b.timestamp || 'Unknown')}</td><td>{tNode(b.source || 'Unknown')}</td><td><State value={b.level || 'Unknown'}/></td></tr>))}{tNode(!snap.bulletins.length && <tr><td colSpan={3}>{t("No retained bulletins returned.")}</td></tr>)}</tbody></table></div><p className="reader-caption">{t("Bulletin message content stays in NiFi. These retained events are not historical logs.")}</p></section>)}
      </div>)}</div>{tNode(!busy && <div className="nifi-followups">{tNode(STARTERS.filter(q => q !== submitted).map(q => <button key={q} onClick={() => void run(t(q))}>{tNode(q)}</button>))}</div>)}</div>)}
      <form className="obs-chat-composer" onSubmit={e => { e.preventDefault(); void run(question); }}><label className="sr-only" htmlFor="nifi-question">{t("Ask about the pipeline")}</label><textarea id="nifi-question" ref={input} value={question} onChange={e => setQuestion(e.target.value)} placeholder={t("Ask about the current pipeline\u2026")} rows={2} maxLength={500} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        void run(question);
    } }}/><div className="obs-chips"><button type="button" className="obs-settings-chip" onClick={() => settings.current?.showModal()}><Settings2 size={13}/>{t("Settings")}</button><button type="button" className="obs-mode-chip" data-mode={mode} onClick={() => settings.current?.showModal()}>{tNode(mode === 'sample' ? 'Sample · fixture data' : 'Live NiFi')}</button></div><span className="composer-hint">{t("Read-only inspection")}</span><button className="composer-send" type="submit" disabled={busy || !question.trim()} aria-label={t("Ask pipeline reader")}><ArrowUp size={19}/></button></form>
    </div></div>
    <dialog ref={settings} className="semantic-dialog nifi-settings"><header><div><p className="eyebrow">{t("PIPELINE READER")}</p><h2>{t("Connection settings")}</h2></div><button autoFocus className="icon-button" onClick={() => settings.current?.close()} aria-label={t("Close connection settings")}><X size={17}/></button></header><p>{t("Choose the source for this inspection.")}</p><div className="mode-switch"><button disabled={pilot} aria-pressed={mode === 'sample'} onClick={() => changeMode('sample')}>{t("Sample preview")}</button><button aria-pressed={mode === 'live'} onClick={() => changeMode('live')}>{t("Live NiFi")}</button></div><p className="reader-caption">{tNode(config?.configured ? 'A live target is configured on the backend.' : 'No live target is configured on the backend.')}</p><details><summary>{t("Backend connection configuration")}</summary><p>{t("Set")}<code>{t("NIFI_API_URL")}</code>{t("to the REST URL ending in")}<code>{t("/nifi-api")}</code>{t(", and")}<code>{t("NIFI_PROCESS_GROUP_ID")}</code>{t("to the process-group UUID.")}</p><p>{t("Use")}<code>{t("NIFI_TOKEN")}</code>{t("for an HTTPS bearer token and")}<code>{t("NIFI_CA_BUNDLE")}</code>{t("for a trusted CA bundle if required. Credentials stay on the server.")}</p></details><button className="primary-button" onClick={() => settings.current?.close()}>{t("Done")}</button></dialog>
  </section>;
}
