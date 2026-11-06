#!/usr/bin/env bash
# Collect the facts a walkthrough is built on. Read-only: never checks out, stages or fetches.
# Usage: bash gather.sh <target>
#   target: PR number / #N / PR URL, A..B range, commit, branch, or a path in the repo.
set -uo pipefail

target="${1:-}"
[ -n "$target" ] || { echo "usage: gather.sh <pr|range|commit|branch|path>" >&2; exit 2; }
root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not inside a git repo" >&2; exit 2; }
cd "$root"

section() { printf '\n=== %s ===\n' "$1"; }

default_base() {
  for b in origin/HEAD origin/main origin/master origin/dev main master dev; do
    git rev-parse --verify -q "$b^{commit}" >/dev/null && { echo "$b"; return; }
  done
}

mode="" base="" head="" paths=()
pr_num=$(printf '%s' "$target" | sed -nE 's@^#?([0-9]+)$@\1@p; s@.*/pull/([0-9]+).*@\1@p; s@.*/merge_requests/([0-9]+).*@\1@p' | head -1)

if [ -n "$pr_num" ]; then
  mode=pr
  if command -v gh >/dev/null && gh pr view "$pr_num" --json number >/dev/null 2>&1; then
    section "PR"
    gh pr view "$pr_num" --json number,title,url,state,author,baseRefName,headRefName,mergeCommit,body \
      --jq '"#\(.number) \(.title)\nurl: \(.url)\nstate: \(.state)  author: \(.author.login)\nbase: \(.baseRefName)  head: \(.headRefName)  merge: \(.mergeCommit.oid // "-")\n\n\(.body // "")"'
    section "PR review discussion (summaries + inline comments)"
    gh pr view "$pr_num" --json reviews,comments \
      --jq '(.reviews[] | select(.body != "") | "[review \(.state)] \(.author.login): \(.body)"), (.comments[] | "[comment] \(.author.login): \(.body)")' 2>/dev/null | head -c 12000
    repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
    [ -n "$repo" ] && gh api "repos/$repo/pulls/$pr_num/comments" --paginate \
      --jq '.[] | "[inline \(.path):\(.line // .original_line)] \(.user.login): \(.body)"' 2>/dev/null | head -c 12000
    merge=$(gh pr view "$pr_num" --json mergeCommit --jq '.mergeCommit.oid // ""')
    headref=$(gh pr view "$pr_num" --json headRefOid --jq .headRefOid)
    baseref=$(gh pr view "$pr_num" --json baseRefName --jq .baseRefName)
    if [ -n "$merge" ] && git cat-file -e "$merge^{commit}" 2>/dev/null; then
      base="$merge^1" head="$merge"
    elif git cat-file -e "$headref^{commit}" 2>/dev/null; then
      head="$headref"
      base=$(git merge-base "origin/$baseref" "$headref" 2>/dev/null || git merge-base "$baseref" "$headref")
    else
      echo "PR head $headref is not in the local clone. Ask the user before fetching: git fetch origin pull/$pr_num/head"
    fi
  else
    echo "gh unavailable or PR not found. Ask for the branch name or a commit range instead."
  fi
elif [[ "$target" == *..* ]]; then
  mode=range base="${target%%..*}" head="${target##*..}"; head="${head#.}"
  base=$(git merge-base "$base" "${head:-HEAD}") head="${head:-HEAD}"
elif [ -e "$target" ]; then
  mode=area paths=("$target") head=HEAD
elif git rev-parse --verify -q "$target^{commit}" >/dev/null; then
  if git show-ref -q --verify "refs/heads/$target" || git show-ref -q --verify "refs/remotes/$target"; then
    mode=branch head="$target" base=$(git merge-base "$(default_base)" "$target")
  else
    mode=commit head="$target" base="$target^1"
  fi
else
  mode=concept head=HEAD
  section "Concept search (top files mentioning the target)"
  git grep -I -l -i -- "$target" | head -40
fi

section "TARGET"
echo "mode: $mode"
[ -n "$base" ] && echo "base: $(git rev-parse "$base")  ($base)"
echo "head: $(git rev-parse "${head:-HEAD}")  (${head:-HEAD})"
[ "$(git rev-parse "${head:-HEAD}")" != "$(git rev-parse HEAD)" ] && \
  echo "note: the checkout is at $(git rev-parse --short HEAD), not the target. Read code with git show <sha>:<path>; run commands in a worktree at the target sha."
origin=$(git remote get-url origin 2>/dev/null) && echo "remote: $origin"

