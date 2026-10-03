# Sprint log

One section per sprint. Fill it in **during** the sprint, not the night before
the milestone deadline - the commit timestamps on this file are part of the
evidence that the process was real.

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
