# Quy tắc nghiệp vụ của hệ thống

Tài liệu này định nghĩa 6 quy tắc nghiệp vụ cốt lõi cho hệ thống AI phân loại, tóm tắt và tra cứu tài liệu. Mỗi quy tắc đều có ví dụ số liệu thực tế để hỗ trợ quá trình phát triển và kiểm thử.

## BR-01: Giới hạn tệp tải lên

Hệ thống chỉ chấp nhận các tệp có định dạng **PDF, DOCX hoặc PPTX**, dung lượng không vượt quá **25 MB/tệp** và tối đa **10 tệp trong một lần tải lên**. Tệp không đáp ứng một trong các điều kiện trên phải bị từ chối trước khi đưa vào hàng đợi xử lý.

**Ví dụ:** Người dùng chọn 8 tệp PDF, mỗi tệp có dung lượng 12 MB. Cả 8 tệp đều được chấp nhận. Nếu người dùng chọn thêm một tệp PDF có dung lượng 31 MB, hệ thống từ chối riêng tệp 31 MB và vẫn cho phép xử lý 8 tệp hợp lệ.

## BR-02: Tính thời gian xử lý tài liệu

Thời gian xử lý tối đa cho một tài liệu được tính theo công thức: **30 giây cơ bản + 3 giây cho mỗi trang**, nhưng không vượt quá **300 giây**. Nếu quá thời gian này mà chưa hoàn thành, tác vụ được đánh dấu là `Quá thời gian` và hệ thống tự động thử lại tối đa **2 lần**.

**Ví dụ:** Một tài liệu dài 40 trang có thời gian xử lý tối đa là `30 + (40 × 3) = 150 giây`. Nếu cả lần đầu và 2 lần thử lại đều vượt quá 150 giây, tác vụ kết thúc ở trạng thái `Thất bại` sau tổng cộng 3 lần xử lý.

## BR-03: Giới hạn độ dài bản tóm tắt

Bản tóm tắt phải có độ dài từ hơn **100 từ** và không nhiều hơn **1.000 từ**. Các giới hạn tối thiểu và tối đa được ưu tiên khi tỷ lệ phần trăm nằm ngoài khoảng cho phép.

**Ví dụ:** Với tài liệu 5.000 từ, bản tóm tắt hợp lệ phải dài từ 100 đến 1.000 từ. Nếu AI tạo ra 1.250 từ, hệ thống phải rút gọn kết quả xuống tối đa 1.000 từ trước khi hiển thị.

## BR-04: Ngưỡng tin cậy khi phân loại tài liệu

Hệ thống chỉ tự động gán danh mục khi độ tin cậy của mô hình đạt từ **80% trở lên**. Nếu độ tin cậy thấp hơn 80%, tài liệu phải được gắn trạng thái `Cần xác nhận` để người dùng chọn danh mục thủ công.

**Ví dụ:** Một hợp đồng được mô hình phân loại vào nhóm `Hợp đồng kinh tế` với độ tin cậy 87% sẽ được tự động gán nhóm. Một báo cáo khác chỉ đạt 72% sẽ không được tự động phân loại và phải chờ người dùng xác nhận.

## BR-05: Bắt buộc truy xuất nguồn cho thông tin quan trọng

Mọi số liệu, ngày tháng, tỷ lệ phần trăm và điều khoản được đưa vào bản tóm tắt phải có ít nhất **1 trích dẫn** liên kết đến đúng tài liệu và số trang gốc. Nếu không tìm được nguồn, nội dung đó không được trình bày như một dữ kiện đã xác minh và phải được gắn nhãn `Chưa xác minh`.

**Ví dụ:** Bản tóm tắt nêu “Phạt chậm thanh toán 0,05% mỗi ngày” thì phải kèm liên kết đến, chẳng hạn, trang 12 của hợp đồng. Nếu hệ thống không xác định được trang nguồn, con số 0,05% phải mang nhãn `Chưa xác minh` để người dùng kiểm tra lại.

## BR-06: Chính sách lưu trữ và xóa tài liệu

Tài liệu của tài khoản thông thường được lưu trong **90 ngày** kể từ lần truy cập cuối cùng. Hệ thống gửi cảnh báo trước **7 ngày** và tự động xóa tài liệu khi hết hạn. Mỗi lần người dùng mở, tải xuống hoặc cập nhật tài liệu, thời hạn 90 ngày được tính lại từ đầu.

**Ví dụ:** Một tài liệu được truy cập lần cuối vào ngày 01/03/2026 sẽ hết hạn vào ngày 30/05/2026. Hệ thống gửi cảnh báo vào ngày 23/05/2026. Nếu người dùng mở lại tài liệu vào ngày 25/05/2026, ngày hết hạn mới sẽ được chuyển thành 23/08/2026.

