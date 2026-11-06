import { t, tNode } from '../i18n'
import { useEffect, useRef, useState } from 'react';
import { Search, FileText, ExternalLink, Image as ImageIcon, X } from 'lucide-react';
import type { KbHit, KnowledgeReadiness } from '../api';
import { searchKb, assetUrl, getKnowledgeReadiness } from '../api';
export function KnowledgeCards({ programId }: {
    programId: string;
}) {
    const [readiness, setReadiness] = useState<KnowledgeReadiness | null>(null);
    useEffect(() => { void getKnowledgeReadiness().then(setReadiness).catch(() => setReadiness(null)); }, []);
    const [kind, setKind] = useState('all');
    const [query, setQuery] = useState('');
    const [hits, setHits] = useState<KbHit[]>([]);
    const [selected, setSelected] = useState<KbHit | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [previewError, setPreviewError] = useState(false);
    const request = useRef(0);
    const dialog = useRef<HTMLDialogElement>(null);
    const load = async (text: string) => {
        const id = ++request.current;
        setLoading(true);
        setError('');
        try {
            const results = await searchKb(text.trim() || 'battery', undefined, 20, false, programId, kind);
            if (id === request.current)
                setHits(results);
        }
        catch {
            if (id === request.current)
                setError('The source collection could not be loaded. Retry the search.');
        }
        finally {
            if (id === request.current)
                setLoading(false);
        }
    };
    useEffect(() => {
        const id = ++request.current;
        let active = true;
        searchKb('battery', undefined, 20, false, programId, kind).then(results => { if (active && id === request.current)
            setHits(results); }).catch(() => { if (active && id === request.current)
            setError('The source collection could not be loaded. Retry the search.'); }).finally(() => { if (active && id === request.current)
            setLoading(false); });
        return () => { active = false; };
    }, [programId, kind]);
    useEffect(() => { if (selected)
        dialog.current?.showModal(); }, [selected]);
    const open = (hit: KbHit) => { setSelected(hit); setPreviewError(false); };
    const title = (hit: KbHit) => hit.source_url?.includes('BMW_i3') ? 'BMW i3 battery pack — original reference photograph' : hit.title;
    return <section className="knowledge-library">
    <div className="library-summary"><div><strong>{t("Source collection")}</strong><p>{t("Generated direct evidence, historical demo evidence, and attributed external references.")}</p></div><span className="context-chip">{tNode(loading ? 'Loading…' : `${hits.length} ${hits.length === 1 ? 'source' : 'sources'}`)}</span></div>
    <label className="context-chip">{t("Evidence type")}<select aria-label={t("Evidence type")} value={kind} onChange={e => setKind(e.target.value)}><option value="all">{t("All evidence")}</option><option value="direct_demo">{t("Program evidence")}</option><option value="external_reference">{t("External references")}</option><option value="historical_demo">{t("Historical evidence")}</option></select></label>
    <form onSubmit={e => { e.preventDefault(); void load(query); }} className="library-search"><Search size={16}/><input aria-label={t("Search knowledge base")} value={query} onChange={e => setQuery(e.target.value)} placeholder={t("Search the source collection\u2026")}/><button className="primary-button" disabled={loading}>{t("Search")}</button></form>
    <p className="library-scope">{t("Evidence is scoped to the selected revision. Direct demo evidence uses seeded observations; external sources provide reference context.")}</p>
    {tNode(readiness && <p className="library-scope">{t("Index:")}{tNode(readiness.index.state)}{t(". Retrieval: lexical + offline token hash. Image similarity:")}{tNode(readiness.image_similarity.state)}{t(". OCR: unverified, cache replay only; paid extraction requires a separate build command.")}</p>)}
    {tNode(error && <p role="alert" className="reader-notice reader-error">{tNode(error)}</p>)}
    {tNode(!loading && !error && !hits.length && <div className="library-empty"><FileText size={24}/><h2>{t("No source material found")}</h2><p>{t("Try another query or evidence type.")}</p></div>)}
    <div className="library-items">{tNode(hits.map(hit => <article key={hit.asset_id} className="library-item"><button className="library-thumbnail" onClick={() => open(hit)} aria-label={t(`Preview ${title(hit)}`)}>{tNode(hit.modality === 'image' ? <img src={assetUrl(hit.asset_id)} alt={title(hit)} onError={e => { e.currentTarget.hidden = true; }}/> : <FileText size={32}/>)}</button><div className="library-item-body"><div className="library-meta"><span>{tNode(hit.modality === 'image' ? <ImageIcon size={13}/> : <FileText size={13}/>)}{tNode(hit.modality === 'image' ? 'Photograph / image' : hit.modality.toUpperCase())}</span><span>{tNode(hit.evidence_kind?.replaceAll('_', ' ') || 'External reference')}</span></div><button onClick={() => open(hit)} className="library-title">{tNode(title(hit))}</button><p>{tNode(hit.caption_text)}</p><small>{tNode(hit.provenance)}</small>{tNode(!!hit.retrieval?.chunks.length && <details><summary>{t("Matched source text")}</summary>{tNode(hit.retrieval.chunks.map(chunk => <p key={chunk.chunk_id}><strong>{t("Page")}{tNode(chunk.page)} · {tNode(chunk.section)}</strong><br />{tNode(chunk.text)}<br /><small>{tNode(chunk.extraction_method)} · {tNode(chunk.verification)}{t("\u00B7 SHA-256")}{tNode(chunk.source_sha256.slice(0, 12))}</small></p>))}</details>)}<div className="library-links"><button onClick={() => open(hit)}>{t("Open preview")}</button>{tNode(hit.source_url && <a href={hit.source_url} target="_blank" rel="noreferrer">{t("Original source")}<ExternalLink size={12}/></a>)}{tNode(hit.license_url && <a href={hit.license_url} target="_blank" rel="noreferrer">{t("License")}<ExternalLink size={12}/></a>)}</div></div></article>))}</div>
    <dialog ref={dialog} onClose={() => setSelected(null)} onClick={e => { if (e.target === e.currentTarget)
        dialog.current?.close(); }} className="semantic-dialog">{tNode(selected && <><header><div><p className="eyebrow">{tNode(selected.evidence_kind?.replaceAll('_', ' ') || 'EXTERNAL REFERENCE')}</p><h2>{tNode(title(selected))}</h2></div><button autoFocus className="quiet-button" onClick={() => dialog.current?.close()} aria-label={t("Close source preview")}><X size={16}/></button></header>{tNode(previewError ? <p role="alert">{t("Preview unavailable. Open the original source below.")}</p> : selected.modality === 'image' ? <img src={assetUrl(selected.asset_id)} alt={title(selected)} onError={() => setPreviewError(true)}/> : <iframe src={assetUrl(selected.asset_id)} title={title(selected)}/>)}<p>{tNode(selected.caption_text)}</p><p className="reader-caption">{tNode(selected.provenance)}</p><p className="reader-notice">{tNode(selected.source_url ? 'External reference material cannot establish Atlas performance or compliance.' : 'Generated demo evidence reproduces seeded engineering records for the displayed program revision.')}</p>{tNode(selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer" className="text-accent underline">{t("Open original source")}</a>)}</>)}</dialog>
  </section>;
}
