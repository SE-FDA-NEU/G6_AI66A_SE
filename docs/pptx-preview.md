# PowerPoint preview

New PPTX uploads are exported to PDF by LibreOffice Impress and displayed by the
same PDF reader as native PDF uploads. This preserves slide position, background,
images and charts rather than reflowing extracted words into a text-only page.
Each slide is one PDF page, including hidden/blank slides; speaker notes are not
included. Unavailable fonts may be substituted, and this is a static preview
without animations/video playback.

## Install and run

- macOS: `brew install --cask libreoffice`
- Debian/Ubuntu: `sudo apt-get update && sudo apt-get install -y libreoffice-impress fonts-dejavu-core fonts-liberation`
- Windows: install LibreOffice and optionally set `SOFFICE_BINARY=C:/Program Files/LibreOffice/program/soffice.exe` in `backend/.env`.

The backend detects `soffice`/`libreoffice` on PATH, the default macOS location,
and the default Windows Program Files location. `SOFFICE_BINARY` overrides it.
Installing Python requirements alone does not install LibreOffice.

Run the existing Python/Uvicorn backend normally after installing LibreOffice
on that host. Keep the current database, storage and environment configuration.
CI installs Impress before backend/frontend integration tests.

For an existing Render Python service, the service owner must verify that
`soffice` is available in its runtime or provision LibreOffice there. A Python
code push alone does not install this system application. If it is unavailable,
PPTX preview reports `renderer_unavailable`; local installation does not install
it on the production server.

## Versioning and limits

Existing readers remain immutable because saved citation coordinates and hashes
refer to their PDF bytes. They are not silently replaced. Reupload an older PPTX
to create its new visual preview and matching extraction/citations. Original
uploads are never overwritten.

Each conversion has its own temporary LibreOffice profile to isolate simultaneous
jobs. The converter has a 90-second ceiling; existing document/BR deadlines can
cancel it earlier. Cancellation stops the worker process tree before temporary
files are removed. Upload stays at most 5 MiB/file and the existing batch and BR
timeouts stay unchanged. Missing LibreOffice returns `renderer_unavailable`,
not a successful text-only substitute.

PDF export parameters use the official [LibreOffice PDF CLI options](https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html):
`ExportHiddenSlides=true`, `ExportNotesPages=false`, `ExportOnlyNotesPages=false`,
and `ExportNotes=false`.
