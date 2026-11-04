import { useEffect, useState } from 'react'
import { api, getRequirements, getDesign, getBom, getTests } from '../api'
import type { Requirement, RuntimeStatus } from '../api'

export function PilotSourceView({ programId, status }: { programId: string; status: RuntimeStatus }) {
  const [records, setRecords] = useState<{ requirements: Requirement[]; designs: number; parts: number; plans: number; observations: Record<string, unknown>[] } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([getRequirements(programId), getDesign(programId), getBom(programId), getTests(programId), api.get(`/programs/${programId}/data/observations`, { params: { limit: 20 }, signal: controller.signal })]).then(([requirements, designs, parts, plans, observations]) => {
      if (!controller.signal.aborted) setRecords({ requirements, designs: designs.length, parts: parts.length, plans: plans.length, observations: observations.data.items })
    }).catch(() => { if (!controller.signal.aborted) setError('Pilot source records are unavailable. No demo data was substituted.') })
    return () => controller.abort()
  }, [programId])
  return <section aria-label="Pilot source inspection">
    <p className="reader-notice">Pilot source inspection · Reviews, computed verdicts, and ML predictions remain unavailable until domain acceptance.</p>
    <p className="reader-caption">{status.source.source_id} · {status.source.revision_id} · {status.source.snapshot_id} · Extracted {status.source.extracted_at}. Freshness: {status.source.freshness?.replaceAll('_', ' ')}.</p>
    <p>{status.source.provenance}</p>
    {error && <p role="alert">{error}</p>}
    {records && <><p>{records.requirements.length} requirements · {records.designs} designs · {records.parts} BOM items · {records.plans} test plans</p><div className="overflow-auto"><table className="w-full text-sm"><thead><tr><th>Requirement</th><th>Description</th><th>Target</th></tr></thead><tbody>{records.requirements.map(r => <tr key={r.req_id}><td>{r.req_id}</td><td>{r.text}</td><td>{r.target_value} {r.unit}</td></tr>)}</tbody></table></div><details className="reader-notice"><summary>Source observations · first 20 records</summary><pre className="overflow-auto">{JSON.stringify(records.observations, null, 2)}</pre></details></>}
  </section>
}
