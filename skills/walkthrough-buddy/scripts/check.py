#!/usr/bin/env python3
"""Verify a walkthrough before handing it over.

  python3 check.py <walkthrough.html|.md> [--repo DIR] [--no-render] [--stamp]

--stamp  on a pass, write the results into the page (it powers the page's trust box).

Checks:
  1. No unfilled {{placeholders}}.
  2. Every code excerpt matches the real file at the pinned commit (HTML: <figure class="code"
     data-file data-lines [data-ref=base] [data-kind=diff]>; Markdown: a `<!-- src: path:A-B [base] -->`
     line right above the fence). '+'/' ' diff lines are checked at head, '-' lines at base.
  3. Every `path:line` citation names a real file and an existing line.
  4. Required sections exist (contributor kit, self-check, ...).
  5. Every Mermaid diagram parses and renders, in a headless Chrome/Chromium/Edge/Brave.
Exit 0 = all pass, 1 = failures, 3 = passed but rendering could not be verified.
"""
import html, json, os, re, shutil, subprocess, sys, tempfile

REQUIRED = ["big-picture", "glossary", "code-tour", "contribute", "check-yourself"]
CHANGE_REQUIRED = ["before-after"]
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"
ELISION = re.compile(r"^\s*(//|#|--|/\*|\*)?\s*(\.\.\.|…)\s*(\*/)?\s*$")

fails, warns = [], []


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def file_at(repo, ref, path, cache={}):
    key = (ref, path)
    if key not in cache:
        cache[key] = git(repo, "show", f"{ref}:{path}") if ref else None
        if cache[key] is None and not ref and os.path.isfile(os.path.join(repo, path)):
            cache[key] = open(os.path.join(repo, path), encoding="utf-8", errors="replace").read()
    return cache[key]


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def in_order(needles, hay):
    """Every needle line appears in hay, in order (elision lines skipped)."""
    i = 0
    for n in needles:
        while i < len(hay) and hay[i] != n:
            i += 1
        if i == len(hay):
            return n
        i += 1
    return None


def check_excerpt(repo, label, path, a, b, text, ref, base, diff):
    lines = [l for l in text.splitlines() if l.strip() and not ELISION.match(l)]
    groups = {}
    if diff:
        for l in lines:
            if l.startswith(("@@", "+++", "---", "diff ", "index ")):
                continue
            sign, body = (l[0], l[1:]) if l[:1] in "+- " else (" ", l)
            if norm(body):
                groups.setdefault("base" if sign == "-" else "head", []).append(norm(body))
        if not base:
            groups.pop("base", None)
    else:
        groups["base" if ref == "base" else "head"] = [norm(l) for l in lines]
    for side, want in groups.items():
        sha = base if side == "base" else HEAD
        src = file_at(repo, sha, path)
        if src is None:
            fails.append(f"{label}: {path} not found at {side} ({sha or 'working tree'})")
            continue
        all_lines = src.splitlines()
        # diffs move code, so they are matched against the whole file; plain excerpts against their range
        lo, hi = (max(0, a - 1 - 3), min(len(all_lines), b + 3)) if a and not diff else (0, len(all_lines))
        window = [norm(l) for l in all_lines[lo:hi]]
        missing = in_order(want, window)
        if missing is not None:
            whole = in_order(want, [norm(l) for l in all_lines])
            where = "exists elsewhere in the file: fix data-lines" if whole is None else "not in the file"
            fails.append(f"{label}: {path}:{a}-{b} @{side}: line {missing[:80]!r} {where}")


def excerpts_html(doc):
    for m in re.finditer(r'<figure\b[^>]*class="[^"]*\bcode\b[^"]*"[^>]*>(.*?)</figure>', doc, re.S):
        tag = m.group(0)[: m.group(0).index(">") + 1]
        attr = dict(re.findall(r'(data-[\w-]+)="([^"]*)"', tag))
        code = re.search(r"<code\b[^>]*>(.*?)</code>", m.group(1), re.S)
        if "data-file" not in attr or not code:
            warns.append(f"code figure without data-file or <code>: {tag[:90]}")
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", code.group(1)))
        diff = attr.get("data-kind") == "diff" or "language-diff" in code.group(0)[:120]
        yield attr["data-file"], attr.get("data-lines", ""), attr.get("data-ref", "head"), diff, text


