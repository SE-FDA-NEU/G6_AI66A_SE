# 1. Product Vision

**Dành cho kế toán, nhà báo, nhân viên Sale và sinh viên thường xuyên phải đọc và quản lý nhiều tài liệu, sản phẩm là hệ thống AI giúp tóm tắt, phân loại và tra cứu văn bản nhanh chóng nhằm giảm thời gian đọc, hạn chế bỏ sót thông tin và quản lý tài liệu hiệu quả hơn, thay vì phải dùng chatbot AI thông thường vốn yêu cầu người dùng tự upload, viết prompt, kiểm tra kết quả và tự tổ chức tài liệu.**

# 2. User Personas

## Persona 1 – Lan, kế toán, 32 tuổi

Lan thường xử lý hợp đồng, công văn và tài liệu hành chính dạng PDF. Cô cần đọc kỹ số liệu và điều khoản nhưng không muốn mất quá nhiều thời gian cho từng tài liệu.

**Goal:** giảm 50% thời gian đọc nhưng vẫn giữ được số liệu, điều khoản và ngữ cảnh quan trọng.

**Blocked by:** dễ bỏ sót ý chính, tài liệu nhiều số liệu và thư mục lưu trữ ngày càng lộn xộn.

**In her words:** *"Tôi cần biết chính xác số liệu nào quan trọng và nó nằm ở đâu trong tài liệu."*

**Technical skill:** sử dụng tốt máy tính và phần mềm văn phòng, ít kinh nghiệm với AI. Ưu tiên bản tóm tắt dạng bảng.

---

## Persona 2 – Minh, nhà báo, 29 tuổi

Minh phải theo dõi hơn 20 nguồn tin và tài liệu mỗi ngày. Với anh, vấn đề không phải thiếu thông tin mà là quá nhiều thông tin cần sàng lọc trong thời gian ngắn.

**Goal:** giảm trên 70% thời gian đọc lướt và nhanh chóng tìm được sự kiện, số liệu và thông tin đáng chú ý.

**Blocked by:** quá tải thông tin, dễ bỏ sót chi tiết và các công cụ AI thường tóm tắt không đúng trọng tâm.

**In his words:** *"Tôi cần biết ngay điều gì đáng chú ý và thông tin đó đến từ đâu."*

**Technical skill:** sử dụng thành thạo máy tính và các công cụ AI. Ưu tiên tốc độ, độ chính xác và khả năng tìm kiếm theo ngữ cảnh.

---

## Persona 3 – Huy, nhân viên Sale, 27 tuổi

Huy thường đọc tin thị trường, hợp đồng và tài liệu khách hàng ngay trên điện thoại. Anh chủ yếu cần biết nhanh thông tin nào liên quan đến khách hàng và hành động tiếp theo là gì.

**Goal:** giảm 50% thời gian xử lý tài liệu và nắm được ý chính nhanh chóng.

**Blocked by:** thuật ngữ khó hiểu, tài liệu thuộc nhiều chủ đề và lo ngại AI tạo ra thông tin sai.

**In his words:** *"Tôi chỉ cần biết chuyện gì đang xảy ra và nó có liên quan gì đến khách hàng của tôi."*

**Technical skill:** sử dụng smartphone thường xuyên, ưu tiên giao diện đơn giản và tóm tắt dạng bullet points.

---

## Persona 4 – Ngọc, sinh viên năm ba, 21 tuổi

Ngọc thường đọc slide, giáo trình và bài báo khoa học để học và làm bài tập. Cô không xử lý quá nhiều tài liệu mỗi ngày nhưng thường gặp khó với nội dung học thuật dài và nhiều thuật ngữ.

**Goal:** giảm 50% thời gian đọc nhưng vẫn hiểu được lập luận, khái niệm và nội dung quan trọng.

**Blocked by:** thuật ngữ khó, AI tóm tắt quá chung chung và tài liệu của nhiều môn học dễ bị lưu lẫn với nhau.

**In her words:** *"Tôi muốn biết phần nào cần học và tại sao phần đó quan trọng."*

**Technical skill:** quen sử dụng AI và các công cụ học tập. Ưu tiên bullet points, phân loại theo môn học và hỏi đáp trực tiếp với tài liệu.

# 3. User Scenarios

