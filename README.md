# git-bench

Time your build/test command at each commit in a git revision range, so you
can see exactly which commit made things slower — before you go looking for
the regression by hand.

`git bench run` walks a revision range oldest-to-newest, checks out each
commit into a throwaway `git worktree`, runs your command there, and logs
the wall-clock time to a local JSON file. Nothing leaves your machine.

## Install

Requires Python 3.8+ and `git` on your `PATH`. No third-party dependencies —
the whole tool is built on the standard library.

```
pip install -e .
```

This installs the `git-bench` console script. To also invoke it as a git
subcommand (`git bench ...`), either put this repo's `bin/` directory on
your `PATH` — git dispatches `git <name>` to a `git-<name>` executable, and
`bin/git-bench` is that executable — or run the one-time setup below.

Inside any git repository you want to benchmark:

```
git bench install
```

This writes a `bench` alias to that repository's local git config (add
`--global` to install it for every repository instead), so `git bench ...`
works without putting anything on `PATH`. It also creates the local
`.git-bench/` results cache and adds it to `info/exclude` in the repo's
git directory — never to a tracked file like `.gitignore` — so it never
shows up as an untracked file in `git status`, even from a linked
`git worktree`. Running it again is safe; it updates the alias in place and
never duplicates the exclude entry.

## Usage

Run a command at every commit between two revisions (oldest first):

```
git bench run <rev-range> -- <command> [args...]
```

For example, to time a test suite across the last 5 commits:

```
git bench run HEAD~5..HEAD -- pytest -q
```

Each commit is checked out into a temporary worktree (your working tree and
index are left untouched), the command runs there, and the elapsed time is
printed:

```
7d7d7ea44cc9     0.097s  fix off-by-one in parser
a1b2c3d4e5f6     0.131s  add caching layer
```

Results accumulate in `.git-bench/results.json` at the repository root,
grouped by the exact command string, so repeated runs with the same command
build up history you can compare over time. A commit whose command exits
non-zero is still recorded (with its real return code); `git-bench` exits
non-zero afterwards if any commit failed.

Render the recorded history as an ASCII sparkline and table:

```
git bench report
```

```
.-=*@

commit        seconds   rc  subject
------------------------------------
7d7d7ea44cc9    0.097s   0  fix off-by-one in parser
a1b2c3d4e5f6    0.131s   0  add caching layer
9f8e7d6c5b4a    0.284s   0  switch to naive regex match
```

The sparkline reads oldest-to-newest, left-to-right, and buckets each timing
into a relative level between the fastest and slowest run in the series, so a
jump in character height is a jump in wall-clock time — the commit under the
tallest character is where to start looking. If more than one command has
been recorded, pass `--command` to pick which one:

```
git bench report --command "pytest -q"
```

Once you know a range got slower, find the exact commit that caused it
without timing every commit in between:

```
git bench bisect <rev-range> --threshold <seconds> -- <command> [args...]
```

For example, if the last 20 commits used to build in under 2 seconds and
now don't:

```
git bench bisect HEAD~20..HEAD --threshold 2.0 -- pytest -q
```

This binary-searches the range instead of walking it linearly: it assumes
the regression is a step change (once a commit crosses the threshold, every
later commit in the range does too), so it only needs to time O(log n)
commits to find the first one over threshold, each of which is still logged
to `.git-bench/results.json` exactly as `run` would. It prints the commit
under test at each step, then the culprit:

```
a1b2c3d4e5f6     0.284s  switch to naive regex match
git-bench: first commit over 2.0s is a1b2c3d4e5f6  switch to naive regex match
```

If nothing in the range exceeds the threshold, it says so and exits
non-zero.

Guard against regressions in CI by comparing HEAD to a baseline revision:

```
git bench check <baseline-rev> --max-regression <percent> -- <command> [args...]
```

For example, to fail a pull request build if it is more than 10% slower than
`main`:

```
git bench check main --max-regression 10 -- pytest -q
```

Both the baseline and `HEAD` are timed the same way `run` times each commit
(a throwaway `git worktree`, so your working tree is untouched), and both
timings are logged to `.git-bench/results.json` alongside everything else:

```
a1b2c3d4e5f6     0.131s  merge main
7d7d7ea44cc9     0.284s  add slow validation pass
git-bench: baseline 0.131s -> HEAD 0.284s (+116.8%, limit 10.0%)
git-bench: HEAD is slower than main by more than 10.0%
```

`--max-regression` defaults to `10.0` (percent) if omitted. `check` exits
non-zero if HEAD is slower than the baseline by more than the threshold, or
if either invocation of the command itself exits non-zero.

## Status

Built autonomously and gated on passing tests: every change ships only after
the automated test suite passes.
