# TÀI LIỆU ĐẶC TẢ YÊU CẦU PHẦN MỀM (SOFTWARE SPECIFICATION)
## ĐỀ TÀI: THIẾT KẾ BỘ THU THẬP DỮ LIỆU 8 KÊNH SỬ DỤNG VI ĐIỀU KHIỂN STM32

* **Sinh viên thực hiện:** Mai Sỹ (MSV: 2022603955)
* **Lớp:** 2022DHKTMT01 - Khoa Công nghệ Thông tin / Trường Điện - Điện tử (ĐH Công nghiệp Hà Nội)
* **Vi điều khiển mục tiêu:** STM32H743VIT6 (ARM Cortex-M7, 480 MHz)
* **Tài liệu cập nhật:** Theo yêu cầu điều chỉnh tần số thu thập và truyền thông mới (ADC 1 kHz -> Trung bình -> Truyền RS232 400 Hz).

---

## 1. TỔNG QUAN BÀI TOÁN & MỤC TIÊU PHẦN MỀM

Hệ thống có nhiệm vụ thu thập tín hiệu analog từ 8 kênh độc lập (dải điện áp đo 0 – 12V qua mạch suy hao phần cứng về 0 – 3.3V), chuyển đổi ADC 16-bit, thực hiện lấy mẫu với tần số 1 kHz, lọc lấy trung bình và gửi lên máy tính với tần số 400 Hz qua chuẩn giao tiếp UART/RS232 (baudrate 115200 bps). Trên máy tính, một ứng dụng chuyên dụng sẽ nhận luồng dữ liệu thời gian thực, kiểm tra toàn vẹn, giải mã, hiển thị đồ thị sóng 8 kênh và ghi dữ liệu ra file phục vụ lưu trữ, phân tích.

### Hệ thống gồm 2 thành phần phần mềm chính:
1. **Firmware nhúng (STM32H743VIT6):** Đảm nhiệm định thời gian cứng (Hardware Timer), kích hoạt ADC đa kênh qua DMA, tính toán lọc trung bình dữ liệu, đóng gói dữ liệu theo giao thức khung (packet protocol) và truyền UART qua DMA.
2. **Ứng dụng giám sát trên máy tính (PC Desktop App):** Đảm nhiệm mở cổng Serial, giải mã luồng byte tốc độ cao (400 gói/giây), hiển thị đồ thị 8 kênh thời gian thực (Real-time plotting), tính toán các thông số điện áp và ghi file log (CSV).

---

## 2. ĐẶC TẢ PHẦN MỀM NHÚNG (FIRMWARE STM32)

### 2.1. Cấu hình phần cứng ngoại vi (Peripherals)
* **Bộ ADC (ADC1):**
  * Độ phân giải: 16-bit (giá trị số từ 0 đến 65535).
  * Số kênh: 8 kênh Regular tương ứng (PC0, PA0, PA2, PA3, PA4, PA5, PA6, PA7).
  * Thời gian lấy mẫu: 64.5 chu kỳ/kênh.
  * Chế độ kích hoạt: Kích hoạt bằng ngoại vi Timer (Trigger Out - TRGO), không dùng Software Trigger hay Continuous Mode để đảm bảo độ chuẩn xác tuyệt đối về tần số lấy mẫu, loại bỏ jitter.
* **Bộ định thời (Hardware Timer - ví dụ TIM2 / TIM3):**
  * Đặt tần số ngắt TRGO = 1 kHz (chu kỳ đúng 1 ms) để kích hoạt ADC1 quét 8 kênh.
* **Bộ DMA (DMA1 Stream0 cho ADC):**
  * Chế độ: Circular Buffer (Double Buffer hoặc Half-Transfer / Transfer-Complete Interrupt).
  * Dữ liệu chuyển đổi tự động chuyển thẳng vào mảng RAM mà không tiêu tốn chu kỳ CPU.
* **Bộ UART (USART1):**
  * Chuẩn truyền: RS232 (qua IC chuyển đổi mức như MAX3232 / SP3232).
  * Thông số cổng: Baudrate 115200 bps, 8 Data bits, 1 Stop bit, No Parity (8N1).
  * Cơ chế truyền: UART DMA (TX DMA) ở chế độ One-shot hoặc Circular kết hợp Ring Buffer, tránh tình trạng CPU bị block chờ truyền ký tự.

