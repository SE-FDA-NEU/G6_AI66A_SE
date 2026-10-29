# Repository hygiene

- Keep backend test source in `backend/tests/`. Preserve intentional acceptance fixtures in `backend/test/fixtures/acceptance/`.
- Use pytest `tmp_path` for generated PDFs/uploads. For a custom `--basetemp`, use a fresh directory under the operating system's temporary directory, outside the checkout. Pytest may delete that directory's contents.
- Keep runtime reports in ignored `test-results/`. Never commit `.tmp*/`, pytest/Python caches, generated uploads or test reports. When a task explicitly requests captured evidence, commit only the curated text evidence under `docs/`.
- Stage specific task files. Before committing, run `python scripts/check_repository_hygiene.py` and inspect `git diff --cached --stat` and `git diff --cached --check`.
- Enable the versioned hooks in a fresh clone with `git config core.hooksPath .githooks`. Never bypass a failing hygiene hook to finish a task; fix the tracked paths instead.
- When deliberately mutating a rule for a test demonstration, restore the original source in `finally`, verify restoration, and capture a passing run before committing. Never commit the deliberate defect.
