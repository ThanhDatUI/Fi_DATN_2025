# Thiết Kế Và Phát Triển Mũ Bảo Hiểm IoT  
### Hỗ Trợ Giám Sát An Toàn Giao Thông Và Cảnh Báo Nguy Cơ Tai Nạn

## 📌 Giới thiệu
Tai nạn giao thông, đặc biệt liên quan đến xe mô tô, vẫn là vấn đề nghiêm trọng. Nhiều trường hợp xảy ra do người lái không đội mũ bảo hiểm hoặc đội sai cách.  
Đề tài này xây dựng **mũ bảo hiểm thông minh tích hợp IoT và cảm biến hiện đại**, nhằm:
- Giám sát việc đội mũ đúng cách.  
- Phát hiện hành vi nguy hiểm khi lái xe.  
- Cảnh báo và hỗ trợ khẩn cấp trong tình huống tai nạn.  

---

## 🎯 Mục tiêu
- Nhận diện người không đội mũ hoặc đội sai cách bằng **camera + học sâu (MobileNet SSD)**.  
- Phát hiện hành vi nguy hiểm: tăng tốc đột ngột, rung lắc, va chạm.  
- Gửi cảnh báo khẩn cấp qua **SMS, cuộc gọi, email** kèm vị trí GPS.  
- Lưu trữ dữ liệu hành vi lái xe và trạng thái an toàn trên **ứng dụng di động/web**.  

---

## ⚙️ Yêu cầu kỹ thuật
- **Nhận diện hình ảnh**: độ chính xác ≥ 50%, kể cả khi người lái đeo kính hoặc khẩu trang.  
- **Cảm biến lực (FSR402, RFP602)** và **Hall A3144**: kiểm tra việc gài quai, đội mũ đúng cách.  
- **Cảm biến gia tốc MPU6050, SW420, SW520**: phát hiện tăng tốc > 3 m/s², rung lắc, nghiêng bất thường.  
- **GPS NEO6M**: sai số vị trí ±2.5m.  
- **Module SIM900A**: gửi cảnh báo qua mạng di động.  
- **Kết nối IoT**: Raspberry Pi Zero 2W xử lý trung tâm, giao tiếp ESP32 qua UART/MQTT.  
- **Ứng dụng di động/web**: theo dõi trạng thái mũ, lịch sử cảnh báo, vị trí.  

---

## 🛠️ Thiết kế hệ thống
### Phần cứng
- **Camera + Raspberry Pi**: xử lý hình ảnh.  
- **Cảm biến lực, Hall, gia tốc, rung, nghiêng**: giám sát trạng thái mũ và hành vi lái xe.  
- **Module GSM + GPS**: truyền thông và định vị.  
- **Relay + buzzer + LCD**: cảnh báo và điều khiển xe.  

### Phần mềm
- **MobileNet SSD**: nhận diện hình ảnh đội mũ.  
- **Thuật toán giám sát**: phát hiện bất thường, lưu trữ dữ liệu.  
- **Ứng dụng React Native**: giao diện người dùng (Dashboard, Alert History, Location Map, Settings).  

---

## 📊 Kết quả thực nghiệm
- Hệ thống nhận diện đội mũ đạt độ chính xác cao trong nhiều điều kiện ánh sáng.  
- Cảm biến lực và Hall xác định chính xác trạng thái gài quai.  
- Cảm biến gia tốc phát hiện tăng tốc bất thường và va chạm hiệu quả.  
- Ứng dụng di động hiển thị trực quan lịch sử cảnh báo, vị trí và trạng thái mũ.  
- Raspberry Pi Zero 2W vận hành ổn định, CPU & RAM đáp ứng yêu cầu xử lý.  

---

## 🚧 Hạn chế
- Độ chính xác nhận diện hình ảnh còn phụ thuộc vào môi trường ánh sáng.  
- Thời gian phản hồi của hệ thống đôi khi bị ảnh hưởng bởi kết nối mạng.  
- Kích thước và trọng lượng mũ tăng do tích hợp nhiều linh kiện.  

---

## 🔮 Hướng phát triển
- Tối ưu mô hình học sâu để tăng độ chính xác nhận diện.  
- Thu nhỏ kích thước phần cứng, nâng cao tính thẩm mỹ và tiện dụng.  
- Tích hợp thêm tính năng phân tích thói quen lái xe bằng AI.  
- Phát triển hệ thống lưu trữ dữ liệu trên nền tảng **cloud** để mở rộng khả năng giám sát.  

---

## 📚 Tài liệu tham khảo
- Các tài liệu tiếng Việt và tiếng Anh về IoT, học sâu, cảm biến và hệ thống nhúng.  
- Phụ lục: danh sách linh kiện, thông số kỹ thuật, mã nguồn hệ thống.  

---

## 👨‍💻 Tác giả
**Phan Thành Đạt**  
Đồ án tổng hợp – Kỹ thuật Điện tử Viễn thông  
Trường Đại học Tôn Đức Thắng – 2025
