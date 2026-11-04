import { useEffect, useRef, useState } from 'react'
import { Search, FileText, ExternalLink, Image as ImageIcon, X } from 'lucide-react'
import type { KbHit, KnowledgeReadiness } from '../api'
import { searchKb, assetUrl, getKnowledgeReadiness } from '../api'

export function KnowledgeCards({ programId }: { programId: string }) {
  const [readiness, setReadiness] = useState<KnowledgeReadiness | null>(null)
  useEffect(() => { void getKnowledgeReadiness().then(setReadiness).catch(() => setReadiness(null)) }, [])
  const [kind, setKind] = useState('all')
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<KbHit[]>([])
  const [selected, setSelected] = useState<KbHit | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [previewError, setPreviewError] = useState(false)
  const request = useRef(0)
  const dialog = useRef<HTMLDialogElement>(null)
  const load = async (text: string) => {
    const id = ++request.current
    setLoading(true); setError('')
    try { const results = await searchKb(text.trim() || 'battery', undefined, 20, false, programId, kind); if (id === request.current) setHits(results) }
    catch { if (id === request.current) setError('The source collection could not be loaded. Retry the search.') }
    finally { if (id === request.current) setLoading(false) }
  }
  useEffect(() => {
    const id = ++request.current
    let active = true
    searchKb('battery', undefined, 20, false, programId, kind).then(results => { if (active && id === request.current) setHits(results) }).catch(() => { if (active && id === request.current) setError('The source collection could not be loaded. Retry the search.') }).finally(() => { if (active && id === request.current) setLoading(false) })
    return () => { active = false }
  }, [programId, kind])
  useEffect(() => { if (selected) dialog.current?.showModal() }, [selected])
  const open = (hit: KbHit) => { setSelected(hit); setPreviewError(false) }
  const title = (hit: KbHit) => hit.source_url?.includes('BMW_i3') ? 'BMW i3 battery pack — original reference photograph' : hit.title
  return <section className="knowledge-library">
    <div className="library-summary"><div><strong>Source collection</strong><p>Generated direct evidence, historical demo evidence, and attributed external references.</p></div><span className="context-chip">{loading ? 'Loading…' : `${hits.length} ${hits.length === 1 ? 'source' : 'sources'}`}</span></div>
    <label className="context-chip">Evidence type <select aria-label="Evidence type" value={kind} onChange={e => setKind(e.target.value)}><option value="all">All evidence</option><option value="direct_demo">Program evidence</option><option value="external_reference">External references</option><option value="historical_demo">Historical evidence</option></select></label>
    <form onSubmit={e => { e.preventDefault(); void load(query) }} className="library-search"><Search size={16} /><input aria-label="Search knowledge base" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search the source collection…" /><button className="primary-button" disabled={loading}>Search</button></form>
    <p className="library-scope">Evidence is scoped to the selected revision. Direct demo evidence uses seeded observations; external sources provide reference context.</p>
    {readiness && <p className="library-scope">Index: {readiness.index.state}. Retrieval: lexical + offline token hash. Image similarity: {readiness.image_similarity.state}. OCR: unverified, cache replay only; paid extraction requires a separate build command.</p>}
    {error && <p role="alert" className="reader-notice reader-error">{error}</p>}
    {!loading && !error && !hits.length && <div className="library-empty"><FileText size={24} /><h2>No source material found</h2><p>Try another query or evidence type.</p></div>}
    <div className="library-items">{hits.map(hit => <article key={hit.asset_id} className="library-item"><button className="library-thumbnail" onClick={() => open(hit)} aria-label={`Preview ${title(hit)}`}>{hit.modality === 'image' ? <img src={assetUrl(hit.asset_id)} alt={title(hit)} onError={e => { e.currentTarget.hidden = true }} /> : <FileText size={32} />}</button><div className="library-item-body"><div className="library-meta"><span>{hit.modality === 'image' ? <ImageIcon size={13} /> : <FileText size={13} />}{hit.modality === 'image' ? 'Photograph / image' : hit.modality.toUpperCase()}</span><span>{hit.evidence_kind?.replaceAll('_', ' ') || 'External reference'}</span></div><button onClick={() => open(hit)} className="library-title">{title(hit)}</button><p>{hit.caption_text}</p><small>{hit.provenance}</small>{!!hit.retrieval?.chunks.length && <details><summary>Matched source text</summary>{hit.retrieval.chunks.map(chunk => <p key={chunk.chunk_id}><strong>Page {chunk.page} · {chunk.section}</strong><br />{chunk.text}<br /><small>{chunk.extraction_method} · {chunk.verification} · SHA-256 {chunk.source_sha256.slice(0, 12)}</small></p>)}</details>}<div className="library-links"><button onClick={() => open(hit)}>Open preview</button>{hit.source_url && <a href={hit.source_url} target="_blank" rel="noreferrer">Original source <ExternalLink size={12} /></a>}{hit.license_url && <a href={hit.license_url} target="_blank" rel="noreferrer">License <ExternalLink size={12} /></a>}</div></div></article>)}</div>
    <dialog ref={dialog} onClose={() => setSelected(null)} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close() }} className="semantic-dialog">{selected && <><header><div><p className="eyebrow">{selected.evidence_kind?.replaceAll('_', ' ') || 'EXTERNAL REFERENCE'}</p><h2>{title(selected)}</h2></div><button autoFocus className="quiet-button" onClick={() => dialog.current?.close()} aria-label="Close source preview"><X size={16} /></button></header>{previewError ? <p role="alert">Preview unavailable. Open the original source below.</p> : selected.modality === 'image' ? <img src={assetUrl(selected.asset_id)} alt={title(selected)} onError={() => setPreviewError(true)} /> : <iframe src={assetUrl(selected.asset_id)} title={title(selected)} />}<p>{selected.caption_text}</p><p className="reader-caption">{selected.provenance}</p><p className="reader-notice">{selected.source_url ? 'External reference material cannot establish Atlas performance or compliance.' : 'Generated demo evidence reproduces seeded engineering records for the displayed program revision.'}</p>{selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer" className="text-accent underline">Open original source</a>}</>}</dialog>
  </section>
}
