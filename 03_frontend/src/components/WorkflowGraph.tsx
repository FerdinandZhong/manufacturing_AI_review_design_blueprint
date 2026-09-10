export interface WorkflowNode {
  id: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'skip' | 'error'
}
const colors = { pending: '#9aa1ac', running: '#e35b1f', completed: '#059669', skip: '#9aa1ac', error: '#dc2626' }

/** Five parallel readers converge on a deterministic decision, then narration. */
export function WorkflowGraph({ nodes, running }: { nodes: WorkflowNode[]; running?: boolean }) {
  const positions = nodes.map((_, i) => i === 0 ? [10, 160] : i < 6 ? [190, 16 + (i - 1) * 72] : [390, i === 6 ? 112 : 220])
  const edges = [[0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [1, 6], [2, 6], [3, 6], [4, 6], [5, 6], [6, 7]]
  return <div className="rounded-lg border border-surface-3 bg-surface-2 p-3">
    <div className="flex justify-between text-xs text-ink-muted"><span className="font-semibold">Agent workflow {running ? '· Live' : ''}</span><span>{nodes.filter(n => n.status === 'completed').length}/{nodes.length} complete</span></div>
    <div className="overflow-x-auto">
      <svg viewBox="0 0 560 375" className="w-full min-w-[420px]" role="img" aria-label="Supervisor dispatches five parallel agents, then computes a recommendation and writes the narrative">
        {edges.map(([a, b]) => {
          const [x, y] = positions[a], [tx, ty] = positions[b]
          const d = a === 6 ? `M ${x + 75} ${y + 48} V ${ty}` : `M ${x + 150} ${y + 24} C ${x + 175} ${y + 24}, ${tx - 25} ${ty + 24}, ${tx} ${ty + 24}`
          return <path key={`${a}-${b}`} d={d} fill="none" stroke={nodes[a].status === 'completed' ? colors.completed : '#d5d9e0'} strokeWidth="2" />
        })}
        {nodes.map((n, i) => <g key={n.id} transform={`translate(${positions[i].join(',')})`}>
          <title>{n.label}: {n.status}</title>
          <rect width="150" height="48" rx="8" fill="white" stroke={colors[n.status]} strokeWidth={n.status === 'running' ? 2 : 1} className={n.status === 'running' ? 'animate-pulse' : ''} />
          <text x="75" y="20" textAnchor="middle" fill="#1a1a2e" fontSize="12" fontWeight="600">{n.label}</text>
          <text x="75" y="36" textAnchor="middle" fill={colors[n.status]} fontSize="10">{n.status}</text>
        </g>)}
      </svg>
    </div>
    <p className="text-xs text-ink-muted">Five specialists read evidence in parallel. Code computes the recommendation; the LLM narrates the findings.</p>
  </div>
}
