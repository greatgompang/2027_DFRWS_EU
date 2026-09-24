"""Original offline extraction functions, unchanged."""
import json
FIELDS = ('recipient', 'iban', 'account_number', 'password', 'file_path', 'date', 'subject')

def leaves(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from leaves(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from leaves(v)


def native_inputs(body, provider):
    """Classify transport blocks, never user/tool-looking text within a block."""
    result = []
    if provider == 'openai':
        for i, message in enumerate(body['messages']):
            if message['role'] in ('user', 'system', 'tool'):
                result.append({'role': message['role'], 'wire_index': i,
                               'texts': list(leaves(message.get('content', '')))})
    elif provider == 'anthropic':
        result.append({'role': 'system', 'wire_index': -1, 'texts': list(leaves(body.get('system', '')))})
        for i, message in enumerate(body['messages']):
            content = message['content']
            if isinstance(content, str):
                if message['role'] == 'user':
                    result.append({'role': 'user', 'wire_index': i, 'texts': [content]})
            else:
                for block in content:
                    if block['type'] == 'tool_result':
                        result.append({'role': 'tool', 'wire_index': i, 'texts': list(leaves(block.get('content', '')))})
                    elif block['type'] == 'text' and message['role'] == 'user':
                        result.append({'role': 'user', 'wire_index': i, 'texts': [block['text']]})
    elif provider == 'google':
        result.append({'role': 'system', 'wire_index': -1, 'texts': list(leaves(body.get('systemInstruction', {})))})
        for i, message in enumerate(body['contents']):
            for block in message['parts']:
                if 'functionResponse' in block:
                    result.append({'role': 'tool', 'wire_index': i, 'texts': list(leaves(block['functionResponse']['response']))})
                elif 'text' in block and message['role'] == 'user':
                    result.append({'role': 'user', 'wire_index': i, 'texts': [block['text']]})
    else:
        raise ValueError(provider)
    return result


def native_calls(response, provider):
    if provider == 'openai':
        calls = response['choices'][0]['message'].get('tool_calls') or []
        return [(c['function']['name'], json.loads(c['function']['arguments'])) for c in calls]
    if provider == 'anthropic':
        return [(c['name'], c['input']) for c in response['content'] if c['type'] == 'tool_use']
    if provider == 'google':
        return [(p['functionCall']['name'], p['functionCall'].get('args', {}))
                for c in response.get('candidates', []) for p in c.get('content', {}).get('parts', []) if 'functionCall' in p]
    raise ValueError(provider)


def string_args(args):
    return [(k, args[k]) for k in sorted(args, key=lambda k: (FIELDS.index(k) if k in FIELDS else len(FIELDS), k))
            if isinstance(args[k], str) and args[k] != '']


def select_target(events):
    """First string-argument action after any external context, then first overall."""
    candidates = [(i, e, string_args(e['args'])) for i, e in enumerate(events)
                  if e['event'] == 'action' and string_args(e['args'])]
    after = [(i, e, args) for i, e, args in candidates if any(c['channel'] in ('document', 'tool') for c in e['context'])]
    if not candidates:
        return None
    i, action, args = (after or candidates)[0]
    key, value = args[0]
    return {'event_index': i, 'action': action, 'arg_key': key, 'literal': value,
            'selection': 'first_string_argument_action_after_external_context' if after else 'first_string_argument_action_no_external_context'}


def contexts_with_locators(events):
    contexts = []
    last_action = None
    last_result = None
    ordinal = 0
    for i, event in enumerate(events):
        if event['event'] == 'action':
            last_action = event['action_id'];last_result = event['result'];ordinal = 0
        elif event['event'] == 'context_input':
            if event['channel'] in ('document', 'tool'):
                assert last_action is not None
                ordinal += 1
                indexed = isinstance(last_result, list) and bool(last_result)
                locator = last_action + '.result' + (f'[{ordinal}]' if indexed else '')
                expected = last_result[ordinal - 1] if indexed else last_result
                actual = event['raw'] if event['channel'] == 'document' else json.loads(event['raw'])
                assert actual == expected, (event['id'], locator)
            else:
                locator = 'request.' + event['channel']
            contexts.append({'event_index': i, 'id': event['id'], 'channel': event['channel'],
                             'raw': event['raw'], 'hash': event['hash'], 'locator': locator,
                             'timestamp': event['timestamp']})
    return contexts
