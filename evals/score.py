#!/usr/bin/env python3
"""Score any walkthrough (HTML or Markdown) the same way, whatever tool wrote it.

  python3 score.py <doc> --repo DIR --head SHA [--base SHA]

grounded_code   share of code lines in the doc that exist verbatim in the repo (head or base)
valid_citations share of `path:line` references that point at a real file and line
diagrams        how many Mermaid diagrams render without error (headless browser)
"""
import html, json, os, re, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "walkthrough-buddy", "scripts"))
try:
    import check  # reuse the browser renderer
except ImportError:
    check = None

SHELL = {"bash", "sh", "shell", "console", "zsh", "text", "txt", "mermaid", "powershell", ""}
ELISION = re.compile(r"^\s*(//|#|--|/\*|\*)?\s*(\.\.\.|…)\s*(\*/)?\s*$")


def git(repo, *a):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def code_blocks(doc, is_md):
    if is_md:
        for lang, body in re.findall(r"```([\w+-]*)[^\n]*\n(.*?)\n```", doc, re.S):
            if lang.lower() not in SHELL:
                yield lang.lower(), body
    else:
        for _pre, attrs, body in re.findall(r"<pre\b([^>]*)>\s*<code\b([^>]*)>(.*?)</code>\s*</pre>", doc, re.S):
            lang = (re.search(r"language-([\w+-]+)", attrs) or re.search(r"lang-([\w+-]+)", attrs))
            lang = lang.group(1).lower() if lang else ""
            if lang not in SHELL:
                yield lang, html.unescape(re.sub(r"<[^>]+>", "", body))


def main():
    a = sys.argv[1:]
    doc_path = a[0]
    repo = a[a.index("--repo") + 1]
    head = a[a.index("--head") + 1]
    base = a[a.index("--base") + 1] if "--base" in a else None
    doc = open(doc_path, encoding="utf-8").read()
    is_md = doc_path.endswith(".md")

    total = grounded = 0
    misses = []
    for lang, body in code_blocks(doc, is_md):
        for line in body.splitlines():
            s = line.rstrip()
            if lang == "diff" and s[:1] in "+- ":
                s = s[1:]
            core = s.strip()
            if len(core) < 8 or ELISION.match(core) or core.startswith((">>>", "$ ", "@@", "+++", "---")):
                continue
            total += 1
            refs = [head] + ([base] if base else [])
            if any(subprocess.run(["git", "-C", repo, "grep", "-q", "-F", "-e", core, r],
                                  capture_output=True).returncode == 0 for r in refs):
                grounded += 1
            else:
                misses.append(core[:100])

    files = (git(repo, "ls-tree", "-r", "--name-only", head) or "").splitlines()
    by_name = {}
    for f in files:
        by_name.setdefault(os.path.basename(f), []).append(f)
    text = re.sub(r"<(script|style)\b.*?</\1>", "", doc, flags=re.S)
    cites = set(re.findall(r"(?<![\w/.])((?:[\w.-]+/)*[\w.-]+\.(?:py|js|ts|tsx|jsx|cjs|mjs|go|rs|rb|java|md|toml|json|cfg|yml|yaml)):L?(\d+)", text))
    valid = 0
    bad = []
    for p, ln in sorted(cites):
        cands = [p] if p in files else [f for f in files if f.endswith("/" + p)] or by_name.get(p, [])
        ok = False
        for c in cands[:3]:
            src = git(repo, "show", f"{head}:{c}")
            if src is not None and int(ln) <= len(src.splitlines()):
                ok = True
                break
        valid += ok
        if not ok:
            bad.append(f"{p}:{ln}")

    blocks = (re.findall(r"```mermaid\n(.*?)\n```", doc, re.S) if is_md else
              [html.unescape(b) for b in re.findall(r'<pre\b[^>]*class="[^"]*\bmermaid\b[^"]*"[^>]*>(.*?)</pre>', doc, re.S)]
              + [html.unescape(b) for b in re.findall(r'<div\b[^>]*class="[^"]*\bmermaid\b[^"]*"[^>]*>(.*?)</div>', doc, re.S)])
    blocks = [b.strip() for b in blocks]
    errs = check.render(blocks) if (check and blocks) else None

    words = len(re.sub(r"<[^>]+>", " ", text).split())
    out = {
        "doc": doc_path,
        "words": words,
        "code_lines": total,
        "grounded_code": round(grounded / total, 3) if total else None,
        "ungrounded_examples": misses[:8],
        "citations": len(cites),
        "valid_citations": round(valid / len(cites), 3) if cites else None,
        "bad_citations": bad[:8],
        "diagrams": len(blocks),
        "diagrams_render_ok": None if errs is None else len(blocks) - len(errs),
        "diagram_errors": errs,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