## Scenario 1 - Lan tối ưu hóa thời gian và truy xuất số liệu hợp đồng
* Lúc 9:00 sáng, Lan tải 5 hợp đồng PDF lên hệ thống để thực hiện mục tiêu tối ưu hóa thời gian, nhằm rút ngắn tối đa thời gian đọc và phân loại so với phương pháp thủ công.
* Hệ thống tự động phân loại tài liệu theo tiêu chí loại tệp (Hợp đồng) và đưa vào đúng không gian làm việc.
* Để kiểm tra số liệu, Lan chọn định dạng đầu ra là bảng tổng hợp số liệu, một dạng tóm tắt hoàn hảo cho nhu cầu đối chiếu tài chính.
* Bảng tổng hợp cung cấp độ sâu thông tin vừa đủ để Lan tự tin đưa ra quyết định kiểm tra con số phạt vi phạm bất thường mà không cần đọc lại toàn bộ tài liệu gốc.
* Nhờ tốc độ xử lý nhanh, Lan có thể phân bổ giá trị thời gian tiết kiệm được (50%) để tập trung hoàn thiện báo cáo tài chính tuần thay vì phải rà soát từng trang giấy.

## Scenario 2 - Minh sàng lọc thông tin và trích xuất tin tức chuẩn xác
* Là một nhà báo 29 tuổi, Minh phải đối mặt với tình trạng quá tải thông tin khi cần theo dõi hơn 20 nguồn tin và tài liệu mỗi ngày để sàng lọc trong thời gian ngắn.
* Dù sử dụng thành thạo máy tính và các công cụ AI, Minh thường xuyên bị cản trở bởi việc các AI thông thường tóm tắt không đúng trọng tâm, khiến anh dễ bỏ sót chi tiết quan trọng.
* Để khắc phục điều này, anh tận dụng khả năng tìm kiếm theo ngữ cảnh của hệ thống mới nhằm nhanh chóng tìm được các sự kiện, số liệu và thông tin đáng chú ý.
* Hệ thống xử lý chuẩn xác, đáp ứng chính xác nhu cầu cốt lõi của Minh: "Tôi cần biết ngay điều gì đáng chú ý và thông tin đó đến từ đâu".
* Nhờ ưu tiên tốc độ và độ chính xác, công cụ này giúp Minh hoàn thành xuất sắc mục tiêu giảm trên 70% thời gian đọc lướt.

## Scenario 3 - Huy nắm bắt trọng tâm tài liệu trên di động qua định dạng ngắn gọn
* Gần sát giờ họp, Huy cần tối ưu hóa thời gian đọc hiểu nên đã tải báo cáo 15 trang lên hệ thống trực tiếp qua điện thoại.
* Anh thiết lập định dạng đầu ra là dạng gạch đầu dòng ngắn gọn, đây là định dạng hoàn hảo nhất để theo dõi các xu hướng giá trên màn hình nhỏ.
* Bản tóm tắt kèm theo "Đề xuất hành động" cung cấp mức độ chi tiết đủ sâu để Huy tự tin đưa ra quyết định chốt phương án thảo luận với khách hàng mà không cần đọc lại toàn bộ tài liệu gốc.
* Tốc độ xử lý hoàn tất trong 3 phút là thước đo quan trọng nhất (KPI) giúp Huy đánh giá phần mềm hoạt động cực kỳ hiệu quả trong các tình huống khẩn cấp.

## Scenario 4 - Ngọc tổ chức tài liệu học tập và truy xuất thông tin chuyên sâu
* Khi bắt đầu ôn thi, Ngọc kỳ vọng hệ thống tự động phân loại tài liệu theo chủ đề học thuật bằng cách gán nhãn "Kinh tế vĩ mô" để dễ dàng quản lý.
* Cô yêu cầu hệ thống cung cấp định dạng đầu ra dạng gạch đầu dòng ngắn gọn để nắm bắt nhanh các khái niệm cốt lõi từ bài báo dài.
* Khi gặp phần khó hiểu, Ngọc sử dụng phương thức tìm kiếm theo ngữ cảnh tóm tắt thông qua việc đặt câu hỏi trực tiếp trong khung chat để truy xuất nhanh đoạn văn bản cần tìm.
* Độ chính xác khi phân loại và khả năng tra cứu trúng đích là thước đo quan trọng để Ngọc đánh giá phần mềm hoạt động hiệu quả.
* Ngọc có thể phân bổ giá trị thời gian hàng giờ đồng hồ tiết kiệm được vào việc hệ thống hóa kiến thức và ghi chú cá nhân, biến công cụ AI thành tiện ích không thể thiếu trong học tập.