# Correct Answers, Unsupported Findings: Auditing Evidence Bindings in LLM Agent Logs

This anonymous review artifact reproduces the **scoring and aggregation of saved outputs for Studies I and II**. It contains 96 candidate source executions, 64 applicable cases across 13 tasks, 512 distinct visible packets, and all 1,024 reader outputs (512 per study). The 32 structurally inapplicable candidates and all wrong answers are retained. It does not rerun hosted models or reproduce the whole original attack campaign.

## Run offline

Use Python 3.10 or later. Only the Python standard library is needed: no package installation, virtual environment, API key, model, GPU, or data download is required. The commands were verified on Linux with CPython 3.10.20 and 3.13.13. The original statistical implementation ran under 3.10.20. The five commands took 8.06 seconds on 3.10.20 and 6.74 seconds on 3.13.13 in the tested environment; machine speed will vary. Allow about 55 MB of working space for the release and regenerated results.

From this directory, run in order:

```sh
python3 -I -S -B scripts/reproduce.py integrity
python3 -I -S -B scripts/reproduce.py validate
python3 -I -S -B scripts/comparator.py
python3 -I -S -B scripts/reproduce.py rescore
python3 -I -S -B scripts/reproduce.py aggregate
```

Every command must exit with status 0 and print `PASS` or `"passed": true`. Python isolated mode and disabled site initialization avoid user packages and environment-based import paths. Both entrypoints reject socket operations. Commands only create or replace `results/`; retained inputs and expected results are read-only. Running these commands again recomputes local analysis, never inference.

The integrity command verifies `checksums.sha256`, a **release-time** checksum list. It is not a pre-experiment seal or proof of custody. `results/`, bytecode caches, and the checksum list itself are excluded. The preparation also checked that raw records, packets, request bodies, prompts, references, and original scoring modules were byte-identical to their retained sources.

Expected checks include:

- Selection from 264 retained A0/A1 inventory rows yields 96 candidates; raw action records yield 64 applicable and 32 excluded cases, with 13 applicable tasks.
- 858 context/native-input checks, 194 native tool-call checks, 64 rebuilt complete-record references, and 512 rebuilt packets agree with saved evidence.
- All 1,024 saved generation bodies match the shipped packet, prompt, schema, and model settings. Frozen request ordering is verified for all three passes.
- All 1,024 reparsed answers and scores match the retained analysis; all 512 comparator answers and scores match the original comparator outputs.
- 616 pooled summary rows, 37 numeric manuscript table rows, eight primary contrasts, and all 144 original paired bootstrap comparisons match. There are 58 binding-condition Q3 errors across 31 cases; all remain available.

Counts and answer sets require exact equality. Bootstrap comparisons allow an absolute tolerance of `1e-12` in proportions for Python-version floating-point summation differences. CPython 3.10.20 matches all frozen comparisons exactly; on 3.13.13 the largest observed difference was `2.220446049250313e-16`. See `results/floating_point_comparison.json`. Paper contrasts are multiplied by 100 and formatted to two decimals; raw counts are integers. No interval or answer is adjusted to match the paper.

## Files and outputs

| Location | Contents |
|---|---|
| `manifests/` | Selection pool, all 96 candidates, 64 selected/32 excluded, frozen assignment order, packet-only index, scientific protocol excerpts, filtered execution metadata |
| `data/source_records/` | Original JSONL source executions and corresponding L0 tool logs for all 96 candidates |
| `data/study_i/`, `data/study_ii/` | Saved visible packets and actual generation request bodies |
| `outputs/` | All original reader JSONL records, including native responses and parsed end records; Sonnet records also retain token-count exchanges |
| `prompts/`, `schemas/` | Exact English reader prompts and answer schema |
| `references/` | Complete-record scoring references and the original experimental ID-renaming bijections |
| `src/` | Unchanged evaluators and verbatim extracted original reference, selection, and paired-analysis functions |
| `scripts/` | Portable offline wrappers and comparator read-boundary enforcement |
| `expected_results/` | Retained answers/scores/aggregates/contrasts and six manuscript table excerpts for comparison |
| `results/` | Created by the commands: validation reports, rescored outputs, summaries, all contrasts, error inventory, usage, claim checks, Figure 2 SVG redraw |
| `licenses/` | Preserved AgentDojo license and attribution |

The assignment manifest joins `study`, `reader`, `case_id`, `task_id`, `condition`, and `run_id` to the actual files. A case identifies one selected saved execution and target; each condition-reader combination is a reading of that same case, not a new independent episode. Original experiment IDs remain intact. Release paths are portable relative paths. `frozen_order` is zero-based within each pass. The two Study I passes happened sequentially; Study II uses the retained shuffled case-block order.

