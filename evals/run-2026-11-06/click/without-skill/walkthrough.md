# Walkthrough: click PR #3877, `Parameter.spec` and the deprecation of `human_readable_name`

- Merge commit: `2247b35ea1c47c727d7a06e51fa280e12a863ff6` (first parent `06b2a67`, PR commit `9f0bcdf`)
- Files: `src/click/core.py` (+121/-12), `tests/test_options.py`, `tests/test_arguments.py`, `tests/test_deprecations.py`, `docs/parameters.md`, `docs/upgrade-guides.md`, `CHANGES.md`
- Who this is for: you are new to click and want to make your first change around how parameters are named, shown in help, and named in error messages.

Every output block marked **(ran)** was produced by running the code against a copy of the merge commit. See "How this was checked" at the end.

---

## 1. The one-minute version

A click parameter (an option or an argument) has several names, and before this PR click used the wrong one when it talked to the user.

```python
@click.option("--my-option", deprecated=True)
```

| | before #3877 | after #3877 |
|---|---|---|
| Warning printed to the user | `The option 'my_option' is deprecated.` | `The option '--my-option' is deprecated.` |

`my_option` is the Python variable name. Nobody types that into a terminal. `--my-option` is what the user typed. The PR:

1. Adds `Parameter.spec`, which returns "how the user spells this parameter on the command line".
2. Uses `spec` everywhere click used to use `human_readable_name`.
3. Deprecates `human_readable_name`, which returned `name` for options. It now warns and returns `spec`. A subclass that *overrides* it gets a warning when the class is defined, because click no longer reads it.
4. Adds `get_help_spec()` to the base `Parameter` class (it already existed on `Option` since 8.5.1) and gives `Argument` its own version.

---

## 2. ELI5: one thing, three names

Think of a kid at school.

- Their **birth certificate** says `Margaret Elizabeth Smith`. That is what the parents *wrote down*: the **decls**.
- The teacher's **register** lists them as `smith_margaret`. Only the school's computer uses that: the **name**.
- Everyone in the playground **shouts** `Maggie!`. That is what people actually say: the **spec**.

If the head teacher announces "smith_margaret is in trouble", nobody on the playground knows who that is. Click had exactly this bug: it used the register name (`name`) in messages meant for the playground (the terminal).

In click terms:

| string | audience | where it comes from | example for `@click.option("-t", "--times")` |
|---|---|---|---|
| `decls` | the developer | what you pass to the decorator | `("-t", "--times")` |
| `spec` | the end user | the declaration with the longest prefix | `--times` |
| `name` | Python / click internals | derived from that same declaration, lower-cased, `-` to `_` | `times` |

Two more lists hang off the parameter. They are the parsed decls:

- `opts`: every spelling that turns the parameter on, e.g. `["-t", "--times"]`.
- `secondary_opts`: the "off" spellings of a boolean flag, e.g. `["--no-color"]`.

---

## 3. Diagram: how one decorator becomes five strings

```
 @click.option("-g", "--gluten-free/--no-gluten-free")
                 |
                 v
   Option._parse_decls(decls)                      (core.py, Option class)
                 |
     for each decl:
       isidentifier()?  -> explicit name, e.g. "repeat_count"
       contains "/"?    -> split: left -> opts, right -> secondary_opts
       otherwise        -> opts
                 |
     possible_names sorted by prefix length (longest first, stable)
                 |
     +-----------+---------------+------------------+
     |                           |                  |
     v                           v                  v
  opts = ["-g","--gluten-free"]  secondary_opts =   name = "gluten_free"
     |                           ["--no-gluten-free"]  ("gluten-free" -> "_", lower)
     |
     v
  spec  (NEW, a property, computed on read)
     = max(opts, key=len(prefix))   -> "--gluten-free"
     |
     v
  get_help_spec(ctx)  -> "-g, --gluten-free / --no-gluten-free"
                         (all spellings + metavar if it takes a value)
```

The key design decision: `spec` uses the **same rule** as `name` ("longest prefix wins, first one on a tie"). So for an option without an explicit name, `spec` is exactly the declaration that `name` was derived from. The PR's test checks that invariant directly:

