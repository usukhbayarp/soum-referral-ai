"""Summarize preserved engineering outputs against explicitly unreviewed labels."""
import argparse
import json
from pathlib import Path
from scripts.medication_experiment import ROOT


def summarize(report):
    expected = json.loads((ROOT / 'evaluation/medication-v1/expected-facts.json').read_text())['cases']
    summary = {
        'label_status': 'provisional, unreviewed development; not clinical accuracy',
        'clinical_candidate_eligible': False,
        'definitions': {
            'missing_relevant_units': 'expected role is non-other, predicted other',
            'extra_relevant_units': 'expected other, predicted non-other; unsupported category, not invented source text',
            'wrong_roles': 'any predicted role differs from provisional expected role',
            'allergy_or_negation_confusions': 'wrong role involving allergy_statement or explicitly_not_administered on either side',
            'empty_selections': 'structurally valid output assigns other to every unit',
        },
        'runs': [],
        'agreements': report.get('agreements', []),
        'stop_reason': report.get('stop_reason'),
    }
    for run in report['runs']:
        row = {k: run[k] for k in ['case_id', 'model', 'wall_seconds']}
        row['error'] = run.get('error')
        row['structurally_valid'] = bool(run.get('validation'))
        response = run.get('response', {})
        row['token_counts'] = {k: response.get(k) for k in ['prompt_eval_count', 'eval_count']}
        if run.get('validation'):
            target = expected[run['case_id']]['roles']
            output = run['validation']['output']
            row['wrong_roles'] = {u: {'expected': r, 'actual': output[u]} for u, r in target.items() if r != output[u]}
            row['missing_relevant_units'] = [u for u, r in target.items() if r != 'other' and output[u] == 'other']
            row['extra_relevant_units'] = [u for u, r in target.items() if r == 'other' and output[u] != 'other']
            sensitive = {'allergy_statement', 'explicitly_not_administered'}
            row['allergy_or_negation_confusions'] = [u for u, pair in row['wrong_roles'].items() if sensitive.intersection(pair.values())]
            row['empty_selections'] = all(r == 'other' for r in output.values())
        summary['runs'].append(row)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(summarize(json.loads(args.report.read_text())), ensure_ascii=False, indent=2) + '\n')
