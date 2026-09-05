# HƯỚNG DẪN SỬ DỤNG ỨNG DỤNG PC DATA LOGGER 8 KÊNH (250 HZ)

Ứng dụng desktop viết bằng Python (PyQt6 + PyQtGraph) chuyên dụng để thu thập dữ liệu thời gian thực từ kit STM32H743VIT6.

---

## 1. YÊU CẦU HỆ THỐNG & CÀI ĐẶT

- **Python:** Phiên bản 3.9 trở lên
- **Thư viện phụ thuộc:**
  - `PyQt6` (Giao diện đồ họa Qt)
  - `pyqtgraph` (Đồ thị thời gian thực tăng tốc phần cứng)
  - `pyserial` (Giao tiếp cổng COM/UART)
  - `numpy` (Xử lý mảng dữ liệu số)

### Cài đặt thư viện:
```bash
pip install -r pc_app/requirements.txt
```

---

## 2. CÁCH KHỞI CHẠY ỨNG DỤNG

### Cách 1: Sử dụng script tự động
```bash
./run_pc_app.sh
```

### Cách 2: Khởi chạy trực tiếp bằng môi trường ảo Python
```bash
.venv/bin/python pc_app/app.py
```

---

## 3. CÁC TÍNH NĂNG CHÍNH

1. **Chế độ Mô phỏng (Offline Test):**
   - Tích chọn ô `Chế độ Mô phỏng (Offline Test)` và nhấn `⚡ KẾT NỐI`.
   - Ứng dụng tự động sinh 8 luồng tín hiệu (Sine, Triangle, Square, DC 3.3V, DC 5V, DC 10V) ở đúng tần số 250 Hz (chu kỳ 4 ms) để kiểm thử đồ thị, bảng số liệu và tính năng ghi log mà không cần cắm phần cứng.

2. **Chế độ Cổng COM Thực (Hardware Mode):**
   - Bỏ chọn `Chế độ Mô phỏng`.
   - Nhấn nút `🔄 Quét` để cập nhật danh sách cổng COM (hoặc `/dev/ttyUSB0`, `/dev/ttyACM0` trên Linux).
   - Chọn Baudrate: Mặc định `115200` (khớp với firmware STM32H7).
   - Nhấn `⚡ KẾT NỐI`.

3. **Hiển thị đồ thị 8 kênh thời gian thực:**
   - 8 kênh màu sắc tương phản cao trên giao diện nền tối (Dark Theme).
   - Cho phép bật/tắt hiển thị từng kênh tùy ý thông qua danh sách checkbox bên phải.
   - Hỗ trợ đổi khung thời gian hiển thị: 2 giây, 5 giây, 10 giây, 30 giây hoặc 60 giây.
   - Nút `Tự động căn chỉnh (Auto Scale)` và `Tạm dừng đồ thị`.

4. **Bảng đo điện áp & Thống kê:**
   - Hiển thị song song: Điện áp thực tế (0 – 12V), Giá trị ADC 16-bit nguyên bản (0 – 65535), Điện áp Min, Max và Trung bình.
   - Hiển thị trực tiếp tần số lấy mẫu thực tế (Hz), số gói đã nhận, số gói bị rớt (dropped), lỗi CRC checksum.

5. **Ghi dữ liệu (Data Logging) ra tệp CSV:**
   - Nhấn nút `🔴 BẮT ĐẦU GHI LOG`.
   - Ứng dụng tự động lưu vào thư mục `logs/` với tên tệp theo thời gian thực: `DataLog_YYYYMMDD_HHMMSS.csv`.
   - Có cơ chế đệm bộ nhớ (RAM Buffer) chống giật/lag I/O đĩa cứng khi ghi ở tốc độ cao 250 mẫu/giây.
