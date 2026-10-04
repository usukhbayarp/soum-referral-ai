"""Faithful mappings of explicit approvals; public fictional data, no training."""
import json,hashlib
from pathlib import Path
from scripts.medfacts import ROOT,CONTRACT,record,hashes
from scripts.partial_review import mapping
OUT=ROOT/'training/reviewed-medfacts-v1'


def build(case,specs,excluded_topics=()):
    units=mapping(case['source_note']);facts=[]
    for topic,attrs,parts,context in specs:
        evidence=[]
        for uid,quote in parts:
            evidence.append({'unit_id':uid,'quote':quote or units[uid]['model_text']})
        facts.append({'topic':topic,'attributes':attrs.split() if attrs else [],'evidence':evidence,'context':context})
    focus=list(dict.fromkeys(e['unit_id'] for f in facts for e in f['evidence']))
    scope=[{'units':focus,'topics':[t for t in CONTRACT['topics'] if t not in excluded_topics]}]
    return {**case,'contract_version':CONTRACT['version'],'source_mapping':units,'scope':scope,'target':{'facts':facts},'target_scope':'Only listed approved facts in requested unit/topic scope; full original note retained as context','unrequested_units':[u for u in units if u not in focus]}


def prepare():
    cases=json.loads((OUT/'cases.json').read_text());a,b=cases
    a=build(a,[
        ('chronic_history','',[('U3','Бамбайн дааврын дутагдалтай')],[]),
        ('medication','regular_use patient_reported',[('U3','левотироксин 50 мкг өглөө өлөн үед өдөр бүр уудаг гэсэн.')],['U4']),
        ('medication','not_asked',[('U4',None)],['U3']),
        ('medication','home_preencounter patient_reported',[('U5',None)],['U6']),
        ('medication','not_documented',[('U6',None)],['U5']),
        ('medication','encounter_administered',[('U9',None),('U10',None)],['U11']),
        ('medication','not_documented',[('U11',None)],['U9','U10']),
        ('symptom_followup','patient_reported',[('U12',None)],[]),
        ('medication','not_administered',[('U13',None)],[]),
        ('drug_allergy','explicit_absence patient_reported',[('U14',None)],[]),
        ('food_allergy','not_asked',[('U15',None)],[]),
    ])
    b=build(b,[
        ('medication','historical_use',[('U2','төмрийн эм өдөрт нэг шахмал уудаг байсан.')],['U3','U4']),
        ('medication','unknown',[('U3',None)],['U2']),
        ('medication_response','stopped patient_reported',[('U4',None)],['U2','U3']),
        ('medication','unknown',[('U5',None)],[]),
        ('drug_allergy','patient_reported',[('U6',None)],['U7']),
        ('drug_allergy','not_clarified',[('U7',None)],['U6']),
        ('medication','planned',[('U10',None)],['U11']),
        ('medication','planned not_administered',[('U11',None)],['U10']),
        ('medication','not_administered',[('U12',None)],[]),
        ('investigation','planned specimen_not_collected',[('U13',None)],[]),
    ],excluded_topics=['chronic_history'])
    # No historical anemia/chronic-history target was listed in TRAIN-002 answers.
    for c in [a,b]:record(c)
    path=OUT/'mapped-cases.json'
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps([a,b],ensure_ascii=False,indent=2)+'\n')
    old=json.loads((ROOT/'evaluation/clinician-partial-v08/annotations.json').read_text())
    dev=[]
    for c in old['cases']:
        cid=c['case_id']
        if cid=='DEV-002':
            specs=[('medication','regular_use',[('U11',None)],['U12']),('medication','not_asked',[('U12',None)],['U11']),('drug_allergy','explicit_absence patient_reported',[('U13',None)],[]),('medication','encounter_administered',[('U21',None)],[]),('treatment','not_administered',[('U23',None)],[])]
        elif cid=='dev-003':specs=[('drug_allergy','explicit_absence',[('U5',None)],[]),('treatment','not_administered',[('U6',None)],[]),('investigation','explicit_absence',[('U7',None)],[])]
        elif cid=='dev-004':specs=[('investigation','',[('U4',None)],[])]
        else:continue
        d=build(c,specs);d['whole_target_loss_available']=False;d['training_eligible']=False;d['evaluation_only_reviewed_scope']=True
        d['excluded_reviewed_facts']='Other approved classifications outside compact contract; unconfirmed clarified home-use source not used'
        dev.append(d)
    (ROOT/'evaluation/medfacts-v1/development.json').write_text(json.dumps(dev,ensure_ascii=False,indent=2)+'\n')
    families=[{'underlying_case_id':c['underlying_case_id'],'split':'train'} for c in [a,b]]+[{'underlying_case_id':c['underlying_case_id'],'split':'development'} for c in old['cases']]
    (OUT/'families.json').write_text(json.dumps({'memberships':families,'reserved_test_contents_opened':False,'reserved_test_registry_supplied':False,'final_test_registration':'required before final evaluation; no fabricated test families'},indent=2)+'\n')
    (OUT/'mapping-provenance.json').write_text(json.dumps({'engineering_mapping':'Exact spans/topics/independent attributes faithfully mapped from approved listed answers; not blanket source fact approval','reviewer':'А. Балжинням','review_date':'2026-10-04','contract_hashes':hashes(),'TRAIN-002_revision':'approved-revised-20261004-2; final approval supersedes draft','normalization':'Targets quote original text; oral normalization is optional linked display-only. No unit conversion/rate/time inference.'},indent=2)+'\n')

if __name__=='__main__':prepare()