```python
assert _split_opt(opt.spec)[1].replace("-", "_").lower() == opt.name
```

`_split_opt` lives in `src/click/parser.py`. It splits `"--times"` into `("--", "times")`, `"-t"` into `("-", "t")` and `"/debug"` into `("/", "debug")`. The "prefix length" in the sort is the length of that first part.

### Arguments are different

An argument has no flag to type. The user sees it in help as an upper-case placeholder (the *metavar*):

```
 @click.argument("filename")
          |
          v
 Argument._parse_decls  -> name = "filename", opts = ["filename"], secondary_opts = []
          |
          v
 Argument.spec (override)        -> metavar if given, else name.upper()  -> "FILENAME"
 Argument.get_help_spec(ctx)     -> make_metavar(ctx), which adds markers:
                                    "FILENAME", "[FILENAME]", "[FILENAME]..."
```

Note that `Argument.opts` is `["filename"]` (lower case). The parser never reads it. That is why the argument needs its own `spec` override: the base `Parameter.spec` would return `"filename"`.

---

## 4. Real values (ran)

Options:

| decls | `spec` | `name` | `opts` | `secondary_opts` |
|---|---|---|---|---|
| `-t, --times` | `--times` | `times` | `['-t', '--times']` | `[]` |
| `--times, -t` | `--times` | `times` | `['--times', '-t']` | `[]` |
| `-t` | `-t` | `t` | `['-t']` | `[]` |
| `--times, --repeat` (tie) | `--times` | `times` | `['--times', '--repeat']` | `[]` |
| `-t, -x` (tie) | `-t` | `t` | `['-t', '-x']` | `[]` |
| `--color/--no-color` | `--color` | `color` | `['--color']` | `['--no-color']` |
| `/debug;/no-debug` | `/debug` | `debug` | `['/debug']` | `['/no-debug']` |
| `--times, repeat_count` (explicit name) | `--times` | `repeat_count` | `['--times']` | `[]` |

The last row is the one case where `spec` and `name` disagree. That is intended. The developer chose the internal name, and the user still types `--times`.

Arguments (declared as `click.Argument(["filename"], **kwargs)`):

| kwargs | `spec` | `get_help_spec(ctx)` |
|---|---|---|
| `{}` | `FILENAME` | `FILENAME` |
| `required=False` | `FILENAME` | `[FILENAME]` |
| `nargs=-1` | `FILENAME` | `[FILENAME]...` |
| `metavar="<file>"` | `<file>` | `<file>` |

Rule of thumb: **`spec` is the bare word. `get_help_spec` is the decorated word for the left column of `--help`.**

---

## 5. Where the user actually sees `spec`

The PR swapped `human_readable_name` for `spec` at every read site in `core.py`. There are no others in `src/` (checked with `git grep` at both commits).

```
                         Parameter.spec
                               |
     +-------------------------+--------------------------+-------------------------+
     |                         |                          |                         |
 Parameter.__init__      Parameter.handle_parse_result   Parameter.get_error_hint  Argument.get_error_hint
 "deprecated and still   echo "DeprecationWarning:       opts or [spec]            ctx -> get_help_spec(ctx)
  required" ValueError    The option '--x' is ..."       (fallback only)           no ctx -> spec
```

What these look like (ran):

```text
ValueError: The option '--old' is deprecated and still required. A deprecated option cannot be required.

DeprecationWarning: The option '--my-option' is deprecated.

Error: Missing argument 'RECIPE'.
Error: Missing option '--count'.
Error: Invalid value for '--count': 'x' is not a valid integer.
```

The last three come from `get_error_hint`. For an option, `opts` is almost never empty, so the hint is built from `opts` and this PR did not change it. The visible changes are the first two lines.

And the help page, from the new example in `docs/parameters.md` (ran):

```text
Usage: bake [OPTIONS] RECIPE          <- Argument: spec / metavar in the usage line

Options:
  -g, --gluten-free / --no-gluten-free   <- Option.get_help_spec(ctx), the left column
  --help                          Show this message and exit.
```

---

## 6. The deprecation machinery (worth learning, it is reused)

Click deprecates in two places at once, and this PR shows both.

