# PowerPoint preview without server applications

PPTX visual preview runs in the browser using the pinned `pptx-preview` npm
package. The frontend downloads the original through the authenticated
`/api/documents/{id}/file` route, then sends the bytes to an isolated iframe.
No public file URL, cloud conversion service, LibreOffice, or Docker is needed.
Existing PPTX files can use this preview immediately; no reupload is needed.

The original slide order, aspect ratio, images and supported styling are rendered
in the browser. The reader's Previous/Next and page selector navigate the visual
slides. Missing fonts or unsupported shapes/charts can differ from PowerPoint;
animations and full PowerPoint fidelity are not guaranteed. Rendering errors
show a localized fallback with the text reader and original download.

## Backend and citations

Python extracts PPTX text and creates a generated text-reader PDF for analysis,
search and citation coordinates, one page per slide including hidden/blank slides.
This requires only the existing Python dependencies. The visual preview does not
claim its coordinates match that text PDF. Use **Open text reader** to see exact
search/citation highlighting; the visual preview opens the same slide number.
DOCX and native PDF behavior is unchanged. Existing immutable reader PDFs and
saved citations are retained.

## Build and deploy

Run `npm ci` in `frontend`; its postinstall builds `/pptx-renderer.js` locally
with esbuild. `npm run dev` and `npm run build` rebuild it as well. The generated
asset is not committed; the pinned sources and package lock are committed.
Deploy the Python backend normally and rebuild the existing Next.js frontend.
No new environment variables or system packages are required.

The renderer uses an iframe with only `allow-scripts`, without same-origin
permission. Its CSP blocks network connections, external images/fonts and inline
scripts from document content. Only the locally bundled renderer script and
embedded image/font data can load. The parent retains authentication and checks
message sources. Files are not sent to third parties.

The 5 MiB/file upload boundary and BR processing deadlines are unchanged. The
preview has a 30-second UI loading fallback, independent of analysis timers.
The browser-side rendering package is loaded only on the PPTX preview path.
