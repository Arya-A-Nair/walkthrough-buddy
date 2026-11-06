# Section contract

Sections in this order. **Required** ids are enforced by `check.py`. Optional ones go in when the target has the thing they describe; drop them otherwise. In Markdown output, put `<a id="..."></a>` on the line above each `##` heading, and put `<!-- walkthrough:head SHA -->` / `<!-- walkthrough:base SHA -->` at the top.

## 1. `big-picture` (required)

- The answer sentence again, then 2–4 sentences: who uses this, when, and what would break without it.
- **ELI5 callout** (`.callout.eli5`): one everyday analogy that maps beat for beat onto the main path. Name the mapping ("the waiter is the router, the kitchen ticket is the job"). End with *Where the analogy breaks:* one line. If no analogy fits beat for beat, use a tiny concrete scenario with names and numbers instead. A loose analogy teaches the wrong model.
- **Context diagram** (`flowchart LR`): the target and its direct neighbours: who calls it, what it calls, where data lives. 5–10 nodes. For change targets, mark nodes with `class X new` / `class Y changed`.

## 2. `before-after` (required when the target is a change)

- What a user or caller saw before, what they see now, and why it had to change. Quote the PR description, issue or commit message, and cite it.
- Two small diagrams, or one diagram with the changed edge highlighted. Prefer `sequenceDiagram` when the change is about order, and `flowchart` when it is about who talks to whom.
- If the change was reworked after review, say what reviewers asked for and what changed because of it. This is often the most useful context a newcomer can get.

## 3. `glossary` (required)

5–12 terms the reader will meet in the code, as `<dl class="glossary">`. Mix domain words ("tenant", "settlement") with code names (`RetryPolicy`). Each entry is one plain sentence plus where it lives: `path/to/file.ts:40`. Define a term the first time it appears; never use one before the glossary.

## 4. `main-flow` (recommended)

- `sequenceDiagram` of the main path, with participants named after real modules. Use `autonumber` so the steps match the trace below.
- **Worked example** (`<ol class="trace">`): follow one real input through every step: "`POST /invoices {amount: 1200}` arrives at `routes/invoices.ts:22` → …". Take the values from a test or fixture and cite it. Concrete values are what make the flow stick.
- Where it can fail: the 1–3 failure points a contributor will hit, each with the line that handles it.
- **Rules the code enforces** (libraries, parsers, whole-repo targets): a table `input → what happens → where (path:line) → test that pins it` for the 4–8 edge cases a contributor will trip on: ordering, precedence, defaults, odd inputs. Run each one or take it from a test; these are the questions newcomers get wrong.

## 5. `code-tour` (required)

Stops in reading order. Each stop follows the same four beats:

1. **What it does:** one sentence, plain words.
2. **ELI5:** one or two sentences, in a `.callout.eli5` only when the idea is abstract (caching, retries, reconciliation, generics). Skip it for obvious code.
3. **The real code:** an excerpt of 15 lines or fewer, using the markup below. For change targets, prefer a diff excerpt that shows the change itself.
4. **Why it's built this way:** the constraint or trade-off (`.callout.why`), cited when it comes from docs or review. Mark it *(inferred)* when it comes from you.

Close with a reading-order table: `file | what it's for | read it when`.

## 6. `data-model` (optional)

Use when the shape of the data is the point: `erDiagram` for stored data, `stateDiagram-v2` for a lifecycle, `classDiagram` for a type hierarchy. Cite the schema, type or migration that defines it.

## 7. `decisions` (optional)

Alternatives that were rejected and why, limits the code does not handle yet, open review threads. Use a table (`option | why not`) or `.callout.why` blocks. Opinions are fine when labelled as yours.

## 8. `contribute` (required): the part that makes the reader productive

