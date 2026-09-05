"""
Module: main_window.py
Giao diện điều khiển, trực quan hóa đồ thị 8 kênh thời gian thực (250 Hz) và ghi log.
Sử dụng PyQt6 và PyQtGraph tăng tốc phần cứng GPU.
"""

import os
import time
from collections import deque
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon

import pyqtgraph as pg

from serial_worker import SerialWorker
from data_logger import DataLogger

# Bảng màu 8 kênh rực rỡ, độ tương phản cao trên nền tối
CHANNEL_COLORS = [
    "#00E5FF",  # Kênh 1: Cyan
    "#FFEA00",  # Kênh 2: Vàng
    "#00E676",  # Kênh 3: Xanh lá neon
    "#FF4081",  # Kênh 4: Hồng neon
    "#FF9100",  # Kênh 5: Cam
    "#7C4DFF",  # Kênh 6: Tím sáng
    "#00B0FF",  # Kênh 7: Xanh dương nhạt
    "#FF5252",  # Kênh 8: Đỏ san hô
]

CHANNEL_NAMES = [f"Kênh {i+1} (CH{i+1})" for i in range(8)]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("HỆ THỐNG THU THẬP DỮ LIỆU 8 KÊNH STM32H7 - 250 HZ")
        self.resize(1350, 850)
        self.setMinimumSize(1000, 650)

        # Khởi tạo luồng xử lý Serial và Data Logger
        self.worker = SerialWorker(self)
        self.logger = DataLogger()

        # Cấu hình bộ đệm hiển thị đồ thị (5 giây ở 250 Hz = 1250 điểm)
        self.sample_rate = 250
        self.window_seconds = 5.0
        self.buffer_size = int(self.sample_rate * self.window_seconds)

        # Mảng dữ liệu thời gian và 8 kênh
        self.time_buffer = deque(maxlen=self.buffer_size)
        self.data_buffers = [deque(maxlen=self.buffer_size) for _ in range(8)]

        # Lưu giá trị Min/Max để tính thống kê
        self.stats_min = [float("inf")] * 8
        self.stats_max = [float("-inf")] * 8
        self.current_voltages = [0.0] * 8
        self.current_raw = [0] * 8

        self._start_time = None

        # Xây dựng giao diện
        self._init_ui()
        self._apply_dark_theme()

        # Kết nối tín hiệu
        self.worker.data_received.connect(self._on_data_received)
        self.worker.stats_updated.connect(self._on_stats_updated)
        self.worker.status_changed.connect(self._on_status_changed)

        # Timer cập nhật đồ thị 35 FPS (mỗi ~28 ms)
        self.plot_timer = QTimer(self)
        self.plot_timer.timeout.connect(self._update_plot)
        self.plot_timer.start(28)

        # Timer cập nhật bảng thống kê và log timer mỗi 250 ms
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui_stats)
        self.ui_timer.start(250)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Thanh công cụ kết nối trên cùng
        top_bar = self._create_top_toolbar()
        main_layout.addWidget(top_bar)

        # 2. Vùng làm việc chính: Splitter chia Đồ thị (Trái) và Bảng điều khiển (Phải)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Khung đồ thị
        plot_container = self._create_plot_area()
        splitter.addWidget(plot_container)

        # Khung điều khiển & thống kê bên phải
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 7)  # Đồ thị chiếm 70%
        splitter.setStretchFactor(1, 3)  # Bảng điều khiển chiếm 30%

        main_layout.addWidget(splitter, 1)

        # 3. Thanh trạng thái dưới cùng
        status_bar = self._create_status_bar()
        main_layout.addWidget(status_bar)

    def _create_top_toolbar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("TopToolbar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Cổng COM
        layout.addWidget(QLabel("Cổng Serial:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(130)
        self._refresh_ports()
        layout.addWidget(self.port_combo)

        # Nút Refresh
        self.btn_refresh = QPushButton("🔄 Quét")
        self.btn_refresh.clicked.connect(self._refresh_ports)
        layout.addWidget(self.btn_refresh)

        # Baudrate
        layout.addWidget(QLabel("Baudrate:"))
        self.baud_combo = QComboBox()
        for b in [115200, 230400, 460800, 921600]:
            self.baud_combo.addItem(str(b), b)
        self.baud_combo.setCurrentText("115200")
        layout.addWidget(self.baud_combo)

        # Checkbox Chế độ mô phỏng
        self.chk_simulation = QCheckBox("Chế độ Mô phỏng (Offline Test)")
        self.chk_simulation.toggled.connect(self._on_sim_toggled)
        layout.addWidget(self.chk_simulation)

        layout.addStretch()

        # Nút Kết nối / Ngắt kết nối
        self.btn_connect = QPushButton("⚡ KẾT NỐI")
        self.btn_connect.setObjectName("BtnConnect")
        self.btn_connect.setMinimumWidth(130)
        self.btn_connect.clicked.connect(self._toggle_connection)
        layout.addWidget(self.btn_connect)

        return frame

    def _create_plot_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Thanh công cụ nhỏ phía trên đồ thị
        plot_ctrl = QHBoxLayout()
        plot_ctrl.addWidget(QLabel("<b>ĐỒ THỊ TÍN HIỆU THỜI GIAN THỰC (0 – 12V)</b>"))
        plot_ctrl.addStretch()

        plot_ctrl.addWidget(QLabel("Cửa sổ hiển thị:"))
        self.window_combo = QComboBox()
        self.window_combo.addItems(["2 giây", "5 giây", "10 giây", "20 giây"])
        self.window_combo.setCurrentText("5 giây")
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        plot_ctrl.addWidget(self.window_combo)

        self.btn_autoscale = QPushButton("🔍 Auto Scale Y")
        self.btn_autoscale.clicked.connect(self._autoscale_plot)
        plot_ctrl.addWidget(self.btn_autoscale)

        self.btn_clear_plot = QPushButton("🗑️ Xóa đồ thị")
        self.btn_clear_plot.clicked.connect(self._clear_buffers)
        plot_ctrl.addWidget(self.btn_clear_plot)

        layout.addLayout(plot_ctrl)

        # Cấu hình PyQtGraph PlotWidget
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("#12151B")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel("left", "Điện áp", units="V")
        self.plot_widget.setLabel("bottom", "Thời gian", units="s")
        self.plot_widget.setYRange(0, 12.5, padding=0.05)

        # Tạo 8 đường curve
        self.curves = []
        for i in range(8):
            pen = pg.mkPen(color=CHANNEL_COLORS[i], width=2)
            curve = self.plot_widget.plot(pen=pen, name=CHANNEL_NAMES[i])
            self.curves.append(curve)

        layout.addWidget(self.plot_widget)
        return container

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(10)

        # 1. Bảng giá trị tức thời của 8 kênh
        grp_channels = QGroupBox("GIÁM SÁT 8 KÊNH ĐO")
        vbox_ch = QVBoxLayout(grp_channels)

        # Nút bật/tắt nhanh
        h_toggles = QHBoxLayout()
        btn_all_on = QPushButton("Bật tất cả")
        btn_all_on.clicked.connect(lambda: self._set_all_channels(True))
        btn_all_off = QPushButton("Tắt tất cả")
        btn_all_off.clicked.connect(lambda: self._set_all_channels(False))
        h_toggles.addWidget(btn_all_on)
        h_toggles.addWidget(btn_all_off)
        vbox_ch.addLayout(h_toggles)

        # Bảng dữ liệu
        self.table = QTableWidget(8, 5)
        self.table.setHorizontalHeaderLabels(["Hiện", "Kênh", "Điện áp (V)", "Min (V)", "Max (V)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        self.channel_checkboxes = []
        for i in range(8):
            # Checkbox ẩn/hiện kênh
            chk = QCheckBox()
            chk.setChecked(True)
            chk.stateChanged.connect(self._on_channel_toggled)
            self.channel_checkboxes.append(chk)
            self.table.setCellWidget(i, 0, chk)

            # Tên kênh kèm màu sắc
            item_name = QTableWidgetItem(f"CH{i+1}")
            item_name.setForeground(QColor(CHANNEL_COLORS[i]))
            item_name.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            item_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 1, item_name)

            # Điện áp tức thời
            item_v = QTableWidgetItem("0.000")
            item_v.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 2, item_v)

            # Min
            item_min = QTableWidgetItem("0.000")
            item_min.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 3, item_min)

            # Max
            item_max = QTableWidgetItem("0.000")
            item_max.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 4, item_max)

        vbox_ch.addWidget(self.table)
        layout.addWidget(grp_channels, 2)

        # 2. Khung ghi log ra CSV
        grp_log = QGroupBox("LƯU TRỮ DỮ LIỆU (DATA LOGGER)")
        vbox_log = QVBoxLayout(grp_log)

        self.btn_toggle_log = QPushButton("⏺ BẮT ĐẦU GHI CSV")
        self.btn_toggle_log.setObjectName("BtnLog")
        self.btn_toggle_log.clicked.connect(self._toggle_logging)
        vbox_log.addWidget(self.btn_toggle_log)

        self.lbl_log_status = QLabel("Trạng thái: Chưa ghi")
        vbox_log.addWidget(self.lbl_log_status)

        self.lbl_log_info = QLabel("Số mẫu: 0 | Kích thước: 0 KB")
        vbox_log.addWidget(self.lbl_log_info)

        layout.addWidget(grp_log, 1)

        # 3. Khung vi sai chẩn đoán (Diagnostics)
        grp_diag = QGroupBox("THỐNG KÊ TRUYỀN THÔNG")
        grid_diag = QGridLayout(grp_diag)

        self.lbl_hz = QLabel("<b>0.0 Hz</b>")
        self.lbl_hz.setObjectName("RateDisplay")
        grid_diag.addWidget(QLabel("Tần số nhận:"), 0, 0)
        grid_diag.addWidget(self.lbl_hz, 0, 1)

        self.lbl_total_pkts = QLabel("0")
        grid_diag.addWidget(QLabel("Tổng gói nhận:"), 1, 0)
        grid_diag.addWidget(self.lbl_total_pkts, 1, 1)

        self.lbl_dropped_pkts = QLabel("0")
        grid_diag.addWidget(QLabel("Gói bị mất:"), 2, 0)
        grid_diag.addWidget(self.lbl_dropped_pkts, 2, 1)

        self.lbl_crc_errs = QLabel("0")
        grid_diag.addWidget(QLabel("Lỗi Checksum:"), 3, 0)
        grid_diag.addWidget(self.lbl_crc_errs, 3, 1)

        layout.addWidget(grp_diag, 1)
        return panel

    def _create_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("StatusBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_conn_status = QLabel("● Chưa kết nối")
        self.lbl_conn_status.setStyleSheet("color: #FF5252; font-weight: bold;")
        layout.addWidget(self.lbl_conn_status)

        layout.addStretch()

        lbl_info = QLabel("Đồ án tốt nghiệp: Bộ thu thập dữ liệu 8 kênh STM32H7 - SV: Mai Sỹ")
        lbl_info.setStyleSheet("color: #8892B0;")
        layout.addWidget(lbl_info)

        return frame

    def _apply_dark_theme(self):
        style = """
        QWidget {
            background-color: #171A21;
            color: #E6EDF3;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 13px;
        }
        QFrame#TopToolbar, QFrame#StatusBar {
            background-color: #1E222B;
            border-radius: 6px;
            border: 1px solid #2B3245;
        }
        QGroupBox {
            background-color: #1E222B;
            border: 1px solid #2B3245;
            border-radius: 6px;
            margin-top: 12px;
            font-weight: bold;
            color: #00E5FF;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #2D3748;
            color: #FFFFFF;
            border: 1px solid #4A5568;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #4A5568;
        }
        QPushButton#BtnConnect {
            background-color: #00C853;
            color: #000000;
            border: none;
            font-size: 14px;
        }
        QPushButton#BtnConnect:hover {
            background-color: #69F0AE;
        }
        QPushButton#BtnConnect.connected {
            background-color: #D50000;
            color: #FFFFFF;
        }
        QPushButton#BtnConnect.connected:hover {
            background-color: #FF5252;
        }
        QPushButton#BtnLog {
            background-color: #0288D1;
            color: #FFFFFF;
        }
        QPushButton#BtnLog.logging {
            background-color: #D50000;
            color: #FFFFFF;
        }
        QComboBox, QTableWidget {
            background-color: #12151B;
            border: 1px solid #2B3245;
            border-radius: 4px;
            padding: 4px;
            color: #E6EDF3;
        }
        QTableWidget QHeaderView::section {
            background-color: #1E222B;
            color: #8892B0;
            padding: 4px;
            border: none;
            font-weight: bold;
        }
        QLabel#RateDisplay {
            font-size: 16px;
            color: #00E676;
        }
        """
        self.setStyleSheet(style)

    def _refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.clear()
        ports = SerialWorker.get_available_ports()
        self.port_combo.addItems(ports)
        if current in ports:
            self.port_combo.setCurrentText(current)
        elif ports:
            self.port_combo.setCurrentIndex(0)

    def _on_sim_toggled(self, checked: bool):
        self.port_combo.setEnabled(not checked)
        self.btn_refresh.setEnabled(not checked)
        self.baud_combo.setEnabled(not checked)

    def _toggle_connection(self):
        if self.worker.isRunning():
            self.worker.stop()
        else:
            is_sim = self.chk_simulation.isChecked()
            port = self.port_combo.currentText()
            baud = int(self.baud_combo.currentText())

            if not is_sim and not port:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn cổng Serial hoặc bật chế độ Mô phỏng!")
                return

            self._clear_buffers()
            self.worker.configure(port=port, baudrate=baud, simulation=is_sim)
            self.worker.start()

    def _on_status_changed(self, is_connected: bool, message: str):
        if is_connected:
            self.btn_connect.setText("⏹ NGẮT KẾT NỐI")
            self.btn_connect.setProperty("class", "connected")
            self.btn_connect.setStyleSheet("background-color: #D50000; color: #FFFFFF;")
            self.lbl_conn_status.setText(f"● {message}")
            self.lbl_conn_status.setStyleSheet("color: #00E676; font-weight: bold;")
        else:
            self.btn_connect.setText("⚡ KẾT NỐI")
            self.btn_connect.setStyleSheet("background-color: #00C853; color: #000000;")
            self.lbl_conn_status.setText(f"● {message}")
            self.lbl_conn_status.setStyleSheet("color: #FF5252; font-weight: bold;")
            if self.logger.is_logging:
                self._toggle_logging()

    def _on_data_received(self, counter: int, voltages: list, raw_adcs: list, timestamp: float):
        if self._start_time is None:
            self._start_time = timestamp
        t = timestamp - self._start_time

        self.time_buffer.append(t)
        for i in range(8):
            self.data_buffers[i].append(voltages[i])
            self.current_voltages[i] = voltages[i]
            self.current_raw[i] = raw_adcs[i]

            # Cập nhật Min / Max
            if voltages[i] < self.stats_min[i]:
                self.stats_min[i] = voltages[i]
            if voltages[i] > self.stats_max[i]:
                self.stats_max[i] = voltages[i]

        # Ghi log nếu đang bật
        if self.logger.is_logging:
            self.logger.log_sample(timestamp, voltages)

    def _update_plot(self):
        """Hàm cập nhật đồ thị định kỳ 35 FPS."""
        if not self.time_buffer:
            return

        t_data = np.array(self.time_buffer)
        t_max = t_data[-1]
        t_min = max(0.0, t_max - self.window_seconds)
        self.plot_widget.setXRange(t_min, t_max, padding=0.01)

        for i in range(8):
            if self.channel_checkboxes[i].isChecked() and len(self.data_buffers[i]) > 0:
                v_data = np.array(self.data_buffers[i])
                self.curves[i].setData(t_data, v_data)
                self.curves[i].setVisible(True)
            else:
                self.curves[i].setVisible(False)

    def _update_ui_stats(self):
        """Cập nhật các nhãn bảng dữ liệu và trạng thái ghi file mỗi 250 ms."""
        for i in range(8):
            v_cur = self.current_voltages[i]
            v_min = self.stats_min[i] if self.stats_min[i] != float("inf") else 0.0
            v_max = self.stats_max[i] if self.stats_max[i] != float("-inf") else 0.0

            item_v = self.table.item(i, 2)
            if item_v:
                item_v.setText(f"{v_cur:.3f}")
            item_min = self.table.item(i, 3)
            if item_min:
                item_min.setText(f"{v_min:.3f}")
            item_max = self.table.item(i, 4)
            if item_max:
                item_max.setText(f"{v_max:.3f}")

        # Cập nhật trạng thái ghi log
        if self.logger.is_logging:
            stats = self.logger.get_stats()
            mins = int(stats["elapsed_sec"] // 60)
            secs = int(stats["elapsed_sec"] % 60)
            self.lbl_log_status.setText(f"Đang ghi: {os.path.basename(stats['file_path'])} ({mins:02d}:{secs:02d})")
            self.lbl_log_info.setText(f"Số mẫu: {stats['total_rows']:,} | Kích thước: {stats['file_size_kb']:.1f} KB")

    def _on_stats_updated(self, total: int, dropped: int, errors: int, hz: float):
        self.lbl_hz.setText(f"<b>{hz:.1f} Hz</b>")
        self.lbl_total_pkts.setText(f"{total:,}")
        self.lbl_dropped_pkts.setText(f"{dropped:,}")
        self.lbl_crc_errs.setText(f"{errors:,}")

    def _toggle_logging(self):
        if self.logger.is_logging:
            self.logger.stop()
            self.btn_toggle_log.setText("⏺ BẮT ĐẦU GHI CSV")
            self.btn_toggle_log.setStyleSheet("background-color: #0288D1; color: #FFFFFF;")
            self.lbl_log_status.setText("Trạng thái: Đã dừng ghi")
        else:
            file_path = self.logger.start(output_dir="logs")
            self.btn_toggle_log.setText("⏹ DỪNG GHI CSV")
            self.btn_toggle_log.setStyleSheet("background-color: #D50000; color: #FFFFFF;")
            self.lbl_log_status.setText(f"Đang ghi: {os.path.basename(file_path)}")

    def _on_window_changed(self):
        text = self.window_combo.currentText()
        if "2" in text:
            self.window_seconds = 2.0
        elif "5" in text:
            self.window_seconds = 5.0
        elif "10" in text:
            self.window_seconds = 10.0
        elif "20" in text:
            self.window_seconds = 20.0

        self.buffer_size = int(self.sample_rate * self.window_seconds)
        self.time_buffer = deque(self.time_buffer, maxlen=self.buffer_size)
        for i in range(8):
            self.data_buffers[i] = deque(self.data_buffers[i], maxlen=self.buffer_size)

    def _autoscale_plot(self):
        self.plot_widget.enableAutoRange(axis='y')

    def _clear_buffers(self):
        self.time_buffer.clear()
        for i in range(8):
            self.data_buffers[i].clear()
            self.stats_min[i] = float("inf")
            self.stats_max[i] = float("-inf")
        self._start_time = None
        self._autoscale_plot()

    def _on_channel_toggled(self):
        self._update_plot()

    def _set_all_channels(self, state: bool):
        for chk in self.channel_checkboxes:
            chk.setChecked(state)

    def closeEvent(self, event):
        """Dừng luồng và đóng file khi thoát app."""
        if self.logger.is_logging:
            self.logger.stop()
        if self.worker.isRunning():
            self.worker.stop()
        event.accept()
