# Milestone 4 - Final submission

The LMS deliverable is **one file: `Team06_M4.pdf`**. Export it from the reviewed testing report after merging into `main`.

## Files for this final update

- `docs/testing.md`
- `docs/sprint-log.md`
- `docs/M4-submission.md`
- `backend/test/export_m4_report.py`
- `docs/evidence/m4/planning.png`
- `docs/evidence/m4/submission day.png`
- `docs/evidence/m4/pytest-full-output.png`

The board screenshots are embedded in the PDF and linked from the testing report and sprint log. Keep any earlier pending test/setup changes with their corresponding issues. Do not commit `.env`, virtualenvs, `node_modules`, `tmp/` or the assignment PDF.

## Export

From the repository root, with the development dependencies installed:

```powershell
& ./backend/.venv/Scripts/python.exe backend/test/export_m4_report.py --final
```

For the working environment created during this local verification, use:

```powershell
& ./tmp/m4-verify/backend/.venv/Scripts/python.exe backend/test/export_m4_report.py --final
```

The exporter uses the supplied image filenames by default and writes `output/pdf/Team06_M4.pdf`. Arial and Consolas are loaded from `C:/Windows/Fonts`.

## PDF contents

1. Team/project cover with members and student IDs, PO, Sprint 4 SM, repository, board, setup guide and submitter.
2. The Planning and submission-day board screenshots.
3. Full captured pytest output with every test name retained.
4. The four sections from `docs/testing.md`.

Before uploading, check the cover details, final sprint accounting, required reviews and remote CI. Upload only `output/pdf/Team06_M4.pdf`; it does not have to be committed to GitHub. Keep the wrap-up chore open until LMS confirms successful submission.
