"""Versioned A-v2 clinician corrections; private staging, metadata-only split registry.
Never reads reserved-test notes, trains, or edits provisional labels.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from scripts.medication_experiment import request, validate_output, model_view, load_cases, ROLES, ROOT

VERSION = 'medication-role-review-1'

def source_units(note):
    return {k: {x:v[x] for x in ('start','end','text')} for k,v in model_view(note)[1].items()}

def validate(records, registry):
    if not isinstance(records,list) or not records: raise ValueError('Corrections must be a nonempty list')
    membership={}
    for row in registry:
        if set(row) != {'underlying_case_id','split'}: raise ValueError('Registry accepts family/split metadata only')
        family,split=row['underlying_case_id'],row['split']
        if not isinstance(family,str) or not family or split not in ('train','development','test'): raise ValueError('Invalid family registry')
        if family in membership: raise ValueError('Duplicate/overlapping family registry')
        membership[family]=split
    known={x['case_id']:x for x in load_cases()}; used={x['underlying_case_id'] for x in known.values()}
    if any(membership.get(f) not in (None,'development') for f in used): raise ValueError('Previously used development families cannot move splits')
    ids=set();notes={}
    for row in records:
        if row.get('split')=='test': raise ValueError('Reserved test contents must not be supplied')
        if row.get('annotation_version')!=VERSION or row.get('prompt_version')!='medication-A-2' or row.get('extraction_contract')!='medication-representation-1' or row.get('segmentation_version')!='sentence-lines-1': raise ValueError('Contract/version mismatch')
        cid,family,note=row.get('case_id'),row.get('underlying_case_id'),row.get('source_note')
        if not isinstance(cid,str) or not cid or cid in ids: raise ValueError('Missing/duplicate case ID')
        ids.add(cid)
        if row.get('split') not in ('train','development') or membership.get(family)!=row['split']: raise ValueError('Family/split mismatch')
        if not isinstance(note,str) or not 1<=len(note)<=3000: raise ValueError('Invalid source length')
        digest=hashlib.sha256(note.encode()).hexdigest()
        if row.get('source_sha256')!=digest or row.get('source_units')!=source_units(note): raise ValueError('Source hash/offsets/IDs mismatch')
        if digest in notes and notes[digest]!=row['split']: raise ValueError('Source overlap across splits')
        notes[digest]=row['split']
        if cid in known and (note!=known[cid]['source_note'] or family!=known[cid]['underlying_case_id']): raise ValueError('Existing source/family changed; corrections must preserve original')
        # Exact reused notes may not be laundered into training using new identifiers.
        if any(note==k['source_note'] for k in known.values()) and row['split']!='development': raise ValueError('Development source reuse in training')
        if row.get('review_status') not in ('unreviewed','reviewed','rejected'): raise ValueError('Invalid explicit review status')
        if row.get('review_status')=='reviewed':
            if not isinstance(row.get('reviewer'),str) or not row['reviewer'].strip(): raise ValueError('Reviewed corrections require reviewer')
            try: datetime.fromisoformat(row['review_date'])
            except (ValueError,KeyError,TypeError): raise ValueError('Reviewed corrections require ISO review date') from None
        provenance=row.get('provenance',{})
        if provenance.get('fictional') is not True or not provenance.get('origin') or not provenance.get('correction_basis'): raise ValueError('Explicit fictional origin/correction provenance required; real content unsupported here')
        if not row.get('correction_version') or not row.get('supersedes'): raise ValueError('New correction version and original reference required')
        # Frozen A schema retains every unit, including mixed/unclear and other.
        smoke=json.loads((ROOT/'training/engineering4b-fixture.json').read_text())
        if note==smoke['source_note'] or cid.startswith('ENGINEERING-'): raise ValueError('Engineering smoke fixtures cannot become clinical training data')
        try: validate_output('A',json.dumps(row.get('labels')),model_view(note)[1])
        except (ValueError,TypeError): raise ValueError('Labels must assign one frozen role to every source unit') from None
    return records

def stage(records,registry,output,export=False):
    records=validate(records,registry)
    output=output.resolve()
    if not any(output.is_relative_to(ROOT/x) for x in ('private','.runtime')): raise ValueError('Output must remain in ignored private/ or .runtime/')
    if output.exists(): raise ValueError('Refusing to overwrite prior correction version')
    selected=[r for r in records if r['review_status']=='reviewed']
    if export and not any(r['split']=='test' for r in registry): raise ValueError('Reserved-test family metadata required; do not supply test notes')
    if export and any(not any(r['split']==s for r in selected) for s in ('train','development')): raise ValueError('Separate reviewed train and development required')
    output.mkdir(parents=True)
    (output/'corrections.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    (output/'families.json').write_text(json.dumps(registry,indent=2)+'\n')
    counts={}
    if export:
        for split,name in [('train','train.jsonl'),('development','valid.jsonl')]:
            lines=[]
            for row in selected:
                if row['split']!=split:continue
                req,_=request('A',row['source_note'],2)
                lines.append(json.dumps({'messages':req['messages']+[{'role':'assistant','content':json.dumps(row['labels'],ensure_ascii=False,separators=(',',':'))}]},ensure_ascii=False))
            (output/name).write_text('\n'.join(lines)+'\n');counts[split]=len(lines)
    (output/'manifest.json').write_text(json.dumps({'annotation_version':VERSION,'clinical_quality_claim':None,'export_counts':counts,'excluded_unreviewed_or_rejected':len(records)-len(selected),'reserved_test_families':[f for f,s in ((r['underlying_case_id'],r['split']) for r in registry) if s=='test'],'contract_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'experiments/medication-v2/A.txt',ROOT/'experiments/medication-v2/roles.json']}},indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('corrections',type=Path);p.add_argument('--families',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--export-mlx',action='store_true');a=p.parse_args()
    try: stage(json.loads(a.corrections.read_text()),json.loads(a.families.read_text()),a.output,a.export_mlx)
    except (ValueError,TypeError,KeyError) as exc: p.exit(1,'Correction validation failed: '+str(exc)+'\n')
    print('Validated and staged privately. No training started.')

if __name__=='__main__':main()
