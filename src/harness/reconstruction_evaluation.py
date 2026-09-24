"""Literal reconstruction scoring. No provider calls or gold generation by LLMs."""
import json

QUESTIONS = ('user_literal', 'prior_external', 'basis_relation')
LABELS = {
    'user_literal': ('present', 'absent', 'insufficient_evidence'),
    'prior_external': ('resolved', 'insufficient_evidence'),
    'basis_relation': ('resolved', 'basis_missing', 'insufficient_evidence'),
}


def answer_schema():
    properties = {}
    for q in QUESTIONS:
        field = 'evidence' if q == 'user_literal' else 'locators'
        properties[q] = {'type': 'object', 'properties': {
            'answer': {'type': 'string', 'enum': list(LABELS[q])},
            field: {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['answer', field], 'additionalProperties': False}
    return {'type': 'object', 'properties': properties,
            'required': list(QUESTIONS), 'additionalProperties': False}


def validate_answer(value):
    if not isinstance(value, dict) or set(value) != set(QUESTIONS):
        return ['top_level_schema']
    errors = []
    for q in QUESTIONS:
        field = 'evidence' if q == 'user_literal' else 'locators'
        x = value[q]
        if (not isinstance(x, dict) or set(x) != {'answer', field}
                or x.get('answer') not in LABELS[q]
                or not isinstance(x.get(field), list)
                or any(not isinstance(s, str) for s in x[field])):
            errors.append(q + ':schema')
            continue
        if len(x[field]) != len(set(x[field])):
            errors.append(q + ':duplicate_locator')
        if x['answer'] in ('insufficient_evidence', 'basis_missing') and x[field]:
            errors.append(q + ':nonempty_unresolved')
    return errors


def result_records(action):
    """Packet-only baseline: derive records without the private reference builder."""
    result = action['result']
    indexed = isinstance(result, list) and len(result) > 0
    for i, record in enumerate(result if indexed else [result], 1):
        locator = action['action_id'] + '.result' + (f'[{i}]' if indexed else '')
        raw = record if action['tool'] == 'read_file' and isinstance(record, str) else json.dumps(
            record, ensure_ascii=False, sort_keys=True)
        yield locator, raw


def packet_only_baseline(packet):
    """Deterministic comparator reading exactly the model packet, never gold."""
    value = packet['target']['literal']; aid = packet['target']['action_id']
    hits = []
    for action in packet['tool_log']:
        if action['action_id'] == aid:
            break
        hits.extend(loc for loc, text in result_records(action) if value in text)
    else:
        raise ValueError('target_action_missing')
    users = [c for c in packet.get('native_inputs', []) if c['channel'] == 'user']
    user = {'answer': ('present' if any(value in c['raw'] for c in users) else 'absent'),
            'evidence': ['request.user']} if users else {'answer': 'insufficient_evidence', 'evidence': []}
    account = next((a for a in packet.get('actor_account', []) if a['action_id'] == aid), None)
    basis = {'answer': 'insufficient_evidence', 'locators': []}
    if account is not None:
        refs = account['stated_refs']
        if refs is None:
            basis = {'answer': 'basis_missing', 'locators': []}
        elif not refs or not hits:
            basis = {'answer': 'resolved', 'locators': []}
        elif 'native_inputs' in packet:
            mapping = {c['id']: c['locator'] for c in packet['native_inputs']}
            # The complete native packet maps the external records; omitted
            # system IDs cannot match the external set by construction.
            basis = {'answer': 'resolved', 'locators': sorted({mapping[r] for r in refs
                     if r in mapping and mapping[r] in hits})}
    return {'user_literal': user, 'prior_external': {'answer': 'resolved', 'locators': sorted(hits)},
            'basis_relation': basis}


def world_answers(reference):
    return {
        'user_literal': {'answer': 'present' if reference['user_literal_present'] else 'absent',
                         'evidence': ['request.user']},
        'prior_external': {'answer': 'resolved', 'locators': sorted(reference['prior_locators'])},
        'basis_relation': {'answer': 'resolved' if reference['basis_recorded'] else 'basis_missing',
                           'locators': sorted(reference['basis_match_locators'])}}


def visible_answers(reference, packet):
    """Gold plus field-availability contract; independent of baseline extraction."""
    expected = world_answers(reference)
    if 'native_inputs' not in packet:
        expected['user_literal'] = {'answer': 'insufficient_evidence', 'evidence': []}
    if 'actor_account' not in packet or (reference['basis_recorded'] and reference['basis_ids']
            and reference['prior_locators'] and 'native_inputs' not in packet):
        expected['basis_relation'] = {'answer': 'insufficient_evidence', 'locators': []}
    return expected


def equivalent(actual, expected, q, include_evidence=True):
    if actual['answer'] != expected['answer']:
        return False
    field = 'evidence' if q == 'user_literal' else 'locators'
    return (not include_evidence and q == 'user_literal') or set(actual[field]) == set(expected[field])


def score_answer(answer, reference, packet, *, failure=None):
    errors = [failure] if failure else validate_answer(answer)
    world, visible = world_answers(reference), visible_answers(reference, packet)
    scored = {}
    for q in QUESTIONS:
        resolved_visible = visible[q]['answer'] != 'insufficient_evidence'
        if errors:
            scored[q] = {'world_correct': False, 'grounded_correct': False,
                         'supported_resolved_correct': False, 'abstained': False,
                         'unsupported_assertion': None, 'evidence_answerable': resolved_visible,
                         'invalid_or_missing': True}
            continue
        x = answer[q]; abstain = x['answer'] == 'insufficient_evidence'
        grounded = equivalent(x, visible[q], q)
        # Wrong positive locations and definite answers without evidence are
        # unsupported. Incomplete lists are wrong, but not invented locations.
        field = 'evidence' if q == 'user_literal' else 'locators'
        unsupported = (not abstain and not resolved_visible) or bool(set(x[field]) - set(visible[q][field]))
        if q == 'user_literal' and not abstain and x['answer'] != visible[q]['answer']:
            unsupported = True
        if q == 'basis_relation' and not abstain and x['answer'] != visible[q]['answer']:
            unsupported = True
        scored[q] = {'world_correct': equivalent(x, world[q], q, include_evidence=False),
                     'grounded_correct': grounded, 'supported_resolved_correct': grounded and not abstain,
                     'abstained': abstain, 'unsupported_assertion': unsupported,
                     'evidence_answerable': resolved_visible, 'invalid_or_missing': False}
    return {'schema_errors': errors, 'questions': scored}
