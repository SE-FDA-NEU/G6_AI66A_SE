# Task #254 — public P0 flows and production proxy limits

Frontend: https://documind-web-k6i1.onrender.com
Backend: https://documind-n9ny.onrender.com (`/health` → `{"status":"ok","database":"ready"}`)
Repo `main` at test time: `9ea6972993dff59ee0731128aeebdfe3c6812d27`.
Deployed SHA (Render Events frontend/backend): **<điền từ Render>**

## Run 1 — automated HTTP smoke via public proxy (2026-11-13 03:15–03:18 UTC)

Client: macOS, Node 26.12.1, `fetch` with cookie jar (browser-equivalent requests
through the Next.js domain only). Script: [p254/public-smoke.mjs](p254/public-smoke.mjs),
raw output: [p254/public-smoke-2026-11-13.log](p254/public-smoke-2026-11-13.log).
Throwaway accounts `p254_a_mweem02o1eaa`, `p254_b_mweepjoi5365` (`@example.com`).

| Input/thao tác | Mong đợi | Thực tế | Kết quả |
|---|---|---|---|
| Cold start `/` (lần đầu trong ngày) | Trang chủ hiển thị | 200 sau ~33 s (Free plan sleep) | Pass, ghi nhận cold start |
| `/workspace` khi chưa đăng nhập | Về `/` | 307 → `/` | Pass |
| Đăng ký tài khoản A | 201 + cookie an toàn | 201; `documind_session` có `HttpOnly; Secure; SameSite=lax; Path=/` | Pass |
| `/auth/me` với cookie A | 200, đúng user | 200 | Pass |
| Upload 5 PDF × 5,238,784 B (24.98 MiB) qua `/api/upload` | 202 + jobId, không 413/502 | 202 `jobId=60001` sau 16.7 s | Pass |
| Polling `/jobs/60001` mỗi 5 s | 200, tiến độ tăng | 200 suốt; 0→1→2→3/5 | Pass |
| Kết quả job | `completed` 5/5 | **`failed` sau 134 s, 3/5 hoàn thành** | **Fail — cần điều tra** |
| Tải lại 5 file gốc | 200, SHA-256 trùng input | 5/5 trùng, 0.4–0.7 s mỗi file | Pass |
| `Range: bytes=0-15` | 206, đúng Content-Range/bytes | 206 `bytes 0-15/5238784`, `%PDF-1.4\n1 0 obj` | Pass |
| Search "Proxy check" (A) | Có kết quả từ file của A | 200, `total_hits=3` (3 file đã xử lý) | Pass |
| Tài khoản B: danh sách tài liệu | Không thấy tài liệu của A | 0 tài liệu | Pass |
| B truy cập document/file/job của A | Bị từ chối | 403 / 403 / 404 | Pass |
| B search "Proxy check" | 0 kết quả | 0 | Pass |
| Logout A | 204, xóa cookie | 204, `Max-Age=0` | Pass |

### Mở: job 60001 failed 2/5 file

Job-level `failed` nghĩa là ít nhất một file thất bại; file 4–5 kết thúc nhanh
sau file 3 nên có khả năng là lỗi AI provider (quota/rate limit) thay vì timeout.
Cần backend owner xem log Render backend `job=60001` (document 60004, 60005) hoặc
`job_files.error_message`, sửa rồi chạy lại script này.

## Còn lại (thủ công, trình duyệt ẩn danh)

- [ ] Ghi SHA deploy frontend/backend từ Render Events.
- [ ] US01–US09 từ màn đầu trên laptop và điện thoại thật (375 px), không cài đặt/VPN.
- [ ] Table/Bullet/Concept, citation → reader, Back to Results, PDF export, F5 giữ dữ liệu.
- [ ] Search trên tài khoản có ≥20 tài liệu.
- [ ] Chạy lại upload 5 file sau khi sửa lỗi job, xác nhận `completed` 5/5.
