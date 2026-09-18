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
* Lúc 9:00 sáng, Lan nhận được 5 hợp đồng kinh tế định dạng PDF dài hàng chục trang từ bộ phận Kinh doanh cần duyệt gấp.
* Thay vì mở từng file và bị quá tải nhận thức bởi lượng chữ khổng lồ, cô tải cả 5 tệp PDF này lên hệ thống xử lý tài liệu.
* Hệ thống tự động nhận diện nội dung, gán nhãn (tag) "Hợp đồng kinh tế" và phân loại các tệp này vào đúng thư mục dự án tương ứng mà Lan không cần sắp xếp thủ công.
* Nắm được nhu cầu chỉ cần kiểm tra nhanh các điều khoản trọng yếu, Lan chọn định dạng đầu ra là "Tóm tắt dạng bảng" (Table View).
* Hệ thống lập tức tạo ra một bảng tổng hợp đối chiếu với các cột được trích xuất tự động: Tên đối tác, Giá trị hợp đồng, Thời hạn thanh toán và Điều khoản phạt vi phạm.
* Khi lướt qua bảng, Lan phát hiện một hợp đồng có tỷ lệ phạt vi phạm trễ hạn cao bất thường.
* Để tránh tình trạng ảo giác thông tin (hallucination) của AI, cô click thẳng vào con số trên bảng. Hệ thống tự động nhảy đến đúng trang và bôi vàng đoạn văn bản gốc chứa điều khoản đó trong file PDF để cô đối chiếu ngữ cảnh chính xác.
* Sau khi xác nhận thông tin, Lan xuất bảng tóm tắt ra file Excel để đính kèm vào báo cáo tài chính tuần.
* Toàn bộ quá trình hoàn tất trong 15 phút, giúp Lan tiết kiệm hàng giờ đồng hồ đọc rà soát và loại bỏ hoàn toàn rủi ro đọc sót thông tin quan trọng.

## Scenario 2 - Minh lọc tin tức nóng từ hàng chục nguồn dữ liệu đầu ngày
* Lúc 7:30 sáng, Minh bắt đầu ngày làm việc và đối mặt với khối lượng tài liệu lớn gồm hơn 40 thông cáo báo chí và báo cáo thị trường từ các nguồn cấp tin.
* Để giải quyết bài toán lãng phí thời gian khi đọc lướt, Minh truy cập vào không gian làm việc của hệ thống.
* Anh sử dụng thanh tìm kiếm theo ngữ cảnh và gõ: "Biến động giá vàng và chính sách xuất nhập khẩu".
* Hệ thống quét toàn bộ tài liệu được đổ về trong ngày, loại bỏ các tin tức không đúng trọng tâm và tự động lọc ra 4 bài viết mang giá trị cao nhất.
* Minh đọc đoạn văn trích xuất ý chính (Executive Summary) ở trên cùng của mỗi bài. Bản tóm tắt đi thẳng vào trọng tâm, nêu bật các số liệu và sự kiện chính vừa diễn ra trong đêm mà không bị diễn đạt lủng củng.
* Khi cần đưa số liệu vào bản tin gốc, Minh rê chuột vào các chỉ số phần trăm trong đoạn tóm tắt để xem trực tiếp thẻ trích dẫn (citation) nhằm đảm bảo độ chính xác tuyệt đối.
* Anh gắn thẻ "Tin nóng sáng nay" cho 2 tài liệu quan trọng nhất. Nhờ cấu trúc phân loại thông minh, anh biết mình có thể dễ dàng truy xuất lại chúng vào cuối tháng khi cần viết báo cáo tổng hợp.
* Có sẵn ý chính và nguồn trích dẫn chuẩn xác, Minh lập tức bắt tay vào viết bản tin, cắt giảm được hơn 70% thời gian chắt lọc thông tin dư thừa.

## Scenario 3 - Huy nắm bắt trọng tâm tài liệu khách hàng trên di động
* Lúc 14:00, Huy đang ngồi quán cà phê chờ gặp khách hàng và nhận được một báo cáo phân tích thị trường dài 15 trang (.docx) qua email.
* Do giới hạn về môi trường kỹ thuật, anh mở hệ thống trực tiếp trên trình duyệt điện thoại di động và tải tệp báo cáo lên.
* Vì cần thông tin nhanh gọn để chuẩn bị cho cuộc họp sắp diễn ra, Huy chọn chế độ tóm tắt "Gạch đầu dòng" (Bullet points).
* Hệ thống bỏ qua các phần giới thiệu dài dòng, lập tức hiển thị 5 ý chính ngắn gọn về các xu hướng giá mới nhất trong quý. Mức độ chi tiết của các gạch đầu dòng vừa đủ để Huy nắm bắt bối cảnh.
* Để lưu trữ phục vụ việc truy xuất sau này, Huy nhanh chóng chọn các thẻ danh mục gợi ý sẵn như "Báo cáo Q3", "Khách hàng VIP" để hệ thống tự động đưa vào kho lưu trữ có tổ chức.
* Huy sao chép nhanh các gạch đầu dòng tóm tắt này vào ứng dụng ghi chú trên điện thoại để làm dàn ý thảo luận.
* Toàn bộ thao tác diễn ra trong 3 phút, giúp Huy tự tin bước vào cuộc họp với đầy đủ thông tin chiến lược mà không cần căng mắt cuộn đọc toàn bộ tài liệu trên màn hình nhỏ.

## Scenario 4 - Ngọc học tập và tương tác với tài liệu học thuật
* Lúc 20:00, Ngọc bắt đầu ôn thi môn Kinh tế vĩ mô. Cô cần xử lý khối lượng văn bản lớn gồm 3 bài báo khoa học PDF dài và 2 tập slide bài giảng tiếng Anh.
* Cô tải toàn bộ tài liệu lên hệ thống. Hệ thống nhận diện nội dung học thuật và tự động đề xuất phân loại vào nhóm "Nghiên cứu kinh tế", giúp Ngọc không bị rối rắm bởi cấu trúc thư mục thủ công.
* Ngọc yêu cầu hệ thống tóm tắt các khái niệm cốt lõi trong 3 bài báo dưới dạng danh sách gạch đầu dòng để tránh bỏ sót ý chính.
* Hệ thống trích xuất các định nghĩa và lập luận quan trọng nhất, giúp Ngọc nắm được bức tranh tổng thể của các bài báo trong vài phút.
* Khi gặp một phần lập luận phức tạp về nguyên nhân lạm phát, Ngọc không đọc toàn bộ văn bản. Cô sử dụng công cụ "Tìm kiếm nội bộ" của hệ thống và gõ cụm từ khóa "nguyên nhân lạm phát".
* Thay vì sinh ra văn bản tự do, hệ thống ngay lập tức lọc ra và hiển thị chính xác các đoạn văn bản gốc có chứa lập luận này từ cả 3 bài báo, đi kèm link trỏ về đúng trang chứa đoạn văn đó (ví dụ: Trang 12, Bài báo 2).
* Ngọc bấm vào link để đọc nguyên văn đoạn gốc nhằm hiểu sâu ngữ cảnh, sau đó bôi đậm (highlight) và lưu ghi chú cá nhân.
* Sau 45 phút, Ngọc đã hệ thống hóa xong kiến thức trọng tâm thay vì mất hàng giờ đồng hồ chật vật tìm kiếm thông tin và loay hoay sắp xếp tài liệu như trước đây.