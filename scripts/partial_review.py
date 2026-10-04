"""Evaluation-only, fact-scoped clinician review. Never a whole-note training target."""
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from scripts.medication_experiment import ROOT, load_cases, model_view

OUT = ROOT / 'evaluation/clinician-partial-v08'
VERSION = 'clinician-partial-20261004-1'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def mapping(note):
    result = model_view(note)[1]
    for unit in result.values():
        labels = list(re.finditer(r'\[S\d+\]', note[:unit['start'] + len(unit['text'])]))
        unit['original_s_id'] = labels[-1][0][1:-1] if labels else None
    return result


def validate(bundle):
    if bundle['version'] != VERSION or bundle['purpose'] != 'evaluation-only' or bundle['whole_note_training_eligible'] is not False:
        raise ValueError('Partial reviews cannot become whole-note training targets')
    if not bundle.get('reviewer', '').strip(): raise ValueError('Reviewer required')
    date.fromisoformat(bundle['review_date'])
    known = {c['case_id']: c for c in load_cases()}
    for row in bundle['cases']:
        case = known[row['case_id']]
        if row['source_note'] != case['source_note'] or row['source_sha256'] != digest(case['source_note']):
            raise ValueError('Immutable source mismatch')
        if row['source_mapping'] != mapping(case['source_note']):
            raise ValueError('Source ID/offset mismatch')
        if row['underlying_case_id'] != case['underlying_case_id'] or row['split'] != 'development':
            raise ValueError('Used family must remain development')
        if row['review_status'] != ('partial' if row['decisions'] else 'unreviewed') or row['unreviewed_remainder'] is not True:
            raise ValueError('No blanket approval')
        from scripts.medication_experiment import ROLES
        covered = {u for item in row['decisions'] for u in item['units']}
        if any(u not in covered or role not in ROLES for u, role in row['reviewed_A_v2_labels'].items()):
            raise ValueError('Role labels must be in explicit reviewed scope')
        for item in row['decisions']:
            if not item['scope'] or not item['clinical_decision'] or not item['units']:
                raise ValueError('Missing review scope')
            if any(u not in row['source_mapping'] for u in item['units']):
                raise ValueError('Unknown reviewed source ID')
    return bundle


if __name__ == '__main__':
    b = validate(json.loads((OUT / 'annotations.json').read_text()))
    print('Validated evaluation-only partial annotations for', len(b['cases']), 'development cases; no training export.')
