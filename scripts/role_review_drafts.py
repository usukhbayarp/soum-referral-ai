"""Prepare private, explicitly unreviewed A-v2 correction forms from existing dev fixtures."""
import argparse,hashlib,json
from pathlib import Path
from scripts.role_review import ROOT,VERSION,source_units
from scripts.medication_experiment import load_cases,DATA

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
 if not any(out.is_relative_to(ROOT/x) for x in ('private','.runtime')):p.error('Keep drafts in private/ or .runtime/')
 if out.exists():p.error('Choose a new output directory; never overwrite corrections')
 expected=json.loads((DATA/'expected-facts.json').read_text());rows=[]
 for case in load_cases():
  note=case['source_note'];rows.append({'annotation_version':VERSION,'correction_version':'clinician-correction-1','supersedes':'evaluation/medication-v1/expected-facts.json','case_id':case['case_id'],'underlying_case_id':case['underlying_case_id'],'source_note':note,'source_sha256':hashlib.sha256(note.encode()).hexdigest(),'source_units':source_units(note),'labels':expected['cases'][case['case_id']]['roles'],'form_version':'experimental-0.7','extraction_contract':'medication-representation-1','prompt_version':'medication-A-2','segmentation_version':'sentence-lines-1','split':'development','review_status':'unreviewed','reviewer':None,'review_date':None,'provenance':{'fictional':True,'origin':case['synthetic_origin'],'correction_basis':'Provisional labels copied for clinician correction; no review performed'},'review_notes':''})
 out.mkdir(parents=True);(out/'corrections.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');(out/'families.json').write_text(json.dumps([{'underlying_case_id':r['underlying_case_id'],'split':'development'} for r in rows],indent=2)+'\n');print('Unreviewed private drafts created. No train/test family invented; no training export.')

if __name__=='__main__':main()