### 2.2. Xử lý dữ liệu & Thuật toán lọc trung bình (Averaging / Decimation)
* Tần số lấy mẫu ADC đầu vào: **1 kHz (1000 mẫu/giây/kênh)**.
* Tần số truyền dữ liệu lên máy tính: **400 Hz (400 gói/giây)**.
* **Phân tích toán học:** Tỷ lệ lấy mẫu / truyền = 1000 / 400 = 2.5 (nghĩa là trong 10 ms có 10 mẫu ADC và có 4 gói tin UART được gửi đi).
* **Thuật toán xử lý trên MCU:**
  * *Cách 1 (Bộ lọc trung bình trượt - Moving Average Filter):* Mỗi khi có mẫu 1 kHz mới, cập nhật vào mảng trượt kích thước N (ví dụ N = 4 hoặc 8). Một Timer phụ chạy ở tần số 400 Hz (hoặc biến đếm ngắt chu kỳ 2.5 ms) sẽ lấy giá trị trung bình trượt hiện tại đóng gói và kích hoạt gửi UART DMA.
  * *Cách 2 (Lấy mẫu theo chu kỳ linh hoạt):* Lần gửi 1 lấy trung bình 2 mẫu ADC, lần gửi 2 lấy trung bình 3 mẫu ADC (xen kẽ 2 - 3 - 2 - 3 = trung bình 2.5 mẫu/lần gửi).
  * *Gợi ý nâng cao nếu được phép tinh chỉnh Timer ADC:* Có thể cho Timer ADC kích hoạt ở 1200 Hz (trung bình 3 mẫu -> ra 400 Hz) hoặc 2000 Hz (trung bình 5 mẫu -> ra 400 Hz) để phép chia trung bình hoàn toàn nguyên và triệt tiêu nhiễu cao tần tốt hơn.

### 2.3. Thiết kế giao thức truyền thông (UART Packet Protocol)
Để đảm bảo ứng dụng máy tính nhận đúng từng khung dữ liệu ở tốc độ 400 Hz, tránh hiện tượng lệch pha byte, khung dữ liệu nhị phân (Binary Protocol) được thiết kế nhỏ gọn, tối ưu băng thông:

#### Cấu trúc khung dữ liệu (Tổng cộng: 21 bytes/gói):
| Thứ tự Byte | Trường dữ liệu | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- | :--- |
| Byte 0 | Header 1 | `uint8_t` | Ký tự đồng bộ 1 (`0xAA`) |
| Byte 1 | Header 2 | `uint8_t` | Ký tự đồng bộ 2 (`0x55`) |
| Byte 2 | Packet Counter | `uint8_t` | Bộ đếm gói tin (0 -> 255 cuốn chiếu, phát hiện mất gói) |
| Byte 3 - 4 | Channel 1 | `uint16_t` | Dữ liệu ADC kênh 1 (Little-Endian: Low Byte trước, High Byte sau) |
| Byte 5 - 6 | Channel 2 | `uint16_t` | Dữ liệu ADC kênh 2 (0 - 65535) |
| Byte 7 - 8 | Channel 3 | `uint16_t` | Dữ liệu ADC kênh 3 |
| Byte 9 - 10 | Channel 4 | `uint16_t` | Dữ liệu ADC kênh 4 |
| Byte 11 - 12 | Channel 5 | `uint16_t` | Dữ liệu ADC kênh 5 |
| Byte 13 - 14 | Channel 6 | `uint16_t` | Dữ liệu ADC kênh 6 |
| Byte 15 - 16 | Channel 7 | `uint16_t` | Dữ liệu ADC kênh 7 |
| Byte 17 - 18 | Channel 8 | `uint16_t` | Dữ liệu ADC kênh 8 |
| Byte 19 | Checksum | `uint8_t` | Checksum XOR hoặc CRC-8 từ Byte 2 đến Byte 18 |
| Byte 20 | Tail / End | `uint8_t` | Ký tự kết thúc khung (`0x0D` hoặc `0x5A`) |

