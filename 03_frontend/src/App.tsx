import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'
import { Boxes, ChevronRight, Factory, LayoutDashboard, Network, Search, ShieldCheck, Share2, Library } from 'lucide-react'
import { ModelsView } from './components/ModelsView'
import { SemanticView } from './components/SemanticView'
import { NifiView } from './components/NifiView'
import { CockpitView } from './components/CockpitView'
import { KnowledgeCards } from './components/KnowledgeCards'
import { getRuntimeStatus, getPrograms } from './api'
import type { RuntimeStatus, Program } from './api'
import { PilotSourceView } from './components/PilotSourceView'
import './App.css'
import './uob-alignment.css'

const SCENARIOS = [{key:'PACK-ATLAS-01',label:'Original baseline'}, {key:'PACK-ATLAS-01@atlas-v2',label:'Expanded validation'}, {key:'PACK-ATLAS-01@atlas-v3',label:'Revised design'}]
const pages = [
  { id: 'cockpit', label: 'Program Cockpit', icon: LayoutDashboard, group: 'ENGINEERING', description: 'Review requirements, engineering evidence, and release readiness for your battery-pack program.' },
  { id: 'knowledge', label: 'Knowledge base', icon: Library, group: 'ENGINEERING', description: 'Browse original source material, attribution, and the engineering context attached to each asset.' },
  { id: 'semantic', label: 'Semantic context', icon: Share2, group: 'ENGINEERING INTELLIGENCE', description: 'See how AI connects program records with real figures, documents, and published measurements.' },
  { id: 'nifi', label: 'NiFi reader', icon: Network, group: 'DATA OPERATIONS', description: 'Inspect flow health, processor states, and queued data in one read-only workspace.' },
  { id: 'models', label: 'Models', icon: Boxes, group: 'WORKSPACE', description: 'Manage language models for agent findings and gate narratives.' },
] as const
type View = typeof pages[number]['id']

