import { useEffect, useState } from 'react'
import type { RiskScore, FeatureImportance } from '../api'
import { getRisk } from '../api'
import { RiskBadge } from './Badge'

interface Props {
  programId: string
}

/** Ranked design-risk scores (HIGH stands out in red) plus a lightweight
 *  feature-importance bar list — no charting lib needed for 5 bars. */
export const RiskPanel: React.FC<Props> = ({ programId }) => {
  const [scores, setScores] = useState<RiskScore[]>([])
  const [explanation, setExplanation] = useState<FeatureImportance[]>([])

  useEffect(() => {
    getRisk(programId).then(d => {
      setScores([...d.scores].sort((a, b) => b.risk_prob - a.risk_prob))
      setExplanation(d.explanation)
    })
  }, [programId])

  const maxImportance = Math.max(1e-9, ...explanation.map(f => f.importance))

  return (
    <div className="bg-surface-1 rounded-lg shadow-soft p-4 space-y-4">
      <p className="text-2xs uppercase tracking-wider text-ink-faint">Design risk</p>

      <div className="space-y-1.5">
        {scores.map(s => (
          <div
            key={s.entity_id}
            className={`flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5
              ${s.risk_band === 'HIGH' ? 'bg-aml-red/10' : 'bg-surface-2'}`}
          >
            <div className="min-w-0">
              <p className="text-xs font-mono font-semibold text-ink truncate">{s.entity_id}</p>
              <p className="text-2xs text-ink-faint truncate">{s.top_features.join(', ')}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-2xs font-mono text-ink-muted">{(s.risk_prob * 100).toFixed(0)}%</span>
              <RiskBadge band={s.risk_band} small />
            </div>
          </div>
        ))}
        {scores.length === 0 && <p className="text-2xs text-ink-faint">No risk scores yet.</p>}
      </div>

      {explanation.length > 0 && (
        <div>
          <p className="text-2xs uppercase tracking-wider text-ink-faint mb-1.5">Top features</p>
          <div className="space-y-1">
            {explanation.slice(0, 5).map(f => (
              <div key={f.feature} className="flex items-center gap-2">
                <span className="text-2xs text-ink-muted w-28 truncate shrink-0">{f.feature}</span>
                <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full"
                    style={{ width: `${(f.importance / maxImportance) * 100}%` }}
                  />
                </div>
                <span className="text-2xs font-mono text-ink-faint w-10 text-right">{f.importance.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
