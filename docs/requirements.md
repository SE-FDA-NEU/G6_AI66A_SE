# DocuMind — Requirements Document

## 1. Product vision

For accountants, journalists, sales staff and students who regularly read and organize many documents, DocuMind is an AI-assisted web application that summarizes documents, suggests labels and searches their contents. It helps users spend less time reading and avoid missing important information, while leaving folder organization under their control. Unlike a general-purpose chatbot, it provides a structured workflow for uploading files, choosing an output format, finding source passages and managing a document workspace.

## 2. Personas

### Persona 1 – Lan, 32, accountant

- **Role:** Reviews PDF contracts, official letters and administrative documents containing important figures and clauses.
- **Goal:** Reduce reading time by 50% while retaining important numbers, clauses and context.
- **Blocked by:** Long number-heavy documents, missed clauses and an increasingly disorganized file collection.
- **In her words:** “I need to know exactly which figures matter and where they appear in the document.”
- **Technical skill:** Comfortable with office software but less experienced with AI; prefers a comparison table.

### Persona 2 – Minh, 29, journalist

- **Role:** Monitors more than 20 news sources and documents each day.
- **Goal:** Cut skimming time by more than 70% and find noteworthy events and figures quickly.
- **Blocked by:** Information overload, missed details and summaries that lack source context.
- **In his words:** “I need to know immediately what matters and where that information came from.”
- **Technical skill:** Confident with computers and AI tools; values speed, accuracy and contextual search.

### Persona 3 – Huy, 27, sales representative

- **Role:** Reads market updates, contracts and customer documents on his phone before meetings.
- **Goal:** Reduce document-processing time by 50% and identify the next useful action.
- **Blocked by:** Dense terminology, documents on many topics and concern about inaccurate AI output.
- **In his words:** “I just need to know what is happening and how it relates to my customer.”
- **Technical skill:** Frequent smartphone user; prefers a simple interface and bullet summaries.

### Persona 4 – Ngoc, 21, third-year student

- **Role:** Studies lecture slides, textbooks and research papers across different courses.
- **Goal:** Reduce reading time by 50% while understanding key arguments and concepts.
- **Blocked by:** Academic terminology, overly generic summaries and documents mixed across subjects.
- **In her words:** “I want to know which parts I should study and why they matter.”
- **Technical skill:** Familiar with AI study tools; prefers bullet points, subject labels and in-document lookup.

## 3. Scenarios

### Scenario 1 – Lan compares contract figures before reporting

1. On Monday morning, Lan receives five PDF contracts while preparing the weekly financial report.
2. She uploads all five files from her desktop and requests a financial-clause comparison table.
3. DocuMind suggests a `Contract` label for each file and produces rows with values, payment terms, penalties and source pages; it does not move the files into folders.
4. Lan spots an unusual penalty, opens the cited page to verify it and records the finding in her report.

### Scenario 2 – Minh verifies a newsworthy figure

1. During a shift, Minh receives more than 20 documents and reports about a recent economic event.
2. He uploads them in valid batches and searches his workspace for the relevant event.
3. DocuMind returns concise facts and figures, each with a document name and page citation.
4. Minh opens the cited page, checks the original passage and uses the verified figure in his article.

### Scenario 3 – Huy prepares on his phone before a meeting

1. Ten minutes before a customer meeting, Huy receives a 15-page market report.
2. He uploads it through a mobile browser and chooses a bullet summary.
3. DocuMind presents the key price trends in a layout that fits his phone.
4. Huy reads the recommended actions, chooses a viable option and enters the meeting prepared.

### Scenario 4 – Ngoc organizes and studies academic papers

1. While preparing for exams, Ngoc uploads several research papers.
2. DocuMind suggests a subject label for each paper and shows its confidence. Ngoc decides which course folder, if any, should contain each paper.
3. Ngoc requests a short overview of core concepts, then opens one paper in the reader.
4. She searches for a difficult term; the reader jumps to and highlights the explanatory passage.
5. She checks the context, takes a note and continues studying.

## 4. User stories

Priorities: P0 = essential for the first usable release, P1 = important follow-up, P2 = later enhancement. Points are relative estimates, not time commitments.

