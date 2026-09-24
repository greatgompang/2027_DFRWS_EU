"""Original independent reference function, unchanged."""
import json

def independent_reference(events, target):
    """Second implementation uses action snapshots and source-event ordinal.

    It does not import the preflight's selectors, native parser, or locator code.
    Native wire reconciliation is separately preserved by the prior audit.
    """
    action_index = next(i for i, e in enumerate(events)
                        if e.get('event') == 'action' and e['action_id'] == target['action_id'])
    action = events[action_index]
    value = target['literal']
    assert action['args'][target['arg_key']] == value
    origins = {}; last = None; record_number = 0
    for event in events[:action_index]:
        if event['event'] == 'action':
            last = event; record_number = 0
        elif event['event'] == 'context_input' and event['channel'] in ('document', 'tool'):
            assert last is not None
            record_number += 1
            result = last['result']
            if isinstance(result, list) and len(result):
                loc = '%s.result[%d]' % (last['action_id'], record_number)
                record = result[record_number - 1]
            else:
                assert record_number == 1
                loc = last['action_id'] + '.result'; record = result
            assert (event['raw'] if event['channel'] == 'document' else json.loads(event['raw'])) == record
            origins[event['id']] = loc
    matches = [c for c in action['context'] if c['channel'] in ('document', 'tool') and value in c['raw']]
    refs = action['stated_refs']
    return {'target': target,
            'user_literal_present': any(value in c['raw'] for c in action['context'] if c['channel'] == 'user'),
            'prior_locators': sorted(origins[c['id']] for c in matches),
            'basis_recorded': refs is not None,
            'basis_ids': refs,
            'basis_match_locators': sorted(origins[c['id']] for c in matches if refs is not None and c['id'] in refs),
            'reference_kind': 'mechanically_verified_literal_observations_not_human_gold'}
