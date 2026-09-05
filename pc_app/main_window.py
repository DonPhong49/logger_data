"""
Module: main_window.py
Giao diện giám sát và phân tích tín hiệu 8 kênh phong cách Saleae Logic Analyzer.
Hỗ trợ hiển thị đa làn (Stacked Channels), đồng bộ trục thời gian X-Axis,
con trỏ đo thời gian thực (Cursors & Crosshair), xem lại lịch sử và xuất dữ liệu.
"""

import os
import time
from collections import deque
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QGroupBox,
    QFileDialog, QMessageBox, QFrame, QSplitter, QScrollArea,
    QToolTip
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor

import pyqtgraph as pg

from serial_worker import SerialWorker
from data_logger import DataLogger

# Bảng màu 8 kênh chuẩn Saleae Logic (Neon sắc nét trên nền đen)
CHANNEL_COLORS = [
    "#00E5FF",  # CH1: Cyan
    "#FFEB3B",  # CH2: Bright Yellow
    "#00E676",  # CH3: Neon Green
    "#FF4081",  # CH4: Vivid Pink
    "#FF9100",  # CH5: Deep Orange
    "#B388FF",  # CH6: Lavender Violet
    "#40C4FF",  # CH7: Sky Blue
    "#FF5252",  # CH8: Coral Red
]