#### Phân tích tải đường truyền UART:
* Chiều dài mỗi khung tin: 21 bytes.
* Tần số gửi: 400 gói/giây.
* Lưu lượng dữ liệu cần truyền: `21 bytes x 400 = 8400 bytes/giây`.
* Băng thông tối đa của UART 115200 (8N1: 10 bit/byte): `115200 / 10 = 11520 bytes/giây`.
* **Hệ số tải (Bus Load):** `8400 / 11520 = 72.9%` (rất an toàn, không bị nghẽn buffer UART).

---

## 3. ĐẶC TẢ PHẦN MỀM MÁY TÍNH (PC DESKTOP APPLICATION)

### 3.1. Lựa chọn công nghệ phát triển
* **Ngôn ngữ:** Python 3.10+ (Được khuyến nghị cao nhất cho đồ án kỹ thuật máy tính).
* **Framework Giao diện (GUI):** `PyQt6` hoặc `PySide6`.
* **Thư viện vẽ đồ thị thời gian thực:** `PyQtGraph` (Xử lý đồ thị bằng OpenGL / GPU, vẽ mượt mà ở tốc độ 400 Hz với 8 kênh cùng lúc mà không gây đơ lag giao diện).
* **Giao tiếp phần cứng:** `pyserial` (giao tiếp cổng COM).
* **Xử lý số liệu & Xuất file:** `numpy`, `csv`, `pandas`.

### 3.2. Kiến trúc đa luồng (Multi-threading Architecture)
Để ứng dụng không bị "Not Responding" khi nhận 400 gói dữ liệu/giây kết hợp vẽ đồ thị và ghi đĩa, hệ thống được chia làm 3 luồng riêng biệt:

```
[STM32 via RS232]
       │
       ▼
[Thread 1: Serial Reader & Parser]  -->  (State Machine: Tìm Header, Check CRC)
       │ (Ring Buffer / Queue)
       ├────────────────────────────────────────┐
       ▼                                        ▼
[Thread 2: Data Logger]             [Thread 3: GUI & Real-time Plotting]
- Ghi dữ liệu dạng nhị phân/CSV     - Cập nhật 8 đường tín hiệu (30 - 60 FPS)
- Bộ đệm Flush định kỳ              - Hiển thị giá trị tức thời (V), Min, Max
```

1. **Luồng 1: Thu nhận & Phân tích gói tin (Serial Worker Thread):**
   * Đọc dữ liệu từ cổng COM liên tục.
   * Sử dụng máy trạng thái (Finite State Machine - FSM) để bắt cặp Header `0xAA 0x55`.
   * Thu thập đủ 21 bytes, kiểm tra Checksum.
   * Nếu hợp lệ: Giải mã 8 kênh ADC (16-bit raw) -> tính ra điện áp:
     `V_in = (ADC_raw / 65535.0) * V_ref_actual * (12.0 / 3.3)`
   * Đẩy dữ liệu đã tính toán vào hàng đợi đa luồng (`thread-safe Queue`).
   * Đếm số gói nhận được, phát hiện gói bị rơi (dựa vào Packet Counter).

2. **Luồng 2: Ghi dữ liệu ra tệp (Logging Worker Thread):**
   * Đọc từ hàng đợi dữ liệu.
   * Ghi ra file định dạng `.csv` theo từng mẻ (Batch write) để tối ưu I/O ổ cứng.
   * Cấu trúc cột file CSV: `Timestamp (ms), V_CH1, V_CH2, V_CH3, V_CH4, V_CH5, V_CH6, V_CH7, V_CH8`.

3. **Luồng 3: Giao diện chính & Hiển thị (Main UI Thread):**
   * Chạy Timer đồ họa với tần số 30 Hz - 60 Hz (mắt người nhận biết mượt mà).
   * Lấy các điểm đo mới nhất từ Queue và vẽ nối tiếp vào đồ thị dạng cuộn (Scrolling Plot) hoặc quét (Oscilloscope sweep).
   * Cập nhật các đồng hồ số hiển thị điện áp tức thời.

### 3.3. Các tính năng chính của giao diện phần mềm
1. **Khối kết nối (Connection Control):**
   * Tự động quét danh sách cổng COM khả dụng.
   * Chọn Baudrate (mặc định 115200).
   * Nút Connect / Disconnect kèm đèn trạng thái (Xanh / Đỏ).
