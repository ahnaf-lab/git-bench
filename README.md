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
subcommand (`git bench ...`), put this repo's `bin/` directory on your
`PATH` — git dispatches `git <name>` to a `git-<name>` executable, and
`bin/git-bench` is that executable.

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

## Status

Built autonomously and gated on passing tests: every change ships only after
the automated test suite passes.
