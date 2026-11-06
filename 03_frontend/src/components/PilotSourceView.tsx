import { t, tNode, formatDetails } from '../i18n'
import { useEffect, useState } from 'react';
import { api, getRequirements, getDesign, getBom, getTests } from '../api';
import type { Requirement, RuntimeStatus } from '../api';
export function PilotSourceView({ programId, status }: {
    programId: string;
    status: RuntimeStatus;
}) {
    const [records, setRecords] = useState<{
        requirements: Requirement[];
        designs: number;
        parts: number;
        plans: number;
        observations: Record<string, unknown>[];
    } | null>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        const controller = new AbortController();
        Promise.all([getRequirements(programId), getDesign(programId), getBom(programId), getTests(programId), api.get(`/programs/${programId}/data/observations`, { params: { limit: 20 }, signal: controller.signal })]).then(([requirements, designs, parts, plans, observations]) => {
            if (!controller.signal.aborted)
                setRecords({ requirements, designs: designs.length, parts: parts.length, plans: plans.length, observations: observations.data.items });
        }).catch(() => { if (!controller.signal.aborted)
            setError('Pilot source records are unavailable. No demo data was substituted.'); });
        return () => controller.abort();
    }, [programId]);
    return <section aria-label={t("Pilot source inspection")}>
    <p className="reader-notice">{t("Pilot source inspection \u00B7 Reviews, computed verdicts, and ML predictions remain unavailable until domain acceptance.")}</p>
    <p className="reader-caption">{tNode(status.source.source_id)} · {tNode(status.source.revision_id)} · {tNode(status.source.snapshot_id)}{t("\u00B7 Extracted")}{tNode(status.source.extracted_at)}{t(". Freshness:")}{tNode(status.source.freshness?.replaceAll('_', ' '))}.</p>
    <p>{tNode(status.source.provenance)}</p>
    {tNode(error && <p role="alert">{tNode(error)}</p>)}
    {tNode(records && <><p>{tNode(records.requirements.length)}{t("requirements \u00B7")}{tNode(records.designs)}{t("designs \u00B7")}{tNode(records.parts)}{t("BOM items \u00B7")}{tNode(records.plans)}{t("test plans")}</p><div className="overflow-auto"><table className="w-full text-sm"><thead><tr><th>{t("Requirement")}</th><th>{t("Description")}</th><th>{t("Target")}</th></tr></thead><tbody>{tNode(records.requirements.map(r => <tr key={r.req_id}><td>{tNode(r.req_id)}</td><td>{tNode(r.text)}</td><td>{tNode(r.target_value)} {tNode(r.unit)}</td></tr>))}</tbody></table></div><details className="reader-notice"><summary>{t("Source observations \u00B7 first 20 records")}</summary><pre className="overflow-auto">{formatDetails(records.observations)}</pre></details></>)}
  </section>;
}
