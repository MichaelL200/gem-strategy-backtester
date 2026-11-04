# AGENTS.md

Python/Streamlit backtester for momentum strategies on financial markets.
The Streamlit UI lives in `app/`, while reusable backtesting and data logic
lives in `src/`.

## Commands

- Run: `streamlit run app.py`
- Test: `pytest` (all tests must pass before a commit)
- Lint: `ruff check .`
- Install: `pip install -e .`
- Install test and lint dependencies: `pip install -e ".[test,lint]"`

## Structure

- `app.py`: root launcher for Streamlit deployment.
- `app/`: Streamlit orchestration and UI components.
- `src/`: reusable assets, data loading, period helpers, strategies, engine,
  and metrics. The top-level modules are `assets`, `data`, and `periods`;
  `backtest` is the strategy package.
- `tests/`: unit and Streamlit `AppTest` coverage.
- `docs/`: architecture and technical documentation.
- `notebooks/`: exploratory analysis.

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
