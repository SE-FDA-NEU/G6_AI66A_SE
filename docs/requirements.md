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

## Scenario 1 - Lan đối chiếu nhanh số liệu hợp đồng trước giờ làm báo cáo
* Sáng thứ Hai, Lan cần hoàn thiện báo cáo tài chính tuần nhưng lại nhận được 5 bản hợp đồng PDF mới cần rà soát khẩn cấp.
* Thay vì tự đọc từng trang, cô mở hệ thống trên máy tính và tải cùng lúc cả 5 tệp lên.
* Hệ thống tự động nhận diện đây là hợp đồng và phân loại chúng vào đúng không gian làm việc của dự án.
* Để lấy số liệu nhanh, Lan yêu cầu hệ thống tóm tắt các điều khoản tài chính quan trọng.
* Hệ thống trả về một bảng thông tin tổng hợp liệt kê rõ các con số phạt vi phạm từ cả 5 hợp đồng.
* Nhìn vào bảng, Lan phát hiện ngay một tỷ lệ phạt bất thường, ghi chú lại vào báo cáo tài chính của mình và hoàn thành công việc đúng hạn mà không cần mở từng tài liệu gốc ra dò tìm.

## Scenario 2 - Minh bóc tách thông tin và truy xuất nguồn tin báo chí
* Đang trong ca làm việc, nhà báo Minh nhận được hơn 20 tài liệu và báo cáo khác nhau về một sự kiện kinh tế vừa diễn ra.
* Anh đưa toàn bộ tài liệu này vào hệ thống và nhập một câu hỏi tìm kiếm để lọc ra các diễn biến đáng chú ý nhất.
* Thay vì đưa ra một đoạn tóm tắt chung chung, hệ thống hiển thị ngay các sự kiện trọng tâm kèm theo số liệu cụ thể.
* Dưới mỗi thông tin, Minh nhìn thấy ngay chú thích nguồn rõ ràng (ví dụ: nằm ở tài liệu nào, trang số mấy).
* Anh bấm vào chú thích để đối chiếu nhanh với bản gốc, xác nhận thông tin chuẩn xác và đưa ngay dữ kiện đó vào bài viết đang chuẩn bị lên trang.

## Scenario 3 - Huy nắm bắt trọng tâm báo cáo trên điện thoại trước cuộc họp khẩn
* Chỉ còn 10 phút nữa là bắt đầu cuộc họp với khách hàng, Huy đang đi trên hành lang thì nhận được một bản báo cáo thị trường dài 15 trang.
* Không có sẵn máy tính, anh mở trình duyệt trên điện thoại và tải nhanh file báo cáo lên hệ thống.
* Huy chọn chế độ tóm tắt ngắn gọn.
* Hệ thống hiển thị ngay các xu hướng giá chính dưới dạng danh sách, được tối ưu hóa giao diện nên rất dễ đọc trên màn hình nhỏ.
* Cuộn xuống cuối bản tóm tắt, Huy đọc được các đề xuất hành động cụ thể từ báo cáo.
* Anh nhanh chóng chọn ra được một phương án khả thi và tự tin bước vào phòng thảo luận để chốt vấn đề.

## Scenario 4 - Ngọc tổ chức tài liệu và tra cứu kiến thức khó hiểu khi ôn thi
* Buổi tối bắt đầu kỳ ôn thi, Ngọc có một loạt bài báo học thuật dài cần xử lý.
* Cô tải tài liệu lên, hệ thống tự động phân tích nội dung và gắn nhãn "Kinh tế vĩ mô" để đưa vào đúng thư mục môn học.
* Ngọc mở một bài báo và yêu cầu hệ thống liệt kê các khái niệm cốt lõi nhất để nắm bắt tổng quan.
* Trong lúc đọc, cô gặp một thuật ngữ lý thuyết khá mơ hồ.
* Thay vì phải đọc dò từng dòng, Ngọc gõ từ khóa đó vào thanh tìm kiếm nội bộ ngay trên màn hình đọc tài liệu.
* Hệ thống lập tức tự động cuộn trang đến đúng vị trí và tô sáng (highlight) đoạn văn bản gốc giải thích chi tiết cho thuật ngữ đó.
* Ngọc đọc lướt qua đoạn highlight, hiểu rõ vấn đề, ghi chú lại vào sổ tay cá nhân và tiếp tục mạch học tập của mình một cách liền mạch.

# User Stories & Acceptance Criteria

## US01 - Trích xuất bảng số liệu từ nhiều hợp đồng cùng lúc 
Là Lan, tôi muốn tải lên nhiều hợp đồng PDF cùng lúc và nhận kết quả trích xuất dưới dạng bảng tổng hợp số liệu để tôi có thể nhanh chóng đối chiếu các khoản phạt vi phạm mà không cần mở từng tài liệu.

