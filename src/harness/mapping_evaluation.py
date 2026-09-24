"""Literal ID-link intervention. Old packets and scoring are never modified."""
import copy
import json
import random
import re

from harness import reconstruction_evaluation as old

QUESTIONS = old.QUESTIONS
CONDITIONS = ('C00', 'C10', 'C01', 'C11')
ID_PATTERN = re.compile(r'\b(?:in|tr)-\d+\b')


def rename_value(value, mapping):
    if isinstance(value, str):
        return ID_PATTERN.sub(lambda match: mapping[match.group()], value)
    if isinstance(value, list):
        return [rename_value(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: rename_value(v, mapping) for k, v in value.items()}
    return value


def make_packets(base, native_packet):
    """Transform only actor-local ID references and an optional mapping table."""
    native = native_packet['native_inputs']
    ids = sorted({r['id'] for r in native})
    if ID_PATTERN.search(json.dumps(base['tool_log'])):
        raise ValueError('local_ID_in_immutable_tool_evidence_needs_design_review')
    actor_ids = set(ID_PATTERN.findall(json.dumps(base['actor_account'])))
    if actor_ids - set(ids):
        raise ValueError('actor_ID_without_native_mapping')
    rng = random.Random('42:' + base['case_id'])
    mapping = {i: 'ref_' + format(rng.getrandbits(64), '016x') for i in ids}
    if len(set(mapping.values())) != len(ids):
        raise ValueError('opaque_ID_collision')
    entries = [{'id': r['id'], 'locator': r['locator']} for r in native]
    if len({r['id'] for r in entries}) != len(entries):
        raise ValueError('native_ID_not_unique')
    packets = {}
    for condition in CONDITIONS:
        packet = copy.deepcopy(base)
        if condition in ('C01', 'C11'):
            packet['actor_account'] = rename_value(packet['actor_account'], mapping)
        if condition in ('C10', 'C11'):
            packet['id_mapping'] = [
                {'id': mapping[r['id']] if condition == 'C11' else r['id'], 'locator': r['locator']}
                for r in entries]
        packets[condition] = packet
    return packets, mapping


def baseline(packet):
    """Reads the same visible packet only, never complete private references."""
    answers = old.packet_only_baseline(packet)
    if 'id_mapping' in packet:
        account = next((x for x in packet.get('actor_account', [])
                        if x['action_id'] == packet['target']['action_id']), None)
        if account is not None and account['stated_refs'] is not None:
            mapping = {r['id']: r['locator'] for r in packet['id_mapping']}
            hits = set(answers['prior_external']['locators'])
            answers['basis_relation'] = {'answer': 'resolved', 'locators': sorted({
                mapping[r] for r in account['stated_refs'] if r in mapping and mapping[r] in hits})}
    return answers


def visible_answers(reference, packet):
    answers = old.visible_answers(reference, packet)
    if 'id_mapping' in packet and 'actor_account' in packet:
        answers['basis_relation'] = old.world_answers(reference)['basis_relation']
    return answers


def score_answer(answer, reference, packet, failure=None):
    errors = [failure] if failure else old.validate_answer(answer)
    world = old.world_answers(reference)
    visible = visible_answers(reference, packet)
    scored = {}
    for question in QUESTIONS:
        answerable = visible[question]['answer'] != 'insufficient_evidence'
        if errors:
            scored[question] = {'world_correct': False, 'grounded_correct': False,
                'supported_resolved_correct': False, 'abstained': False,
                'unsupported_assertion': None, 'evidence_answerable': answerable,
                'invalid_or_missing': True}
            continue
        actual = answer[question]
        abstain = actual['answer'] == 'insufficient_evidence'
        grounded = old.equivalent(actual, visible[question], question)
        field = 'evidence' if question == 'user_literal' else 'locators'
        unsupported = (not abstain and not answerable) or bool(set(actual[field]) - set(visible[question][field]))
        if question in ('user_literal', 'basis_relation') and not abstain and actual['answer'] != visible[question]['answer']:
            unsupported = True
        scored[question] = {'world_correct': old.equivalent(actual, world[question], question, include_evidence=False),
            'grounded_correct': grounded, 'supported_resolved_correct': grounded and not abstain,
            'abstained': abstain, 'unsupported_assertion': unsupported,
            'evidence_answerable': answerable, 'invalid_or_missing': False}
    return {'schema_errors': errors, 'questions': scored}
