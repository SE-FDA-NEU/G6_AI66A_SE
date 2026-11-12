# Bàn giao deploy frontend Next.js lên Render

Người phụ trách: Tai (@taibaonguyen). Task: #253, #254, #255.

## 1. Nhận thông tin từ Dang

- Backend origin đang kiểm tra: `https://documind-n9ny.onrender.com`, không có / cuối. Xác nhận với Dang đây là backend phát hành.
- Health URL phải trả HTTP 200: [backend health](https://documind-n9ny.onrender.com/health).
- Main SHA phát hành và link CI xanh; frontend/backend dùng cùng SHA.
- Hai tài khoản demo thông thường, gửi theo kênh thống nhất.
- Liên hệ: Dang phụ trách backend, Duong phụ trách TiDB/storage.

Kiểm tra backend đã có đăng ký, /health và restart recovery. Không cần nhận DB
password, JWT secret hoặc provider API key để deploy frontend.

## 2. Tạo frontend Web Service

Render → New → Web Service → kết nối repo `SE-FDA-NEU/G6_AI66A_SE`.

Hoặc dùng New → Blueprint với `render.yaml` ở root repo. Blueprint chỉ quản lý
frontend; nhập BACKEND_ORIGIN khi tạo. Cấu hình mẫu dùng Free để thử; thống nhất
plan và region với nhóm trước khi nghiệm thu. Không tạo thêm backend bằng blueprint này.

| Mục | Giá trị |
|---|---|
| Name | `documind-web` hoặc tên còn trống |
| Branch | `main` |
| Runtime | Node |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Start Command | `npm start` |
| Region | Ưu tiên cùng vùng với backend |
| Auto-Deploy | After CI Checks Pass |

Tạo ba biến môi trường:

```dotenv
NODE_ENV=production
NODE_VERSION=24
BACKEND_ORIGIN=https://<tên-backend>.onrender.com
```

Dùng Web Service vì ứng dụng có SSR, session lookup và API rewrites. Không dùng
Static Site hoặc static export. `npm start` bind `0.0.0.0` và đọc `PORT` do Render
cung cấp (mặc định Next.js là 3000 khi host không đặt PORT). Có thể ghi đè host/port
bằng `npm start -- --hostname <host> --port <port>`. Không chạy next dev.

BACKEND_ORIGIN phải có ở cả build và runtime: rewrites lấy giá trị khi build,
session lookup đọc lúc chạy. Đổi biến này phải build/deploy lại. Không dùng
localhost, URL frontend hoặc thêm /api vào cuối origin.

Build/start production sẽ báo lỗi khi thiếu BACKEND_ORIGIN, origin có path,
credentials/query/fragment hoặc trỏ về loopback. Start cũng đối chiếu sáu rewrite
trong `.next/routes-manifest.json` với origin runtime và từ chối chạy khi lệch.
Origin HTTPS public ở trên giúp đường Next.js → backend được mã hóa.

Frontend không cần persistent disk cho dữ liệu ứng dụng; tài liệu do backend
lưu. Có thể dùng Free để thử tạm nhưng phải tính sleep/cold start và yêu cầu
giữ ứng dụng online đến lúc chấm.

## 3. Giữ nguyên proxy và session

Browser gọi API trên cùng domain frontend:

| Đường dẫn frontend | Đích backend |
|---|---|
| `/auth/:path*` | `/auth/:path*` |
| `/jobs/:path*` | `/jobs/:path*` |
| `/api/upload` | `/upload` |
| `/api/search` | `/search` |
| `/api/folders` | `/folders` |
| `/api/documents/:path*` | `/documents/:path*` |

Giữ rewrites trong frontend/next.config.mjs và các request tương đối của browser.
Không chuyển JWT sang localStorage hoặc cho browser gọi backend cross-origin
chỉ để sửa lỗi cấu hình.

Session lookup phía server trong frontend/lib/session.js chuyển cookie của
request tới backend. Qua HTTPS, xác nhận cookie trên domain frontend có HttpOnly,
Secure và SameSite=Lax. Backend phải xử lý đúng forwarded HTTPS headers.

Backend owner phải xác nhận Uvicorn `--proxy-headers` và `--forwarded-allow-ips`
phù hợp với proxy trực tiếp của Render. Chỉ tin địa chỉ/mạng proxy đã xác định;
không tin mọi nguồn khi backend còn truy cập trực tiếp được. TLS edge phải ghi đè
forwarded headers của client. Không tự lấy header bất kỳ để quyết định Secure.
Vì frontend gọi backend public HTTPS, backend cũng phải nhận biết HTTPS trên hop
này. Xác minh bằng Set-Cookie thực tế qua URL frontend, không suy từ health 200.

Luồng same-origin này thường không cần mở CORS. Không bật wildcard origins kèm
credentials để che lỗi proxy.

## 4. Deploy và thử từ đầu đến cuối

Bấm Create Web Service / Deploy, đọc Events/Logs rồi mở URL public:

1. Mở trình duyệt ẩn danh: trang chủ hiển thị; vào /workspace khi chưa đăng nhập
   phải quay về trang chủ.
2. Đăng ký tài khoản mới: vào workspace riêng, không thấy dữ liệu người khác.
3. Đăng xuất, đăng nhập lại, F5 và mở lại trang: session còn hợp lệ.
4. DevTools → Application → Cookies: kiểm tra documind_session có HttpOnly,
   Secure và SameSite=Lax trên domain frontend.
5. Network: auth/upload/jobs/search đi qua domain frontend, không còn localhost.
6. Upload, chạy Table/Bullet/Concept, mở lịch sử, citation, reader và PDF export.
7. Kiểm tra hai tài khoản, tìm kiếm trên ít nhất 20 tài liệu.
8. Thử laptop và điện thoại 375 px, không cần cài đặt/VPN.
9. Đối chiếu SHA trong Render Events của frontend/backend với SHA phát hành.

Session lookup hiện timeout sau năm giây. Backend đang sleep hoặc không truy cập
được có thể khiến người đã đăng nhập bị chuyển về trang chủ. Kiểm tra health và
độ sẵn sàng backend trước khi sửa auth.

## 5. Kiểm tra upload lớn qua URL public

Phải thử năm file hợp lệ gần 5 MiB mỗi file: tổng gần 25 MiB cộng multipart
overhead. Thử qua browser → Next.js → FastAPI, không chỉ gọi trực tiếp backend.

Config đã đặt `experimental.proxyClientMaxBodySize: '30mb'`, đồng thời giữ
`agentUpgrade: 'security'`. Bài thử production trước thay đổi đã ghi cảnh báo
body vượt 10 MB trên `/api/upload`; cần giữ bài thử 25 MiB để ngăn lỗi quay lại.

Proxy matcher bảo vệ các trang workspace/upload/results/documents, không match
/api/upload. Tuy nhiên bản Next.js đang cài tạo cloneable body trước khi match
route; bài thử đã chứng minh external rewrite bị ảnh hưởng. Setting Server
Actions hoặc API body parser không điều khiển giới hạn này.

Kiểm tra lỗi 413/502, file thiếu hoặc bị cắt, polling và timeout. POST upload phải
trả jobId; xử lý AI chạy nền và browser polling /jobs, không chờ toàn bộ AI trong
một request upload. Không âm thầm giảm giới hạn nghiệp vụ để khớp host.

Kiểm tra thêm PDF download/range khi có dùng, nhảy citation, Back to Results và
dữ liệu sau F5. Nếu giới hạn cứng của nền tảng không đáp ứng, đổi cấu hình/hosting.

## 6. Ghi bằng chứng và bàn giao

Ghi kết quả thực tế:

| Commit SHA | Thời gian | Thiết bị/viewport | Input/thao tác | Mong đợi | Thực tế | Bằng chứng |
|---|---|---|---|---|---|---|
| <điền> | <điền> | <điền> | <điền> | <điền> | <điền> | <điền> |

Cập nhật README với URL frontend, CI badge main, hướng dẫn tài khoản demo đúng
quyền và thao tác bắt đầu P0. Cập nhật SETUP với BACKEND_ORIGIN, lệnh production
và health URL; secret dùng placeholder. Giữ nguyên hướng dẫn test cô lập.

Gửi URL, SHA, CI link và kết quả nghiệm thu cho Vu viết operations/release.
Phối hợp Dang thử rollback cặp frontend/backend tương thích ở staging; kiểm tra
lại login, DB/file và reader. Code rollback không khôi phục dữ liệu DB hoặc file.

## 6a. Kiểm thử production trước khi tạo service

Cài Python dependencies và browser theo [SETUP](SETUP.md), sau đó từ `frontend`:

```powershell
npm.cmd ci
npm.cmd run test:config
npm.cmd run test:production
```

`test:production` chạy `npm run build` rồi `npm start -- --port 18000` cùng một
BACKEND_ORIGIN trên IPv4 interface của máy, không dùng loopback làm rewrite target.
Fixture backend bind `0.0.0.0:18001` chỉ trong bài test, dùng SQLite/storage tạm
và không gọi AI. Chạy trên máy/mạng tin cậy, giữ hai port trống. Test không thay
đổi backend Render. Trên Linux/macOS bỏ hậu tố `.cmd`.

Các bài thử bao gồm login/logout, reload, JWT hết hạn/giả mạo, SSR, sáu nhóm API,
Secure/HttpOnly/SameSite và upload 25 MiB với kích thước từng file chính xác.
CI chạy các bài này trong check `Node build and tests` hiện có.
Kiểm thử proxy tin cậy/không tin cậy phía backend:

```powershell
cd backend
& ./.venv/Scripts/python.exe -m pytest tests/test_proxy_session.py tests/test_auth_authorization.py -q
```

Đây là kiểm thử local của bản production và hợp đồng proxy; chưa thay cho xác
nhận cấu hình Render/backend owner, nghiệm thu HTTPS public và rollback #252.

## 7. Xử lý lỗi thường gặp

| Triệu chứng | Kiểm tra |
|---|---|
| Không mở được service | Start command bind 0.0.0.0:$PORT |
| Login/upload 502 | BACKEND_ORIGIN, backend health; rebuild sau đổi biến |
| Login thành công rồi quay về trang chủ | Cookie, SSR origin, HTTPS headers, timeout năm giây |
| Có lịch sử nhưng reader lỗi | Backend disk/path migration; liên hệ Dang/Duong |
| Upload lớn lỗi/cắt file | Giới hạn proxy/middleware/host và multipart overhead |
| /health 404 | Sai backend URL hoặc deploy sai commit |
| AI quota/timeout | Backend provider; không thêm key vào frontend |

## Nguồn tham khảo

- [Render: deploy Next.js](https://render.com/docs/deploy-nextjs-app)
- [Render: service và port](https://render.com/docs/web-services)
- [Render: CI gate](https://render.com/docs/deploys)
- [Render: giới hạn Free](https://render.com/docs/free)
- [Next.js: proxy body size](https://nextjs.org/docs/app/api-reference/config/next-config-js/proxyClientMaxBodySize)
- [Render: Blueprint fields](https://render.com/docs/blueprint-spec)
- [Uvicorn: proxy headers and trusted peers](https://uvicorn.dev/settings/)

Kết quả kiểm thử và phần nghiệm thu còn lại của #253:
[frontend deployment evidence](evidence/m5/frontend-deployment-253.md).
