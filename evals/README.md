# How the skill was measured

The question this tests: does a walkthrough written with the skill leave a newcomer better able to change the code than one written by the same model without it?

## Setup

Two public targets, each picked to exercise a different mode of the skill:

| Target | Mode | Size |
|---|---|---|
| [pallets/click #3877](https://github.com/pallets/click/pull/3877), "Add `Parameter.spec` and deprecate `human_readable_name`" | pull request | 7 files, +266/−26 |
| [tj/commander.js](https://github.com/tj/commander.js) at `ba6d13d` | whole repository | ~4,400 lines in `lib/` |

For each target, five kinds of agent ran, all on the same model with fresh context and no shared memory:

1. **Author, with the skill.** Told to follow `SKILL.md`.
2. **Author, without the skill.** Told to write "a walkthrough with diagrams and ELI5-style examples, good enough that after reading it they could contribute". It was free to pick the format, and it was not allowed to read any skill.
3. **Examiner.** Read the code, never saw either walkthrough, and wrote 8 questions with an answer key (`exam.json`) plus a small contribution task with a hidden test (`hidden_test_task.py`, `hidden_task.test.js`). It confirmed the hidden test fails on the unmodified code and passes with its own reference patch (`reference.patch`).
4. **Reader.** One per walkthrough. It got the walkthrough under a neutral name (`A`/`B`, mapping in `blind_map.json`) and answered the 8 questions **closed book**, with no repo and no web. Then it was given a clean checkout and asked to do the contribution task.
5. **Grader.** Scored all quiz answers against the answer key, per key point, without knowing which walkthrough each reader had.

The hidden tests and the projects' full test suites were run on each reader's patch afterwards, outside the readers' control.

## Results

| | click, with skill | click, without | commander, with skill | commander, without |
|---|---|---|---|---|
| Closed-book quiz score | **0.88** | 0.83 | **0.86** | 0.77 |
| Quiz answers the reader marked as guesses | 1 | 3 | 5 | 3 |
| Contribution: hidden test | pass (11/11) | pass (11/11) | pass (8/8) | pass (8/8) |
| Contribution: full suite after the patch | pass | pass | pass | pass |
| Reader tool calls for the task | 8 | 5 | 13 | ~15 |
| Code lines in the doc that exist verbatim in the repo | **100%** (96) | 44% (16) | **96%** (117) | 21% (78) |
| `path:line` citations / valid | **53 / 53** | 0 | **60 / 60** | 0 |
| Mermaid diagrams that render | 4 / 4 | none (ASCII art) | 5 / 5 | 8 / 8 |
| Author cost (tokens / tool calls / minutes) | 130k / 32 / 5.4 | 93k / 13 / 2.5 | 135k / 29 / 5.8 | 142k / 31 / 5.6 |

Code and citation figures come from `score.py`, which reads any HTML or Markdown file the same way and does not depend on the skill's markup. Rendering was checked in headless Chrome against Mermaid 11.4.1.

## What this does and does not show

- **Readers understood more from the skill's pages**, by 5 and 9 points on the quiz. With one reader per cell, read that as a direction, not an effect size.
- **Every reader finished the task.** These are strong models and the repos are small and well tested, so the task did not separate the arms. A harder task or a weaker reader would be a better test of "can contribute".
- **The skill's pages can be checked; the others can't.** Almost all of their code is quoted from the pinned commit and every claim links to a line. The baselines' code blocks are mostly runnable usage examples they wrote themselves (often correct, since they ran them), but a reader cannot trace them to the source.
- **The skill costs more to run on a small PR**: roughly 1.4× the tokens and 2× the time on click. On the larger target, cost was even.
- **The skill's commander page left gaps** on parser edge cases (`-abcx` splitting, optional values, negative numbers). Its reader had to guess there. Since this run, `references/sections.md` asks for a "rules the code enforces" table on library and whole-repo targets. That change has **not** been re-measured.
- After the run, the participant labels in the commander example were un-quoted. That fixed a display bug in the skill's own Mermaid guidance; no content changed.

## Reproduce

```bash
python3 evals/score.py <walkthrough.html|md> --repo <clone> --head <sha> [--base <sha>]
```

The exams, hidden tests, reference patches, all four walkthroughs, the readers' answers and patches, and the grades are in `run-2026-11-06/`.
