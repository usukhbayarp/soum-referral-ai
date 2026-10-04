"""Reviewed scoped train export; partial development targets never become train/valid JSONL."""
import argparse,hashlib,json
from pathlib import Path
from scripts.medfacts import ROOT,record,hashes,CONTRACT
from scripts.partial_review import mapping
DATA=ROOT/'training/reviewed-medfacts-v1'


def validated():
    authoritative={c['case_id']:c for c in json.loads((DATA/'cases.json').read_text())}
    rows=json.loads((DATA/'mapped-cases.json').read_text())
    families=json.loads((DATA/'families.json').read_text())['memberships']
    membership={}
    for f in families:
        if f['underlying_case_id'] in membership:raise ValueError('Duplicate/family overlap')
        membership[f['underlying_case_id']]=f['split']
    dev=json.loads((ROOT/'evaluation/medfacts-v1/development.json').read_text())
    from scripts.medication_experiment import load_cases
    for c in load_cases():
        if membership.get(c['underlying_case_id'])!='development':raise ValueError('Used development family moved')
    if len(rows)!=len(authoritative):raise ValueError('Missing/extra reviewed source')
    for c in rows:
        a=authoritative[c['case_id']]
        if any(c.get(k)!=a[k] for k in a):raise ValueError('Approval/source/version differs from authority')
        if c['split']!='train' or membership[c['underlying_case_id']]!='train':raise ValueError('Training family mismatch')
        if c['review_status']!='approved_supplied_source_and_listed_answers':raise ValueError('Unreviewed training target')
        if hashlib.sha256(c['source_note'].encode()).hexdigest()!=c['source_sha256'] or c['source_mapping']!=mapping(c['source_note']):raise ValueError('Source hash/IDs/offsets changed')
        if c['contract_version']!=CONTRACT['version']:raise ValueError('Contract mismatch')
        record(c)
    # Engineering mappings are frozen in a manifest; adding targets needs a new reviewed mapping revision.
    manifest=json.loads((DATA/'approved-mapping-manifest.json').read_text())
    for name,want in manifest['sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=want:raise ValueError('Frozen reviewed mapping changed: '+name)
    if any(membership.get(c['underlying_case_id'])!='development' or c.get('training_eligible') is not False for c in dev):raise ValueError('Partial development split/eligibility changed')
    return rows,dev


def export(output):
    rows,dev=validated();output=output.resolve()
    if not any(output.is_relative_to(ROOT/p) for p in ['private','.runtime']) or output.exists():raise ValueError('Fresh private/runtime output required')
    output.mkdir(parents=True)
    (output/'train.jsonl').write_text(''.join(json.dumps(record(c),ensure_ascii=False)+'\n' for c in rows))
    (output/'manifest.json').write_text(json.dumps({'contract_version':CONTRACT['version'],'contract_hashes':hashes(),'training_cases':[c['case_id'] for c in rows],'training_families':[c['underlying_case_id'] for c in rows],'training_record_sha256':hashlib.sha256((output/'train.jsonl').read_bytes()).hexdigest(),'development_loss_available':False,'development_evaluation':'reviewed-subset semantic only; no valid.jsonl fabricated','test_contents_included':False,'training_started':False},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();export(a.output)