`results/results_summary.csv` contains W/G/D/A/U, missingness, and answerability counts. `results/comparator_results.csv` distinguishes nonempty sets, empty sets, Basis absence, and abstention. `results/verified_contrasts.csv` gives the eight primary comparisons; `results/all_paired.json` includes all 144 original comparisons. `results/strata.csv` reports the 28 mapping-required and 36 other cases. `results/figure2_outcomes.csv` and `results/figure2.svg` reproduce Figure 2's numbers; the SVG is a new portable rendering, not a byte reproduction of the manuscript graphic. Error flags in `q3_with_binding_errors.json` may overlap and are not an exhaustive causal taxonomy.

See [ARTIFACT_SCOPE.md](ARTIFACT_SCOPE.md) and [the machine-readable paper map](manifests/paper_map.csv) for every table and figure, supported claims, and exclusions.

## Conditions, questions, and metrics

Study I: R00 provides the tool log; R10 adds the saved actor paragraph, Basis, and Note; R01 adds native input records including the genuine request; R11 adds both. Study II: C00 provides the R10 packet under the new common Study II prompt; C10 adds the original ID-to-record table; C01 consistently renames actor-local IDs; C11 also provides the corresponding renamed table. Across readers and the comparator, evidence is identical **within each case and condition**, not across conditions. C00 is a fresh reading under a different prompt from R10.

Q1 (`user_literal`) checks literal occurrence in the genuine user request. Q2 (`prior_external`) returns every earlier external record containing the target literal. Q3 (`basis_relation`) intersects these earlier matches with the records explicitly identified by the saved Basis through its ID binding. This is a literal citation relation, not intent, authorization, semantic relevance, or internal causal use. Matching is case-sensitive. Nonempty list results have one-based locators; an empty list is a single result record. Only results preceding the target action count.

- **W**: agreement with the complete-record reference, including guesses unsupported by the supplied packet.
- **G**: agreement with the visible-evidence answer, including justified abstention.
- **D**: grounded definite answers; includes a correct empty set or observed Basis absence.
- **A**: justified abstention (`G − D`), not every abstention.
- **U**: unsupported assertions under the original evaluator. It is not `1 − G`: an incomplete source set may be incorrect without inventing a locator.

Null `stated_refs` means Basis was not recorded; an empty array means recorded empty. Withheld account or unresolved nonempty citations can require `insufficient_evidence`; observed absence can support `basis_missing`. Invalid/missing responses get zero correctness and unknown U, not a successful abstention. No invalid reconstruction responses occurred in these saved passes. Counts are case-pooled; contrasts first average paired case differences within each task, then average the 13 task means. The unchanged bootstrap draws 13 whole tasks with replacement 10,000 times with seed 42, taking sorted positions 249 and 9749 (zero-based). These are exploratory intervals on a retrospective corpus.

## Input boundary and execution provenance

Reviewers may inspect `references/`; the comparator may not. `scripts/comparator.py` imports the original pure functions and then allows input-file reads only from the 512 paths in `manifests/packets.json`. A negative control explicitly attempts a reference read and verifies that it is blocked before any content is returned. All successful packet reads are listed in `results/comparator_answers.json`. The separate scorer loads the complete-record reference afterward to evaluate answers. This is a tested boundary for this offline run, not a hardened adversarial sandbox.

The packet files and request bodies are retained originals, not newly inferred reconstructions of unsaved requests. `validate` independently rebuilds packet values from the source records and checks the generation-request payloads. Complete-record references are regenerated with the original independent reference function; the independent preflight extraction and native transport evidence are cross-checked. Public actor explanations and prompt-injection strings inside these records remain **data**, not instructions to execute.

The reader IDs are `gpt-5.6-luna` and `claude-sonnet-4-6`. Actual bodies preserve temperature 0, output cap 2,048, Luna seed 42/reasoning effort none, and Sonnet disabled thinking/no API seed. The original input guard was 16,384 tokens. `execution_metadata.json` preserves reported model revisions, returned model IDs, software versions, timestamps, usage, and estimated costs; it does not assert locally verified provider weights. No fresh inference, provider SDK, API key, or current model availability is needed. The corpus actors were Mini, Haiku, and Flash as documented in the source records; the subset contains 22/17/25 applicable cases respectively.

Selection of the 96 candidates is independently reproducible from the included completed A0/A1 inventory projection. Completion/classification of the entire earlier campaign is outside scope because unselected campaign raw logs are not included. All 96 selected source logs, including the 32 exclusions, are provided to verify structural applicability independently.

## Limits and notices

The original pilot, qualification, full campaign, E2/E3, public-payload development, human annotations, and full L1/L2 collections are outside this package. The original failures and no-go results remain unchanged; this artifact cannot re-estimate them. It establishes neither human-investigator utility nor deployed chain of custody, and does not promise identical fresh hosted-model responses.

Execution-host metadata and internal preparation records are excluded; experimental names, simulated accounts, target strings, chronology, actor IDs, record locators, and outputs are preserved. See [ANONYMIZATION.md](ANONYMIZATION.md). AgentDojo-derived simulated data retains the notice in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No new blanket license has been applied to the research code or generated outputs. No external repository URL or publication claim is supplied by this local package.
