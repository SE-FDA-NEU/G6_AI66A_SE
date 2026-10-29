# Sprint log

One section per sprint. Fill it in **during** the sprint, not the night before
the milestone deadline - the commit timestamps on this file are part of the
evidence that the process was real.

---

## Sprint 4 - October 2026

### Sprint goal

Establish an isolated regression test suite covering all P0 stories (US01-US09), verify clean-clone test instructions and existing CI, collect mutation and defect detection evidence, and compile the final testing report for Milestone 4.

### Roles

| Role | Member |
|---|---|
| Product Owner | @PhanDangVu |
| Scrum Master | @Dangtooo |

The Scrum Master rotates from @taibaonguyen in Sprint 3.

### Committed

Scope: Verification of the isolated test environment, regression test coverage across all nine P0 user stories (US01-US09), interface regression checks, test evidence handovers, clean-clone setup verification, and compiling the Milestone 4 testing documentation.

Total committed: 20 backlog items, 64 points.

| Issue | Task | Story Points | Owner | Reviewer | Dependencies | Parent Story |
|---|---|---:|---|---|---|---|
| [#202](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/202) | Refine backlog for Sprint 4 | 2 | @PhanDangVu | @Dangtooo | None | #PO |
| [#203](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/203) | Add authentication and authorization regression tests | 4 | @PhanDangVu | @taibaonguyen | #205 | #50 (US05) |
| [#204](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/204) | Complete upload validation boundary tests | 4 | @PhanDangVu | @taibaonguyen | #205 | #51 (US06) |
| [#205](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/205) | Verify the isolated pytest environment and baseline | 3 | @PhanDangVu | @Dangtooo | None | #50 (US05), #51 (US06) |
| [#206](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/206) | Hand over authentication and upload test evidence | 3 | @PhanDangVu | @Dangtooo | #203, #204, #205 | #50 (US05), #51 (US06) |
| [#207](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/207) | Document how to run the test suites | 3 | @Dangtooo | @PhanDangVu | #205, #210 | US01-US09 (#46-#54) |
| [#208](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/208) | Extend processing lifecycle and timeout regression tests | 4 | @Dangtooo | @PhanDangVu | #205 | #52 (US07) |
| [#209](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/209) | Compile the testing report and defect detection evidence | 3 | @Dangtooo | @PhanDangVu | #206, #216, #221, #210 | US01-US09 (#46-#54) |
| [#210](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/210) | Verify clean-clone test instructions and existing CI | 4 | @Dangtooo | @PhanDangVu | #203, #204, #208, #212-#215, #217-#219 | US01-US09 (#46-#54) |
| [#211](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/211) | Wrap up Sprint 4 and prepare the milestone submission | 2 | @Dangtooo | @PhanDangVu | #202, #209, #210 | #SM |
| [#212](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/212) | Extend AI label and concept validation tests | 4 | @duongbui0811 | @PhanDangVu | #205 | #49 (US04) |
| [#213](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/213) | Extend in-document search regression tests | 3 | @duongbui0811 | @PhanDangVu | #205 | #49 (US04) |
| [#214](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/214) | Extend evidence and citation integrity tests | 4 | @duongbui0811 | @PhanDangVu | #205 | #53 (US08) |
| [#215](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/215) | Extend citation-to-reader navigation tests | 3 | @duongbui0811 | @PhanDangVu | #205 | #54 (US09) |
| [#216](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/216) | Hand over label, evidence and reader test evidence | 2 | @duongbui0811 | @Dangtooo | #212, #213, #214, #215 | #49 (US04), #53 (US08), #54 (US09) |
| [#217](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/217) | Extend contract comparison table regression tests | 4 | @taibaonguyen | @PhanDangVu | #205 | #46 (US01) |
| [#218](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/218) | Extend cross-document search regression tests | 4 | @taibaonguyen | @duongbui0811 | #205 | #47 (US02) |
| [#219](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/219) | Extend bullet summary and action recommendation tests | 4 | @taibaonguyen | @PhanDangVu | #205 | #48 (US03) |
| [#220](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/220) | Review existing P0 interface regression coverage | 2 | @taibaonguyen | @Dangtooo | #203, #204, #215, #217-#219 | US01-US09 (#46-#54) |
| [#221](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/221) | Hand over table, search and summary test evidence | 2 | @taibaonguyen | @Dangtooo | #217, #218, #219, #220 | #46 (US01), #47 (US02), #48 (US03) |

**Total committed: 64 points across 20 tasks.**

### Story Coverage Matrix (US01-US09)

| User Story | Title | Covered Backlog Tasks |
|---|---|---|
| US01 (#46) | Upload multiple contracts and view financial comparison table | #217, #221, #207, #209, #210, #220 |
| US02 (#47) | Search across 20+ documents for relevant facts and figures | #218, #221, #207, #209, #210, #220 |
| US03 (#48) | Mobile-friendly bullet summary with action recommendations | #219, #221, #207, #209, #210, #220 |
| US04 (#49) | AI-suggested label with confidence and unverified warning | #212, #213, #216, #207, #209, #210, #220 |
| US05 (#50) | Sign in and access own documents securely | #203, #205, #206, #207, #209, #210, #220 |
| US06 (#51) | Validate upload format and size before processing | #204, #205, #206, #207, #209, #210, #220 |
| US07 (#52) | Track processing progress with live updates | #208, #207, #209, #210, #220 |
| US08 (#53) | Link each important summary point to exact document page | #214, #216, #207, #209, #210, #220 |
| US09 (#54) | Open citation at exact page in document reader | #215, #216, #207, #209, #210, #220 |

### Planning Board Capture

Sprint 4 planning board immediately after Planning:
- Board URL: [Sprint Board - Text Classification and Summarization Service](https://github.com/orgs/SE-FDA-NEU/projects/24/views/1)
- Initial status: 20 issues refined, estimated, and assigned to Sprint 4.

### Attendance

| Member | Planning | Review | Retro |
|---|---|---|---|
| @PhanDangVu | ✓ | TBD | TBD |
| @Dangtooo | ✓ | TBD | TBD |
| @duongbui0811 | ✓ | TBD | TBD |
| @taibaonguyen | ✓ | TBD | TBD |

---

## Sprint 3 - October 2026

### Sprint goal

Complete the P0 document workflows for US01-US09 and prepare the Milestone 3 UI report, running-app evidence and supporting setup/verification work.

### Roles

| Role | Member |
|---|---|
| Product Owner | @PhanDangVu |
| Scrum Master | @taibaonguyen |

The Scrum Master rotates from @duongbui0811 in Sprint 2.

### Committed

Scope: P0 stories US01-US09 and the supporting CI, fixture and reader-fix tasks. Each row represents one issue. Owners follow the issue records; all listed tasks are Done. Points are assigned retrospectively using the Fibonacci scale (1, 2, 3, 5, 8), based on relative complexity, effort and uncertainty. Tasks #68 and #70 were completed before Sprint 3 and are excluded.

| Issue | Task | Points | Owner | PR |
|---|---|---:|---|---|
| [#62](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/62) | Build the landing page with sign-in form | 3 | @Dangtooo | [#148](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/148) |
| [#63](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/63) | Add route guard middleware in Next.js | 2 | @Dangtooo | [#149](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/149) |
| [#64](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/64) | Test guest redirects and cross-account access denial | 3 | @PhanDangVu | [#150](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/150) |
| [#65](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/65) | Client-side file validation on the upload page | 3 | @PhanDangVu | [#151](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/151) |
| [#66](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/66) | Server-side file validation in POST /upload | 3 | @PhanDangVu | [#152](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/152) |
| [#67](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/67) | Test file rejection scenarios | 2 | @taibaonguyen | No linked PR recorded |
| [#69](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/69) | Implement async POST /upload that creates a job and returns jobId immediately | 5 | @Dangtooo | [#153](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/153) |
| [#71](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/71) | Implement per-document timeout logic with retry (BR02) | 5 | @Dangtooo | [#154](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/154) |
| [#72](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/72) | Build results page with live progress bar and status badge | 3 | @Dangtooo | [#155](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/155) |
| [#73](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/73) | Test job lifecycle: completed, timed_out, revisit after completion | 3 | @Dangtooo | [#156](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/156) |
| [#109](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/109) | Extract PDF text by page with stable source positions | 5 | @Dangtooo | [#157](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/157) |
| [#110](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/110) | Support DOCX and PPTX extraction with a stable reader representation | 8 | @Dangtooo | [#158](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/158) |
| [#111](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/111) | Connect extraction and result persistence to the existing job pipeline | 5 | @Dangtooo | [#159](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/159) |
| [#112](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/112) | Generate and validate structured evidence for AI claims | 5 | @Dangtooo | [#160](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/160) |
| [#113](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/113) | Persist evidence and expose it alongside saved results | 3 | @duongbui0811 | [#161](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/161) |
| [#114](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/114) | Build reusable citation badges and Unverified rendering | 3 | @duongbui0811 | [#162](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/162) |
| [#115](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/115) | Serve original and rendered document files to the reader | 3 | @duongbui0811 | [#163](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/163) |
| [#116](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/116) | Build the document reader with page controls and direct-link support | 5 | @duongbui0811 | [#164](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/164) |
| [#117](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/117) | Highlight cited evidence and handle unavailable highlighting | 5 | @duongbui0811 | [#165](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/165) |
| [#118](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/118) | Preserve Back to Results and workspace return navigation | 2 | @duongbui0811 | [#166](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/166) |
| [#119](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/119) | Predict and persist AI labels with confidence | 5 | @duongbui0811 | [#167](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/167) |
| [#120](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/120) | Display AI labels and confidence badges in workspace and reader | 2 | @duongbui0811 | [#168](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/168) |
| [#121](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/121) | Add in-document search, match navigation and highlighting | 5 | @duongbui0811 | [#169](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/169) |
| [#122](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/122) | Generate and persist a source-grounded concept overview | 5 | @duongbui0811 | [#170](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/170) |
| [#123](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/123) | Build the analysis-mode selector and render concept results | 3 | @duongbui0811 | [#171](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/171) |
| [#124](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/124) | Connect financial-clause mode to the existing batch upload flow | 3 | @taibaonguyen | [#172](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/172) |
| [#125](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/125) | Extract and save financial-clause comparison data | 5 | @taibaonguyen | [#173](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/173) |
| [#126](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/126) | Render the comparison table with citations and mobile cards | 5 | @taibaonguyen | [#174](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/174) |
| [#127](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/127) | Generate bullets and source-grounded recommended actions | 5 | @taibaonguyen | [#175](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/175) |
| [#128](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/128) | Render bullet summaries, actions and their citations | 3 | @taibaonguyen | [#176](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/176) |
| [#129](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/129) | Finish responsive upload and results layouts at 375 px | 3 | @taibaonguyen | [#177](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/177) |
| [#130](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/130) | Index document content by owner, document and page | 5 | @taibaonguyen | [#178](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/178) |
| [#131](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/131) | Implement cross-document search with ranked snippets | 5 | @taibaonguyen | [#179](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/179) |
| [#132](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/132) | Complete the workspace document list and content-search UI | 5 | @taibaonguyen | [#180](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/180) |
| [#144](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/144) | Make CI run the actual backend and frontend checks | 3 | @taibaonguyen | [#192](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/192) |
| [#145](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/145) | Prepare acceptance fixtures for the remaining features | 5 | @taibaonguyen | [#193](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/193) |
| [#194](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/194) | Fix file reader | 3 | Unassigned | [#195](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/195) |

**Total committed: 146 points across 37 tasks.**

### Result

| Issue | Points | Status | If not done, why |
|---|---:|---|---|
| [#62](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/62) | 3 | Done | - |
| [#63](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/63) | 2 | Done | - |
| [#64](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/64) | 3 | Done | - |
| [#65](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/65) | 3 | Done | - |
| [#66](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/66) | 3 | Done | - |
| [#67](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/67) | 2 | Done | - |
| [#69](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/69) | 5 | Done | - |
| [#71](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/71) | 5 | Done | - |
| [#72](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/72) | 3 | Done | - |
| [#73](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/73) | 3 | Done | - |
| [#109](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/109) | 5 | Done | - |
| [#110](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/110) | 8 | Done | - |
| [#111](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/111) | 5 | Done | - |
| [#112](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/112) | 5 | Done | - |
| [#113](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/113) | 3 | Done | - |
| [#114](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/114) | 3 | Done | - |
| [#115](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/115) | 3 | Done | - |
| [#116](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/116) | 5 | Done | - |
| [#117](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/117) | 5 | Done | - |
| [#118](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/118) | 2 | Done | - |
| [#119](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/119) | 5 | Done | - |
| [#120](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/120) | 2 | Done | - |
| [#121](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/121) | 5 | Done | - |
| [#122](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/122) | 5 | Done | - |
| [#123](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/123) | 3 | Done | - |
| [#124](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/124) | 3 | Done | - |
| [#125](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/125) | 5 | Done | - |
| [#126](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/126) | 5 | Done | - |
| [#127](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/127) | 5 | Done | - |
| [#128](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/128) | 3 | Done | - |
| [#129](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/129) | 3 | Done | - |
| [#130](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/130) | 5 | Done | - |
| [#131](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/131) | 5 | Done | - |
| [#132](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/132) | 5 | Done | - |
| [#144](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/144) | 3 | Done | - |
| [#145](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/145) | 5 | Done | - |
| [#194](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/194) | 3 | Done | - |

| Metric | Result |
|---|---|
| Completed tasks | 37 / 37 |
| Completion rate | 100% |
| Completed points | 146 points |
| Story-point velocity (retrospective) | 146 points |

### Merged pull requests

All 36 merged PRs linked to the committed issues are listed below. Closed issue [#67](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/67) has no linked PR recorded.

| PR | Issue | Change | Author | Approval by another member |
|---|---|---|---|---|
| [#148](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/148) | [#62](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/62) | Build the landing page with sign-in form | @Dangtooo | @PhanDangVu |
| [#149](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/149) | [#63](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/63) | Add route guard middleware in Next.js | @Dangtooo | @PhanDangVu |
| [#150](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/150) | [#64](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/64) | Test guest redirects and cross-account access denial | @PhanDangVu | @duongbui0811 |
| [#151](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/151) | [#65](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/65) | Client-side file validation on the upload page | @PhanDangVu | @taibaonguyen |
| [#152](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/152) | [#66](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/66) | Server-side file validation in POST /upload | @PhanDangVu | @Dangtooo, @taibaonguyen |
| [#153](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/153) | [#69](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/69) | Implement async POST /upload that creates a job and returns jobId immediately | @Dangtooo | @PhanDangVu |
| [#154](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/154) | [#71](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/71) | Implement per-document timeout logic with retry (BR02) | @Dangtooo | @PhanDangVu |
| [#155](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/155) | [#72](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/72) | Build results page with live progress bar and status badge | @Dangtooo | @PhanDangVu |
| [#156](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/156) | [#73](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/73) | Test job lifecycle: completed, timed_out, revisit after completion | @Dangtooo | @PhanDangVu |
| [#157](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/157) | [#109](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/109) | Extract PDF text by page with stable source positions | @Dangtooo | @PhanDangVu |
| [#158](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/158) | [#110](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/110) | Support DOCX and PPTX extraction with a stable reader representation | @Dangtooo | @PhanDangVu |
| [#159](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/159) | [#111](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/111) | Connect extraction and result persistence to the existing job pipeline | @Dangtooo | @duongbui0811 |
| [#160](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/160) | [#112](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/112) | Generate and validate structured evidence for AI claims | @Dangtooo | @duongbui0811 |
| [#161](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/161) | [#113](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/113) | Persist evidence and expose it alongside saved results | @duongbui0811 | @Dangtooo |
| [#162](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/162) | [#114](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/114) | Build reusable citation badges and Unverified rendering | @duongbui0811 | @Dangtooo |
| [#163](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/163) | [#115](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/115) | Serve original and rendered document files to the reader | @duongbui0811 | @Dangtooo |
| [#164](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/164) | [#116](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/116) | Build the document reader with page controls and direct-link support | @duongbui0811 | @Dangtooo |
| [#165](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/165) | [#117](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/117) | Highlight cited evidence and handle unavailable highlighting | @duongbui0811 | @Dangtooo |
| [#166](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/166) | [#118](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/118) | Preserve Back to Results and workspace return navigation | @duongbui0811 | @Dangtooo |
| [#167](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/167) | [#119](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/119) | Predict and persist AI labels with confidence | @duongbui0811 | @Dangtooo |
| [#168](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/168) | [#120](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/120) | Display AI labels and confidence badges in workspace and reader | @duongbui0811 | @Dangtooo |
| [#169](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/169) | [#121](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/121) | Add in-document search, match navigation and highlighting | @duongbui0811 | @Dangtooo |
| [#170](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/170) | [#122](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/122) | Generate and persist a source-grounded concept overview | @duongbui0811 | @Dangtooo |
| [#171](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/171) | [#123](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/123) | Build the analysis-mode selector and render concept results | @duongbui0811 | @PhanDangVu |
| [#172](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/172) | [#124](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/124) | Connect financial-clause mode to the existing batch upload flow | @taibaonguyen | @PhanDangVu |
| [#173](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/173) | [#125](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/125) | Extract and save financial-clause comparison data | @taibaonguyen | @PhanDangVu |
| [#174](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/174) | [#126](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/126) | Render the comparison table with citations and mobile cards | @taibaonguyen | @PhanDangVu |
| [#175](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/175) | [#127](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/127) | Generate bullets and source-grounded recommended actions | @taibaonguyen | @PhanDangVu |
| [#176](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/176) | [#128](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/128) | Render bullet summaries, actions and their citations | @taibaonguyen | @PhanDangVu |
| [#177](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/177) | [#129](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/129) | Finish responsive upload and results layouts at 375 px | @taibaonguyen | @PhanDangVu |
| [#178](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/178) | [#130](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/130) | Index document content by owner, document and page | @taibaonguyen | @PhanDangVu |
| [#179](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/179) | [#131](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/131) | Implement cross-document search with ranked snippets | @taibaonguyen | @PhanDangVu |
| [#180](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/180) | [#132](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/132) | Complete the workspace document list and content-search UI | @taibaonguyen | @PhanDangVu |
| [#192](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/192) | [#144](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/144) | Make CI run the actual backend and frontend checks | @taibaonguyen | @PhanDangVu |
| [#193](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/193) | [#145](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/145) | Prepare acceptance fixtures for the remaining features | @taibaonguyen | @PhanDangVu |
| [#195](https://github.com/SE-FDA-NEU/G6_AI66A_SE/pull/195) | [#194](https://github.com/SE-FDA-NEU/G6_AI66A_SE/issues/194) | Fix file reader | @PhanDangVu | @Dangtooo |

### Sprint Review

| Item | Record |
|---|---|
| Delivered workflows | Sign-in, validated upload, processing progress, financial comparison, bullet/action and concept results, document search, citations and reader highlighting. |
| Supporting completed work | Native Office reading, Vietnamese/English support, CI, acceptance fixtures, regression verification and documentation. |
| Running-app evidence | [UI report](ui.md): Login, four Workspace states, valid/invalid upload, processing/completion, saved summary and highlighted citation. |
| Planning and end-board captures | [Start](images/ui/start.png), [End](images/ui/end.png). |
| Documentation | [SETUP](SETUP.md), [design](design.md), [traceability](traceability.md) and [P0 screen flow](screen-flow.mmd). |
| Instructor/user feedback | Not recorded. |

### Retrospective

The following improvement actions are proposed for the next sprint.

| Keep doing | Stop doing | Start doing |
|---|---|---|
| Split frontend/backend work into linked tasks and review PRs before merging. | Letting UI screenshots and documentation drift from the implementation. | Update screenshots and traceability with each changed workflow. |
| Preserve source citations and verify AI output against documents. | Leaving point estimates until after the sprint. | Agree on issue points during Planning and confirm completed points during Review. |

**Next-sprint action:** keep the setup guide, UI report and traceability synchronized with merged changes. **Owner:** @taibaonguyen.

### Attendance

| Member | Planning | Review | Retro |
|---|---|---|---|
| @PhanDangVu | TBD | TBD | TBD |
| @Dangtooo | TBD | TBD | TBD |
| @duongbui0811 | TBD | TBD | TBD |
| @taibaonguyen | TBD | TBD | TBD |

---

## Sprint 2 — Sep 22 to Oct 5

<!-- Sprint 1: weeks 5-6 | Sprint 2: 7-8 | Sprint 3: 9-10 | Sprint 4: 11-12 | Sprint 5: 13-14 -->

### Sprint goal

Design the database schema, implement data models and authentication, and document the API so the team can build features on a proven foundation in Sprint 3.

### Committed

| Issue | Story | Points | Owner         |
| ----- | ----- | ------ | ------------- |
| #58   | —     | 2      | @taibaonguyen |
| #74   | —     | 3      | @taibaonguyen |
| #91   | —     | 3      | @taibaonguyen |
| #59   | US05  | 3      | @PhanDangVu   |
| #60   | US05  | 2      | @PhanDangVu   |
| #76   | —     | 2      | @PhanDangVu   |
| #86   | —     | 1      | @PhanDangVu   |
| #75   | —     | 5      | @duongbui0811 |
| #61   | US05  | 3      | @duongbui0811 |
| #88   | —     | 2      | @duongbui0811 |
| #95   | —     | 2      | @duongbui0811 |
| #92   | —     | 3      | @duongbui0811 |
| #83   | —     | 2      | @Dangtooo     |
| #93   | —     | 2      | @Dangtooo     |
| #99   | —     | 1      | @PhanDangVu   |

**Total committed: 36 points**

### Result

| Issue | Points | Status | If not done, why |
| ----- | ------ | ------ | ---------------- |
| #58   | 2      | Done   |                  |
| #74   | 3      | Done   |                  |
| #91   | 3      | Done   |                  |
| #59   | 3      | Done   |                  |
| #60   | 2      | Done   |                  |
| #76   | 2      | Done   |                  |
| #86   | 1      | Done   |                  |
| #75   | 5      | Done   |                  |
| #61   | 3      | Done   |                  |
| #88   | 2      | Done   |                  |
| #95   | 2      | Done   |                  |
| #92   | 3      | Done   |                  |
| #83   | 2      | Done   |                  |
| #93   | 2      | Done   |                  |
| #99   | 1      | Done   |                  |

**Completed: 36 points. Velocity this sprint: 36**

### Sprint Review

- What we demonstrated: Walking Skeleton — `GET /documents` returns 12 seeded rows from MySQL, proving the full stack (FastAPI → SQLAlchemy → MySQL) works end-to-end.
- Feedback received: Instructor confirmed the API design covers all user stories; suggested adding pagination early.
- Backlog changes as a result: Created #95 to add seed data for demo; pagination parameters already included in `GET /documents`.

### Retrospective

| Keep doing                                      | Stop doing                | Start doing                       |
| ----------------------------------------------- | ------------------------- | --------------------------------- |
| Splitting docs and backend into separate issues | Merging without PR review | Requiring 1 approval before merge |

### Attendance

| Member        | Planning | Review | Retro |
| ------------- | -------- | ------ | ----- |
| @PhanDangVu   | ✓        | ✓      | ✓     |
| @Dangtooo     | ✓        | ✓      | ✓     |
| @duongbui0811 | ✓        | ✓      | ✓     |
| @taibaonguyen | ✓        | ✓      | ✓     |