| ID | Story | Priority | Points |
|---|---|---|---:|
| US01 | As Lan, I want to upload five contracts and receive a comparison table so that I can review financial clauses without reading every page. | P0 | 8 |
| US02 | As Minh, I want to search across at least 20 documents so that I can find relevant facts and figures quickly. | P0 | 8 |
| US03 | As Huy, I want a mobile-friendly bullet summary with action recommendations so that I can prepare for a meeting. | P0 | 5 |
| US04 | As Ngoc, I want an AI-suggested label and in-document search so that I can understand and study each paper. | P0 | 8 |
| US05 | As a user, I want to sign in and access only my own documents so that my workspace remains private. | P0 | 5 |
| US06 | As a user, I want invalid uploads rejected with clear reasons so that I can correct them before processing. | P0 | 3 |
| US07 | As a user, I want to see processing progress and failures so that I know when a result is ready. | P0 | 5 |
| US08 | As Minh, I want each important claim linked to its source page so that I can verify it before publication. | P0 | 5 |
| US09 | As Lan, I want to open a citation at the exact page and highlighted passage so that I can check its context. | P0 | 5 |
| US10 | As Ngoc, I want to choose folders myself and filter by suggested labels so that course materials stay organized my way. | P1 | 3 |
| US11 | As Lan, I want to export the contract comparison table so that I can include it in my report. | P1 | 3 |
| US12 | As a user, I want uncertain label suggestions and unsupported claims flagged so that I do not mistake AI output for verified information. | P1 | 5 |

### Acceptance criteria and tasks

#### US01 – Compare multiple contracts · P0 · 8 points · Screens: /upload, /results/:jobId

As Lan, I want to upload five contracts and receive a comparison table so that I can review financial clauses without reading every page.

Acceptance criteria:

- Given five valid PDF contracts, when I choose the financial-clause table and start processing, then `/results/:jobId` shows one row per contract with the contract name, value, payment term, penalty and source page (BR01, BR05).
- Given a contract states a daily late-payment penalty of 0.05%, when the table is generated, then it shows `0.05% per day` rather than `5%` and links to the source page (BR05).
- Given a valid batch of five contracts, when processing begins, then label prediction and the comparison result complete within five minutes or the job displays a visible failure state (BR02).

Tasks:

- Build batch upload and financial-clause mode on `/upload`.
- Extract contract fields and render the comparison table on `/results/:jobId`.
- Test numerical accuracy and the five-minute batch target with five sample PDFs.

#### US02 – Search across documents · P0 · 8 points · Screen: /workspace

As Minh, I want to search across at least 20 documents so that I can find relevant facts and figures quickly.

Acceptance criteria:

- Given a workspace with 20 indexed documents, when I search for `gold price movement`, then results from all 20 documents are eligible and each hit shows a short relevant excerpt, document name and page number (BR05).
- Given a document unrelated to the query, when results are displayed, then it is not presented as a matching fact.
- Given a result points to page 6, when I select it, then the reader opens that document at page 6 (BR05).

Tasks:

- Index extracted document text by document and page.
- Implement cross-document search and result snippets on `/workspace`.
- Test recall and citation navigation with a 20-document fixture.

#### US03 – Mobile bullet summary and actions · P0 · 5 points · Screens: /upload, /results/:jobId

As Huy, I want a mobile-friendly bullet summary with action recommendations so that I can prepare for a meeting.

Acceptance criteria:

- Given a valid 15-page PDF, when I select bullet summary and start processing, then the result is ready within three minutes or a failure state is shown (BR02).
- Given the summary is ready, when I open it on a 375-pixel-wide phone, then the bullets and controls are readable without horizontal scrolling.
- Given the source supports at least two actions, when I reach the `Recommended actions` section, then I see at least two source-grounded options; otherwise the system states that the document does not support two recommendations (BR05).

Tasks:

- Add the bullet-summary choice on `/upload` and responsive layout on `/results/:jobId`.
- Generate concise bullets and source-grounded action recommendations.
- Test a 15-page PDF on Android and iOS viewport sizes.

