import { useState } from 'react'
import { WorkflowGraph, type WorkflowNode } from './WorkflowGraph'
import { PlayCircle } from 'lucide-react'
import type { PipelineItem } from './PipelineStream'
import { PipelineStream } from './PipelineStream'
import { streamReview } from '../api'

const PHASES = ['COLLECTING', 'ANALYZING']
const WORKER_LABEL: Record<string, string> = {
  coverage: 'Coverage',
  testverdict: 'Test Verdict',
  compliance: 'Compliance',
  designrisk: 'Design Risk',
  knowledgereuse: 'Knowledge Reuse',
}

const REC_CLS: Record<string, string> = {
  PASS: 'text-aml-green bg-aml-green/10 border-aml-green/30',
  CONDITIONAL: 'text-aml-amber bg-aml-amber/10 border-aml-amber/30',
  FAIL: 'text-aml-red bg-aml-red/10 border-aml-red/30',
}

interface Props {
  programId: string
  onReviewDone: (reviewId: string | null) => void
}

export const GateReview: React.FC<Props> = ({ programId, onReviewDone }) => {
  const [error, setError] = useState('')
  const [started, setStarted] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [activePhase, setActivePhase] = useState<string | null>(null)
  const [items, setItems] = useState<PipelineItem[]>([])
  const [narrative, setNarrative] = useState('')
  const [recommendation, setRecommendation] = useState<string | null>(null)
  const [reviewId, setReviewId] = useState<string | null>(null)

  const run = () => {
    const id = `REV-${Date.now()}`
    onReviewDone(null)
    setError('')
    setStarted([])
    setReviewId(null)
    setRunning(true)
    setActivePhase(null)
    setRecommendation(null)
    setNarrative('')
    setItems(Object.entries(WORKER_LABEL).map(([key, label]) => ({
      key, label, status: 'running' as const,
    })))

    let completed = false
    streamReview(programId, id, evt => {
      const type = evt.type as string
      if (type === 'phase') {
        setActivePhase(evt.phase as string)
      } else if (type === 'worker_start') {
        setStarted(prev => [...prev, evt.worker as string])
      } else if (type === 'worker_done') {
        const worker = evt.worker as string
        setItems(prev => prev.map(it => it.key === worker
          ? { ...it, status: 'ok', detail: evt.findings as string, chips: evt.evidence_ids as string[] }
          : it))
      } else if (type === 'recommendation') {
        setRecommendation(evt.value as string)
      } else if (type === 'token') {
        setNarrative(prev => prev + (evt.text as string))
      } else if (type === 'done') {
        completed = true
        setRunning(false)
        setReviewId(id)
        onReviewDone(id)
      }
    }).then(() => { if (!completed) throw new Error('Review stream ended before completion. Please retry.') })
      .catch((err: Error) => { setRunning(false); setError(err.message); setItems(prev => prev.map(it => it.status === 'running' ? { ...it, status: 'error' } : it)) })
  }

  const nodes: WorkflowNode[] = [
    { id: 'supervisor', label: 'Supervisor', status: items.length ? 'completed' : 'pending' },
    ...Object.entries(WORKER_LABEL).map(([id, label]): WorkflowNode => {
      const item = items.find(it => it.key === id)
      return { id, label, status: item?.status === 'ok' ? 'completed' : item?.status === 'error' ? 'error' : started.includes(id) ? 'running' : 'pending' }
    }),
    { id: 'decision', label: 'Code decision', status: recommendation ? 'completed' : error ? 'error' : 'pending' },
    { id: 'narrative', label: 'Gate narrative', status: reviewId ? 'completed' : error ? 'error' : activePhase === 'ANALYZING' ? 'running' : 'pending' },
  ]

  return (
    <div className="bg-surface-1 rounded-lg shadow-soft p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-2xs uppercase tracking-wider text-ink-faint">Gate review</p>
        <div className="flex items-center gap-2">
          {recommendation && (
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${REC_CLS[recommendation] ?? ''}`}>
              {recommendation}
            </span>
          )}
          <button
            onClick={run}
            disabled={running}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
              bg-accent text-white hover:bg-accent-dim disabled:opacity-50 transition-colors"
          >
            <PlayCircle className="w-3.5 h-3.5" />
            {running ? 'Running…' : 'Run Gate Review'}
          </button>
        </div>
      </div>

      <WorkflowGraph nodes={nodes} running={running} />
      {error && <p role="alert" className="text-sm text-aml-red">{error}</p>}
      <PipelineStream
        phases={PHASES}
        activePhase={activePhase}
        items={items}
        narrative={narrative}
        narrativeTitle="Gate review narrative"
        running={running}
        idle={<span>No gate review run yet. Click "Run Gate Review" to start.</span>}
      />

      {reviewId && !running && (
        <p className="text-2xs text-ink-faint">review_id: <span className="font-mono">{reviewId}</span></p>
      )}
    </div>
  )
}
