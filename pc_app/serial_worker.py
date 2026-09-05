"""
Module: serial_worker.py
Luồng thu nhận và phân tích gói tin Serial nhị phân tốc độ cao (250 Hz) độc lập.
Hỗ trợ cả chế độ cổng COM thực và chế độ mô phỏng (Simulation Mode) để test offline.
"""

import time
import math
import serial
import serial.tools.list_ports
from PyQt6.QtCore import QThread, pyqtSignal

from protocol import (
    FRAME_SIZE,
    HEADER_1,
    HEADER_2,
    parse_frame,
    build_simulated_frame,
    DEFAULT_VREF,
    DEFAULT_DIVIDER_RATIO,
)


class SerialWorker(QThread):
    # Signals gửi sang Main UI
    data_received = pyqtSignal(int, list, list, float)   # counter, voltages, raw_adcs, timestamp
    stats_updated = pyqtSignal(int, int, int, float)    # total_pkts, dropped, crc_errs, hz
    status_changed = pyqtSignal(bool, str)              # is_connected, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.port_name = ""
        self.baudrate = 115200
        self.is_simulation = False
        self.running = False
        self._serial: serial.Serial = None

        # Hiệu chuẩn điện áp
        self.vref = DEFAULT_VREF
        self.divider_ratio = DEFAULT_DIVIDER_RATIO

        # Biến thống kê
        self.total_packets = 0
        self.dropped_packets = 0
        self.crc_errors = 0
        self.last_counter = -1
        self.current_hz = 0.0

    @staticmethod
    def get_available_ports():
        """Lấy danh sách các cổng COM/Serial khả dụng trên hệ thống."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def configure(self, port: str, baudrate: int = 115200, simulation: bool = False,
                  vref: float = 3.3, divider_ratio: float = 12.0/3.3):
        self.port_name = port
        self.baudrate = baudrate
        self.is_simulation = simulation
        self.vref = vref
        self.divider_ratio = divider_ratio

    def run(self):
        self.running = True
        self.total_packets = 0
        self.dropped_packets = 0
        self.crc_errors = 0
        self.last_counter = -1
        self.current_hz = 0.0

        if self.is_simulation:
            self._run_simulation()
        else:
            self._run_hardware()

    def stop(self):
        self.running = False
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self.wait(1000)

    def _run_hardware(self):
        try:
            self._serial = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=0.1,
                write_timeout=0.1,
            )
            # Xóa buffer rác cũ
            self._serial.reset_input_buffer()
            self.status_changed.emit(True, f"Đã kết nối {self.port_name} ({self.baudrate} bps)")
        except Exception as e:
            self.status_changed.emit(False, f"Lỗi mở cổng: {str(e)}")
            self.running = False
            return

        buffer = bytearray()
        last_stat_time = time.time()
        stat_packet_count = 0

        while self.running:
            try:
                bytes_available = self._serial.in_waiting
                if bytes_available > 0:
                    data = self._serial.read(min(bytes_available, 512))
                    buffer.extend(data)

                    # Bóc tách khung 21 bytes
                    while len(buffer) >= FRAME_SIZE:
                        # Tìm Header 0xAA 0x55
                        if buffer[0] != HEADER_1 or buffer[1] != HEADER_2:
                            buffer.pop(0)
                            continue

                        # Đã tìm thấy Header, kiểm tra đủ 21 bytes chưa
                        if len(buffer) < FRAME_SIZE:
                            break

                        candidate_frame = bytes(buffer[:FRAME_SIZE])
                        result = parse_frame(candidate_frame, self.vref, self.divider_ratio)

                        if result is not None:
                            # Khung hợp lệ
                            counter, voltages, raw_adcs = result
                            now_time = time.time()

                            # Kiểm tra mất gói
                            if self.last_counter != -1:
                                expected = (self.last_counter + 1) & 0xFF
                                if counter != expected:
                                    diff = (counter - expected) & 0xFF
                                    self.dropped_packets += diff

                            self.last_counter = counter
                            self.total_packets += 1
                            stat_packet_count += 1

                            self.data_received.emit(counter, voltages, raw_adcs, now_time)
                            # Cắt bỏ khung đã xử lý
                            del buffer[:FRAME_SIZE]
                        else:
                            # Lỗi checksum hoặc tail -> lệch byte, bỏ 1 byte để dò lại
                            self.crc_errors += 1
                            buffer.pop(0)

                else:
                    time.sleep(0.001)

                # Tính tần số Hz mỗi 500 ms
                now = time.time()
                elapsed = now - last_stat_time
                if elapsed >= 0.5:
                    self.current_hz = stat_packet_count / elapsed
                    stat_packet_count = 0
                    last_stat_time = now
                    self.stats_updated.emit(
                        self.total_packets,
                        self.dropped_packets,
                        self.crc_errors,
                        self.current_hz
                    )

            except Exception as e:
                if self.running:
                    self.status_changed.emit(False, f"Lỗi đọc cổng: {str(e)}")
                break

        if self._serial and self._serial.is_open:
            self._serial.close()
        self.status_changed.emit(False, "Đã ngắt kết nối cổng Serial")

    def _run_simulation(self):
        """Chế độ tạo dữ liệu giả lập 250 Hz phục vụ test giao diện không cần kit."""
        self.status_changed.emit(True, "Đang chạy chế độ mô phỏng (Simulation 250 Hz)")
        counter = 0
        sim_time = 0.0
        dt = 1.0 / 250.0  # 4 ms

        last_stat_time = time.time()
        stat_packet_count = 0

        while self.running:
            loop_start = time.time()

            # Tạo 8 tín hiệu mẫu có dạng sóng đa dạng
            # CH1: Sine 2 Hz (0 - 10V)
            ch1 = 5.0 + 4.5 * math.sin(2 * math.pi * 2.0 * sim_time)
            # CH2: Sine 5 Hz (1 - 5V)
            ch2 = 3.0 + 2.0 * math.sin(2 * math.pi * 5.0 * sim_time)
            # CH3: Triangle wave 1 Hz (0 - 8V)
            ch3 = 8.0 * abs((sim_time * 1.0) % 1.0 - 0.5) * 2
            # CH4: Square wave 2 Hz (0V hoặc 6V)
            ch4 = 6.0 if math.sin(2 * math.pi * 2.0 * sim_time) > 0 else 0.5
            # CH5: DC 3.3V
            ch5 = 3.3
            # CH6: DC 5.0V
            ch6 = 5.0
            # CH7: DC 10.0V
            ch7 = 10.0
            # CH8: Sine 0.5 Hz dao động chậm (0 - 12V)
            ch8 = 6.0 + 5.5 * math.sin(2 * math.pi * 0.5 * sim_time)

            voltages = [ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8]
            # Đổi sang ADC 16-bit
            raw_adcs = [
                int(max(0, min(65535, (v / (self.vref * self.divider_ratio)) * 65535)))
                for v in voltages
            ]

            now_time = time.time()
            self.total_packets += 1
            stat_packet_count += 1
            self.data_received.emit(counter, voltages, raw_adcs, now_time)

            counter = (counter + 1) & 0xFF
            sim_time += dt

            # Tính tần số Hz mỗi 500 ms
            now = time.time()
            elapsed = now - last_stat_time
            if elapsed >= 0.5:
                self.current_hz = stat_packet_count / elapsed
                stat_packet_count = 0
                last_stat_time = now
                self.stats_updated.emit(
                    self.total_packets,
                    self.dropped_packets,
                    self.crc_errors,
                    self.current_hz
                )

            # Ngủ để duy trì nhịp 250 Hz (4 ms)
            spent = time.time() - loop_start
            sleep_time = max(0.0, dt - spent)
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.status_changed.emit(False, "Đã dừng chế độ mô phỏng")
