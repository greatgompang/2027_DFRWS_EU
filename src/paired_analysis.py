"""Original paired task-cluster analysis, unchanged."""
import collections
import random

def paired_cluster_summary(rows, question, metric, left, right):
    lookup = {(r['case_id'], r['condition']): r for r in rows}
    by_task = collections.defaultdict(list)
    complete = 0
    for case in sorted({r['case_id'] for r in rows}):
        a, b = lookup[(case, left)], lookup[(case, right)]
        av, bv = a['score']['questions'][question][metric], b['score']['questions'][question][metric]
        # Unknown unsupported-assertion status on failed requests is not zero.
        if av is None or bv is None:
            continue
        by_task[a['task_id']].append(int(bv) - int(av))
        complete += a['execution_state'] == b['execution_state'] == 'completed'
    means = [sum(x) / len(x) for _, x in sorted(by_task.items())]
    if not means:
        return {'difference': None, 'paired_cases': 0, 'task_clusters': 0}
    rng = random.Random(42)
    samples = sorted(sum(rng.choices(means, k=len(means))) / len(means) for _ in range(10000))
    return {'difference': sum(means) / len(means), 'direction': right + '-' + left,
            'task_equal_weighted': True, 'task_clusters': len(means),
            'paired_cases': sum(map(len, by_task.values())), 'pairs_both_completed': complete,
            'exploratory_cluster_bootstrap_95_percentile': [samples[249], samples[9749]],
            'bootstrap_seed': 42, 'bootstrap_draws': 10000,
            'limitation': 'Few task clusters; retrospective corpus; interval is not a confirmatory causal test.'}
