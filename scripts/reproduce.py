"""Offline verification and reanalysis of retained outputs. Standard library only."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from harness import reconstruction_evaluation as rec, mapping_evaluation as mapping
from source_evidence import select_target, contexts_with_locators, native_inputs, native_calls
from reference_builder import independent_reference
from paired_analysis import paired_cluster_summary


def offline(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('Offline reproduction prohibits network access')
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=Path(args[0]).resolve()
        if not path.is_relative_to(ROOT):
            raise PermissionError('Analysis read outside the release directory')
        if any(c in (args[1] or '') for c in 'wax+') and not path.is_relative_to(ROOT/'results'):
            raise PermissionError('Analysis write outside results/')


def read(path):
    return json.loads((ROOT/path).read_text())


def events(path):
    return [json.loads(s) for s in (ROOT/path).read_text().splitlines()]


def digest(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def dump(path,value):
    dest=ROOT/'results'/path;dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def csvout(name,rows):
    with (ROOT/'results'/name).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def csvread(path):
    return list(csv.DictReader((ROOT/path).open()))


def verify_integrity():
    count=0;listed=set()
    for line in (ROOT/'checksums.sha256').read_text().splitlines():
        expected,path=line.split('  ',1)
        assert not (ROOT/path).is_symlink() and (ROOT/path).resolve().is_relative_to(ROOT)
        assert digest(path)==expected,path
        count+=1;listed.add(path)
    actual=set()
    for path in ROOT.rglob('*'):
        assert not path.is_symlink(),str(path)
        rel=path.relative_to(ROOT)
        if path.is_file() and rel.parts[0]!='results' and '__pycache__' not in rel.parts and str(rel)!='checksums.sha256':actual.add(str(rel))
    assert listed==actual,{'unlisted':sorted(actual-listed),'missing':sorted(listed-actual)}
    return {'release_checksums_verified':count}


def verify_inputs():
    assignments=read('manifests/assignments.json'); candidates=read('manifests/candidates96.json')
    refs=read('references/complete_record.json');schema=read('schemas/answer.json')
    assert schema==rec.answer_schema()
    assert len(assignments)==1024 and len(candidates)==96 and len(refs)==64
    assert len({r['run_id'] for r in assignments})==1024
    assert len({r['task_id'] for r in assignments})==13
    assert set(Counter((r['study'],r['reader'],r['condition']) for r in assignments).values())=={64}
    assert {(r['study'],r['reader'],r['condition']) for r in assignments}=={(s,r,c) for s,cs in [('I',('R00','R10','R01','R11')),('II',mapping.CONDITIONS)] for r in ('luna','sonnet') for c in cs}
    pool=read('manifests/selection_pool.json')
    assert len(pool)==264
    selected={r['run_id'] for r in pool if r['level']=='A0'}
    for task in sorted({r['user_task'] for r in pool}):
        pairs={r['pair_id'] for r in pool if r['user_task']==task and r['level']=='A1'}
        for provider in ('openai','anthropic','google'):
            assert {r['pair_id'] for r in pool if r['user_task']==task and r['level']=='A1' and r['provider']==provider}==pairs
        pair=min(pairs,key=lambda p:hashlib.sha256(('evidence-reconstruction-proposal-v1/20260915/'+p).encode()).hexdigest())
        chosen=[r for r in pool if r['user_task']==task and r['level']=='A1' and r['pair_id']==pair]
        assert {r['provider'] for r in chosen}=={'openai','anthropic','google'}
        selected.update(r['run_id'] for r in chosen)
    assert selected=={r['run_id'] for r in candidates}
    bycase={r['case_id']:r for r in candidates}
    expected_selected=read('manifests/selected64.json');excluded=read('manifests/excluded32.json')
    applicability=[]; rebuilt={}; native_checks=0;call_checks=0
    for item in candidates:
        case=item['case_id'];es=events(item['raw_path'])
        assert digest(item['raw_path'])==item['raw_sha256']
        assert digest(item['l0_path'])==item['l0_sha256']
        contexts=contexts_with_locators(es); cbyid={c['id']:c for c in contexts}
        actions=[(i,e) for i,e in enumerate(es) if e['event']=='action']
        base=[{k:e[k] for k in ('action_id','tool','args','result')} for _,e in actions]
        assert base==events(item['l0_path'])
        for i,a in actions:
            req=next(e for e in reversed(es[:i]) if e['event']=='api_request')
            resp=next(e for e in reversed(es[:i]) if e['event']=='api_response')
            assert (a['tool'],a['args']) in native_calls(resp['response'],item['provider'])
            call_checks+=1
            wire=native_inputs(req['body'],item['provider'])
            for c in a['context']:
                role=c['channel'] if c['channel'] in ('user','system') else 'tool'
                assert any(c['raw'] in text for block in wire if block['role']==role for text in block['texts'])
                original=cbyid[c['id']]
                assert c['raw']==original['raw'] and c['hash']==original['hash'] and original['event_index']<i
                norm=' '.join(unicodedata.normalize('NFKC',c['raw']).split())
                assert hashlib.sha256(norm.encode()).hexdigest()==c['hash']
                native_checks+=1
        target=select_target(es)
        if target is None:
            assert item['reference']=={'status':'not_applicable_no_nonempty_string_argument','target':None}
            applicability.append({'case_id':case,'task_id':item['user_task'],'reason':item['reference']['status']})
            continue
        t={'action_id':target['action']['action_id'],'arg_key':target['arg_key'],'literal':target['literal']}
        ref=independent_reference(es,t);assert ref==refs[case]
        pre=item['reference']
        assert pre['target']==dict(t,selection=target['selection'],event_index=target['event_index'])
        assert pre['user_literal_present']==ref['user_literal_present'] and pre['basis_available']==ref['basis_recorded']
        assert sorted(x['locator'] for x in pre['prior_external_matches'])==ref['prior_locators']
        assert sorted(pre['basis_cited_prior_matches'] or [])==ref['basis_match_locators']
        for cond in ('R00','R10','R01','R11'):
            packet={'case_id':case,'target':t,'tool_log':base}
            if cond[1]=='1':packet['actor_account']=[{k:a[k] for k in ('action_id','reasoning_text','stated_refs','stated_note')} for _,a in actions]
            if cond[2]=='1':packet['native_inputs']=[{k:c[k] for k in ('id','channel','raw','locator','timestamp','event_index')} for c in contexts if c['channel']!='system']
            assert packet==read(f'data/study_i/packets/{case}/{cond}.json')
            rebuilt[case,cond]=packet
    assert applicability==excluded and len(applicability)==32
    assert set(refs)=={r['case_id'] for r in expected_selected}
    assert Counter(bycase[c]['provider'] for c in refs)=={'openai':22,'anthropic':17,'google':25}
    permutations=read('references/experimental_id_permutations.json')
    for case in refs:
        packets,permutation=mapping.make_packets(rebuilt[case,'R10'],rebuilt[case,'R11'])
        assert permutation==permutations[case]
        for cond,packet in packets.items():assert packet==read(f'data/study_ii/packets/{case}/{cond}.json')
    # Independently recreate each frozen randomization order.
    for reader,pass_id in [('luna','04_reconstruction_reader_v1'),('sonnet','04_sonnet_reconstruction_v1')]:
        group=[r for r in assignments if r['pass_id']==pass_id]
        if reader=='luna':
            order=[(c['case_id'],cond) for c in candidates if c['case_id'] in refs for cond in ('R00','R10','R01','R11')]
            random.Random(42).shuffle(order)
            assert order==[(r['case_id'],r['condition']) for r in group]
        assert [r['frozen_order'] for r in group]==list(range(256))
    # Sonnet Study I used the preserved first-reader manifest order.
    assert [(r['case_id'],r['condition']) for r in assignments if r['pass_id']=='04_reconstruction_reader_v1']==[(r['case_id'],r['condition']) for r in assignments if r['pass_id']=='04_sonnet_reconstruction_v1']
    rng=random.Random(42);cases=sorted(refs);rng.shuffle(cases);order=[]
    for case in cases:
        block=[(case,c,reader) for c in mapping.CONDITIONS for reader in ('luna','sonnet')]
        rng.shuffle(block);order.extend(block)
    assert order==[(r['case_id'],r['condition'],r['reader']) for r in assignments if r['study']=='II']
    for item in assignments:
        assert digest(item['packet_path'])==item['packet_sha256'] and digest(item['body_path'])==item['body_sha256']
        assert digest(item['source_raw_path'])==item['source_raw_sha256']
        assert item['source_run_id']==bycase[item['case_id']]['run_id'] and item['task_id']==bycase[item['case_id']]['user_task']
        body=read(item['body_path']); packet=read(item['packet_path']);es=events(item['response_path'])
        generation=[e for e in es if e['event']=='api_request' and ('max_tokens' in e['body'] or 'max_completion_tokens' in e['body'])]
        assert len(generation)==1 and generation[0]['body']==body
        assert next(e for e in es if e['event']=='reader_meta')['gold_supplied'] is False
        prompt=(ROOT/('prompts/study_i.md' if item['study']=='I' else 'prompts/study_ii.md')).read_text()
        assert body['temperature']==0
        if item['reader']=='luna':
            assert body['model']=='gpt-5.6-luna' and body['seed']==42 and body['reasoning_effort']=='none'
            assert body['max_completion_tokens']==2048 and body['response_format']['json_schema']['schema']==schema
            assert len(body['messages'])==2 and body['messages'][0]=={'role':'system','content':prompt}
            assert body['messages'][1]['role']=='user' and json.loads(body['messages'][1]['content'])==packet
        else:
            assert body['model']=='claude-sonnet-4-6' and 'seed' not in body and body['thinking']=={'type':'disabled'}
            assert body['max_tokens']==2048 and body['output_config']['format']['schema']==schema
            assert body['system']==prompt and len(body['messages'])==1 and body['messages'][0]['role']=='user'
            assert json.loads(body['messages'][0]['content'])==packet
    metadata=read('manifests/execution_metadata.json')
    assert {r['run_id'] for r in metadata}=={r['run_id'] for r in assignments}
    for item in metadata:
        row=next(r for r in assignments if r['run_id']==item['run_id'])
        body=read(row['body_path'])
        assert item['model']==body['model'] and item['temperature']==body['temperature']
        assert item['raw_sha256']==digest(row['response_path'])
    result={'candidates':96,'applicable':64,'excluded':32,'tasks':13,'selection_pool_rows':264,
            'selection_recomputed':True,'native_context_checks':native_checks,'native_call_checks':call_checks,
            'references_rebuilt':64,'packets_rebuilt':512,'saved_generation_requests_verified':1024,
            'assignment_orders_verified':True,'packet_payloads_byte_identical_to_retained_sources':True}
    dump('input_validation.json',result);return result


def rescore():
    refs=read('references/complete_record.json')
    expected={r['run_id']:r for r in read('expected_results/saved_scores.json')}
    rows=[]
    for item in read('manifests/assignments.json'):
        es=events(item['response_path']);responses=[e['response'] for e in es if e['event']=='api_response' and ('choices' in e['response'] or 'content' in e['response'])]
        assert len(responses)==1
        raw=responses[0]
        text=raw['choices'][0]['message']['content'] if item['reader']=='luna' else ''.join(b['text'] for b in raw['content'] if b['type']=='text')
        answer=json.loads(text)
        ends=[e for e in es if e['event']=='reader_end'];assert len(ends)==1 and ends[0]['parsed_answer']==answer
        assert rec.validate_answer(answer)==[]
        packet=read(item['packet_path']);scorer=rec if item['study']=='I' else mapping
        score=scorer.score_answer(answer,refs[item['case_id']],packet)
        assert answer==expected[item['run_id']]['answer'] and score==expected[item['run_id']]['score']
        rows.append(item|{'answer':answer,'score':score,'native_usage':raw.get('usage',{})})
    dump('rescored.json',rows)
    result={'reader_outputs_reparsed':len(rows),'saved_scores_exact_matches':len(rows),'schema_invalid':0}
    dump('rescore_validation.json',result);return result


def aggregate():
    rows=read('results/rescored.json');comp=read('results/comparator_answers.json')
    refs=read('references/complete_record.json')
    expected={(r['study'],r['case_id'],r['condition']):r for r in read('expected_results/comparator.json')}
    bykey={(r['study'],r['case_id'],r['condition']):r for r in rows}
    comparators=[]
    for answer in comp['answers']:
        key=(answer['study'],answer['case_id'],answer['condition']);item=bykey[key]
        packet=read(item['packet_path']);scorer=rec if answer['study']=='I' else mapping
        score=scorer.score_answer(answer['answer'],refs[answer['case_id']],packet)
        assert answer['answer']==expected[key]['answer'] and score==expected[key]['score']
        assert all(s['grounded_correct'] for s in score['questions'].values())
        comparators.append(item|{'reader':'comparator','answer':answer['answer'],'score':score})
    summaries=[];details=[];figure=[];strata=[]
    for study in ('I','II'):
        conditions=('R00','R10','R01','R11') if study=='I' else mapping.CONDITIONS
        for reader in ('luna','sonnet','comparator'):
            for cond in conditions:
                group=[r for r in rows+comparators if r['study']==study and r['reader']==reader and r['condition']==cond];assert len(group)==64
                for q in rec.QUESTIONS:
                    scores=[r['score']['questions'][q] for r in group]
                    metrics={'G':sum(s['grounded_correct'] for s in scores),'D':sum(s['supported_resolved_correct'] for s in scores),
                        'A':sum(s['grounded_correct'] and s['abstained'] for s in scores),'U':sum(s['unsupported_assertion'] is True for s in scores),
                        'U_unknown':sum(s['unsupported_assertion'] is None for s in scores),'W':sum(s['world_correct'] for s in scores),
                        'answerable':sum(s['evidence_answerable'] for s in scores),'invalid':sum(s['invalid_or_missing'] for s in scores)}
                    assert metrics['G']==metrics['D']+metrics['A']
                    for metric,value in metrics.items():summaries.append(dict(study=study,reader_or_comparator=reader,condition=cond,question=q,stratum='all',n=64,metric=metric,value=value))
                    if reader=='comparator':
                        detail=Counter((r['answer'][q]['answer'],bool(r['answer'][q].get('locators',[]))) for r in group)
                        details.append(dict(study=study,condition=cond,question=q,N=64,**metrics,nonempty_source_set=detail['resolved',True],empty_source_set=detail['resolved',False],basis_missing=detail['basis_missing',False]))
                    elif study=='II' and q=='basis_relation':figure.append(dict(reader=reader,condition=cond,N=64,D=metrics['D'],A=metrics['A'],U=metrics['U'],other_incorrect=64-metrics['G']-metrics['U']))
                if study=='II' and reader!='comparator':
                    for stratum in ('mapping_required','mapping_not_required'):
                        ss=[r['score']['questions']['basis_relation'] for r in group if r['stratum']==stratum]
                        values={'G':sum(s['grounded_correct'] for s in ss),'D':sum(s['supported_resolved_correct'] for s in ss),
                                'A':sum(s['grounded_correct'] and s['abstained'] for s in ss),'U':sum(s['unsupported_assertion'] is True for s in ss),
                                'W_and_U':sum(s['world_correct'] and s['unsupported_assertion'] is True for s in ss)}
                        strata.append(dict(reader=reader,condition=cond,stratum=stratum,n=len(ss),**values))
                        if stratum=='mapping_required':
                            for metric,value in values.items():summaries.append(dict(study=study,reader_or_comparator=reader,condition=cond,question='basis_relation',stratum=stratum,n=28,metric=metric,value=value))
    for name,actual in [('results_summary.csv',summaries),('comparator_results.csv',details),('figure2_outcomes.csv',figure)]:
        saved=csvread('expected_results/'+name)
        assert len(actual)==len(saved)
        for a,b in zip(actual,saved):
            assert all(str(value)==b[k] for k,value in a.items()),(name,a,b)
        csvout(name,actual)
    csvout('strata.csv',strata)
    frozen=read('expected_results/frozen_paired.json');paired=[];primary=[];roundoff=[]
    for pass_id,old in frozen.items():
        specifications=[dict(zip(('left','right','question','metric'),k.split(':')),reader='luna' if 'sonnet' not in pass_id else 'sonnet',expected=v) for k,v in old.items()] if isinstance(old,dict) else [dict(r,expected=r) for r in old]
        for spec in specifications:
            rr=[r for r in rows if r['pass_id']==pass_id and r['reader']==spec['reader']]
            result=paired_cluster_summary(rr,spec['question'],spec['metric'],spec['left'],spec['right'])
            for key,value in result.items():
                previous=spec['expected'][key]
                if value==previous:continue
                if key=='difference':distance=abs(value-previous)
                elif key=='exploratory_cluster_bootstrap_95_percentile':distance=max(abs(a-b) for a,b in zip(value,previous))
                else:raise AssertionError((pass_id,key,value,previous))
                assert distance<=1e-12,(pass_id,key,value,previous)
                roundoff.append(dict(pass_id=pass_id,reader=spec['reader'],left=spec['left'],right=spec['right'],question=spec['question'],metric=spec['metric'],field=key,max_absolute_difference=distance))
            study=rr[0]['study'];out={k:spec[k] for k in ('reader','left','right','question','metric')}
            paired.append(dict(study=study,**out,**result))
            if spec['metric']=='grounded_correct' and ((study=='I' and spec['question']=='prior_external' and (spec['left'],spec['right']) in [('R00','R10'),('R01','R11')]) or (study=='II' and spec['question']=='basis_relation' and (spec['left'],spec['right']) in [('C00','C10'),('C01','C11')])):
                primary.append(dict(study=study,reader=spec['reader'],question=spec['question'],left=spec['left'],right=spec['right'],change_pp=100*result['difference'],lower_pp=100*result['exploratory_cluster_bootstrap_95_percentile'][0],upper_pp=100*result['exploratory_cluster_bootstrap_95_percentile'][1],clusters=13,draws=10000,seed=42))
    saved_primary=csvread('expected_results/verified_contrasts.csv')
    for a in primary:
        b=next(r for r in saved_primary if all(r[k]==a[k] for k in ('study','reader','left','right')))
        assert all(abs(a[k]-float(b[k]))<1e-12 for k in ('change_pp','lower_pp','upper_pp'))
    dump('all_paired.json',paired);dump('floating_point_comparison.json',roundoff);csvout('verified_contrasts.csv',primary)
    errors=[]
    for r in rows:
        if r['study']!='II' or r['condition'] not in ('C10','C11') or r['score']['questions']['basis_relation']['grounded_correct']:continue
        packet=read(r['packet_path']);exp=mapping.visible_answers(refs[r['case_id']],packet)['basis_relation'];got=r['answer']['basis_relation']
        eset,gset=set(exp['locators']),set(got['locators'])
        locators={loc for a in packet['tool_log'] for loc,_ in rec.result_records(a)}|{'request.user'}
        pos=next(i for i,a in enumerate(packet['tool_log']) if a['action_id']==packet['target']['action_id'])
        later={loc for a in packet['tool_log'][pos:] for loc,_ in rec.result_records(a)}
        errors.append(dict(case_id=r['case_id'],reader=r['reader'],condition=r['condition'],U=r['score']['questions']['basis_relation']['unsupported_assertion'],
            expected=exp,observed=got,unwarranted_abstention=got['answer']=='insufficient_evidence',extra_locator=bool(gset-eset),nonexistent_locator=bool(gset-locators),
            subset_omission=got['answer']==exp['answer']=='resolved' and gset<eset,wrong_answer_state=got['answer']!=exp['answer'],target_or_later_locator=bool(gset&later)))
    error_summary=[]
    for reader in ('luna','sonnet'):
        for cond in ('C10','C11'):
            group=[r for r in errors if r['reader']==reader and r['condition']==cond]
            error_summary.append(dict(reader=reader,condition=cond,errors=len(group),U=sum(r['U'] is True for r in group),**{k:sum(r[k] for r in group) for k in ('unwarranted_abstention','extra_locator','nonexistent_locator','subset_omission','wrong_answer_state','target_or_later_locator')}))
    for a,b in zip(error_summary,csvread('expected_results/q3_error_summary.csv')):assert all(str(v)==b[k] for k,v in a.items())
    assert len(errors)==58 and len({r['case_id'] for r in errors})==31
    dump('q3_with_binding_errors.json',errors);csvout('q3_error_summary.csv',error_summary)
    # Same answer comparison as the frozen mapping analysis, preserving set semantics.
    def equal(a,b,q):return rec.equivalent(a['answer'][q],b['answer'][q],q)
    lookup={(r['study'],r['reader'],r['case_id'],r['condition']):r for r in rows}
    agreements=[];renaming=[]
    for cond in mapping.CONDITIONS:
        pairs=[(lookup['II','luna',case,cond],lookup['II','sonnet',case,cond]) for case in refs]
        agreements.append(dict(condition=cond,Q3_equal=sum(equal(a,b,'basis_relation') for a,b in pairs),shared_W_and_U=sum(equal(a,b,'basis_relation') and all(x['score']['questions']['basis_relation']['world_correct'] and x['score']['questions']['basis_relation']['unsupported_assertion'] for x in (a,b)) for a,b in pairs)))
    for reader in ('luna','sonnet'):
        for left,right in [('C00','C01'),('C10','C11')]:
            renaming.append(dict(reader=reader,left=left,right=right,Q3_changed=sum(not equal(lookup['II',reader,c,left],lookup['II',reader,c,right],'basis_relation') for c in refs)))
    assert [r['Q3_equal'] for r in agreements]==[41,44,28,41]
    assert [r['shared_W_and_U'] for r in agreements]==[11,0,8,0]
    assert [r['Q3_changed'] for r in renaming]==[25,16,9,7]
    count=sum(not s['grounded_correct'] or bool(s['unsupported_assertion']) for r in rows if r['study']=='II' for s in r['score']['questions'].values());assert count==274
    shared=[c for c in refs if equal(lookup['I','luna',c,'R10'],lookup['I','sonnet',c,'R10'],'basis_relation') and all(lookup['I',reader,c,'R10']['score']['questions']['basis_relation']['world_correct'] and lookup['I',reader,c,'R10']['score']['questions']['basis_relation']['unsupported_assertion'] for reader in ('luna','sonnet'))]
    assert len(shared)==16 and len({lookup['I','luna',c,'R10']['task_id'] for c in shared})==7
    claims=dict(agreements=agreements,renaming=renaming,study_ii_error_question_items=count,study_i_shared_W_and_U_cases=shared)
    dump('additional_claims.json',claims)
    # Verify the six shipped manuscript table excerpts against recalculated values.
    def metric(study,reader,cond,q,m):
        return next(r['value'] for r in summaries if r['study']==study and r['reader_or_comparator']==reader and r['condition']==cond and r['question']==q and r['metric']==m and r['stratum']=='all')
    table_rows=0
    for study,name in [('I','study1'),('II','study2')]:
        for line in (ROOT/f'expected_results/paper_tables/{name}.tex').read_text().splitlines():
            if not re.match(r'^(Luna|Sonnet) &',line):continue
            cells=[c.strip() for c in line.rstrip('\\ ').split('&')];reader,cond=cells[:2];reader=reader.lower()
            values=[metric(study,reader,cond,q,m) for q,m in [('user_literal','G'),('prior_external','G'),('basis_relation','G'),('basis_relation','D'),('basis_relation','U')]]
            if study=='II':values.append(metric(study,reader,cond,'basis_relation','W'))
            assert list(map(int,cells[2:]))==values;table_rows+=1
    for line in (ROOT/'expected_results/paper_tables/required.tex').read_text().splitlines():
        if not re.match(r'^(Luna|Sonnet) &',line):continue
        cells=[c.strip() for c in line.rstrip('\\ ').split('&')]
        r=next(r for r in strata if r['reader']==cells[0].lower() and r['condition']==cells[1] and r['stratum']=='mapping_required')
        assert list(map(int,cells[2:]))==[r[k] for k in ('n','A','D','U','W_and_U')];table_rows+=1
    for line in (ROOT/'expected_results/paper_tables/contrasts.tex').read_text().splitlines():
        if not re.match(r'^II?: Q',line):continue
        cells=[c.strip() for c in line.rstrip('\\ ').split('&')];right,_,left=cells[2].split()
        r=next(r for r in primary if r['reader']==cells[1].lower() and r['left']==left and r['right']==right)
        assert cells[3]==f"{r['change_pp']:+.2f}" and cells[4]==f"[{r['lower_pp']:+.2f}, {r['upper_pp']:+.2f}]";table_rows+=1
    for line in (ROOT/'expected_results/paper_tables/comparator.tex').read_text().splitlines():
        if not re.match(r'^[RC][01][01]',line):continue
        cells=[c.strip() for c in line.rstrip('\\ ').split('&')]
        for cond in cells[0].split(', '):
            r=next(r for r in details if r['condition']==cond and r['question']=='basis_relation')
            assert list(map(int,cells[1:]))==[r[k] for k in ('D','A','nonempty_source_set','empty_source_set','basis_missing')]
        table_rows+=1
    # Token counts and recorded estimates remain separate from inference reruns.
    meta={r['run_id']:r for r in read('manifests/execution_metadata.json')};burden=[]
    for study in ('I','II'):
        for reader in ('luna','sonnet'):
            for cond in sorted({r['condition'] for r in rows if r['study']==study}):
                group=[meta[r['run_id']] for r in rows if r['study']==study and r['reader']==reader and r['condition']==cond]
                burden.append(dict(study=study,reader=reader,condition=cond,readings=len(group),input_tokens=sum(r['input_tokens'] for r in group),output_tokens=sum(r['output_tokens'] for r in group),estimated_cost_usd=sum(r['estimated_cost_usd'] for r in group)))
    csvout('recorded_usage.csv',burden)
    # A portable SVG redraw of Figure 2, using the verified outcome counts.
    colors={'D':'#377eb8','A':'#8ecae6','U':'#e76f51','other_incorrect':'#bdbdbd'}
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="410" viewBox="0 0 900 410">','<rect width="900" height="410" fill="white"/>','<text x="20" y="25" font-family="sans-serif" font-size="18">Study II Q3 outcomes (64 readings per row)</text>']
    for i,row in enumerate(figure):
        y=50+i*36;svg.append(f'<text x="15" y="{y+19}" font-family="sans-serif" font-size="14">{row["reader"]} {row["condition"]}</text>');x=155
        for key,color in colors.items():
            width=row[key]*10
            svg.append(f'<rect x="{x}" y="{y}" width="{width}" height="27" fill="{color}"/>')
            if width:svg.append(f'<text x="{x+width/2}" y="{y+19}" text-anchor="middle" font-family="sans-serif" font-size="13">{row[key]}</text>')
            x+=width
    for i,(key,color) in enumerate(colors.items()):
        x=20+i*210;svg.extend([f'<rect x="{x}" y="365" width="15" height="15" fill="{color}"/>',f'<text x="{x+22}" y="378" font-family="sans-serif" font-size="13">{key}</text>'])
    svg.append('</svg>');(ROOT/'results/figure2.svg').write_text('\n'.join(svg)+'\n')
    result={'comparator_answers_and_scores_exact_matches':512,'pooled_summary_rows':len(summaries),'primary_contrasts':len(primary),'paper_numeric_table_rows_verified':table_rows,
            'all_frozen_bootstrap_contrasts_matches_within_1e_12':len(paired),'bootstrap_roundoff_fields':len(roundoff),
            'maximum_absolute_roundoff':max((x['max_absolute_difference'] for x in roundoff),default=0),
            'bootstrap_draws_each':10000,'seed':42,'q3_binding_errors':58,'q3_binding_error_cases':31,
            'numerical_mismatches_above_tolerance':0,'comparator_boundary':comp['boundary']}
    dump('aggregation_validation.json',result)
    return {k:v for k,v in result.items() if k!='comparator_boundary'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['integrity','validate','rescore','aggregate']);args=parser.parse_args()
    # Load the standard-library CLI machinery before restricting input-file reads.
    sys.addaudithook(offline)
    start=time.monotonic()
    result={'integrity':verify_integrity,'validate':verify_inputs,'rescore':rescore,'aggregate':aggregate}[args.command]()
    print(json.dumps(dict(command=args.command,passed=True,elapsed_seconds=round(time.monotonic()-start,3),**result)))


if __name__=='__main__':main()