### 6a. Reading the old property warns

```python
@property
def human_readable_name(self) -> str:
    warnings.warn("'human_readable_name' is deprecated ... Use 'spec' instead.",
                  DeprecationWarning, stacklevel=2)
    return self.spec
```

`stacklevel=2` is enough here. The caller is whoever touched `.human_readable_name`, one frame up. Note the **behaviour change**: for an option it now returns `--my-option` instead of `my_option`. This is called out in `CHANGES.md` and `docs/upgrade-guides.md`.

### 6b. Overriding the old property warns at class-definition time

Click no longer *reads* `human_readable_name`. So a plugin that did this:

```python
class MyOption(click.Option):
    @property
    def human_readable_name(self):
        return "custom"
```

would silently stop working. The PR catches it with `__init_subclass__`:

```python
def __init_subclass__(cls, **kwargs):
    super().__init_subclass__(**kwargs)
    if "human_readable_name" in cls.__dict__:      # defined on THIS class, not inherited
        warnings.warn(..., DeprecationWarning,
                      stacklevel=_outside_click_stacklevel(skip=("abc",)))
```

ELI5: a hall monitor stands at the classroom door. Each time a new class (a subclass) walks in, the monitor checks whether it brought the old, banned name tag. Only the class that brought it gets told off, not its children (that is the `cls.__dict__` check).

Why the `skip=("abc",)`? `Parameter` is an `ABC`. When Python runs a `class` statement, the call chain is:

```
your_plugin.py   class MyOption(click.Option):   <- the warning should point HERE
      |
abc.py           ABCMeta.__new__                 <- module "abc": skip it
      |
click/core.py    Parameter.__init_subclass__     <- module "click.core": skip it
      |
warnings.warn(stacklevel=N)
```

`_outside_click_stacklevel()` walks up the frames until it leaves the `click` package. This PR adds an optional `skip` argument so it also walks past `abc`. Verified (ran): the warning is attributed to the `class Old(click.Option):` line of the calling script, not to `abc.py`.

Output (ran):

```text
Old overrides 'human_readable_name'. Click no longer reads that property. Override 'spec' instead. Click will remove 'human_readable_name' in 9.0.
```

---

## 7. Class map after the PR

```
Parameter (ABC)
 |  name, opts, secondary_opts            (now documented attributes)
 |  spec            -> longest-prefix opt, or name if no opts       NEW
 |  get_help_spec() -> spec                                         NEW on base
 |  human_readable_name -> warns, returns spec                      DEPRECATED
 |  __init_subclass__  -> warns if a subclass overrides it          NEW
 |
 +-- Option
 |     get_help_spec() -> "-c, --config TEXT"   (existed since 8.5.1, unchanged)
 |     get_help_record() -> (get_help_spec(), help + extras)  or None if hidden
 |
 +-- Argument
       spec            -> metavar or NAME.upper()                   (renamed from human_readable_name)
       get_help_spec() -> make_metavar(ctx), e.g. "[FILENAME]..."   NEW
       get_help_record() -> (get_help_spec(), help)                 now routed through get_help_spec
       get_error_hint()  -> uses get_help_spec / spec
```

`spec` and `get_help_spec` are the two override points. If you write a custom `Parameter` subclass and want click's messages to use a different label, override `spec`.

---

## 8. Tests the PR added (read these first)

| test | file | what it pins down |
|---|---|---|
| `test_spec` | `tests/test_options.py` | longest prefix wins over order; `spec` matches `name` |
| `test_spec_with_explicit_name` | `tests/test_options.py` | explicit name does not leak into `spec` |
| `test_deprecated_warning` (edited) | `tests/test_options.py` | message now says `'--my-option'` |
| `test_spec_and_help_spec` | `tests/test_arguments.py` | bare vs decorated metavar |
| `test_help_spec_matches_help_record` | `tests/test_arguments.py` | left column of help == `get_help_spec` |
| `test_parameter_human_readable_name_deprecated` | `tests/test_deprecations.py` | reading warns and returns spec |
| `test_parameter_human_readable_name_override_deprecated` | `tests/test_deprecations.py` | overriding warns for `Parameter`, `Option`, `Argument` |
| `test_parameter_subclass_without_override_is_silent` | `tests/test_deprecations.py` | no false positives |

