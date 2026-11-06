import { t, tNode } from '../i18n'
import { useEffect, useState } from 'react';
import type { MatrixRow } from '../api';
import { getMatrix } from '../api';
interface Props {
    programId: string;
}
const VERDICT_CLS: Record<string, string> = {
    PASS: 'text-aml-green bg-aml-green/10',
    MARGINAL: 'text-aml-amber bg-aml-amber/10',
    FAIL: 'text-aml-red bg-aml-red/10',
};
/** Requirement x (design, test, verdict) grid. Rows with a null spec_id,
 *  test_id, or verdict are coverage gaps — highlighted, not hidden. */
export const TraceabilityMatrix: React.FC<Props> = ({ programId }) => {
    const [rows, setRows] = useState<MatrixRow[]>([]);
    useEffect(() => {
        getMatrix(programId).then(m => setRows(m.rows));
    }, [programId]);
    return (<div className="bg-surface-1 rounded-lg shadow-soft overflow-hidden">
      <p className="text-2xs uppercase tracking-wider text-ink-faint px-4 pt-3">{t("Traceability matrix")}</p>
      <div className="max-h-72 overflow-y-auto mt-2">
        <table className="w-full text-2xs">
          <thead className="sticky top-0 bg-surface-2 text-ink-faint uppercase tracking-wide">
            <tr>
              <th className="text-left font-semibold px-3 py-1.5">{t("Req ID")}</th>
              <th className="text-left font-semibold px-3 py-1.5">{t("Category")}</th>
              <th className="text-left font-semibold px-3 py-1.5">{t("Spec ID")}</th>
              <th className="text-left font-semibold px-3 py-1.5">{t("Test ID")}</th>
              <th className="text-left font-semibold px-3 py-1.5">{t("Verdict")}</th>
            </tr>
          </thead>
          <tbody>
            {tNode(rows.map(row => {
            const gap = row.spec_id == null || row.test_id == null || row.verdict == null;
            return (<tr key={row.req_id} className={`border-t border-surface-2 ${gap ? 'bg-aml-amber/5' : ''}`}>
                  <td className="px-3 py-1.5 font-mono text-ink">{tNode(row.req_id)}</td>
                  <td className="px-3 py-1.5 text-ink">{tNode(row.category)}</td>
                  <td className="px-3 py-1.5 font-mono text-ink">
                    {tNode(row.spec_id ?? <span className="text-aml-amber font-semibold">{t("gap")}</span>)}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-ink">
                    {tNode(row.test_id ?? <span className="text-aml-amber font-semibold">{t("gap")}</span>)}
                  </td>
                  <td className="px-3 py-1.5">
                    {tNode(row.verdict ? (<span className={`font-semibold px-1.5 py-0.5 rounded-full ${VERDICT_CLS[row.verdict] ?? ''}`}>
                        {tNode(row.verdict)}
                      </span>) : (<span className="text-aml-amber font-semibold">{t("gap")}</span>))}
                  </td>
                </tr>);
        }))}
          </tbody>
        </table>
        {tNode(rows.length === 0 && <p className="text-2xs text-ink-faint px-3 py-3">{t("No requirements.")}</p>)}
      </div>
    </div>);
};