export default function App() {
  const [programId, setProgramId] = useState('PACK-ATLAS-01@atlas-v2')
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null)
  const [runtimeError, setRuntimeError] = useState('')
  const [runtimeAttempt, setRuntimeAttempt] = useState(0)
  const [pilotPrograms, setPilotPrograms] = useState<Program[]>([])
  useEffect(() => {
    getRuntimeStatus().then(async status => {
      setRuntime(status)
      if (status.mode === 'pilot' && status.source_ready) { const programs = await getPrograms(); setPilotPrograms(programs); setProgramId(programs[0]?.program_id || '') }
    }).catch((error: unknown) => {
      const status = isAxiosError(error) ? error.response?.status : undefined
      const detail: unknown = isAxiosError(error) ? error.response?.data?.detail : undefined
      setRuntimeError(`Workspace status unavailable${status ? ` (HTTP ${status})` : ''}. ${typeof detail === 'string' ? detail : 'The runtime status request failed. Inspect the response for routing or backend errors.'}`)
    })
  }, [runtimeAttempt])
  const [view, setView] = useState<View>('cockpit')
  const [search, setSearch] = useState('')
  const page = pages.find(p => p.id === view)!
  const navigate = (id: View) => { setView(id); setSearch('') }
  return (
    <div className="workspace-shell" data-view={view}>
      <a className="skip-link" href="#workspace-content">Skip to content</a>
      <aside className="workspace-sidebar">
        <button className="brand" onClick={() => navigate('cockpit')} aria-label="Cloudera workspace home">
          <img src="./cloudera-wordmark.png" alt="Cloudera" />
        </button>
        <div className="workspace-identity"><span className="workspace-dot" /><div><strong>Vehicle NPI</strong><small>Manufacturing workspace</small></div></div>
        <nav aria-label="Main navigation">{pages.map((p, i) => <div key={p.id}>{(i === 0 || pages[i - 1].group !== p.group) && <p className="nav-label">{p.group}</p>}<button className={`nav-item ${view === p.id ? 'active' : ''}`} onClick={() => navigate(p.id)} aria-current={view === p.id ? 'page' : undefined}><p.icon size={18} /><span>{p.label}</span><ChevronRight size={14} /></button></div>)}</nav>
        <div className="sidebar-note"><ShieldCheck size={21} /><strong>Evidence-led decisions</strong><p>From engineering requirements to a reviewed release decision.</p></div>
        <div className="workspace-profile"><span className="avatar"><Factory size={16} /></span><div><strong>Cloudera AI</strong><small>Applied ML Prototype</small></div></div>
      </aside>
      <main className="workspace-main" id="workspace-content" tabIndex={-1}>
        <header className="global-header">
          <div className="workspace-search"><Search size={16} /><input aria-label="Find a workspace page" placeholder="Find a workspace page…" value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') setSearch('') }} />
            {search && <div className="search-results">{pages.filter(p => `${p.label} ${p.description}`.toLowerCase().includes(search.toLowerCase())).map(p => <button key={p.id} onClick={() => navigate(p.id)}>{p.label}<ChevronRight size={14} /></button>)}{!pages.some(p => `${p.label} ${p.description}`.toLowerCase().includes(search.toLowerCase())) && <p>No matching pages.</p>}</div>}
          </div>
          <div className="top-actions"><span className="workspace-badge">{runtime ? `${runtime.mode === 'demo' ? 'Demo' : 'Pilot'} · ${runtime.identity.permission}` : runtimeError ? 'Workspace unavailable' : 'Checking workspace'}</span><span className="header-profile"><img src="./favicon.svg" alt="" /><span><strong>Vehicle manufacturing</strong><small>Cloudera AI workspace</small></span></span></div>
        </header>
        <div className="breadcrumb">AI workspace <ChevronRight size={12} /><span>{page.label}</span><small>New product introduction</small></div>
        <div className="workspace-page">
          <section className="page-heading" hidden={view === 'nifi'}><div><p className="eyebrow">{page.group}</p><h1>{page.label}</h1><p>{page.description}</p></div><span className="context-chip">{view === 'cockpit' ? (runtime?.mode === 'pilot' ? 'Read-only pilot inspection' : programId) : view === 'nifi' ? 'Read-only inspection' : view === 'semantic' ? 'Predefined context · Multimodal evidence' : view === 'knowledge' ? 'Attributed source collection' : 'Narration configuration'}</span></section>
          {runtime?.mode === 'demo' && (view === 'cockpit' || view === 'semantic' || view === 'knowledge') && <div className="program-context"><label className="revision-control"><span>Engineering revision</span><select aria-label="Engineering revision" value={programId} onChange={e => setProgramId(e.target.value)}>{SCENARIOS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}</select></label><span className="program-source-status">Synthetic demo data · {runtime.source_ready ? 'Ready' : 'Not ready'}</span></div>}
          {runtimeError && <div role="alert" className="reader-notice reader-error"><p>{runtimeError}</p><p>Workbench requires the application's HTTPS origin and trusted ingress proxy configuration.</p><div className="runtime-error-actions"><a href="/api/runtime/status" target="_blank" rel="noreferrer">Inspect runtime status response</a><button className="quiet-button" onClick={() => { setRuntimeError(''); setRuntimeAttempt(n => n + 1) }}>Retry workspace status</button></div></div>}
          {runtime?.mode === 'pilot' && <p className="reader-caption">Pilot source · {runtime.source.state} · {runtime.source.detail}</p>}
          {runtime?.mode === 'demo' && !runtime.review_ready && <p className="reader-notice">Review artifacts are unready. Run Demo preparation before reviewing.</p>}
          {runtime?.mode === 'pilot' && !runtime.source_ready && <p role="alert" className="reader-notice">Pilot source is unready. Configure a validated read-only source. No demo data was substituted.</p>}
          {runtime?.mode === 'pilot' && runtime.source_ready && view === 'cockpit' && <><label className="context-chip">Pilot program <select aria-label="Pilot program" value={programId} onChange={e => setProgramId(e.target.value)}>{pilotPrograms.map(p => <option key={p.program_id} value={p.program_id}>{p.name}</option>)}</select></label>{pilotPrograms.length > 0 && <PilotSourceView key={programId} programId={programId} status={runtime} />}</>}
          {runtime?.mode === 'demo' && <div hidden={view !== 'cockpit'}><CockpitView canWrite={runtime.identity.permission === 'RW'} reviewReady={runtime.review_ready} key={programId} programId={programId} /></div>}
          {runtime?.mode === 'pilot' && ['semantic','knowledge'].includes(view) && <p className="reader-notice">This capability is unavailable until a pilot semantic and evidence package is approved.</p>}
          {runtime?.mode === 'demo' && view === 'knowledge' && <KnowledgeCards key={programId} programId={programId} />}
          {runtime && view === 'models' && <>{runtime.identity.permission === 'RO' && <p className="reader-notice">Workbench RW permission is required to change or test model configuration.</p>}<fieldset disabled={runtime.identity.permission !== 'RW'}><ModelsView /></fieldset></>}
          {runtime && view === 'nifi' && <NifiView pilot={runtime.mode === 'pilot'} />}
          {runtime?.mode === 'demo' && view === 'semantic' && <SemanticView key={programId} programId={programId} />}
          <footer className="workspace-footer"><span>Cloudera AI · Vehicle Manufacturing Blueprint</span><span>{view === 'nifi' ? 'Current snapshots · No operational actions' : 'Code decides · AI narrates'}</span></footer>
        </div>
      </main>
    </div>
  )
}
