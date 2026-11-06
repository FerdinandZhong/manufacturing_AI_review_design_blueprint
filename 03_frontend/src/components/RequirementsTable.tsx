import { t, tNode } from '../i18n'
import { useEffect, useState } from 'react';
import type { Requirement, DesignSpec, BomItem } from '../api';
import { getRequirements, getDesign, getBom } from '../api';
interface Props {
    programId: string;
}
type Tab = 'requirements' | 'design' | 'bom';
/** Requirements table with adjacent Design/BOM sub-tabs — a lightweight
 *  viewer, not a full editor. */
export const RequirementsTable: React.FC<Props> = ({ programId }) => {
    const [tab, setTab] = useState<Tab>('requirements');
    const [requirements, setRequirements] = useState<Requirement[]>([]);
    const [design, setDesign] = useState<DesignSpec[]>([]);
    const [bom, setBom] = useState<BomItem[]>([]);
    useEffect(() => {
        getRequirements(programId).then(setRequirements);
        getDesign(programId).then(setDesign);
        getBom(programId).then(setBom);
    }, [programId]);
    return (<div className="bg-surface-1 rounded-lg shadow-soft overflow-hidden">
      <div className="record-tabs">
        {tNode((['requirements', 'design', 'bom'] as Tab[]).map(t => (<button key={t === 'bom' ? 'Bill of materials' : t === 'design' ? 'Design specifications' : 'Requirements'} onClick={() => setTab(t)} aria-pressed={tab === t}>
            {tNode(t === 'bom' ? 'Bill of materials' : t === 'design' ? 'Design specifications' : 'Requirements')}
          </button>)))}
      </div>

      <div className="max-h-80 overflow-y-auto">
        {tNode(tab === 'requirements' && (<table className="w-full text-2xs">
            <thead className="sticky top-0 bg-surface-2 text-ink-faint uppercase tracking-wide">
              <tr>
                <Th>{t("Req ID")}</Th><Th>{t("Category")}</Th><Th>{t("Text")}</Th><Th>{t("Target")}</Th><Th>{t("Priority")}</Th><Th>{t("Status")}</Th>
              </tr>
            </thead>
            <tbody>
              {tNode(requirements.map(r => (<tr key={r.req_id} className="border-t border-surface-2">
                  <Td mono>{tNode(r.req_id)}</Td>
                  <Td>{tNode(r.category)}</Td>
                  <Td className="max-w-xs">{tNode(r.text)}</Td>
                  <Td>{tNode(r.target_value != null ? `${r.target_value} ${r.unit ?? ''}` : '—')}</Td>
                  <Td>{tNode(r.priority)}</Td>
                  <Td>{tNode(r.status)}</Td>
                </tr>)))}
            </tbody>
          </table>))}

        {tNode(tab === 'design' && (<table className="w-full text-2xs">
            <thead className="sticky top-0 bg-surface-2 text-ink-faint uppercase tracking-wide">
              <tr>
                <Th>{t("Spec ID")}</Th><Th>{t("Req ID")}</Th><Th>{t("Parameter")}</Th><Th>{t("Value")}</Th><Th>{t("Chemistry")}</Th><Th>{t("Version")}</Th>
              </tr>
            </thead>
            <tbody>
              {tNode(design.map(d => (<tr key={d.spec_id} className="border-t border-surface-2">
                  <Td mono>{tNode(d.spec_id)}</Td>
                  <Td mono>{tNode(d.req_id)}</Td>
                  <Td>{tNode(d.parameter)}</Td>
                  <Td>{tNode(d.value != null ? `${d.value} ${d.unit ?? ''}` : '—')}</Td>
                  <Td>{tNode(d.cell_chemistry ?? '—')}</Td>
                  <Td>{tNode(d.version)}</Td>
                </tr>)))}
            </tbody>
          </table>))}

        {tNode(tab === 'bom' && (<table className="w-full text-2xs">
            <thead className="sticky top-0 bg-surface-2 text-ink-faint uppercase tracking-wide">
              <tr>
                <Th>{t("Part ID")}</Th><Th>{t("Name")}</Th><Th>{t("Supplier")}</Th><Th>{t("Qty")}</Th><Th>{t("Unit Cost")}</Th><Th>{t("Mass (kg)")}</Th>
              </tr>
            </thead>
            <tbody>
              {tNode(bom.map(b => (<tr key={b.part_id} className="border-t border-surface-2">
                  <Td mono>{tNode(b.part_id)}</Td>
                  <Td>{tNode(b.name)}</Td>
                  <Td>{tNode(b.supplier_id)}</Td>
                  <Td>{tNode(b.qty)}</Td>
                  <Td>${tNode(b.unit_cost.toFixed(2))}</Td>
                  <Td>{tNode(b.mass_kg)}</Td>
                </tr>)))}
            </tbody>
          </table>))}
      </div>
    </div>);
};
const Th: React.FC<{
    children: React.ReactNode;
}> = ({ children }) => (<th className="text-left font-semibold px-3 py-1.5">{tNode(children)}</th>);
const Td: React.FC<{
    children: React.ReactNode;
    mono?: boolean;
    className?: string;
}> = ({ children, mono, className }) => (<td className={`px-3 py-1.5 text-ink ${mono ? 'font-mono' : ''} ${className ?? ''}`}>{tNode(children)}</td>);