#### US04 – Suggest a label and search inside a document · P0 · 8 points · Screens: /workspace, /documents/:documentId

As Ngoc, I want an AI-suggested label and in-document search so that I can understand and study each paper.

Acceptance criteria:

- Given a macroeconomics paper with prediction confidence of 87%, when processing finishes, then `Macroeconomics` appears as an AI-suggested label with its confidence; the paper remains in its current folder until I move it (BR03).
- Given prediction confidence of 72%, when processing finishes, then the proposed label is marked `Needs review`; the system still does not choose a folder (BR03).
- Given the term `inflation causes` occurs on page 12, when I search within the reader, then the reader moves to page 12 and highlights the matching passage.
- Given I request a concept overview, when the bullet result is ready, then it contains three to five core concepts grounded in the paper (BR04, BR05).

Tasks:

- Store the suggested label, confidence and review state separately from the user-selected folder.
- Add document-level text search, page navigation and highlighting.
- Test high- and low-confidence label suggestions, unchanged folder placement and concept counts.

#### US05 – Sign in and protect the workspace · P0 · 5 points · Screens: /, /workspace

As a user, I want to sign in and access only my own documents so that my workspace remains private.

Acceptance criteria:

- Given I am a guest, when I open `/workspace`, `/upload`, `/results/:jobId` or `/documents/:documentId` directly, then I am redirected to `/` and asked to sign in (BR07).
- Given I sign in successfully, when I continue, then `/workspace` shows only documents belonging to my account (BR07).
- Given user A owns document 42, when user B requests `/documents/42`, then access is denied without exposing its content (BR07).

Tasks:

- Implement the landing-page sign-in entry and session handling.
- Apply route guards and document ownership checks on the server.
- Test guest redirects and cross-account access denial.

#### US06 – Validate upload files · P0 · 3 points · Screen: /upload

As a user, I want invalid uploads rejected with clear reasons so that I can correct them before processing.

Acceptance criteria:

- Given five valid PDF, DOCX or PPTX files of 5 MB each, when I select them, then all five are accepted because each file is within the 5 MB limit and their combined size is 25 MB (BR01).
- Given I select a sixth file, when validation runs, then the sixth file is rejected with `Maximum 5 files per batch` and the five valid files remain selected (BR01).
- Given I select a 5.1 MB file or an EXE file, when validation runs, then it is rejected with a size or format explanation before processing begins (BR01).

Tasks:

- Validate format, file count, per-file size and combined batch size in the browser and on the server.
- Show per-file validation messages without discarding valid selections.

#### US07 – Track processing status · P0 · 5 points · Screens: /upload, /results/:jobId

As a user, I want to see processing progress and failures so that I know when a result is ready.

Acceptance criteria:

- Given a submitted batch of five documents, when processing is ongoing, then `/results/:jobId` displays a status and a completed-file count such as `3/5`.
- Given all five files finish, when I revisit the job URL, then its status is `Completed` and the results remain visible.
- Given a file fails or exceeds the processing limit, when the job updates, then the affected file has a `Failed` or `Timed out` state and the user is not shown a false completion message (BR02).

Tasks:

- Persist per-file and overall job states.
- Connect progress updates and failure messages to the results screen.

#### US08 – Cite important facts · P0 · 5 points · Screens: /workspace, /results/:jobId

As Minh, I want each important claim linked to its source page so that I can verify it before publication.

Acceptance criteria:

- Given a summary contains `Revenue increased by 8.2%`, when the result is displayed, then it includes a clickable citation in the form `Document name — page X` (BR05).
- Given a result contains a date, amount, percentage or contract clause with no retrievable source, when it is displayed, then it is marked `Unverified` rather than presented as a confirmed fact (BR05).
- Given two documents support the same fact, when I inspect the result, then the system preserves each document's own name and page reference rather than merging their citations.

Tasks:

- Persist evidence spans and page references with extracted facts.
- Render citations and unverified states in search and summary results.

#### US09 – Inspect a cited passage · P0 · 5 points · Screen: /documents/:documentId

