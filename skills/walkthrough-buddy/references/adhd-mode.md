# ADHD mode

Use this mode when the user asks for it ("ADHD mode", "I have ADHD", "make it easier to read", "I lose focus on long docs"), or when the `i-have-adhd` skill is active in the session. It changes how the page is shaped, never what it covers. Every required section, excerpt and check from `sections.md` still applies.

Five facts about reading with ADHD drive every rule below:

1. Working memory is small. Whatever is off screen is gone.
2. Starting is the hardest step.
3. Vague time feels endless, so "a few minutes" reads the same as "an hour".
4. Visible progress keeps the reader going. Buried wins don't register.
5. Tangents derail. One open loop at a time.

## Switch it on

- HTML: `<body class="adhd">` and `<meta name="walkthrough:mode" content="adhd">`. The template's script then adds a reading-progress bar, a "Part N of M · ~X min" label on every section, a "Done" checkbox per section (remembered in this browser), and a live "~X min left" counter.
- Markdown: put `<!-- walkthrough:mode adhd -->` at the top. Use `- [ ] Done` under each section instead of the checkbox.

## The page, rule by rule

1. **Start-here box first** (`<div class="start-here">`, before the first section). It holds exactly three lines:
   - **Do this first:** the smallest thing that shows the code working: a single test, a command, or a click. Take it from anywhere on the page, and mark it ✅ only if you ran it. If it needs setup, give the setup first with its time ("Set up, about 3 min: …, then run …"). Never pretend setup is already done.
   - **What this is:** the answer sentence.
   - **This page:** "N parts, ~M min. You can stop after any part."

2. **Every section is a chunk.** Give each `<section>` a `data-minutes="3"` attribute: an honest reading time, about 200 words per minute plus 1 minute per diagram. The section opens with `<p class="tldr">`, the whole section in one line, and closes with `<p class="won">You can now: …</p>`, the concrete thing the reader can do or answer after this part.

3. **Small working set.**
   - Paragraphs: 3 sentences at most.
   - Bullet lists: 5 items at most. Group or rank anything longer, and move the rest into a `<details>`.
   - Numbered step lists: 7 steps at most. Never hide a step in prose to stay under the cap; split the task into two stages instead.
   - Code excerpts: 10 lines at most, not counting `…` lines, and with at most one `…` per excerpt. This replaces the 15-line limit in `sections.md`. Use two stops instead of one long one.
   - Diagrams: 8 nodes at most, and one diagram per section. An optional `data-model` section may hold its own diagram.
   - Glossary: the 5–7 terms the reader truly needs. The rest go in a collapsed "More terms" `<details>`.
   - Bold the single most important phrase in each paragraph, and only that one.

4. **No back-references in the reading flow.** Never write "as mentioned above", "recall that", or "see section 2". Restate the fact in half a line where it is needed. Hidden answers in "Check yourself" are the one exception: they may point to "Part 5, stop 1", because the reader opens them to look back on purpose. When a glossary term appears in a section for the first time, give it a short gloss in brackets: `Context` (the object that carries one run's state).

5. **Tangents are collapsed.** Anything the reader can skip and still contribute goes in `<details class="extra"><summary>Extra, skip if busy</summary>…</details>`. That covers history, alternatives, edge cases outside the main path, and long review threads. In the contribute section, keep the top 3 gotchas visible and collapse the rest.

6. **Numbered, one-action steps.** The setup, the recipe and the starter task are numbered lists where each step does one thing. No step says "and then" twice. Each one carries a time estimate in concrete units: "2 min", "about 15 min if the venv exists".

7. **Starter task is sized and staged.** State the total ("about 40 min"), make step 1 take under 2 minutes ("open `src/x.py` at line 120"), and say what "done" looks like: the exact test command and what it prints.

8. **End with one next step.** The `next` section (required in this mode) opens with "Your next 2-minute step: …", followed by at most 3 links.

9. **Plain, literal, calm.** No idioms ("under the hood", "circle back"). No hype. Errors and gotchas are stated as cause and fix. ELI5 analogies stay; they help more here, not less. But keep each one to 3 sentences, plus the "where it breaks" line.

## Checker

`check.py` reads the mode meta tag and also enforces the following. Fix each one rather than arguing with it:

- the start-here box exists, and the `next` section exists;
- every section has `data-minutes`, a `.tldr` and a `.won`;
- no bullet list in the body has more than 5 items, and no numbered list more than 7 (lists inside `<details>` are exempt);
- no code excerpt is longer than 10 lines, and none has more than one `…`;
- no paragraph has more than 3 sentences (warning only).