Note the shape: small `pytest.mark.parametrize` tables, one behaviour per test, a one-line docstring saying *why*. Match that style.

---

## 9. Making your first contribution here

### Setup and checks

The repo uses `tox` with `tox-uv` (see `[tool.tox]` in `pyproject.toml`).

```bash
tox -e py3.13                      # pytest
tox -e py3.13 -- tests/test_options.py -k spec
tox -e style                       # pre-commit (ruff)
tox -e typing                      # mypy + pyright --verifytypes
tox -e docs                        # sphinx with -W: warnings fail the build
```

Plain pytest also works if you install the package into a venv: `pip install pytest . && pytest tests/test_options.py`.

### The checklist this PR follows (from `.github/pull_request_template.md`)

1. Open or link an issue first.
2. Add tests that **fail without the change**.
3. Update the docs in `docs/` *and* the docstrings. This PR rewrote "Parameter Names" in `docs/parameters.md`.
4. Add a `CHANGES.md` entry under "Unreleased" with `{pr}\`NNNN\``.
5. Add `.. versionadded::` / `.. versionchanged::` / `.. deprecated::` to docstrings.
6. For a deprecation, also add a bullet to `docs/upgrade-guides.md`. For a wording change that breaks people's test assertions, add it under "Changes" there too.

### Gotchas

- **`spec` must agree with `name`.** If you change how `Option._parse_decls` picks `name` (sorting, tie-breaking), change `spec` too. `test_spec` will catch a mismatch.
- **Ties go to the first declaration.** `possible_names.sort(...)` is stable and `max(...)` returns the first maximum, so they agree. Do not swap `max` for something that returns the last one.
- **Do not reintroduce reads of `human_readable_name` inside click.** The `__init_subclass__` warning promises users that click ignores it.
- **`spec` vs `get_help_spec`.** Use `spec` in sentences ("The option '--x' ..."). Use `get_help_spec(ctx)` where the decorated form belongs (help column, argument error hints). `get_help_spec` needs a `ctx` because metavars can depend on it. `spec` does not, so it works where `ctx` is `None`.
- **Deprecation warnings need the right `stacklevel`.** Use `_outside_click_stacklevel()` (and `skip=` when a non-click frame like `abc` sits in between). Otherwise the warning points into click and users cannot find their own code.
- **User-facing wording changes break downstream tests.** Document them under "Changes" in `docs/upgrade-guides.md`.

### Good first follow-ups to look for

These are leads to check, not confirmed bugs:

- Grep `src/click/` for `self.name` in user-facing strings (`exceptions.py`, `shell_completion.py`, `_(...)` calls) and see whether any should be `spec`.
- `Parameter.spec` returns `name` when `opts` is empty. That case is reachable: `click.Option([" /--no-foo", "x"])` gives `opts == []`, `secondary_opts == ['--no-foo']` and `spec == 'x'` (ran). That `spec` is a Python name the user cannot type. It is an edge case, so ask on the issue tracker whether it is worth changing before you send a PR.
- In 9.0, removing `human_readable_name` and the `__init_subclass__` hook is a planned cleanup.

---

## How this was checked

- Read the full diff `git diff 06b2a67 2247b35` and the surrounding code at the merge commit (`Option._parse_decls`, `Argument._parse_decls`, `Option.get_help_spec`, `_split_opt`, `_outside_click_stacklevel`, `handle_parse_result`), using `git show 2247b35:<path>` so the clone was never modified.
- `git archive 2247b35 | tar -x` into a scratch directory outside the clone, built a venv, and installed that tree plus pytest.
- Ran the three test files the PR touched: **971 passed**.
- Ran a script that prints every value and message in sections 4, 5 and 6 against the installed merge-commit click. The tables and **(ran)** blocks are copied from its output, including the warning's file and line number.
- The ASCII diagrams were checked by hand against the code. They are not generated. The "before" column in section 1 is taken from the PR's edit to `test_deprecated_warning` and its `CHANGES.md` entry, not from running the old commit.