As Lan, I want to open a citation at the exact page and highlighted passage so that I can check its context.

Acceptance criteria:

- Given a table cell cites page 12 of a 24-page contract, when I click it, then `/documents/:documentId` opens at page 12 with the cited passage highlighted (BR05).
- Given I arrived from `/results/:jobId`, when I click `Back to Results`, then I return to the same job.
- Given a document has no searchable text on the cited page, when I open the citation, then the reader still opens the correct page and explains that precise text highlighting is unavailable.

Tasks:

- Pass document, page and evidence-span identifiers through citation links.
- Implement page jump, highlighting and return-to-job navigation.

#### US10 – Organize folders and filter by label · P1 · 3 points · Screen: /workspace

As Ngoc, I want to choose folders myself and filter by suggested labels so that course materials stay organized my way.

Acceptance criteria:

- Given 8 documents have a suggested `Macroeconomics` label and 12 have other suggestions, when I filter by `Macroeconomics`, then only the 8 matching documents appear, regardless of their folders (BR03).
- Given an uploaded paper with no folder selected, when I choose my `Economics 101` folder, then the paper appears there; the AI label does not change the folder automatically (BR03).
- Given a paper is in `Economics 101`, when I move it to `Research`, then it appears in `Research` while its suggested label remains unchanged (BR03).
- Given I clear the label filter, when the list updates, then all 20 documents reappear.

Tasks:

- Add user-controlled folder selection or move and a suggested-label filter to `/workspace`.
- Store folder membership separately from predicted label metadata.

#### US11 – Export the comparison table · P1 · 3 points · Screen: /results/:jobId

As Lan, I want to export the contract comparison table to Excel so that I can include it in my report.

Acceptance criteria:

- Given a completed five-contract comparison, when I click `Export Table`, then an PDF file downloads with five data rows and columns for document name, value, payment term, penalty and source page.
- Given a value of 1,200,000,000 VND and a penalty of 0.05% per day, when I open the export, then both values retain their units and are not rounded into a different meaning (BR05).
- Given processing is incomplete, when I view the results page, then the export action is disabled until a completed table exists.

Tasks:

- Generate an export from the same structured data used by the table.
- Test row count, units and source references in the downloaded file.

#### US12 – Surface uncertainty · P1 · 5 points · Screens: /workspace, /results/:jobId

As a user, I want uncertain label suggestions and unsupported claims flagged so that I do not mistake AI output for verified information.

Acceptance criteria:

- Given the model predicts `Contract` with 79% confidence, when I open the workspace, then its suggestion shows `Needs review`; at 80% it shows a high-confidence suggestion, but neither outcome moves the document to a folder (BR03).
- Given a table cell has no source passage, when I view the result, then the cell says `Unverified` and has no link pretending to lead to evidence (BR05).
- Given I confirm or edit a suggested label, when I revisit the document, then my chosen label persists and is distinguishable from the original AI suggestion; its folder remains unchanged.

Tasks:

- Add label review/editing and persistence without changing folder membership.
- Display provenance and verification states consistently across screens.

## 5. Business rules

The rules below govern the stories above. Numerical values are proposed acceptance thresholds for this requirements baseline; they must be agreed with the team before implementation.

