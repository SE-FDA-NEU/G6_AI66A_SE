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

## Scenario 1 - Lan trích xuất và đối chiếu số liệu từ loạt hợp đồng mới

1. Lúc 9:00 sáng, Lan nhận được 5 hợp đồng kinh tế định dạng PDF dài hàng chục trang từ bộ phận Kinh doanh cần duyệt gấp.
2. Cô mở hệ thống quản lý tài liệu AI trên máy tính và kéo thả 5 tệp PDF này vào không gian làm việc.
3. Hệ thống tự động nhận diện, phân loại các tệp này vào thư mục "Hợp đồng" và tiến hành xử lý ngôn ngữ.
4. Nắm được nhu cầu đọc nhanh số liệu, Lan chọn chế độ hiển thị "Tóm tắt dạng bảng" (Table View).
5. Hệ thống lập tức tạo ra một bảng tổng hợp đối chiếu với các cột: Tên đối tác, Giá trị hợp đồng, Thời hạn thanh toán và Điều khoản phạt vi phạm.
6. Khi lướt qua bảng, Lan phát hiện một hợp đồng có tỷ lệ phạt vi phạm trễ hạn cao bất thường.
7. Cô click thẳng vào con số trên bảng, hệ thống tự động nhảy đến đúng trang và bôi vàng đoạn văn bản chứa điều khoản đó trong file PDF gốc để cô đối chiếu ngữ cảnh.
8. Sau khi kiểm tra và xác nhận thông tin chính xác, Lan xuất bảng tóm tắt ra file Excel để đính kèm vào báo cáo tài chính tuần.
9. Toàn bộ quá trình xử lý hoàn tất trong 15 phút, giúp Lan tiết kiệm 50% thời gian so với việc đọc rà soát từng trang tài liệu.

---

## Scenario 2 - Minh lọc tin tức nóng từ hàng chục nguồn dữ liệu đầu ngày

1. Lúc 7:30 sáng, Minh bắt đầu ngày làm việc và đối mặt với hơn 40 thông cáo báo chí, báo cáo thị trường từ 20 nguồn cấp tin khác nhau được đổ về hệ thống.
2. Thay vì phải mở từng tab để đọc lướt, Minh truy cập vào bảng điều khiển chung của hệ thống AI.
3. Anh sử dụng thanh tìm kiếm theo ngữ cảnh và gõ: "Biến động giá vàng và các chính sách xuất nhập khẩu mới nhất".
4. Hệ thống AI quét toàn bộ tài liệu trong ngày, loại bỏ các tin tức không liên quan và chọn ra 4 bài viết quan trọng nhất.
5. Minh đọc đoạn tóm tắt siêu ngắn (Executive Summary) do AI tự động tạo ở trên cùng, nêu bật 2 sự kiện chính vừa diễn ra trong đêm.
6. Để đảm bảo tính chính xác cho bài viết, Minh rê chuột vào các chỉ số phần trăm trong đoạn tóm tắt để xem trực tiếp thẻ trích dẫn (citation) trỏ về nguồn báo cáo gốc.
7. Anh ghim (pin) 2 tài liệu chứa thông tin đắt giá nhất vào thư mục "Bài viết hôm nay" để hệ thống theo dõi các cập nhật liên quan.
8. Có sẵn ý chính và nguồn trích dẫn chuẩn xác, Minh lập tức bắt tay vào viết bản tin sáng, cắt giảm được hơn 70% thời gian sàng lọc thông tin dư thừa.

---

## Scenario 3 - Huy nắm bắt trọng tâm tài liệu khách hàng trên di động

1. Lúc 14:00, Huy đang ngồi quán cà phê chờ gặp khách hàng và nhận được một báo cáo phân tích thị trường dài 15 trang qua email.
2. Anh mở hệ thống AI trực tiếp trên trình duyệt điện thoại di động và tải tệp báo cáo lên.
3. Vì cần thông tin nhanh gọn, Huy chọn chế độ tóm tắt "Gạch đầu dòng" (Bullet points).
4. Hệ thống lập tức hiển thị 5 ý chính ngắn gọn về các xu hướng giá mới nhất trong quý.
5. Trong bản tóm tắt xuất hiện một thuật ngữ kinh tế chuyên ngành, Huy chạm vào từ đó và hệ thống hiển thị một pop-up giải thích ngắn gọn ngay trên màn hình điện thoại.
6. Ở cuối bản tóm tắt, AI tự động tạo mục "Đề xuất hành động", gợi ý Huy nên nhấn mạnh vào dòng sản phẩm tầm trung với khách hàng dựa trên xu hướng báo cáo.
7. Huy sao chép nhanh các gạch đầu dòng này vào ứng dụng ghi chú để làm dàn ý thảo luận.
8. Toàn bộ thao tác diễn ra trong 3 phút, giúp Huy tự tin bước vào cuộc họp mà không cần căng mắt đọc tài liệu dài trên màn hình nhỏ.

---

## Scenario 4 - Ngọc học tập và tương tác với tài liệu học thuật

1. Lúc 20:00, Ngọc bắt đầu ôn thi môn Kinh tế vĩ mô và cần xử lý 3 bài báo khoa học dài cùng 2 tập slide bài giảng tiếng Anh.
2. Cô tải toàn bộ tài liệu lên hệ thống và tạo nhãn phân loại "Kinh tế vĩ mô" để tự động đưa vào đúng thư mục môn học, tránh lẫn với tài liệu môn khác.
3. Ngọc yêu cầu hệ thống tóm tắt các khái niệm cốt lõi trong 3 bài báo dưới dạng danh sách gạch đầu dòng (Bullet points).
4. Hệ thống trích xuất các định nghĩa và lập luận quan trọng nhất, giúp Ngọc nắm được bức tranh tổng thể của các bài báo trong vài phút.
5. Khi gặp một phần lập luận khó hiểu về nguyên nhân lạm phát, Ngọc gõ câu hỏi trực tiếp vào khung chat bên cạnh tài liệu: "Tác giả giải thích nguyên nhân lạm phát trong bài này như thế nào?".
6. Hệ thống AI phản hồi ngay lập tức bằng một câu trả lời trực tiếp, kèm theo link liên kết dẫn thẳng đến đoạn văn bản tương ứng ở trang 12 của bài báo số 2.
7. Ngọc bấm vào link để đọc nguyên văn đoạn gốc, sau đó bôi đậm (highlight) và lưu ghi chú cá nhân ngay trên nền tảng.
8. Sau 45 phút, Ngọc đã hệ thống hóa xong kiến thức trọng tâm của bài học thay vì mất hàng giờ chật vật tra cứu thuật ngữ và đọc chay tài liệu.