if [ -n "$base" ] && [ -n "$head" ]; then
  section "COMMITS (oldest first)"
  git log --reverse --format='%h %an %ad %s' --date=short "$base..$head" | head -60
  section "DIFFSTAT"
  git diff --stat=120 "$base" "$head" | tail -80
  section "FILES BY STATUS (A=added M=modified D=deleted R=renamed)"
  git diff --name-status -M "$base" "$head" | head -200
  while IFS= read -r f; do paths+=("$f"); done < <(git diff --name-only "$base" "$head" | head -200)
fi

if [ "$mode" = area ]; then
  section "AREA FILES (largest first, generated/vendor skipped)"
  git ls-files -- "$target" | grep -vE '(^|/)(node_modules|vendor|dist|build|generated|__generated__)/|\.lock$|\.min\.' \
    | while IFS= read -r f; do grep -Iq . "$f" 2>/dev/null && printf '%6s %s\n' "$(wc -l <"$f")" "$f"; done | sort -rn | head -60
  section "RECENT HISTORY OF AREA"
  git log --format='%h %ad %s' --date=short -20 -- "$target"
  section "WHO KNOWS THIS AREA (commits, last year)"
  who=$(git shortlog -sn --since='1 year ago' HEAD -- "$target" | head -8)
  echo "${who:-$(git shortlog -sn HEAD -- "$target" | head -8)}"
fi

section "ONBOARDING DOCS PRESENT"
git ls-files | grep -iE '^(readme|contributing|architecture|hacking|development|agents|claude|context|codeowners)(\.[a-z]+)?$|^(docs?|\.github)/(contributing|development|hacking|architecture|codeowners|pull_request_template)[^/]*$|^\.github/PULL_REQUEST_TEMPLATE/|^\.editorconfig$' | head -20
# docs that sit beside the touched files, walking up to the root
for p in "${paths[@]:-}"; do
  [ -n "$p" ] || continue
  d=$(dirname "$p")
  while [ "$d" != "." ] && [ "$d" != "/" ]; do
    for f in README.md CONTEXT.md AGENTS.md CLAUDE.md; do [ -f "$d/$f" ] && echo "$d/$f"; done
    d=$(dirname "$d")
  done
done | sort -u | head -40

section "BUILD / TEST ENTRY POINTS (nearest manifests to touched files)"
manifests=$(for p in "${paths[@]:-.}"; do
  d=$([ -d "$p" ] && echo "$p" || dirname "$p")
  while :; do
    for m in package.json Cargo.toml go.mod pyproject.toml setup.cfg Makefile justfile Taskfile.yml BUILD.bazel pom.xml build.gradle Gemfile mix.exs composer.json; do
      [ -f "$d/$m" ] && echo "$d/$m"
    done
    [ "$d" = "." ] || [ "$d" = "/" ] && break
    d=$(dirname "$d")
  done
done | sort -u | head -15)
for m in $manifests; do
  echo "--- $m"
  case "$m" in
    *package.json) python3 -c 'import json,sys;[print(f"  npm run {k}: {v}") for k,v in json.load(open(sys.argv[1])).get("scripts",{}).items()]' "$m" | head -25 ;;
    *Makefile|*justfile) grep -E '^[A-Za-z0-9_.-]+:' "$m" | cut -d: -f1 | head -25 | sed 's/^/  target: /' ;;
    *) head -15 "$m" | sed 's/^/  /' ;;
  esac
done
for s in scripts/verify.sh scripts/test.sh scripts/check.sh bin/test; do [ -f "$s" ] && echo "repo script: $s"; done
ls .github/workflows 2>/dev/null | sed 's@^@ci workflow: .github/workflows/@' | head -15

section "TESTS NEAR THE TARGET"
if [ -n "$base" ]; then git diff --name-only "$base" "$head" | grep -iE '(^|/)(tests?|spec|__tests__)/|[._-](test|spec)\.[a-z]+$|(^|/)test_[^/]+$' | sed 's/^/changed test: /'; fi
for p in "${paths[@]:-}"; do
  [ -n "$p" ] || continue
  stem=$(basename "${p%.*}")
  git ls-files | grep -E "(^|/)(test_)?${stem}([._-](test|spec))?\.[a-z]+$|(^|/)tests?/.*${stem}" | grep -v "^$p$"
done | sort -u | head -30
echo "test dirs: $(git ls-files | grep -oE '^([^/]+/)*(tests?|spec|__tests__)/' | sort | uniq -c | sort -rn | head -5 | awk '{print $2" ("$1" files)"}' | tr '\n' ' ')"