| ID | Rule | Worked example |
|---|---|---|
| BR01 | Accept only PDF, DOCX and PPTX; at most five files per submission; each file may be at most 5 MB and the combined size of all files in one submission may be at most 50 MB. Validate before processing. | Five 5 MB PDFs are accepted: 25 MB combined. A sixth file is rejected. A 5.1 MB PDF is rejected even if the combined size is below 50 MB. |
| BR02 | A valid batch of five contracts must complete label prediction and table generation within five minutes; a single 15-page PDF bullet summary must finish within three minutes. If a target is missed, show a visible timeout or failure, not a successful result. | Five contracts submitted at 09:00 must produce a table by 09:05. A 15-page report submitted at 14:00 must produce bullets by 14:03. |
| BR03 | After upload, the model predicts a label and confidence; at 80% or above, display it as a high-confidence suggestion, otherwise mark it `Needs review`. The user may accept or edit the label and independently choose or change a folder. The model never assigns or moves a folder automatically. | A contract scores 87% for `Contract`, so the suggestion is shown, but its folder stays unchanged. A paper scores 72% for `Macroeconomics`, so it is marked `Needs review`; Ngoc can place either document in any folder she chooses. |
| BR04 | A requested concept overview contains three to five core concepts. A general summary contains at most 1,000 words; for a very short source, do not pad the output to meet an artificial minimum. | A research paper yields four concept bullets. A 5,000-word report yielding 1,250 summary words is shortened to 1,000 or fewer. |
| BR05 | Every factual amount, date, percentage and contract clause shown as verified must link to its source document and page. If no source is available, mark the claim `Unverified`; citation navigation opens the source page and highlights the passage when possible. | `Late fee: 0.05% per day` links to `Contract A.pdf — page 12`. A fee with no source is marked `Unverified`. |
| BR06 | Retain an ordinary user's document for at most 30 days after its last access, warn seven days before expiry and restart the 30-day period after opening, downloading or updating it. | Last accessed on 1 March 2026: expiry 31 March; warning 24 March. Opened again on 25 March: new expiry 24 April. |
| BR07 | Guests may view only `/`. Other routes require sign-in, and authenticated users may access only their own documents and jobs. | Guest opening `/upload` returns to `/`. User B requesting User A's document 42 receives access denied. |

## 6. Screens and flow

Access: G = guest (not signed in), U = signed-in user, A = administrator. An administrator can use U screens, but there is no admin-only screen in this five-screen scope.

| Route | Purpose | Access | Priority |
|---|---|---|---|
| `/` | Product introduction and sign-in entry; authenticated users proceed to `/workspace`. | G | P0 |
| `/workspace` | Document list, AI-suggested labels, user-controlled folders, status, cross-document search and links to upload or read a document. | U | P0 |
| `/upload` | File selection, validation, upload progress and analysis-mode configuration. | U | P0 |
| `/results/:jobId` | Processing status, comparison table, bullet summary, recommendations, citations and Excel export. | U | P0 |
| `/documents/:documentId` | Original-document reader with page navigation, in-document search, evidence highlighting and return navigation. | U | P0 |

Main path: `/` → `/workspace` → `/upload` → `/results/:jobId` → `/documents/:documentId`. A guest who opens a protected route is returned to `/` for sign-in (BR07).

How each screen is reached:

| Screen | Reached from |
|---|---|
| `/` | Initial visit; sign-out from `/workspace`. |
| `/workspace` | Successful sign-in from `/`; cancel from `/upload`; back from results or reader. |
| `/upload` | `Upload documents` on `/workspace`. |
| `/results/:jobId` | `Start processing` on `/upload`; `Back to Results` on the reader. |
| `/documents/:documentId` | A document or search hit on `/workspace`; a source citation on `/results/:jobId`. |

## Flow Diagram

```sql
                         ┌─────────────────┐
                         │        /        │  guest user
                         │ Landing / Login │
                         └────────┬────────┘
                                  │ sign in successfully
                                  ▼
                       ┌───────────────────────┐
              ┌───────▶│      /workspace      │◀──────────────┐
              │        │  Document Workspace  │               │
              │        └──────┬─────────┬──────┘               │
              │               │         │                      │
              │  cancel       │         │ open existing        │
              │  upload       │         │ document             │
              │               │         └───────────────┐      │
              │               │ upload documents       │      │
              │               ▼                        │      │
              │        ┌───────────────┐                │      │
              └────────┤    /upload    │                │      │
                       │ Upload Files  │                │      │
                       └───────┬───────┘                │      │
                               │ start processing       │      │
                               ▼                        │      │
                    ┌───────────────────────┐            │      │
                    │    /results/:jobId    │            │      │
                    │ Processing & Results  │            │      │
                    └───────────┬───────────┘            │      │
                                │ open source citation   │      │
                                ▼                        ▼      │
                    ┌───────────────────────────────┐            │
                    │ /documents/:documentId        │            │
                    │ Document Reader               ├────────────┘
                    └───────────────────────────────┘  back to workspace
```
