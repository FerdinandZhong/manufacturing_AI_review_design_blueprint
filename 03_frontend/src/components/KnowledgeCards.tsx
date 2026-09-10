import { useEffect, useRef, useState } from 'react'
import { Search, FileText, ExternalLink } from 'lucide-react'
import type { KbHit } from '../api'
import { searchKb, assetUrl } from '../api'

function Preview({ hit }: { hit: KbHit }) {
  const [text, setText] = useState('')
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    if (hit.modality === 'text') fetch(assetUrl(hit.asset_id), { signal: controller.signal }).then(r => {
      if (!r.ok) throw new Error('Unavailable')
      return r.text()
    }).then(setText).catch(e => { if (e.name !== 'AbortError') setFailed(true) })
    return () => controller.abort()
  }, [hit.asset_id, hit.modality])
  if (failed) return <p role="alert" className="p-4 text-sm text-aml-red">Preview unavailable. Try searching again.</p>
  if (hit.modality === 'image') return <img src={assetUrl(hit.asset_id)} alt={hit.title} onError={() => setFailed(true)} className="w-full max-h-[55vh] object-contain rounded-lg bg-surface-2" />
  if (hit.modality === 'pdf') return <iframe title={hit.title} src={assetUrl(hit.asset_id)} className="w-full h-96" />
  return <pre className="whitespace-pre-wrap rounded-lg bg-surface-2 p-5 text-sm leading-relaxed text-ink font-sans">{text || 'Loading document…'}</pre>
}