### Acceptance criteria
*  Tôi tải lên một cụm 5 tệp PDF thành công, khi hệ thống quét nội dung, 100% các tệp này tự động được gắn nhãn loại tệp "Hợp đồng" và đưa vào đúng thư mục dự án mà không cần thao tác thủ công.
*  Tôi chọn tính năng tóm tắt điều khoản tài chính, khi kết quả hiển thị, dữ liệu bắt buộc phải được trình bày dưới định dạng bảng lưới, trong đó trích xuất chính xác các con số phạt vi phạm (ví dụ: %, VNĐ) từ từng hợp đồng.
* Tôi tải lên tối đa 5 hợp đồng (dung lượng dưới 50MB/tệp), khi tôi nhấn "Xử lý", tổng thời gian hệ thống hoàn thành phân loại và xuất bảng tóm tắt không được vượt quá 5 phút.


## US02 - Tìm kiếm ngữ cảnh và trích xuất thông tin có trích dẫn nguồn 
Là Minh, tôi muốn tìm kiếm thông tin trên một tập hợp hơn 20 tài liệu cùng lúc để nhanh chóng bóc tách các sự kiện, số liệu quan trọng kèm theo nguồn gốc rõ ràng nhằm phục vụ việc viết bài chính xác.

### Acceptance criteria
*  Tôi đang ở trong không gian làm việc chứa 20 tệp tài liệu, khi tôi nhập từ khóa tìm kiếm sự kiện, hệ thống trả về danh sách các sự kiện và số liệu trọng tâm, không hiển thị các câu văn dẫn dắt thừa thãi.
*  Hệ thống trả về kết quả tóm tắt, khi tôi xem chi tiết, dưới mỗi số liệu/sự kiện bắt buộc phải có một dòng chú thích nguồn cụ thể (định dạng: "Tên tài liệu - Trang số X").
*  Một thông tin có đính kèm trích dẫn nguồn, khi tôi nhấn vào chú thích đó, hệ thống phải mở popup hoặc chuyển hướng đến đúng trang tài liệu gốc chứa đoạn văn bản đó để tôi đối chiếu.


## US03 - Tóm tắt báo cáo dạng gạch đầu dòng tối ưu trên mobile 
Là Huy, tôi muốn tải một báo cáo dài lên hệ thống qua trình duyệt điện thoại và nhận bản tóm tắt dạng gạch đầu dòng kèm đề xuất hành động để tôi có thể chốt phương án trước giờ họp khẩn.

### Acceptance criteria
*  Tôi truy cập hệ thống bằng trình duyệt điện thoại (iOS/Android), khi tôi xem bản tóm tắt, giao diện hiển thị dạng danh sách gạch đầu dòng tương thích 100% với chiều rộng màn hình, không bị tràn viền hay che khuất chữ.
*  Hệ thống hoàn tất việc tạo bản tóm tắt, khi tôi cuộn xuống cuối màn hình, bắt buộc phải có một phần tiêu đề "Đề xuất hành động" chứa tối thiểu 2 phương án thực thi được tổng hợp từ tài liệu gốc.
*  Tôi tải lên tệp báo cáo PDF dài 15 trang, khi tôi yêu cầu hệ thống tóm tắt, toàn bộ quá trình đọc hiểu và trả kết quả phải hoàn thành trong thời gian tối đa là 3 phút.


## US04 - Tự động gắn nhãn và tra cứu khái niệm qua thanh tìm kiếm 
Là Ngọc, tôi muốn hệ thống tự động gắn nhãn chủ đề cho tài liệu và cho phép tôi tra cứu nhanh các khái niệm khó qua thanh tìm kiếm nội bộ, giúp tôi dễ dàng tổ chức lưu trữ và tiết kiệm thời gian ôn thi.

### Acceptance criteria
*  Tôi tải lên một tệp bài báo học thuật mới, khi quá trình tải hoàn tất, hệ thống tự động phân tích và gán đúng nhãn chủ đề (ví dụ: "Kinh tế vĩ mô") vào metadata của tệp.
*  Tôi yêu cầu tóm tắt tổng quan bài báo, khi hệ thống trả kết quả, t bản tóm tắt bắt buộc phải theo định dạng gạch đầu dòng và giới hạn hiển thị từ 3 đến 5 khái niệm cốt lõi nhất.
*  Tôi có thắc mắc về một khái niệm trong lúc đọc tài liệu, khi tôi nhập từ khóa vào thanh tìm kiếm nội bộ của tài liệu đó, hệ thống phải tìm thấy, tự động cuộn đến và đánh dấu chính xác đoạn văn bản chứa giải thích cho khái niệm đó.