CHANNEL_NAMES = [f"Kênh {i+1} (CH{i+1})" for i in range(8)]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SALEAE LOGIC ANALYZER - 8-CHANNEL DATA LOGGER (250 HZ)")
        self.resize(1400, 880)
        self.setMinimumSize(1050, 680)

        # Cấu hình PyQtGraph tối ưu tốc độ render
        pg.setConfigOptions(antialias=False, useOpenGL=False)

        # Khởi tạo Serial Worker và Data Logger
        self.worker = SerialWorker(self)
        self.logger = DataLogger()

        # Bộ đệm dữ liệu lịch sử trong RAM (100.000 điểm = 400 giây ở 250 Hz)
        self.max_points = 100000
        self.time_buffer = deque(maxlen=self.max_points)
        self.channel_buffers = [deque(maxlen=self.max_points) for _ in range(8)]

        # Biến trạng thái
        self.is_capturing = False
        self.follow_live = True       # Tự động cuộn theo thời gian thực
        self.window_seconds = 5.0     # Khung nhìn mặc định (5 giây)
        self.current_voltages = [0.0] * 8
        self.current_raw = [0] * 8
        self.start_timestamp = None

        # Danh sách widget các kênh
        self.plot_items = []
        self.plot_curves = []
        self.crosshair_lines = []
        self.channel_cards = []
        self.channel_val_labels = []
        self.channel_raw_labels = []
        self.channel_chkboxes = []

        # Xây dựng giao diện
        self._init_ui()
        self._apply_saleae_theme()

        # Kết nối tín hiệu
        self.worker.data_received.connect(self._on_data_received)
        self.worker.stats_updated.connect(self._on_stats_updated)
        self.worker.status_changed.connect(self._on_status_changed)

        # Timer cập nhật đồ thị (35 FPS)
        self.plot_timer = QTimer(self)
        self.plot_timer.timeout.connect(self._update_plots)
        self.plot_timer.start(28)

        # Timer cập nhật thông số thẻ kênh (4 Hz)
        self.stat_timer = QTimer(self)
        self.stat_timer.timeout.connect(self._update_cards_ui)
        self.stat_timer.start(250)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. Thanh công cụ phía trên (Top Toolbar phong cách Saleae)
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        # 2. Thanh đo đạc và thông tin con trỏ Cursors
        cursor_bar = self._create_cursor_bar()
        main_layout.addWidget(cursor_bar)

        # 3. Vùng hiển thị chính: Splitter chia Thẻ kênh bên trái và Đồ thị đa làn bên phải
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # Cột trái: Thẻ thông tin 8 kênh
        left_panel = self._create_channel_headers_panel()
        splitter.addWidget(left_panel)

        # Cột phải: Đồ thị đa làn sóng
        graph_panel = self._create_stacked_graphs()
        splitter.addWidget(graph_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([230, 1170])
        main_layout.addWidget(splitter, 1)

        # 4. Thanh trạng thái dưới cùng
        self.status_bar = self._create_status_bar()
        main_layout.addWidget(self.status_bar)

    def _create_top_bar(self) -> QWidget:
        """Thanh điều khiển chính trên cùng phong cách Saleae."""
        bar = QFrame()
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Nút START / STOP CAPTURE lớn nổi bật
        self.btn_capture = QPushButton("▶ BẮT ĐẦU THU THẬP")
        self.btn_capture.setObjectName("BtnCapture")
        self.btn_capture.setMinimumHeight(38)
        self.btn_capture.setMinimumWidth(180)
        self.btn_capture.clicked.connect(self._toggle_capture)
        layout.addWidget(self.btn_capture)

        # Cổng COM
        layout.addWidget(QLabel("Cổng:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(130)
        self._refresh_ports()
        layout.addWidget(self.port_combo)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setToolTip("Quét lại danh sách cổng COM")
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.clicked.connect(self._refresh_ports)
        layout.addWidget(self.btn_refresh)

        # Baudrate
        layout.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        for b in [115200, 230400, 460800, 921600]:
            self.baud_combo.addItem(str(b), b)
        self.baud_combo.setCurrentText("115200")
        layout.addWidget(self.baud_combo)

        # Chế độ mô phỏng
        self.chk_simulation = QCheckBox("Mô phỏng (Test Offline)")
        self.chk_simulation.toggled.connect(self._on_sim_toggled)
        layout.addWidget(self.chk_simulation)

        layout.addSpacing(15)

        # Điều khiển dòng thời gian
        self.btn_follow_live = QPushButton("⚡ Theo dõi trực tiếp")
        self.btn_follow_live.setCheckable(True)
        self.btn_follow_live.setChecked(True)
        self.btn_follow_live.setObjectName("BtnFollowLive")
        self.btn_follow_live.toggled.connect(self._on_follow_live_toggled)
        layout.addWidget(self.btn_follow_live)

        self.btn_fit_all = QPushButton("🔍 Fit All")
        self.btn_fit_all.setToolTip("Phóng to hiển thị toàn bộ lịch sử đo")
        self.btn_fit_all.clicked.connect(self._fit_all_data)
        layout.addWidget(self.btn_fit_all)

        layout.addWidget(QLabel("Cửa sổ:"))
        self.window_combo = QComboBox()
        for sec in [2, 5, 10, 30, 60]:
            self.window_combo.addItem(f"{sec} giây", sec)
        self.window_combo.setCurrentText("5 giây")
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        layout.addWidget(self.window_combo)

        layout.addStretch()

        # Xuất dữ liệu & Ghi log
        self.btn_export = QPushButton("💾 Xuất CSV...")
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.clicked.connect(self._export_csv_dialog)
        layout.addWidget(self.btn_export)

        self.btn_record = QPushButton("🔴 Ghi Log File")
        self.btn_record.setObjectName("BtnRecord")
        self.btn_record.clicked.connect(self._toggle_disk_logging)
        layout.addWidget(self.btn_record)

        return bar

    def _create_cursor_bar(self) -> QWidget:
        """Thanh đo đạc thời gian và con trỏ T1 / T2."""
        bar = QFrame()
        bar.setObjectName("CursorBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(12)

        self.chk_show_cursors = QCheckBox("Bật thước đo Cursors (T1 / T2)")
        self.chk_show_cursors.setChecked(False)
        self.chk_show_cursors.toggled.connect(self._on_toggle_cursors)
        layout.addWidget(self.chk_show_cursors)

        self.lbl_cursor_measure = QLabel(
            "T1: --- s | T2: --- s | Δt: --- ms | Tần số tương đương: --- Hz"
        )
        self.lbl_cursor_measure.setObjectName("CursorMeasurementLabel")
        layout.addWidget(self.lbl_cursor_measure)

        layout.addStretch()

        self.lbl_crosshair_info = QLabel("Con trỏ: Rê chuột vào đồ thị để xem chi tiết")
        self.lbl_crosshair_info.setObjectName("CrosshairInfoLabel")
        layout.addWidget(self.lbl_crosshair_info)

        return bar

    def _create_channel_headers_panel(self) -> QWidget:
        """Bảng thẻ điều khiển và thông số 8 kênh ở cột bên trái."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        title = QLabel("<b>DANH SÁCH KÊNH ĐO (0 – 12V)</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        for i in range(8):
            card = QFrame()
            card.setObjectName(f"ChannelCard_{i}")
            card.setStyleSheet(f"""
                QFrame#ChannelCard_{i} {{
                    background-color: #1e2126;
                    border: 1px solid #2c313a;
                    border-left: 5px solid {CHANNEL_COLORS[i]};
                    border-radius: 4px;
                    padding: 4px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(6, 4, 6, 4)
            card_layout.setSpacing(2)

            top_row = QHBoxLayout()
            chk = QCheckBox(f"CH{i+1}")
            chk.setChecked(True)
            chk.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            chk.setStyleSheet(f"color: {CHANNEL_COLORS[i]};")
            chk.toggled.connect(lambda checked, idx=i: self._on_channel_toggled(idx, checked))
            top_row.addWidget(chk)
            top_row.addStretch()

            badge_range = QLabel("0-12V")
            badge_range.setStyleSheet("color: #78909C; font-size: 8pt;")
            top_row.addWidget(badge_range)
            card_layout.addLayout(top_row)

            # Điện áp tức thời
            lbl_volt = QLabel("0.000 V")
            lbl_volt.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            lbl_volt.setStyleSheet(f"color: {CHANNEL_COLORS[i]};")
            card_layout.addWidget(lbl_volt)

            # Giá trị ADC thô
            lbl_raw = QLabel("Raw: 0 (16-bit)")
            lbl_raw.setStyleSheet("color: #90A4AE; font-size: 8pt; font-family: Consolas;")
            card_layout.addWidget(lbl_raw)

            layout.addWidget(card)

            self.channel_cards.append(card)
            self.channel_chkboxes.append(chk)
            self.channel_val_labels.append(lbl_volt)
            self.channel_raw_labels.append(lbl_raw)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _create_stacked_graphs(self) -> QWidget:
        """Khu vực đồ thị đa làn sóng 8 kênh phong cách Saleae."""
        self.gl_widget = pg.GraphicsLayoutWidget()
        self.gl_widget.setBackground("#141619")

        # Cặp con trỏ đo T1, T2
        self.cursor_t1 = pg.InfiniteLine(
            pos=1.0,
            angle=90,
            movable=True,
            pen=pg.mkPen("#FFD600", width=1.5, style=Qt.PenStyle.DashLine),
            label="T1",
            labelOpts={"position": 0.9, "color": "#FFD600", "fill": (20, 20, 20, 150)}
        )
        self.cursor_t2 = pg.InfiniteLine(
            pos=2.0,
            angle=90,
            movable=True,
            pen=pg.mkPen("#FF6D00", width=1.5, style=Qt.PenStyle.DashLine),
            label="T2",
            labelOpts={"position": 0.9, "color": "#FF6D00", "fill": (20, 20, 20, 150)}
        )
        self.cursor_t1.sigPositionChanged.connect(self._update_cursor_measurement)
        self.cursor_t2.sigPositionChanged.connect(self._update_cursor_measurement)

        master_plot = None

        for i in range(8):
            # Tạo từng làn PlotItem
            p = self.gl_widget.addPlot(row=i, col=0)
            p.setMenuEnabled(False)
            p.showGrid(x=True, y=True, alpha=0.25)
            p.setYRange(-0.5, 12.5, padding=0.0)
            p.getAxis("left").setWidth(42)
            p.getAxis("left").setStyle(tickFont=QFont("Segoe UI", 7))
            p.getAxis("left").setLabel(f"CH{i+1}", color=CHANNEL_COLORS[i])

            if master_plot is None:
                master_plot = p
            else:
                # Đồng bộ hoàn toàn trục X với Plot đầu tiên
                p.setXLink(master_plot)

            # Ẩn trục X ở các kênh 1-7, chỉ hiển thị ở kênh cuối cùng
            if i < 7:
                p.hideAxis("bottom")
            else:
                p.showAxis("bottom")
                p.getAxis("bottom").setLabel("Thời gian (giây)", color="#B0BEC5")
                p.getAxis("bottom").setStyle(tickFont=QFont("Segoe UI", 8))

            # Đường cong tín hiệu với màu sắc riêng
            pen = pg.mkPen(color=CHANNEL_COLORS[i], width=1.5)
            # Tạo bóng mờ nhẹ bên dưới đường sóng phong cách Saleae
            c_color = QColor(CHANNEL_COLORS[i])
            brush = pg.mkBrush(c_color.red(), c_color.green(), c_color.blue(), 25)
            curve = p.plot(pen=pen, fillLevel=0.0, fillBrush=brush)
            self.plot_curves.append(curve)
            self.plot_items.append(p)

            # Đường gióng con trỏ Crosshair trên từng kênh
            crosshair = pg.InfiniteLine(
                angle=90,
                movable=False,
                pen=pg.mkPen("#FFFFFF", width=1, style=Qt.PenStyle.DotLine)
            )
            crosshair.setVisible(False)
            p.addItem(crosshair, ignoreBounds=True)
            self.crosshair_lines.append(crosshair)

            # Cho phép kéo chuột hoặc cuộn chuột để soi sóng
            p.getViewBox().sigRangeChangedManually.connect(self._on_user_interacted_plot)

        # Thêm Cursors vào master plot
        master_plot.addItem(self.cursor_t1, ignoreBounds=True)
        master_plot.addItem(self.cursor_t2, ignoreBounds=True)
        self.cursor_t1.setVisible(False)
        self.cursor_t2.setVisible(False)

        # Theo dõi sự kiện rê chuột trên GraphicsLayoutWidget
        self.gl_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        return self.gl_widget

    def _create_status_bar(self) -> QWidget:
        """Thanh trạng thái dưới cùng hiển thị chẩn đoán kết nối."""
        bar = QFrame()
        bar.setObjectName("BottomStatusBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 3, 10, 3)

        self.lbl_conn_status = QLabel("Trạng thái: Chưa kết nối")
        layout.addWidget(self.lbl_conn_status)

        layout.addStretch()

        self.lbl_rate_info = QLabel("Tần số: 0.0 Hz | Tổng gói: 0 | Mất: 0 | Lỗi CRC: 0")
        layout.addWidget(self.lbl_rate_info)

        layout.addSpacing(20)
        self.lbl_log_status = QLabel("Log: Đang tắt")
        layout.addWidget(self.lbl_log_status)

        return bar

    def _apply_saleae_theme(self):
        """Áp dụng theme nền tối graphite sang trọng của Saleae Logic 2."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f1012;
            }
            QWidget {
                color: #e6edf3;
                font-family: 'Segoe UI', 'Ubuntu', sans-serif;
                font-size: 9pt;
            }
            QFrame#TopBar, QFrame#CursorBar, QFrame#BottomStatusBar {
                background-color: #1a1d21;
                border: 1px solid #282c34;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #2b2f36;
                color: #e6edf3;
                border: 1px solid #3c414c;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #383d47;
                border-color: #00E5FF;
            }
            QPushButton:pressed {
                background-color: #1f2227;
            }
            QPushButton#BtnCapture {
                background-color: #00C853;
                color: #000000;
                font-weight: bold;
                font-size: 10pt;
                border: none;
                border-radius: 5px;
            }
            QPushButton#BtnCapture:hover {
                background-color: #00E676;
            }
            QPushButton#BtnFollowLive:checked {
                background-color: #00E5FF;
                color: #000000;
                font-weight: bold;
                border-color: #00B0FF;
            }
            QPushButton#BtnRecord {
                background-color: #37474F;
                color: #ECEFF1;
                border: 1px solid #546E7A;
            }
            QPushButton#BtnExport {
                background-color: #263238;
                color: #80D8FF;
                border: 1px solid #00B0FF;
            }
            QComboBox {
                background-color: #212429;
                color: #e6edf3;
                border: 1px solid #3c414c;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1d21;
                color: #e6edf3;
                selection-background-color: #00B0FF;
                selection-color: #000000;
            }
            QCheckBox {
                color: #CFD8DC;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QLabel#CursorMeasurementLabel {
                color: #FFD54F;
                font-family: Consolas, monospace;
                font-weight: bold;
            }
            QLabel#CrosshairInfoLabel {
                color: #80DEEA;
                font-family: Consolas, monospace;
            }
            QSplitter::handle {
                background-color: #282c34;
            }
        """)

    # ==========================
    # CÁC HÀM XỬ LÝ SỰ KIỆN KẾT NỐI
    # ==========================

    def _refresh_ports(self):
        """Quét lại cổng COM trên máy tính."""
        self.port_combo.clear()
        ports = SerialWorker.get_available_ports()
        if ports:
            for p in ports:
                self.port_combo.addItem(p)
        else:
            self.port_combo.addItem("Không tìm thấy cổng")

    def _on_sim_toggled(self, checked: bool):
        self.port_combo.setEnabled(not checked)
        self.btn_refresh.setEnabled(not checked)

    def _toggle_capture(self):
        """Bắt đầu hoặc dừng phiên thu thập dữ liệu."""
        if not self.is_capturing:
            # Khởi động thu thập
            sim_mode = self.chk_simulation.isChecked()
            port = self.port_combo.currentText()
            baud = self.baud_combo.currentData() or 115200

            if not sim_mode and (not port or "Không" in port):
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một cổng COM hợp lệ hoặc bật chế độ Mô phỏng!")
                return

            self.worker.configure(port=port, baudrate=baud, simulation=sim_mode)
            self.worker.start()

            self.is_capturing = True
            self.btn_capture.setText("■ DỪNG THU THẬP")
            self.btn_capture.setStyleSheet("background-color: #D50000; color: #FFFFFF;")
            self.btn_follow_live.setChecked(True)
        else:
            # Dừng thu thập
            self.worker.stop()
            self.is_capturing = False
            self.btn_capture.setText("▶ BẮT ĐẦU THU THẬP")
            self.btn_capture.setStyleSheet("")

    def _on_status_changed(self, is_connected: bool, msg: str):
        self.lbl_conn_status.setText(f"Trạng thái: {msg}")
        if not is_connected and self.is_capturing:
            self._toggle_capture()

    def _on_stats_updated(self, total: int, dropped: int, crc_err: int, hz: float):
        self.lbl_rate_info.setText(
            f"Tần số: {hz:.1f} Hz | Tổng gói: {total} | Mất: {dropped} | Lỗi CRC: {crc_err}"
        )

    # ==========================
    # CƠ CHẾ DỮ LIỆU & RENDER ĐỒ THỊ
    # ==========================

    def _on_data_received(self, counter: int, voltages: list, raw_adcs: list, timestamp: float):
        if self.start_timestamp is None:
            self.start_timestamp = timestamp

        # Thời gian tương đối (giây) tính từ khi bắt đầu
        rel_time = timestamp - self.start_timestamp

        self.time_buffer.append(rel_time)
        for i in range(8):
            self.channel_buffers[i].append(voltages[i])

        self.current_voltages = voltages
        self.current_raw = raw_adcs

        # Nếu đang bật ghi log ra đĩa
        if self.logger.is_logging:
            self.logger.log_sample(timestamp, voltages)

    def _update_plots(self):
        """Cập nhật đồ thị 8 kênh ở tần số 35 FPS."""
        if not self.time_buffer:
            return

        num_points = len(self.time_buffer)
        if num_points < 2:
            return

        t_array = np.array(self.time_buffer)
        latest_t = t_array[-1]

        # Tự động cuộn theo thời gian thực nếu Follow Live đang bật
        if self.follow_live:
            t_min = max(0.0, latest_t - self.window_seconds)
            t_max = max(self.window_seconds, latest_t)
            self.plot_items[0].setXRange(t_min, t_max, padding=0.0)

        # Lấy phạm vi hiển thị hiện tại để downsampling tối ưu
        x_range = self.plot_items[0].getViewBox().viewRange()[0]
        v_min, v_max = x_range[0], x_range[1]

        # Chỉ vẽ dữ liệu trong khoảng nhìn thấy (hoặc toàn bộ nếu vừa đủ)
        idx_start = np.searchsorted(t_array, v_min, side='left')
        idx_end = np.searchsorted(t_array, v_max, side='right')
        idx_start = max(0, idx_start - 2)
        idx_end = min(num_points, idx_end + 2)

        if idx_end <= idx_start:
            return

        x_slice = t_array[idx_start:idx_end]
        slice_len = len(x_slice)

        # Tự động giảm mẫu (Downsample) khi zoom ra xa để giữ 60 FPS
        step = 1
        if slice_len > 2500:
            step = slice_len // 1500
            x_slice = x_slice[::step]

        for i in range(8):
            if self.channel_chkboxes[i].isChecked():
                y_array = np.array(self.channel_buffers[i])[idx_start:idx_end]
                if step > 1:
                    y_array = y_array[::step]
                self.plot_curves[i].setData(x_slice, y_array)
            else:
                self.plot_curves[i].clear()

    def _update_cards_ui(self):
        """Cập nhật giá trị điện áp hiển thị trên các thẻ kênh bên trái."""
        for i in range(8):
            v = self.current_voltages[i]
            r = self.current_raw[i]
            self.channel_val_labels[i].setText(f"{v:.3f} V")
            self.channel_raw_labels[i].setText(f"Raw: {r}")

        # Cập nhật trạng thái log file nếu đang chạy
        if self.logger.is_logging:
            stats = self.logger.get_stats()
            self.lbl_log_status.setText(
                f"Log: Đang ghi ({stats['total_rows']} mẫu, {stats['file_size_kb']:.1f} KB)"
            )

    # ==========================
    # CÁC THAO TÁC SALEAE LOGIC (ZOOM, PAN, CURSORS)
    # ==========================

    def _on_user_interacted_plot(self):
        """Khi người dùng cuộn chuột hoặc kéo pan đồ thị -> tắt Follow Live để soi sóng."""
        if self.follow_live:
            self.follow_live = False
            self.btn_follow_live.setChecked(False)
            self.btn_follow_live.setText("⏸ Xem lại (Paused)")

    def _on_follow_live_toggled(self, checked: bool):
        self.follow_live = checked
        if checked:
            self.btn_follow_live.setText("⚡ Theo dõi trực tiếp")
        else:
            self.btn_follow_live.setText("⏸ Xem lại (Paused)")

    def _fit_all_data(self):
        """Phóng to hiển thị toàn bộ lịch sử dữ liệu thu được."""
        if not self.time_buffer:
            return
        self.follow_live = False
        self.btn_follow_live.setChecked(False)
        self.plot_items[0].setXRange(self.time_buffer[0], self.time_buffer[-1], padding=0.02)

    def _on_window_changed(self):
        val = self.window_combo.currentData()
        if val:
            self.window_seconds = float(val)

    def _on_channel_toggled(self, idx: int, checked: bool):
        """Ẩn/hiện một làn kênh."""
        if checked:
            self.plot_items[idx].show()
        else:
            self.plot_items[idx].hide()

    def _on_toggle_cursors(self, checked: bool):
        """Bật/tắt cặp con trỏ đo T1 / T2."""
        self.cursor_t1.setVisible(checked)
        self.cursor_t2.setVisible(checked)
        if checked:
            # Đặt vị trí T1, T2 vào giữa khung nhìn hiện tại
            x_range = self.plot_items[0].getViewBox().viewRange()[0]
            center = (x_range[0] + x_range[1]) / 2.0
            span = max(0.1, (x_range[1] - x_range[0]) * 0.15)
            self.cursor_t1.setValue(center - span)
            self.cursor_t2.setValue(center + span)
            self._update_cursor_measurement()
        else:
            self.lbl_cursor_measure.setText(
                "T1: --- s | T2: --- s | Δt: --- ms | Tần số tương đương: --- Hz"
            )

    def _update_cursor_measurement(self):
        """Tính toán khoảng cách thời gian Delta t và tần số giữa T1 và T2."""
        t1 = self.cursor_t1.value()
        t2 = self.cursor_t2.value()
        delta_t = abs(t2 - t1)
        delta_ms = delta_t * 1000.0
        freq = (1.0 / delta_t) if delta_t > 1e-6 else 0.0

        self.lbl_cursor_measure.setText(
            f"T1: {t1:.4f}s | T2: {t2:.4f}s | Δt: {delta_ms:.2f} ms | Tần số: {freq:.2f} Hz"
        )

    def _on_mouse_moved(self, scene_pos):
        """Di chuyển đường gióng Crosshair qua cả 8 kênh theo vị trí con trỏ chuột."""
        view_box = self.plot_items[0].getViewBox()
        if not view_box.sceneBoundingRect().contains(scene_pos):
            for line in self.crosshair_lines:
                line.setVisible(False)
            return

        mouse_point = view_box.mapSceneToView(scene_pos)
        x_val = mouse_point.x()

        # Hiển thị đường gióng trên tất cả các kênh
        for line in self.crosshair_lines:
            line.setValue(x_val)
            line.setVisible(True)

        # Tra cứu giá trị điện áp tức thời tại vị trí chuột
        if self.time_buffer:
            t_array = np.array(self.time_buffer)
            idx = int(np.searchsorted(t_array, x_val))
            idx = max(0, min(len(t_array) - 1, idx))

            t_val = t_array[idx]
            v_list = [f"CH{ch+1}: {self.channel_buffers[ch][idx]:.2f}V" for ch in range(8)]
            summary_str = f"Thời điểm: {t_val:.4f}s | " + " | ".join(v_list[:4])
            self.lbl_crosshair_info.setText(summary_str)

    # ==========================
    # LƯU TRỮ VÀ XUẤT FILE CSV
    # ==========================

    def _toggle_disk_logging(self):
        """Bật/tắt chế độ ghi liên tục xuống đĩa."""
        if not self.logger.is_logging:
            path = self.logger.start()
            self.btn_record.setText("⏹ DỪNG GHI LOG")
            self.btn_record.setStyleSheet("background-color: #C62828; color: #FFFFFF;")
            self.lbl_log_status.setText(f"Log: Đang ghi -> {os.path.basename(path)}")
        else:
            self.logger.stop()
            self.btn_record.setText("🔴 Ghi Log File")
            self.btn_record.setStyleSheet("")
            self.lbl_log_status.setText("Log: Đã dừng và lưu file.")
            QMessageBox.information(
                self, "Thông báo",
                f"Đã lưu file log thành công tại:\n{self.logger.file_path}"
            )

    def _export_csv_dialog(self):
        """Xuất dữ liệu phiên đo (Toàn bộ hoặc vùng nhìn thấy) ra CSV phong cách Saleae."""
        if not self.time_buffer:
            QMessageBox.warning(self, "Thông báo", "Chưa có dữ liệu nào trong bộ nhớ để xuất!")
            return

        reply = QMessageBox.question(
            self, "Tùy chọn xuất CSV",
            "Bạn muốn xuất vùng dữ liệu nào?\n\n"
            "- Nhấn 'Yes' để xuất TOÀN BỘ phiên đo trong bộ nhớ.\n"
            "- Nhấn 'No' để chỉ xuất ĐOẠN ĐANG PHÓNG TO (Visible Window).\n"
            "- Nhấn 'Cancel' để hủy.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        start_t = None
        end_t = None
        if reply == QMessageBox.StandardButton.No:
            x_range = self.plot_items[0].getViewBox().viewRange()[0]
            start_t = x_range[0]
            end_t = x_range[1]

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu tệp CSV", "logs/Saleae_Capture.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        t_list = list(self.time_buffer)
        ch_list = [list(self.channel_buffers[i]) for i in range(8)]
        rows = DataLogger.export_data(file_path, t_list, ch_list, start_t, end_t)

        QMessageBox.information(
            self, "Xuất thành công",
            f"Đã xuất thành công {rows} dòng dữ liệu vào tệp:\n{file_path}"
        )
