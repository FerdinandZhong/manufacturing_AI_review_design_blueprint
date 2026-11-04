"""Shared read-only metrics for cockpit, semantic context, and agent evidence."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import source
from common.runtime import data_mode
from common.db import get_connection
from engineering.traceability import coverage, missing_standards, decide
from ml.risk_model import get_scores

DEFINITIONS = {
    'coverage': 'Requirements linked to at least one design and one test plan / all requirements',
    'tests_needing_attention': 'Stored test results whose verdict is MARGINAL or FAIL',
    'high_risk_requirements': 'Stored requirement scores with risk_band HIGH',
    'recommendation': 'FAIL if any FAIL or coverage < 0.6; CONDITIONAL if marginal, gap, or missing standard; otherwise PASS',
    'executed_coverage': 'Requirements linked to a design and a current stored test result / all requirements',
    'unscored_requirements': 'All requirements minus requirements with a current snapshot ML score',
    'bom_cost': 'Sum of quantity times unit_cost across all BOM items, USD',
    'bom_mass_kg': 'Sum of quantity times mass_kg across all BOM items',
    'open_issues': 'Issues whose status is not CLOSED',
    'action_completion': 'Closed corrective actions / all corrective actions; zero denominator means no actions',
    'observation_evidence_coverage': 'Plans linked to seeded observation records / all plans',
    'acceptance_margin': '(observation mean - target) / abs(target), sign reversed for lower-is-better',
}

def summary(program_id):
    if data_mode()=='pilot':
        return pilot_summary(program_id)
    identity = source.snapshot_identity(program_id)
    with get_connection() as conn:
        results = [dict(r) for r in conn.execute('SELECT * FROM test_results WHERE program_id=? ORDER BY test_id', (program_id,))]
        review = conn.execute('SELECT review_id,recommendation,decision,state FROM gate_reviews WHERE program_id=? AND snapshot_id=? ORDER BY rowid DESC LIMIT 1', (program_id,identity['snapshot_id'])).fetchone()
    cov = coverage(program_id)
    missing = missing_standards(program_id)
    prepared = bool(results) and {r['test_id'] for r in results} == {p['test_id'] for p in source.list_test_plans(program_id)} and all(r['snapshot_id']==identity['snapshot_id'] for r in results)
    results = [r for r in results if r["snapshot_id"] == identity["snapshot_id"]]
    scores = get_scores(program_id)
    requirements = source.list_requirements(program_id)
    plans = source.list_test_plans(program_id)
    executed = {p['req_id'] for p in plans if p['test_id'] in {r['test_id'] for r in results}}
    designed = {d['req_id'] for d in source.list_design_specs(program_id)}
    snapshot = source.get_snapshot(program_id) or {}
    issues = snapshot.get('issues', [])
    boms = source.list_bom(program_id)
    return {**identity, 'definitions':DEFINITIONS, 'coverage':cov,
            'requirement_count':len(requirements), 'planned_test_count':len(plans), 'executed_coverage':{'traced':len(executed & designed), 'total':len(requirements), 'pct':round(len(executed & designed)/len(requirements),3) if requirements else 0.}, 'unscored_requirements':len(requirements)-len(scores), 'bom_cost':round(sum(b['qty']*b['unit_cost'] for b in boms),2), 'bom_mass_kg':round(sum(b['qty']*b['mass_kg'] for b in boms),3), 'open_issues':sum(i['status']!='CLOSED' for i in issues), 'action_completion':{'complete':sum(i['status']=='CLOSED' for i in issues),'total':len(issues)}, 'observation_evidence_coverage':{'linked_tests':sum(any(o['test_id']==p['test_id'] for o in source.list_observations(program_id)) for p in plans),'total_tests':len(plans), 'basis':'Plans linked to independent seeded observations; generated report is reproducible from the same records'}, 'test_count':len(results), 'observation_count':len(source.list_observations(program_id)),
            'tests_needing_attention':sum(r['verdict']!='PASS' for r in results),
            'high_risk_requirements':sum(s['risk_band']=='HIGH' for s in get_scores(program_id)),
            'missing_standards':missing, 'prepared':prepared,
            'recommendation':decide(cov,results,missing) if prepared else None,
            'latest_review':dict(review) if review else None}

def pilot_summary(program_id):
    """Describe source structure without loading a demo decision or risk policy."""
    identity = source.snapshot_identity(program_id)
    requirements = source.list_requirements(program_id)
    designs = source.list_design_specs(program_id)
    plans = source.list_test_plans(program_id)
    parts = source.list_bom(program_id)
    observations = source.list_observations(program_id)
    linked = {observation['test_id'] for observation in observations}
    status = 'unavailable_pending_approved_pilot_rules'
    return {
        **identity, 'metric_status':'structural_source_inspection_only',
        'definitions':{
            'coverage':'Requirements linked to at least one imported design and test plan / all imported requirements; structural only',
            'bom_cost':'Sum of quantity times imported unit_cost; source-owner currency applies',
            'bom_mass_kg':'Sum of quantity times imported mass_kg',
            'observation_evidence_coverage':'Imported plans linked to source observation records / all imported plans; not acceptance coverage',
        },
        'coverage':coverage(program_id), 'coverage_status':'structural_only',
        'requirement_count':len(requirements), 'design_count':len(designs),
        'bom_item_count':len(parts), 'planned_test_count':len(plans),
        'observation_count':len(observations),
        'bom_cost':round(sum(p['qty']*p['unit_cost'] for p in parts),2),
        'bom_mass_kg':round(sum(p['qty']*p['mass_kg'] for p in parts),3),
        'observation_evidence_coverage':{
            'linked_tests':sum(p['test_id'] in linked for p in plans),
            'total_tests':len(plans), 'basis':'Imported source observations joined by exact test identity; no computed verdict',
        },
        'prepared':False, 'review_ready':False,
        'test_count':None, 'tests_needing_attention':None,
        'high_risk_requirements':None, 'unscored_requirements':None,
        'executed_coverage':None, 'missing_standards':None,
        'open_issues':None, 'action_completion':None,
        'recommendation':None, 'latest_review':None,
        'unsupported_metrics':{
            'risk':'unavailable_until_domain_model_validation',
            'verdict':status, 'recommendation':status, 'standards_coverage':status,
            'executed_coverage':status, 'issue_action_policy':status,
        },
    }


if __name__ == '__main__':
    assert 'coverage' in DEFINITIONS
    assert source.snapshot_identity('PACK-ATLAS-01@atlas-v2')['revision_id']=='atlas-v2'
    print('Shared metric contract OK')
