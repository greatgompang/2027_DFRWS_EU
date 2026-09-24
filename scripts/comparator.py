"""Run the original comparator with packet-only filesystem reads enforced."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from harness import reconstruction_evaluation as rec, mapping_evaluation as mapping

index_path = ROOT / 'manifests/packets.json'
index = json.loads(index_path.read_text())
output = ROOT / 'results/comparator_answers.json'
output.parent.mkdir(exist_ok=True)
allowed = {(ROOT / r['packet_path']).resolve() for r in index}
reads = set()
denied = []


def boundary(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('Network access disabled')
    if event != 'open' or not isinstance(args[0], (str, bytes)):
        return
    path = Path(args[0]).resolve()
    mode = args[1] or ''
    if any(c in mode for c in 'wax+'):
        if path != output:
            raise PermissionError('Comparator write outside designated output')
    elif path not in allowed:
        denied.append(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else 'outside-release')
        raise PermissionError('Comparator read outside visible packets')
    else:
        reads.add(str(path.relative_to(ROOT)))


sys.addaudithook(boundary)
# Negative control: even an explicit reference read must be rejected.
try:
    (ROOT / 'references/complete_record.json').read_text()
except PermissionError:
    pass
else:
    raise AssertionError('Reference read was not blocked')
rows = []
for item in index:
    data = (ROOT / item['packet_path']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == item['packet_sha256']
    packet = json.loads(data)
    answer = rec.packet_only_baseline(packet) if item['study'] == 'I' else mapping.baseline(packet)
    rows.append({k: item[k] for k in ('study','case_id','condition')} | {'answer': answer})
assert len(rows) == len(reads) == 512
assert denied == ['references/complete_record.json']
output.write_text(json.dumps({'answers': rows, 'boundary': {'unique_packet_reads':len(reads),
    'read_paths':sorted(reads), 'reference_negative_control_blocked':True,
    'unexpected_read_attempts':0, 'reference_content_read':False}}, indent=2)+'\n')
print('PASS: 512 packet-only answers; reference access negative control blocked.')
