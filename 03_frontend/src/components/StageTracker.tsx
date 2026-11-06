import { t, tNode } from '../i18n'
import { useEffect, useState } from 'react';
import type { Program } from '../api';
import { getProgram } from '../api';
const STAGES = ['REQUIREMENTS', 'DESIGN', 'ENGINEERING', 'VALIDATION', 'GATE_REVIEW', 'RELEASED'];
interface Props {
    programId: string;
}
/** Horizontal lifecycle stepper. The showcase program is pre-seeded through
 *  VALIDATION with GATE_REVIEW as the live action, so we highlight whichever
 *  stage the program row reports (falling back to GATE_REVIEW if unknown). */
export const StageTracker: React.FC<Props> = ({ programId }) => {
    const [program, setProgram] = useState<Program | null>(null);
    useEffect(() => {
        getProgram(programId).then(d => setProgram(d.program)).catch(() => setProgram(null));
    }, [programId]);
    const currentIdx = (() => {
        const idx = STAGES.indexOf(program?.stage ?? '');
        return idx >= 0 ? idx : STAGES.indexOf('GATE_REVIEW');
    })();
    return (<div className="lifecycle-strip">
      {tNode(program && (<div className="pr-4 border-r border-surface-3 mr-2">
          <p className="text-sm font-semibold text-ink">{tNode(program.name)}</p>
          <p className="text-2xs text-ink-faint">{tNode(program.vehicle_platform)}</p>
        </div>))}
      <div className="flex flex-wrap items-center gap-1.5">
        {tNode(STAGES.map((s, i) => {
            const done = currentIdx > i;
            const active = currentIdx === i;
            return (<span key={s} className={`lifecycle-step ${active ? 'active' : done ? 'complete' : ''}`}>
              <span>{tNode(i + 1)}</span>{tNode(s.replace('_', ' ').toLowerCase())}
            </span>);
        }))}
      </div>
      {tNode(program && (<span className="ml-auto text-2xs text-ink-faint">{t("gate status:")}<span className="font-semibold text-ink-muted">{tNode(program.gate_status)}</span>
        </span>))}
    </div>);
};
