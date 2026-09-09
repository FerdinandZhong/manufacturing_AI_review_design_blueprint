import { useEffect, useState } from 'react'
import { Search, FileText, Image as ImageIcon } from 'lucide-react'
import type { KbHit } from '../api'
import { searchKb, assetUrl } from '../api'

const DEFAULT_QUERY = 'thermal runaway containment design'

/** Multimodal knowledge-base search — "the data is the demo" panel.
 *  Image hits render a real thumbnail via /api/asset/{id}; pdf/text hits
 *  show an icon since a raw <img> can't render those. */
export const KnowledgeCards: React.FC = () => {
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [hits, setHits] = useState<KbHit[]>([])

  const search = (q: string) => searchKb(q).then(setHits).catch(() => setHits([]))

  useEffect(() => { search(DEFAULT_QUERY) }, [])

  return (
    <div className="bg-surface-1 rounded-lg shadow-soft p-4 space-y-3">
      <p className="text-2xs uppercase tracking-wider text-ink-faint">Knowledge base</p>

      <form
        onSubmit={e => { e.preventDefault(); search(query) }}
        className="flex items-center gap-2"
      >
        <div className="flex-1 flex items-center gap-1.5 bg-surface-2 rounded-lg px-2.5 py-1.5">
          <Search className="w-3.5 h-3.5 text-ink-faint shrink-0" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="flex-1 bg-transparent text-xs text-ink outline-none"
            placeholder="Search the knowledge base…"
          />
        </div>
        <button
          type="submit"
          className="px-2.5 py-1.5 rounded-lg text-2xs font-semibold bg-accent text-white hover:bg-accent-dim"
        >
          Search
        </button>
      </form>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {hits.map(h => (
          <div key={h.asset_id} className="flex gap-3 bg-surface-2 rounded-lg p-2.5">
            <div className="w-14 h-14 rounded-lg bg-surface-1 flex items-center justify-center overflow-hidden shrink-0">
              {h.modality === 'image' ? (
                <img src={assetUrl(h.asset_id)} alt={h.title} className="w-full h-full object-cover" />
              ) : h.modality === 'pdf' ? (
                <FileText className="w-5 h-5 text-ink-faint" />
              ) : (
                <ImageIcon className="w-5 h-5 text-ink-faint" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-2xs font-semibold px-1.5 py-0.5 rounded-full bg-accent/10 text-accent uppercase tracking-wide">
                  {h.ontology_class}
                </span>
                <span className="text-2xs text-ink-faint">score {h.score.toFixed(2)}</span>
              </div>
              <p className="text-xs font-semibold text-ink truncate mt-0.5">{h.title}</p>
              <p className="text-2xs text-ink-faint truncate">
                linked: {h.linked_entity_type} · <span className="font-mono">{h.linked_entity_id}</span>
              </p>
            </div>
          </div>
        ))}
        {hits.length === 0 && <p className="text-2xs text-ink-faint">No matches.</p>}
      </div>
    </div>
  )
}