def excerpts_md(doc):
    for m in re.finditer(r"<!--\s*src:\s*([^\s:]+)(?::(\d+(?:-\d+)?))?\s*(base)?\s*-->\s*\n```(\w*)\n(.*?)\n```", doc, re.S):
        yield m.group(1), m.group(2) or "", m.group(3) or "head", m.group(4) == "diff", m.group(5)


def mermaid_blocks(doc, is_md):
    pat = r"```mermaid\n(.*?)\n```" if is_md else r'<pre\b[^>]*class="[^"]*\bmermaid\b[^"]*"[^>]*>(.*?)</pre>'
    return [html.unescape(b).strip() for b in re.findall(pat, doc, re.S)]


def find_browser():
    env = os.environ.get("CHROME") or os.environ.get("CHROME_PATH")
    if env:
        return env
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser", "chrome"]:
        if shutil.which(name):
            return shutil.which(name)
    for p in [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]:
        if os.path.exists(p):
            return p
    return None


def render(blocks):
    """Parse + render each block in a real browser. Returns list of (index, error) or None if unverifiable."""
    browser = find_browser()
    if not browser:
        return None
    page = """<!doctype html><meta charset=utf-8><body><pre id=out>pending</pre>
<script type=module>
import mermaid from '%s';
mermaid.initialize({startOnLoad:false, securityLevel:'strict'});
const blocks = %s, res = [];
for (let i = 0; i < blocks.length; i++) {
  try { await mermaid.parse(blocks[i]); const {svg} = await mermaid.render('m'+i, blocks[i]);
        if (!svg.includes('<svg') || /Syntax error/i.test(svg)) throw new Error('rendered an error diagram'); }
  catch (e) { res.push([i, String(e && e.message || e).slice(0, 300)]); }
}
document.getElementById('out').textContent = 'RESULT' + JSON.stringify(res);
</script>""" % (MERMAID, json.dumps(blocks))
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "m.html")
        open(f, "w").write(page)
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               f"--user-data-dir={d}/profile", "--virtual-time-budget=30000", "--dump-dom", "file://" + f]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=90).stdout
        except subprocess.TimeoutExpired:
            return None
    m = re.search(r"RESULT(\[.*?\])</pre>", html.unescape(out), re.S)
    return json.loads(m.group(1)) if m else None


def adhd_checks(doc, is_md):
    """Shape rules from references/adhd-mode.md. Only runs when the page declares ADHD mode."""
    body = re.sub(r"<details\b.*?</details>", "", doc, flags=re.S)
    if is_md:
        if "Do this first" not in doc:
            fails.append("adhd: no start-here block ('**Do this first:**' line at the top)")
        run = 0
        for line in body.splitlines() + [""]:
            run = run + 1 if re.match(r"\s{0,1}([-*]|\d+\.)\s", line) else 0
            if run == (8 if re.match(r"\s{0,1}\d+\.", line) else 6):
                fails.append(f"adhd: a list has more than 5 items (near {line.strip()[:50]!r})")
        for lang, code in re.findall(r"```(\w*)\n(.*?)\n```", body, re.S):
            if lang != "mermaid" and len([l for l in code.splitlines() if l.strip() and not ELISION.match(l)]) > 10:
                fails.append(f"adhd: a {lang or 'code'} block is longer than 10 lines")
        return
    main = (re.search(r"<main\b.*?</main>", body, re.S) or re.search(r".*", body, re.S)).group(0)
    if 'class="start-here"' not in doc:
        fails.append('adhd: no <div class="start-here"> before the first section')
    if 'class="adhd"' not in doc and "class='adhd'" not in doc:
        fails.append('adhd: <body> is missing class="adhd", so progress, part labels and checkboxes will not appear')
    for tag, sid, inner in re.findall(r'(<section\b[^>]*\bid="([^"]+)"[^>]*>)(.*?)</section>', main, re.S):
        miss = [w for w, ok in (("data-minutes", "data-minutes=" in tag), ("tldr", 'class="tldr"' in inner),
                                 ("won", 'class="won"' in inner)) if not ok]
        if miss:
            fails.append(f"adhd: section '{sid}' is missing {', '.join(miss)}")
    for kind, inner in re.findall(r"<(ul|ol)\b[^>]*>((?:(?!<(?:ul|ol)\b).)*?)</\1>", main, re.S):
        n = len(re.findall(r"<li\b", inner))
        if n > (7 if kind == "ol" else 5):
            first = re.sub(r"<[^>]+>", "", inner).strip()[:50]
            fails.append(f"adhd: a {'numbered' if kind == 'ol' else 'bullet'} list has {n} items (max {7 if kind == 'ol' else 5}): {first!r}")
    for m in re.finditer(r'<figure\b[^>]*class="[^"]*\bcode\b[^"]*"[^>]*\bdata-file="([^"]+)".*?<code\b[^>]*>(.*?)</code>', main, re.S):
        lines = [l for l in html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).splitlines() if l.strip()]
        n, gaps = len([l for l in lines if not ELISION.match(l)]), len([l for l in lines if ELISION.match(l)])
        if n > 10:
            fails.append(f"adhd: excerpt of {m.group(1)} has {n} lines (max 10; split it into two stops)")
        if gaps > 1:
            fails.append(f"adhd: excerpt of {m.group(1)} skips code {gaps} times (max one '…'; split it into two stops)")
    for para in re.findall(r"<p\b(?![^>]*class=\"(?:tldr|won)\")[^>]*>(.*?)</p>", main, re.S):
        text = re.sub(r"<code\b.*?</code>", "x", para, flags=re.S)
        text = html.unescape(re.sub(r"<[^>]+>", "", text))
        n = len(re.findall(r"[.!?](?:\s+|$)(?=[A-Z(\"]|$)", text.strip()))
        if n > 3:
            warns.append(f"adhd: paragraph with {n} sentences (max 3): {text.strip()[:60]!r}")