- **Set up and run:** exact commands from the repo, in order, each marked ✅ ran / ⚠️ not run here. Note any prerequisite (runtime version, env file, service that has to be up).
- **Test it:** the exact command that runs the tests for this area, the test file that covers the main path (`path:line`), how to run a single test case, the test helpers or fixtures the existing tests use, and the closest existing test to copy when writing a new one.
- **Conventions that apply here:** formatting, lint, naming, file-size limits, docs that have to be updated alongside code, commit/PR rules. Cite where each rule is written. Do not include generic advice.
- **Recipe:** "To add another `<thing like this>`": a numbered list of the files to touch, in order, each with what goes there. This is the most valuable block on the page; derive it from how the existing instances are wired.
- **Watch out** (`.callout.gotcha`): non-obvious traps: generated files you must not edit, order-dependent registration, caches, flags, env differences.
- **Who knows this:** top recent committers to the area or CODEOWNERS, as names only, no contact details.

## 9. `check-yourself` (required)

- 3–5 questions whose answers are on the page, each in `<details><summary>Q</summary>A + where on the page</details>`. Ask "where would you change…", "what happens if…" and "which test fails if…". Do not ask trivia.
- **Starter task** (`.callout.try`): one realistic, small change, with hints that name the files and the test that proves it is done. It should take 30–90 minutes for the named reader. Use a real gap or `TODO` from the code if one exists; otherwise make a plausible extension.

## 10. `next` (optional)

2–5 links to code or docs worth reading next, each with one line on why.

---

## Excerpt markup

HTML: copy the text from `git show <head-sha>:<path>`, HTML-escape `<`, `>` and `&`, and keep real line numbers:

```html
<figure class="code" data-file="src/retry.ts" data-lines="14-28">
  <figcaption><a href="https://github.com/o/r/blob/<sha>/src/retry.ts#L14-L28">src/retry.ts:14-28</a><span class="tag changed">changed</span></figcaption>
  <pre><code class="language-ts">…</code></pre>
</figure>
```

- `data-ref="base"` for code that only exists before the change.
- Diff excerpts: `data-kind="diff"` and `class="language-diff"`. `+` and context lines are checked at head, `-` lines at base. `data-lines` gives the head range.
- Drop lines with a line containing only `…` or `// ...`; the checker skips those.
- Permalinks: build them from the remote and the pinned **sha**, never a branch name, so they don't rot. Omit the link for remotes that aren't on GitHub, GitLab or Bitbucket.
- Tags: `new`, `changed`, `removed`, `context` (unchanged code shown for understanding).

Markdown: put `<!-- src: path:14-28 -->` (add ` base` for base-side code) on the line directly above the fence. Use a `diff` fence for diffs.

## Mermaid rules (most failures come from these)

- Wrap any label containing spaces with punctuation, parentheses, slashes, `:` or quotes in quotes: `A["parse(config)"]`. Inside a quoted label, use `#quot;` for a double quote.
- Node ids are short and alphanumeric (`api`, `db1`). Never use `end`, `graph` or `subgraph` as an id; `End` is fine.
- 12 nodes or fewer per diagram. If you need more, split into two diagrams.
- Color only to mean something. Add this to every flowchart that marks changes:
  `classDef new fill:#e3f5ea,stroke:#1f8a4c,color:#0f3d22` and `classDef changed fill:#fdf0dc,stroke:#b26b00,color:#4a2c00`
- In `sequenceDiagram`, message text must not contain `;` or `#`. For long names, write `participant A as Long name` without quotes: Mermaid prints quotes literally there. Keep self-messages (`A->>A`) short, because their labels sit on top of the lifeline.
- Every diagram gets a `<figcaption>` that tells the reader what to notice, not what the diagram is.

## Writing rules

- Plain words, short sentences, active voice. Explain what something *does* before naming it.
- Names in `code`, numbers as digits, one idea per paragraph.
- Every factual claim about the code is either visible in an excerpt or carries a `path:line`.
- Analogies belong in ELI5 callouts and bodies, never in headings or diagram labels.
- No filler or hype: no "robust", "seamless", "leverage", "powerful", "comprehensive", "delve". If a sentence would fit any codebase, delete it.
- Label uncertainty: *(inferred)* for your reading, *not run here* for commands you did not execute.
