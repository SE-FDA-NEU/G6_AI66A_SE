https://documind-web-k6i1.onrender.com

[![CI](https://github.com/SE-FDA-NEU/G6_AI66A_SE/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SE-FDA-NEU/G6_AI66A_SE/actions/workflows/ci.yml)

# DocuMind

## Production demo

Open the public URL above and sign in. This is an ordinary user account with synthetic documents; it has no administrator privileges.

| Email | Demo password | Role |
|---|---|---|
| test@gmail.com | 12345678 | Standard user |

The demo corpus contains at least 21 documents, saved Table/Bullet/Concept results and source citations. A valid Gemini key is required for new AI processing; do not commit or publish API keys. The demo sign-in and live AI were verified on 13 November 2026. The v1.0 release is pending deployment-SHA verification and final acceptance.

| P0 story | Starting clicks after sign-in |
|---|---|
| US01 — Contract comparison | Choose files → So sánh điều khoản → Tải lên và phân tích |
| US02 — Cross-document search | Workspace → Tìm kiếm tài liệu → enter a query → Tìm kiếm (entry restored by PR #271; public deployment pending) |
| US03 — Bullet summary | Choose files → Đọc nhanh ý chính → Tải lên và phân tích |
| US04 — Labels, concepts and reader search | Choose files → Hiểu các khái niệm; open a saved document to inspect its label and search text |
| US05 — Private workspace | Landing → Đăng nhập; Đăng xuất returns to the landing page |
| US06 — Upload validation | Workspace → Chọn tệp tài liệu; select six files or an unsupported/oversized file |
| US07 — Progress and failures | Upload a batch → Results; reopen its saved job to check persisted status |
| US08 — Source evidence | Results → citation beside a claim; inspect Chưa xác thực warnings |
| US09 — Exact-page reader | Citation → reader page/highlight → Về kết quả |

Local setup and isolated tests: [docs/SETUP.md](docs/SETUP.md). Operations: [docs/operations.md](docs/operations.md). Release evidence: [docs/release-acceptance.md](docs/release-acceptance.md).

Công cụ tóm tắt và phân loại văn bản, hệ thống hoá các thư mục.

**Group:** G6_AI66A
**Product Owner:** @PhanDangVu
**Scrum Master (Sprint 5):** @taibaonguyen
**Board:** [Sprint Board - Text Classification and Summarization Service](https://github.com/orgs/SE-FDA-NEU/projects/24/views/1)

---

## Team

| Thành viên | GitHub | Vai trò |
| :--- | :--- | :--- |
| Phan Dang Vu | @PhanDangVu | Product Owner |
| To Hien Hai Dang | @Dangtooo | Scrum Master (Sprint 1) |
| Bui Dang Duong | @duongbui0811 | Member |
| Nguyen Bao Tai | @taibaonguyen | Scrum Master (Sprint 5) |
---

## Scrum Master rotation

| Sprint | 1 | 2 | 3 | 4 | 5 |
| :--- | :--- | :--- | :--- | :--- | --- |
| Scrum Master | @Dangtooo | @duongbui0811 | @taibaonguyen | @Dangtooo | @taibaonguyen |
---

## Definition of Done

Xem chi tiết tại [docs/definition-of-done.md](docs/definition-of-done.md) — tất cả 8 tiêu chí bắt buộc phải được đáp ứng; không được bỏ qua tiêu chí nào.
---

## Running the Project

Local setup: [SETUP](docs/SETUP.md). Production frontend on Render:
[deployment guide](docs/deploy-frontend-render.md), with a frontend-only
[Blueprint](render.yaml). The public URL is listed above; deployment SHA and release acceptance remain
tracked in [release evidence](docs/release-acceptance.md).

Follow [docs/SETUP.md](docs/SETUP.md) for local MySQL configuration, dependencies, startup and isolated backend/frontend tests. Production is accessed through the public HTTPS URL; local startup is separate.

---

## If a member stops responding
Sau 3 ngày: Scrum Master nhắn tin riêng. Sau 5 ngày: nhóm báo cáo giảng viên và phân phối lại công việc.


