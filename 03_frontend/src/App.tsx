import { useState } from 'react'
import { StageTracker } from './components/StageTracker'
import { RequirementsTable } from './components/RequirementsTable'
import { RiskPanel } from './components/RiskPanel'
import { TraceabilityMatrix } from './components/TraceabilityMatrix'
import { GateReview } from './components/GateReview'
import { KnowledgeCards } from './components/KnowledgeCards'
import { DecisionControl } from './components/DecisionControl'

// Dashboard A only (Dashboard B is Phase 2, out of scope). A single-page
// cockpit is the lazier-and-correct MVP for one dashboard — no router needed.
const PROGRAM_ID = 'PACK-ATLAS-01'

export default function App() {
  const [reviewId, setReviewId] = useState<string | null>(null)

  return (
    <div className="min-h-screen flex flex-col bg-surface-0 font-sans">

      {/* ── Cloudera header ── */}
      <header className="bg-header border-b-[3px] border-accent flex items-center px-6 py-0 shrink-0 h-14">
        <div className="flex items-center gap-3 pr-8 border-r border-white/10">
          <span className="text-white font-black text-lg tracking-[0.06em] leading-none select-none">
            CLOUDERA
          </span>
        </div>
        <div className="px-6">
          <p className="text-white font-semibold text-sm leading-tight">Vehicle NPI Platform</p>
          <p className="text-white/40 text-2xs leading-tight">
            Agentic NPI lifecycle · Cloudera AI Applied ML Prototype
          </p>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex-1 p-5 space-y-4">
        <StageTracker programId={PROGRAM_ID} />

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.3fr_1fr] gap-4">
          {/* Left */}
          <div className="space-y-4">
            <RequirementsTable programId={PROGRAM_ID} />
            <RiskPanel programId={PROGRAM_ID} />
          </div>

          {/* Center */}
          <div className="space-y-4">
            <TraceabilityMatrix programId={PROGRAM_ID} />
            <GateReview programId={PROGRAM_ID} onReviewDone={setReviewId} />
            <DecisionControl reviewId={reviewId} />
          </div>

          {/* Right */}
          <div className="space-y-4">
            <KnowledgeCards />
          </div>
        </div>
      </div>
    </div>
  )
}
