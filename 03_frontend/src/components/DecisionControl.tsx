import { useState } from 'react'
import type { GateReviewRow, ReviewDecision } from '../api'
import { postDecision } from '../api'

const DECISIONS: ReviewDecision[] = ['APPROVED', 'APPROVED_WITH_CONDITIONS', 'REJECTED']

interface Props {
  reviewId: string | null
}

/** Human gate-decision control. Disabled until a GateReview run has produced
 *  a review_id; submits POST /api/review/{review_id}/decision and shows the
 *  persisted gate_reviews row. */
export const DecisionControl: React.FC<Props> = ({ reviewId }) => {
  const [decision, setDecision] = useState<ReviewDecision>('APPROVED_WITH_CONDITIONS')
  const [rationale, setRationale] = useState('')
  const [adjudicator, setAdjudicator] = useState('')
  const [result, setResult] = useState<GateReviewRow | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    if (!reviewId) return
    setSubmitting(true)
    try {
      const row = await postDecision(reviewId, { decision, rationale, adjudicator })
      setResult(row)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-surface-1 rounded-lg shadow-soft p-4 space-y-3">
      <p className="text-2xs uppercase tracking-wider text-ink-faint">Gate decision</p>

      <div className="flex flex-wrap items-center gap-2">
        {DECISIONS.map(d => (
          <button
            key={d}
            disabled={!reviewId}
            onClick={() => setDecision(d)}
            className={`text-2xs font-semibold px-2.5 py-1.5 rounded-full border transition-colors disabled:opacity-40
              ${decision === d ? 'bg-accent text-white border-accent' : 'border-surface-3 text-ink-muted hover:border-accent/40'}`}
          >
            {d.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <input
          disabled={!reviewId}
          value={adjudicator}
          onChange={e => setAdjudicator(e.target.value)}
          placeholder="Adjudicator"
          className="text-xs bg-surface-2 rounded-lg px-2.5 py-1.5 outline-none disabled:opacity-40"
        />
        <input
          disabled={!reviewId}
          value={rationale}
          onChange={e => setRationale(e.target.value)}
          placeholder="Rationale (optional)"
          className="text-xs bg-surface-2 rounded-lg px-2.5 py-1.5 outline-none disabled:opacity-40"
        />
      </div>

      <button
        onClick={submit}
        disabled={!reviewId || submitting}
        className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-accent text-white hover:bg-accent-dim disabled:opacity-40"
      >
        {submitting ? 'Submitting…' : reviewId ? 'Submit decision' : 'Run a gate review first'}
      </button>

      {result && (
        <div className="bg-surface-2 rounded-lg p-3 text-2xs space-y-0.5">
          <p><span className="text-ink-faint">review_id</span> <span className="font-mono text-ink">{result.review_id}</span></p>
          <p><span className="text-ink-faint">state</span> <span className="font-mono text-ink">{result.state}</span></p>
          <p><span className="text-ink-faint">decision</span> <span className="font-mono text-ink">{result.decision}</span></p>
          <p><span className="text-ink-faint">decided_by</span> <span className="font-mono text-ink">{result.decided_by}</span></p>
        </div>
      )}
    </div>
  )
}
