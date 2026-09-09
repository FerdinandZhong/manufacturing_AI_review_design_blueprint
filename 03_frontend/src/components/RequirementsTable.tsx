import { useEffect, useState } from 'react'
import type { Requirement, DesignSpec, BomItem } from '../api'
import { getRequirements, getDesign, getBom } from '../api'

interface Props {
  programId: string
}

type Tab = 'requirements' | 'design' | 'bom'

/** Requirements table with adjacent Design/BOM sub-tabs — a lightweight
 *  viewer, not a full editor. */
export const RequirementsTable: React.FC<Props> = ({ programId }) => {
  const [tab, setTab] = useState<Tab>('requirements')
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [design, setDesign] = useState<DesignSpec[]>([])
  const [bom, setBom] = useState<BomItem[]>([])

  useEffect(() => {
    getRequirements(programId).then(setRequirements)
    getDesign(programId).then(setDesign)
    getBom(programId).then(setBom)
  }, [programId])

  return (
    <div className="bg-surface-1 rounded-lg shadow-soft overflow-hidden">
      <div className="flex items-center gap-1 border-b border-surface-3 px-3 py-2">
        {(['requirements', 'design', 'bom'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`text-2xs font-semibold uppercase tracking-wide px-2.5 py-1 rounded-full transition-colors
              ${tab === t ? 'bg-accent text-white' : 'text-ink-faint hover:text-ink-muted'}`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="max-h-80 overflow-y-auto">
        {tab === 'requirements' && (
          <table className="w-full text-2xs">
            <thead className="sticky top-0 bg-surface-2 text-ink-faint uppercase tracking-wide">
              <tr>
                <Th>Req ID</Th><Th>Category</Th><Th>Text</Th><Th>Target</Th><Th>Priority</Th><Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {requirements.map(r => (
                <tr key={r.req_id} className="border-t border-surface-2">
                  <Td mono>{r.req_id}</Td>
                  <Td>{r.category}</Td>
                  <Td className="max-w-xs">{r.text}</Td>
                  <Td>{r.target_value != null ? `${r.target_value} ${r.unit ?? ''}` : '—'}</Td>
                  <Td>{r.priority}</Td>
                  <Td>{r.status}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'design' && (
          <table className="w-full text-2xs">
            <thead className="sticky top-0 bg-surface-2 text-ink-faint uppercase tracking-wide">
              <tr>
                <Th>Spec ID</Th><Th>Req ID</Th><Th>Parameter</Th><Th>Value</Th><Th>Chemistry</Th><Th>Version</Th>
              </tr>
            </thead>
            <tbody>
              {design.map(d => (
                <tr key={d.spec_id} className="border-t border-surface-2">
                  <Td mono>{d.spec_id}</Td>
                  <Td mono>{d.req_id}</Td>
                  <Td>{d.parameter}</Td>
                  <Td>{d.value != null ? `${d.value} ${d.unit ?? ''}` : '—'}</Td>
                  <Td>{d.cell_chemistry ?? '—'}</Td>
                  <Td>{d.version}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'bom' && (
          <table className="w-full text-2xs">
            <thead className="sticky top-0 bg-surface-2 text-ink-faint uppercase tracking-wide">
              <tr>
                <Th>Part ID</Th><Th>Name</Th><Th>Supplier</Th><Th>Qty</Th><Th>Unit Cost</Th><Th>Mass (kg)</Th>
              </tr>
            </thead>
            <tbody>
              {bom.map(b => (
                <tr key={b.part_id} className="border-t border-surface-2">
                  <Td mono>{b.part_id}</Td>
                  <Td>{b.name}</Td>
                  <Td>{b.supplier_id}</Td>
                  <Td>{b.qty}</Td>
                  <Td>${b.unit_cost.toFixed(2)}</Td>
                  <Td>{b.mass_kg}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

const Th: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <th className="text-left font-semibold px-3 py-1.5">{children}</th>
)

const Td: React.FC<{ children: React.ReactNode; mono?: boolean; className?: string }> = ({ children, mono, className }) => (
  <td className={`px-3 py-1.5 text-ink ${mono ? 'font-mono' : ''} ${className ?? ''}`}>{children}</td>
)
