import { t, tNode, useLanguage, setLanguage } from './i18n'
import { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import { Boxes, ChevronRight, Factory, LayoutDashboard, Network, Search, ShieldCheck, Share2, Library } from 'lucide-react';
import { ModelsView } from './components/ModelsView';
import { SemanticView } from './components/SemanticView';
import { NifiView } from './components/NifiView';
import { CockpitView } from './components/CockpitView';
import { KnowledgeCards } from './components/KnowledgeCards';
import { getRuntimeStatus, getPrograms } from './api';
import type { RuntimeStatus, Program } from './api';
import { PilotSourceView } from './components/PilotSourceView';
import './App.css';
import './uob-alignment.css';
const SCENARIOS = [{ key: 'PACK-ATLAS-01', label: 'Original baseline' }, { key: 'PACK-ATLAS-01@atlas-v2', label: 'Expanded validation' }, { key: 'PACK-ATLAS-01@atlas-v3', label: 'Revised design' }];
const pages = [
    { id: 'cockpit', label: 'Program Cockpit', icon: LayoutDashboard, group: 'ENGINEERING', description: 'Review requirements, engineering evidence, and release readiness for your battery-pack program.' },
    { id: 'knowledge', label: 'Knowledge base', icon: Library, group: 'ENGINEERING', description: 'Browse original source material, attribution, and the engineering context attached to each asset.' },
    { id: 'semantic', label: 'Semantic context', icon: Share2, group: 'ENGINEERING INTELLIGENCE', description: 'See how AI connects program records with real figures, documents, and published measurements.' },
    { id: 'nifi', label: 'NiFi reader', icon: Network, group: 'DATA OPERATIONS', description: 'Inspect flow health, processor states, and queued data in one read-only workspace.' },
    { id: 'models', label: 'Models', icon: Boxes, group: 'WORKSPACE', description: 'Manage language models for agent findings and gate narratives.' },
] as const;
type View = typeof pages[number]['id'];
export default function App() {
    const language = useLanguage();
    const [programId, setProgramId] = useState('PACK-ATLAS-01@atlas-v2');
    const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
    const [runtimeError, setRuntimeError] = useState('');
    const [runtimeAttempt, setRuntimeAttempt] = useState(0);
    const [pilotPrograms, setPilotPrograms] = useState<Program[]>([]);
    useEffect(() => {
        getRuntimeStatus().then(async (status) => {
            setRuntime(status);
            if (status.mode === 'pilot' && status.source_ready) {
                const programs = await getPrograms();
                setPilotPrograms(programs);
                setProgramId(programs[0]?.program_id || '');
            }
        }).catch((error: unknown) => {
            const status = isAxiosError(error) ? error.response?.status : undefined;
            const detail: unknown = isAxiosError(error) ? error.response?.data?.detail : undefined;
            setRuntimeError(`Workspace status unavailable${status ? ` (HTTP ${status})` : ''}. ${typeof detail === 'string' ? detail : 'The runtime status request failed. Inspect the response for routing or backend errors.'}`);
        });
    }, [runtimeAttempt]);
    const [view, setView] = useState<View>('cockpit');
    const [search, setSearch] = useState('');
    const page = pages.find(p => p.id === view)!;
    const navigate = (id: View) => { setView(id); setSearch(''); };
    return (<div className="workspace-shell" data-view={view}>
      <a className="skip-link" href="#workspace-content">{t("Skip to content")}</a>
      <aside className="workspace-sidebar">
        <button className="brand" onClick={() => navigate('cockpit')} aria-label={t("Cloudera workspace home")}>
          <img src="./cloudera-wordmark.png" alt={t("Cloudera")}/>
        </button>
        <div className="workspace-identity"><span className="workspace-dot"/><div><strong>{t("Vehicle NPI")}</strong><small>{t("Manufacturing workspace")}</small></div></div>
        <nav aria-label={t("Main navigation")}>{tNode(pages.map((p, i) => <div key={p.id}>{tNode((i === 0 || pages[i - 1].group !== p.group) && <p className="nav-label">{tNode(p.group)}</p>)}<button className={`nav-item ${view === p.id ? 'active' : ''}`} onClick={() => navigate(p.id)} aria-current={view === p.id ? 'page' : undefined}><p.icon size={18}/><span>{tNode(p.label)}</span><ChevronRight size={14}/></button></div>))}</nav>
        <div className="sidebar-note"><ShieldCheck size={21}/><strong>{t("Evidence-led decisions")}</strong><p>{t("From engineering requirements to a reviewed release decision.")}</p></div>
        <div className="workspace-profile"><span className="avatar"><Factory size={16}/></span><div><strong>{t("Cloudera AI")}</strong><small>{t("Applied ML Prototype")}</small></div></div>
      </aside>
      <main className="workspace-main" id="workspace-content" tabIndex={-1}>
        <header className="global-header">
          <div className="workspace-search"><Search size={16}/><input aria-label={t("Find a workspace page")} placeholder={t("Find a workspace page\u2026")} value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === 'Escape')
        setSearch(''); }}/>
            {tNode(search && <div className="search-results">{tNode(pages.filter(p => `${p.label} ${p.description} ${t(p.label)} ${t(p.description)}`.toLowerCase().includes(search.toLowerCase())).map(p => <button key={p.id} onClick={() => navigate(p.id)}>{tNode(p.label)}<ChevronRight size={14}/></button>))}{tNode(!pages.some(p => `${p.label} ${p.description} ${t(p.label)} ${t(p.description)}`.toLowerCase().includes(search.toLowerCase())) && <p>{t("No matching pages.")}</p>)}</div>)}
          </div>
          <div className="top-actions"><div className="language-switch" role="group" aria-label={t("Interface language")}><button type="button" lang="en" aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button><button type="button" lang="zh-CN" aria-pressed={language === "zh"} onClick={() => setLanguage("zh")}>简体中文</button></div><span className="workspace-badge">{tNode(runtime ? `${runtime.mode === 'demo' ? 'Demo' : 'Pilot'} · ${runtime.identity.permission}` : runtimeError ? 'Workspace unavailable' : 'Checking workspace')}</span><span className="header-profile"><img src="./favicon.svg" alt={t("")}/><span><strong>{t("Vehicle manufacturing")}</strong><small>{t("Cloudera AI workspace")}</small></span></span></div>
        </header>
        <div className="breadcrumb">{t("AI workspace")}<ChevronRight size={12}/><span>{tNode(page.label)}</span><small>{t("New product introduction")}</small></div>
        <div className="workspace-page">
          <section className="page-heading" hidden={view === 'nifi'}><div><p className="eyebrow">{tNode(page.group)}</p><h1>{tNode(page.label)}</h1><p>{tNode(page.description)}</p></div><span className="context-chip">{tNode(view === 'cockpit' ? (runtime?.mode === 'pilot' ? 'Read-only pilot inspection' : programId) : view === 'nifi' ? 'Read-only inspection' : view === 'semantic' ? 'Predefined context · Multimodal evidence' : view === 'knowledge' ? 'Attributed source collection' : 'Narration configuration')}</span></section>
          {tNode(runtime?.mode === 'demo' && (view === 'cockpit' || view === 'semantic' || view === 'knowledge') && <div className="program-context"><label className="revision-control"><span>{t("Engineering revision")}</span><select aria-label={t("Engineering revision")} value={programId} onChange={e => setProgramId(e.target.value)}>{tNode(SCENARIOS.map(s => <option key={s.key} value={s.key}>{tNode(s.label)}</option>))}</select></label><span className="program-source-status">{t("Synthetic demo data \u00B7")}{tNode(runtime.source_ready ? 'Ready' : 'Not ready')}</span></div>)}
          {tNode(runtimeError && <div role="alert" className="reader-notice reader-error"><p>{tNode(runtimeError)}</p><p>{t("Workbench requires the application's HTTPS origin and trusted ingress proxy configuration.")}</p><div className="runtime-error-actions"><a href="/api/runtime/status" target="_blank" rel="noreferrer">{t("Inspect runtime status response")}</a><button className="quiet-button" onClick={() => { setRuntimeError(''); setRuntimeAttempt(n => n + 1); }}>{t("Retry workspace status")}</button></div></div>)}
          {tNode(runtime?.mode === 'pilot' && <p className="reader-caption">{t("Pilot source \u00B7")}{tNode(runtime.source.state)} · {tNode(runtime.source.detail)}</p>)}
          {tNode(runtime?.mode === 'demo' && !runtime.review_ready && <p className="reader-notice">{t("Review artifacts are unready. Run Demo preparation before reviewing.")}</p>)}
          {tNode(runtime?.mode === 'pilot' && !runtime.source_ready && <p role="alert" className="reader-notice">{t("Pilot source is unready. Configure a validated read-only source. No demo data was substituted.")}</p>)}
          {tNode(runtime?.mode === 'pilot' && runtime.source_ready && view === 'cockpit' && <><label className="context-chip">{t("Pilot program")}<select aria-label={t("Pilot program")} value={programId} onChange={e => setProgramId(e.target.value)}>{tNode(pilotPrograms.map(p => <option key={p.program_id} value={p.program_id}>{tNode(p.name)}</option>))}</select></label>{tNode(pilotPrograms.length > 0 && <PilotSourceView key={programId} programId={programId} status={runtime}/>)}</>)}
          {tNode(runtime?.mode === 'demo' && <div hidden={view !== 'cockpit'}><CockpitView canWrite={runtime.identity.permission === 'RW'} reviewReady={runtime.review_ready} key={programId} programId={programId}/></div>)}
          {tNode(runtime?.mode === 'pilot' && ['semantic', 'knowledge'].includes(view) && <p className="reader-notice">{t("This capability is unavailable until a pilot semantic and evidence package is approved.")}</p>)}
          {tNode(runtime?.mode === 'demo' && view === 'knowledge' && <KnowledgeCards key={programId} programId={programId}/>)}
          {tNode(runtime && view === 'models' && <>{tNode(runtime.identity.permission === 'RO' && <p className="reader-notice">{t("Workbench RW permission is required to change or test model configuration.")}</p>)}<fieldset disabled={runtime.identity.permission !== 'RW'}><ModelsView /></fieldset></>)}
          {tNode(runtime && view === 'nifi' && <NifiView pilot={runtime.mode === 'pilot'}/>)}
          {tNode(runtime?.mode === 'demo' && view === 'semantic' && <SemanticView key={programId} programId={programId}/>)}
          <footer className="workspace-footer"><span>{t("Cloudera AI \u00B7 Vehicle Manufacturing Blueprint")}</span><span>{tNode(view === 'nifi' ? 'Current snapshots · No operational actions' : 'Code decides · AI narrates')}</span></footer>
        </div>
      </main>
    </div>);
}
