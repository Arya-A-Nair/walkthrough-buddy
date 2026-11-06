#!/usr/bin/env python3
"""Print a ready-to-paste code excerpt, copied from git, escaped, with a permalink.

  python3 excerpt.py <path> <A-B[,C-D...]> --sha SHA [--repo DIR] [--tag new|changed|removed|context]
                     [--lang ts] [--base SHA] [--md]

  <A-B,...>   line ranges at SHA; a gap between ranges becomes a `…` line.
  --base SHA  print the diff of this file between BASE and SHA, limited to hunks touching A-B.
  --old       the excerpt is pre-change code (SHA is the base commit): marks it data-ref="base".
  --md        Markdown (src comment + fence) instead of HTML.
"""
import html, re, subprocess, sys

EXT = {"py": "python", "js": "javascript", "cjs": "javascript", "mjs": "javascript", "ts": "typescript",
       "tsx": "tsx", "jsx": "jsx", "go": "go", "rs": "rust", "rb": "ruby", "java": "java", "kt": "kotlin",
       "cs": "csharp", "php": "php", "swift": "swift", "c": "c", "h": "c", "cpp": "cpp", "sh": "bash",
       "toml": "toml", "yml": "yaml", "yaml": "yaml", "json": "json", "md": "markdown", "sql": "sql"}


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=True).stdout


def permalink(repo, sha, path, a, b):
    try:
        url = git(repo, "remote", "get-url", "origin").strip()
    except subprocess.CalledProcessError:
        return None
    m = re.match(r"(?:https?://|git@|ssh://git@)([^/:]+)[/:](.+?)(?:\.git)?/?$", url)
    if not m:
        return None
    host, slug = m.groups()
    if "github" in host:
        return f"https://{host}/{slug}/blob/{sha}/{path}#L{a}-L{b}"
    if "gitlab" in host:
        return f"https://{host}/{slug}/-/blob/{sha}/{path}#L{a}-{b}"
    if "bitbucket" in host:
        return f"https://{host}/{slug}/src/{sha}/{path}#lines-{a}:{b}"
    return None


def main():
    a = sys.argv[1:]
    if len(a) < 2 or "--sha" not in a:
        sys.exit(__doc__)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    path, spec = a[0], a[1]
    repo, sha, base = opt("--repo", "."), opt("--sha"), opt("--base")
    sha = git(repo, "rev-parse", sha).strip()
    lang = opt("--lang", EXT.get(path.rsplit(".", 1)[-1], ""))
    tag = opt("--tag")
    ranges = [tuple(int(x) for x in r.split("-")) if "-" in r else (int(r), int(r)) for r in spec.split(",")]
    lo, hi = ranges[0][0], ranges[-1][1]

    if base:
        base = git(repo, "rev-parse", base).strip()
        diff = git(repo, "diff", "-U2", base, sha, "--", path).splitlines()
        hunks, cur = [], None
        for line in diff:
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                start, n = int(m.group(1)), int(m.group(2) or 1)
                cur = [] if start <= hi and start + n - 1 >= lo else None
                if cur is not None:
                    hunks.append(cur)
            elif cur is not None:
                cur.append(line)
        body = "\n…\n".join("\n".join(h) for h in hunks)
        if not body:
            sys.exit(f"no hunks of {path} touch lines {lo}-{hi}")
        lang, kind = "diff", ' data-kind="diff"'
    else:
        src = git(repo, "show", f"{sha}:{path}").splitlines()
        parts = ["\n".join(src[x - 1:y]) for x, y in ranges]
        body = "\n…\n".join(parts)
        kind = ' data-ref="base"' if "--old" in a else ""

    label = f"{path}:{lo}-{hi}"
    if "--md" in a:
        print(f"<!-- src: {label}{' base' if '--old' in a else ''} -->\n```{lang}\n{body}\n```")
        return
    link = permalink(repo, sha, path, lo, hi)
    cap = f'<a href="{link}">{label}</a>' if link else label
    tag_html = f'<span class="tag {tag}">{tag}</span>' if tag else ""
    print(f'<figure class="code" data-file="{path}" data-lines="{lo}-{hi}"{kind}>\n'
          f"  <figcaption>{cap}{tag_html}</figcaption>\n"
          f'  <pre><code class="language-{lang}">{html.escape(body, quote=False)}</code></pre>\n</figure>')


if __name__ == "__main__":
    main()
