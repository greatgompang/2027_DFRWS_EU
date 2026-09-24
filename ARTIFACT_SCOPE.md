# Scope of offline reproduction

The reference manuscript is **Correct Answers, Unsupported Findings: Auditing Evidence Bindings in LLM Agent Logs**. Table numbers below correspond to the inspected manuscript; stable labels are also provided in `manifests/paper_map.csv`.

| Paper item | Status | Offline evidence/output |
|---|---|---|
| Table 1, main campaign (`tab:campaign`) | Outside this package | Full 696-slot campaign and its classification inputs are not redistributed. No claim to recompute 23/394/277 outcomes here. |
| Table 2, binding schema (`tab:schema`) | Verifiable contract, not a statistical table | `schemas/answer.json`, saved packets, original scorer; `validate` rebuilds conditions and checks request inputs. The table excerpt is retained. |
| Table 3, comparator (`tab:comparator`) | Recalculable | `results/comparator_results.csv`; 512 packet-only decisions, separately scored. |
| Table 4, Study I (`tab:study1`) | Recalculable | `results/results_summary.csv`, study I; 512 retained readings. |
| Table 5, Study II (`tab:study2`) | Recalculable | `results/results_summary.csv`, study II; 512 retained readings. |
| Table 6, primary contrasts (`tab:contrasts`) | Recalculable | `results/verified_contrasts.csv`; eight task-equal contrasts and 10,000-draw intervals. |
| Table 7, mapping-required stratum (`tab:required`) | Recalculable | `results/strata.csv`; all 28 cases, both readers, all C conditions. |
| Figure 1, study overview (`fig:overview`) | Partly verifiable | 96/64/32 selection, 13 tasks, condition construction, within-condition input equality, and scorer/comparator boundary are verified. Graphic/layout reproduction is outside scope. |
| Figure 2, Q3 outcomes (`fig:q3`) | Numerical content recalculable | `results/figure2_outcomes.csv`, `results/figure2.svg`; new SVG rendering of the same D/A/U/other counts. |

All 37 numeric table rows across Tables 3–7 are checked against the shipped TeX excerpts, including the eight primary intervals rounded to two decimals. Table 2 is a schema description, not an additional numeric test. These excerpts are retained comparison material, not a complete compilable manuscript.

Additional verifiable results include the fixed 96-candidate selection from 264 completed A0/A1 inventory rows; 32/96 exclusions (33.3% rounded); source-model distribution 22/17/25; 28 mapping-required/36 other cases; the abstract's Sonnet C00 26/28 unsupported and 22 reference-matching unsupported answers; 58 erroneous binding-condition responses across 31 cases; 274 incorrect/unsupported Study II question items; renaming changes and cross-reader agreement; and the Study I 16-case/7-task shared unsupported-reference-matching intersection. Original native usage and retained cost estimates can be aggregated in `results/recorded_usage.csv`; provider invoices and whole-pass operational elapsed-time accounting are not reproduced.

Study I Q2 is the original primary endpoint; Study II Q3 is the separate binding intervention's primary endpoint. The latter does not replace the former. All 144 original paired comparisons, including secondary contrasts and unsupported-assertion rates, are regenerated with the original seed and code. Exact pooled counts and task-equal estimates are kept separate.

The selection-pool projection contains the 264 completed E1 A0/A1 records used for selecting cases and only the outcome-independent selection keys. It can reproduce the selection operation but cannot independently establish that these were all completed campaign runs: that requires the omitted full campaign evidence. Each of the 96 chosen source logs is included in full, so target selection, exclusions, complete-record references, and packet construction are independently recomputed from native records. Records labeled `private` in historical terminology mean hidden from the experimental reader, not hidden from this artifact's reviewer. Here they reside in `references/` and remain inaccessible to the comparator execution path.

Omitted materials include the full original campaign/pilot, E2 and E3, the 60-execution attack-development set, full L1/L2 collections, human review material, execution permissions and spending ledger, model weights, provider credentials, original repository history, machine snapshots, manuscript PDF/BibTeX and figure-editing files. Omission of these larger earlier studies is deliberate and does not erase their reported failures or no-go decisions. This package reproduces the two saved-output reconstruction studies, not the entire paper or fresh model inference.
