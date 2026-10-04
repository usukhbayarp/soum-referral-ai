import json
from scripts import medication_experiment as frozen
from scripts.original4b_comparison import TAG

def test_comparison_changes_only_model_identifier(monkeypatch):
    for rev in (1,2):
        for case in frozen.load_cases():
            for candidate in ('A','B'):
                baseline,mapping=frozen.request(candidate,case['source_note'],rev)
                with monkeypatch.context() as m:
                    m.setattr(frozen,'MODEL',TAG)
                    request,new_mapping=frozen.request(candidate,case['source_note'],rev)
                assert request.pop('model')==TAG
                baseline.pop('model')
                assert request==baseline and new_mapping==mapping
                assert 'expected' not in json.dumps(request['messages'])
