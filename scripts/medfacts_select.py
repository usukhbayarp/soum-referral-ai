"""Compare frozen reviewed-subset reports; recommend a diagnostic checkpoint, never promote."""
import argparse,json
from pathlib import Path
from scripts.medfacts import MODEL,hashes
from scripts.medfacts_data import validated
from scripts.medfacts_baseline import score


def summarize(report):
    _,cases=validated()
    if not report.get('finished') or report['contract_hashes']!=hashes():raise ValueError('Incomplete/incompatible report')
    if 'pipeline-test' in report['model']:raise ValueError('Engineering smoke model is not a quality checkpoint')
    if [r['case_id'] for r in report['runs']]!=[c['case_id'] for c in cases]:raise ValueError('Development cohort changed')
    totals={k:0 for k in ['correct','incorrect','unscorable']}
    for row,case in zip(report['runs'],cases):
        if row['source_sha256']!=case['source_sha256']:raise ValueError('Source changed')
        rescored=score(row.get('validation',{}).get('output'),case)
        if rescored!=row['reviewed_subset']:raise ValueError('Score changed')
        for key in totals:totals[key]+=rescored[key]
    return totals


def compare(reports):
    baseline=reports[0]
    if baseline['model']!=MODEL:raise ValueError('First report must be conversion-matched untuned control')
    summaries=[]
    for report in reports:
        counts=summarize(report)
        if report['template_sha256']!=baseline['template_sha256']:raise ValueError('Template changed')
        for a,b in zip(baseline['runs'],report['runs']):
            ar={k:v for k,v in a['request'].items() if k!='model'};br={k:v for k,v in b['request'].items() if k!='model'}
            if ar!=br:raise ValueError('Request/settings changed')
        summaries.append({'model':report['model'],'digest':report['model_digest'],**counts,'invalid_outputs':sum('error' in r for r in report['runs']),'wall_seconds':sum(r['wall_seconds'] for r in report['runs'])})
    # All reviewed failures remain in denominator. Ties retain baseline/earlier checkpoint.
    best=max(range(len(summaries)),key=lambda i:summaries[i]['correct'])
    return {'reports':summaries,'diagnostic_preference':summaries[best]['model'],'selection_rule':'Highest exact reviewed correct count; ties retain baseline then earlier checkpoint. Human review of all errors/extras required; never auto-promote.','development_loss_available':False,'clinical_candidate_eligible':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reports',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    a.output.write_text(json.dumps(compare([json.loads(x.read_text()) for x in a.reports]),ensure_ascii=False,indent=2)+'\n')
