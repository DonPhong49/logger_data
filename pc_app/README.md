# HƯỚNG DẪN SỬ DỤNG ỨNG DỤNG PC DATA LOGGER 8 KÊNH - PHONG CÁCH SALEAE LOGIC ANALYZER

Ứng dụng Desktop viết bằng Python (PyQt6 + PyQtGraph) được thiết kế theo phong cách giao diện máy phân tích logic **Saleae Logic Analyzer**, chuyên dụng để thu thập, hiển thị đa làn sóng và lưu trữ dữ liệu thời gian thực từ kit STM32H743VIT6.

---

## 1. YÊU CẦU HỆ THỐNG & CÀI ĐẶT

- **Hệ điều hành:** Linux, Windows, macOS
- **Python:** Phiên bản 3.9 trở lên
- **Thư viện phụ thuộc:**
  - `PyQt6` (Giao diện đồ họa Qt6 hiện đại)
  - `pyqtgraph` (Vẽ đồ thị thời gian thực tăng tốc phần cứng GPU)
  - `pyserial` (Giao tiếp cổng COM/UART tốc độ cao)
  - `numpy` (Xử lý mảng dữ liệu số hiệu năng cao)

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

### Cách 2: Khởi chạy trực tiếp từ terminal
```bash
.venv/bin/python pc_app/app.py
```

---

## 3. CÁC TÍNH NĂNG NỔI BẬT PHONG CÁCH SALEAE LOGIC

1. **Hiển thị đa làn sóng (Stacked Channels / Lanes):**
   - 8 kênh analog được bố trí trên 8 dải ngang độc lập với màu nhận diện đặc trưng phong cách Saleae.
   - Trục thời gian (X-Axis) liên kết đồng bộ (Linked X-Axis): Khi cuộn chuột phóng to/thu nhỏ (Zoom) hoặc kéo chuột di chuyển (Pan) ở bất kỳ kênh nào, toàn bộ 8 kênh đều dịch chuyển chính xác theo cùng một nhịp.

2. **Thao tác dòng thời gian & Soi sóng lịch sử:**
   - **Cuộn chuột (Mouse Wheel):** Phóng to/thu nhỏ mượt mà tại vị trí con trỏ chuột từ hàng chục giây xuống đến từng phần nghìn giây (ms).
   - **Kéo chuột trái (Drag Pan):** Di chuyển ngược dòng thời gian về quá khứ để soi các gai nhiễu, đột biến tín hiệu.
   - **Nút "⚡ Theo dõi trực tiếp (Follow Live)":** Tự động bám theo đỉnh sóng mới nhất ở 250 Hz. Khi bạn cuộn xem dữ liệu cũ, chế độ này tự chuyển sang "⏸ Xem lại (Paused)" để bạn thoải mái phân tích. Nhấn lại nút để quay về thời gian thực.
   - **Nút "🔍 Fit All":** Tự động co giãn toàn bộ dòng thời gian để nhìn bao quát toàn bộ phiên đo từ lúc bắt đầu.

3. **Hệ thống thước đo Cursors & Đường gióng Crosshair:**
   - **Đường gióng con trỏ (Global Crosshair):** Khi rê chuột qua đồ thị, một đường gióng đứt nét màu trắng sẽ chạy xuyên suốt 8 kênh và hiển thị nhãn thời gian cùng giá trị điện áp tức thời của các kênh tại vị trí chuột.
   - **Cặp con trỏ đo T1 / T2 (Measurement Markers):**
     - Tích chọn "Bật thước đo Cursors (T1 / T2)" để hiện 2 thước đo màu vàng và cam.
     - Dùng chuột kéo thước đo T1, T2 đến các vị trí xung cần đo.
     - Ứng dụng tự động tính và hiển thị: Khoảng cách thời gian (Delta t tính bằng ms/s) và Tần số tương đương (Hz).

4. **Quản lý kênh đo & Thẻ hiển thị bên trái:**
   - Mỗi kênh có thẻ riêng với vạch màu nhận diện, hiển thị điện áp tức thời (ví dụ: `5.120 V`) và giá trị thô 16-bit (`Raw: 27850`).
   - Hộp chọn Checkbox cho phép ẩn/hiện từng kênh để tối ưu không gian hiển thị cho các kênh đang quan tâm.

5. **Lưu trữ & Xuất dữ liệu đa năng:**
   - **Xuất dữ liệu phiên đo (💾 Xuất CSV...):**
     - Xuất toàn bộ phiên đo lưu trong bộ nhớ RAM ra tệp CSV.
     - Hoặc xuất riêng vùng thời gian đang phóng to trên màn hình (Visible Window) phục vụ báo cáo/phân tích.
   - **Ghi liên tục xuống đĩa (🔴 Ghi Log File):**
     - Ghi dữ liệu trực tiếp vào tệp CSV trong thư mục `logs/` với cơ chế đệm RAM 50 mẫu/lần flush, an toàn khi ghi nhiều giờ liên tục.

6. **Chế độ Mô phỏng (Offline Test):**
   - Tích chọn ô "Mô phỏng (Test Offline)" và nhấn "▶ BẮT ĐẦU THU THẬP".
   - Ứng dụng tự động phát 8 dạng sóng (Sine, Tam giác, Vuông, DC 3.3V, DC 5V, DC 10V) ở đúng chu kỳ 4 ms (250 Hz) để kiểm thử đầy đủ tính năng mà không cần cắm kit phần cứng.