export function KnowledgeCards() {
  const [query, setQuery] = useState('thermal runaway containment design')
  const [cls, setCls] = useState('')
  const [hits, setHits] = useState<KbHit[]>([])
  const [selected, setSelected] = useState<KbHit | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const request = useRef(0)
  const dialog = useRef<HTMLDialogElement>(null)
  const search = async () => {
    const id = ++request.current
    setLoading(true); setError('')
    try { const result = await searchKb(query, cls || undefined, 10); if (id === request.current) setHits(result) }
    catch { if (id === request.current) setError('Could not load the knowledge base. Please retry.') }
    finally { if (id === request.current) setLoading(false) }
  }
  useEffect(() => {
    const id = ++request.current
    let active = true
    searchKb('thermal runaway containment design', undefined, 10)
      .then(result => { if (active && id === request.current) setHits(result) })
      .catch(() => { if (active && id === request.current) setError('Could not load the knowledge base. Please retry.') })
      .finally(() => { if (active && id === request.current) setLoading(false) })
    return () => { active = false }
  }, [])
  useEffect(() => { if (selected) dialog.current?.showModal() }, [selected])
  return <section className="bg-surface-1 rounded-lg shadow-soft p-4 space-y-4">
    <div><h2 className="font-semibold text-sm text-ink">Knowledge base</h2><p className="text-xs text-ink-muted mt-1">Explore designs, test evidence, and reusable lessons from prior programs.</p></div>
    <form onSubmit={e => { e.preventDefault(); void search() }} className="space-y-2">
      <div className="flex gap-2"><label className="flex items-center gap-2 bg-surface-2 rounded-lg px-3 flex-1 min-w-0"><Search size={14} /><input aria-label="Search knowledge base" value={query} onChange={e => setQuery(e.target.value)} className="w-full py-2 text-sm outline-none" /></label><button disabled={loading} className="bg-accent text-white rounded-lg px-3 text-xs font-semibold">{loading ? 'Searching…' : 'Search'}</button></div>
      <select aria-label="Asset type" value={cls} onChange={e => setCls(e.target.value)} className="text-xs border border-surface-3 rounded-lg p-2 w-full"><option value="">All asset types</option>{['DesignImage', 'TestReport', 'SpecSheet', 'ComponentPhoto', 'RequirementDoc'].map(c => <option key={c}>{c}</option>)}</select>
    </form>
    {error && <p role="alert" className="text-sm text-aml-red">{error}</p>}
    {!loading && !error && !hits.length && <p className="text-sm text-ink-muted">No matching assets. Try another search or asset type.</p>}
    <div className="space-y-3 max-h-[75vh] overflow-y-auto pr-1">{hits.map(hit => <button key={hit.asset_id} onClick={() => setSelected(hit)} className="w-full text-left rounded-lg border border-surface-3 overflow-hidden hover:border-accent focus-visible:outline-accent">
      {hit.modality === 'image' && <div className="bg-surface-2 p-2"><img src={assetUrl(hit.asset_id)} alt={hit.title} className="w-full h-44 object-contain" onError={e => { e.currentTarget.style.display = 'none' }} /></div>}
      <div className="p-3 space-y-2"><div className="flex items-center gap-2 text-xs"><FileText size={14} className="text-accent"/><span className="text-accent font-semibold">{hit.ontology_class}</span><span className="ml-auto text-ink-faint">Similarity {hit.score.toFixed(2)}</span></div><h3 className="font-semibold text-sm text-ink">{hit.title}</h3><p className="text-xs text-ink-muted leading-relaxed">{hit.caption_text}</p><p className="text-xs font-mono text-ink-faint break-all">{hit.program_ref} · {hit.linked_entity_id}</p><span className="inline-block text-xs font-semibold text-accent">Open asset & details →</span></div>
    </button>)}</div>
    <dialog ref={dialog} onClose={() => setSelected(null)} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close() }} className="m-auto w-[min(1000px,94vw)] max-h-[90vh] overflow-y-auto rounded-xl p-6 bg-surface-1 text-ink backdrop:bg-header/60">
      {selected && <div className="space-y-4"><div className="flex items-start justify-between gap-4"><div><p className="text-xs text-accent font-semibold">{selected.ontology_class} · {selected.modality}</p><h2 className="text-xl font-bold mt-1">{selected.title}</h2></div><button autoFocus onClick={() => dialog.current?.close()} className="px-3 py-2 rounded-lg bg-surface-2 text-sm">Close</button></div>
        <Preview key={selected.asset_id} hit={selected} />
        <p className="text-sm leading-relaxed">{selected.caption_text}</p>
        <dl className="grid sm:grid-cols-2 gap-4 text-sm"><div><dt className="text-ink-muted">Program</dt><dd>{selected.program_ref}</dd></div><div><dt className="text-ink-muted">Linked {selected.linked_entity_type}</dt><dd className="font-mono break-all">{selected.linked_entity_id}</dd></div><div><dt className="text-ink-muted">Asset ID</dt><dd className="font-mono break-all">{selected.asset_id}</dd></div><div><dt className="text-ink-muted">Search similarity</dt><dd>{selected.score.toFixed(2)} · retrieval relevance, not engineering confidence</dd></div></dl>
        <div className="bg-surface-2 rounded-lg p-4 text-sm space-y-2"><h3 className="font-semibold">How to use this evidence</h3><p>{selected.ontology_class === 'DesignImage' ? 'Inspect the barrier and cooling layout, then compare the linked thermal test report before proposing a design change.' : selected.ontology_class === 'TestReport' ? 'Compare the historical test outcome with the current requirement and test result. Reuse the lesson as review context, not as validation of the new pack.' : 'Use this reference to understand the linked component, design specification, or requirement. Validate applicability to the current program.'}</p><p className="text-ink-muted">{selected.provenance || 'Synthetic demo artifact; not production engineering evidence.'}</p>{selected.source_url && <a className="text-accent underline mr-4" href={selected.source_url} target="_blank" rel="noreferrer">Original source</a>}{selected.license_url && <a className="text-accent underline" href={selected.license_url} target="_blank" rel="noreferrer">CC BY-SA 3.0 license</a>}</div>
        <a href={assetUrl(selected.asset_id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm text-accent font-semibold"><ExternalLink size={16}/>Open original asset</a>
      </div>}
    </dialog>
  </section>
}
