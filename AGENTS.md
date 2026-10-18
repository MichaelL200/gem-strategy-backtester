# AGENTS.md

Python/Streamlit backtester for momentum strategy on financial markets: ranks assets by past return and holds the best.

## Commands

- Run: `streamlit run app.py`
- Test: `pytest` (all tests must pass before a commit)

## Rules

- Every change comes with tests; if the behaviour changes, update the README too.
- No look-ahead: a signal may only use prices up to its own close.
- Tests never use the network: fake `data._load` and `data._quote_currency`; the UI is tested with Streamlit `AppTest`.
- Warnings are orange boxes in the `notices` container on the main screen, with `highlight(key)` on the related setting.
- Don't touch unrelated files.

## Commits

Do not commit or push unless asked. Otherwise give the message in a code block.

```
type(scope): subject

Short paragraph: what was wrong or why the change is needed, and what it
does now. Wrapped at 72 characters.

- area: what changed
- tests: what is covered

Closes #N
```

- `type`: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`. `scope` is optional (`ui`, `assets`, `engine`).
- Subject: lowercase, no period, at most 72 characters, no issue number.
- Body: skip it only for trivial changes. Bullets are `- area: change` (areas: `backtest`, `data`, `assets`, `app`, `tests`, `README`).
- Last line after a blank line: `Closes #N`. Partial fix: `Refs #N`. No issue: omit.
- One logical change per commit, with its tests and README update.
- Commit with `git commit -F <file>` or the editor, not a multi-line `-m`: PowerShell drops the line breaks and glues words together.
- Squash merges of contributor PRs: keep the contributor as author and drop the `(#N)` from the subject.