def stamp(path, doc, is_md, facts):
    """Write the checker's own numbers into the page, so the trust box is not the author's claim."""
    payload = json.dumps(facts, separators=(",", ":"))
    if is_md:
        line = (f"> **Checked against `{facts['commit']}` on {facts['date']}:** {facts['excerpts']} excerpts match the source, "
                f"{facts['links']} links point at real lines, {facts['diagrams']} diagrams "
                f"{'render' if facts['rendered'] else '(render not verified)'}. {facts['ran']} commands ran, "
                f"{facts['not_run']} not run, {facts['inferred']} claims marked inferred. <!-- walkthrough:checked {payload} -->")
        doc = re.sub(r"^> \*\*Checked against.*<!-- walkthrough:checked .*?-->$", lambda m: line, doc, flags=re.M) \
            if "<!-- walkthrough:checked " in doc else doc.replace("<!-- trust -->", "<!-- trust -->\n" + line, 1)
    else:
        meta = f"<meta name=\"walkthrough:checked\" content='{html.escape(payload, quote=False)}'>"
        pat = r"<meta name=\"walkthrough:checked\"[^>]*>"
        doc = re.sub(pat, lambda m: meta, doc) if re.search(pat, doc) else doc.replace("</head>", meta + "\n</head>", 1)
    open(path, "w", encoding="utf-8").write(doc)
    print("stamped:", payload)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    repo = args[args.index("--repo") + 1] if "--repo" in args else (git(os.path.dirname(os.path.abspath(path)), "rev-parse", "--show-toplevel") or os.getcwd()).strip()
    repo = (git(repo, "rev-parse", "--show-toplevel") or repo).strip()
    doc = open(path, encoding="utf-8").read()
    is_md = path.endswith((".md", ".markdown"))

    global HEAD
    def meta(k):
        m = (re.search(rf'<meta name="walkthrough:{k}" content="([^"]*)"', doc) or
             re.search(rf"<!--\s*walkthrough:{k}\s+(\S*)\s*-->", doc))
        return (m.group(1) if m else "") or None
    HEAD, base = meta("head"), meta("base")
    if HEAD and git(repo, "cat-file", "-e", HEAD + "^{commit}") is None:
        fails.append(f"walkthrough:head {HEAD} is not a commit in {repo}")
    if not HEAD:
        warns.append("no walkthrough:head pinned; excerpts checked against the working tree")

    for ph in sorted(set(re.findall(r"\{\{[^}]{1,80}\}\}", doc)))[:10]:
        fails.append(f"unfilled placeholder {ph}")

    n = 0
    for i, (f, lines, ref, diff, text) in enumerate((excerpts_md if is_md else excerpts_html)(doc)):
        n += 1
        a, b = (lines.split("-") + [lines])[:2] if lines else ("0", "0")
        a, b = int(a or 0), int(b or a or 0)
        check_excerpt(repo, f"excerpt {i + 1}", f, a, b, text, ref, base, diff)
    if n == 0:
        warns.append("no verified code excerpts: a reader cannot learn the code from prose alone")

    text_only = re.sub(r"<(script|style)\b.*?</\1>", "", doc, flags=re.S)
    tracked = (git(repo, "ls-tree", "-r", "--name-only", HEAD or "HEAD") or "").splitlines()
    links = 0
    for p, ln, end in sorted(set(re.findall(r"(?<![\w/.])((?:[\w.-]+/)*\w[\w.-]*\.[a-z]{1,5}):L?(\d+)(?:-L?(\d+))?\b", text_only))):
        ln = max(int(ln), int(end or 0))
        if "/" not in p and p not in tracked:
            hits = [f for f in tracked if f.rsplit("/", 1)[-1] == p]
            if len(hits) != 1:
                (warns if hits else fails).append(f"citation {p}:{ln}: " + (
                    f"ambiguous, {len(hits)} files share that name; use the full path" if hits else "no such file"))
                continue
            p = hits[0]
        src = file_at(repo, HEAD, p) or (file_at(repo, base, p) if base else None)
        if src is None:
            fails.append(f"citation {p}:{ln}: no such file at head{' or base' if base else ''}")
        elif ln > len(src.splitlines()):
            fails.append(f"citation {p}:{ln}: file has only {len(src.splitlines())} lines")
        else:
            links += 1

    ids = set(re.findall(r'<(?:section|a)\b[^>]*\bid="([^"]+)"', doc))
    adhd = bool(re.search(r'<meta name="walkthrough:mode" content="adhd"|<!--\s*walkthrough:mode\s+adhd\s*-->', doc))
    need = REQUIRED + (CHANGE_REQUIRED if base else []) + (["next"] if adhd else [])
    if adhd:
        adhd_checks(doc, is_md)
    for r in need:
        if r not in ids:
            fails.append(f"missing required section id '{r}' (see references/sections.md)")
    for cls, md_phrase, what in (("not-covered", "Not covered", "a 'Not covered here' list in the trust box"),
                                 ("read-list", "Read these yourself", "a 'Read these yourself' list in the code tour")):
        if not (md_phrase in doc if is_md else re.search(rf'class="[^"]*\b{cls}\b', doc)):
            fails.append(f"missing {what} (see references/sections.md)")

    blocks = mermaid_blocks(doc, is_md)
    if not blocks:
        fails.append("no Mermaid diagrams")
    unverified = False
    if blocks and "--no-render" not in args:
        res = render(blocks)
        if res is None:
            unverified = True
            warns.append("could not render diagrams (no headless Chromium-family browser, or no network for the Mermaid CDN): set CHROME=/path/to/browser")
        for i, err in res or []:
            first = blocks[i].splitlines()[0] if blocks[i] else ""
            fails.append(f"diagram {i + 1} ({first!r}): {err}")
    elif "--no-render" in args:
        unverified = True

    for w in warns:
        print("WARN ", w)
    for f in fails:
        print("FAIL ", f)
    print(f"\n{n} excerpts, {len(blocks)} diagrams, {len(fails)} failures, {len(warns)} warnings"
          + ("" if fails or unverified else " — ALL CHECKS PASSED") + (" — RENDER UNVERIFIED" if unverified and not fails else ""))
    if "--stamp" in args and not fails:
        stamp(path, doc, is_md, {
            "commit": (HEAD or "working tree")[:10], "date": __import__("datetime").date.today().isoformat(),
            "excerpts": n, "links": links, "diagrams": len(blocks), "rendered": not unverified,
            "ran": doc.count("✅"), "not_run": doc.count("⚠️"), "inferred": len(re.findall(r"\(inferred\b", doc)),
        })
    sys.exit(1 if fails else 3 if unverified else 0)


HEAD = None
if __name__ == "__main__":
    main()