2. **Khối đồ thị trực quan thời gian thực (Real-time Graph Display):**
   * Khung đồ thị hiển thị đồng thời 8 kênh với 8 màu sắc phân biệt rõ ràng.
   * Có thanh công cụ: Zoom in, Zoom out, Pan, Auto Scale trục Y (0 - 12V), Auto Scale trục X (thời gian).
   * Cho phép chọn ẩn/hiện từng kênh đo riêng biệt qua Checkbox (CH1 đến CH8).
3. **Khối số liệu đo tức thời (Digital Readout & Statistics):**
   * Bảng hiển thị giá trị điện áp tức thời (V) của 8 kênh với độ chính xác 3 chữ số thập phân.
   * Các thông số thống kê cơ bản: V_max, V_min, V_avg, V_pp (Peak-to-Peak).
4. **Khối ghi & lưu trữ dữ liệu (Data Logging Control):**
   * Chọn đường dẫn lưu file (.csv).
   * Đặt tên file tự động theo thời gian: `Log_YYYYMMDD_HHMMSS.csv`.
   * Nút Start Recording / Stop Recording kèm thời gian đã ghi và dung lượng file.
5. **Khối chẩn đoán truyền thông (Diagnostics):**
   * Tần số nhận thực tế (Packets/second - mục tiêu đạt đúng ~400 Hz).
   * Số lượng gói tin nhận thành công.
   * Số lượng gói lỗi Checksum (Error packets) và số gói bị mất (Dropped packets).

---

## 4. KẾ HOẠCH TRIỂN KHAI CHI TIẾT (IMPLEMENTATION PHASES)

### Giai đoạn 1: Lập trình vi điều khiển STM32H7
* [ ] Cấu hình Timer (ví dụ TIM2) tạo sự kiện ngắt TRGO với tần số 1 kHz (chu kỳ 1 ms).
* [ ] Cấu hình ADC1 kích hoạt qua TIM TRGO, DMA Circular Mode để đọc tuần tự 8 kênh.
* [ ] Cài đặt thuật toán lấy mẫu và lọc trung bình (Decimation / Moving Average) đưa nhịp ra 400 Hz.
* [ ] Viết module đóng gói khung truyền (21 bytes có Header, Counter, Checksum).
* [ ] Cấu hình USART1 TX DMA để truyền khung dữ liệu lên máy tính với chu kỳ 2.5 ms (400 Hz).
* [ ] Kiểm tra thực nghiệm tín hiệu TX trên máy hiện sóng (Oscilloscope) hoặc phần mềm kiểm tra cổng Serial.

### Giai đoạn 2: Lập trình phần mềm máy tính (Python GUI)
* [ ] Viết module kết nối Serial đa luồng (`serial_reader.py`) bóc tách khung 21 bytes và kiểm tra Checksum.
* [ ] Viết module ghi dữ liệu CSV đa luồng (`data_logger.py`).
* [ ] Thiết kế giao diện đồ họa bằng PyQt6 / PySide6 (`main_window.py`).
* [ ] Tích hợp đồ thị đa kênh bằng PyQtGraph, tối ưu hiệu năng vẽ 400 Hz.
* [ ] Kiểm tra đồng bộ dữ liệu, đo tỷ lệ mất gói (< 0.01%).

### Giai đoạn 3: Hiệu chuẩn & Đánh giá toàn hệ thống
* [ ] Cân chỉnh hệ số chuyển đổi điện áp thực tế cho mạch chia áp 0-12V sang 0-3.3V (Hệ số K của từng kênh để bù sai số điện trở).
* [ ] Đánh giá độ chính xác (so sánh với đồng hồ vạn năng hoặc máy phát sóng chuẩn).
* [ ] Kiểm tra độ ổn định liên tục trong thời gian dài (Stress-test hệ thống thu thập trong 1 - 2 giờ).
* [ ] Đóng gói ứng dụng máy tính thành file chạy độc lập (`.exe` bằng PyInstaller).
* [ ] Thu thập số liệu, hình ảnh thực nghiệm hoàn thiện quyển báo cáo đồ án tốt nghiệp.
