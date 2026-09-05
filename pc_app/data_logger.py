"""
Module: data_logger.py
Ghi dữ liệu 8 kênh đo vào tệp CSV với định dạng thời gian chuẩn và cơ chế đệm chống nghẽn I/O.
Hỗ trợ xuất phiên đo (Capture Export) theo dải thời gian chọn lọc phong cách Saleae Logic.
"""

import os
import time
import csv
from typing import List, Optional
from datetime import datetime


class DataLogger:
    def __init__(self, buffer_size: int = 50):
        self.is_logging = False
        self.file_path: Optional[str] = None
        self._file = None
        self._csv_writer = None
        self._buffer: List[List] = []
        self._buffer_size = buffer_size
        self._start_time = 0.0
        self.total_rows_logged = 0

    def start(self, output_dir: str = "logs", custom_filename: Optional[str] = None) -> str:
        """
        Bắt đầu ghi file log mới liên tục xuống đĩa.
        Trả về đường dẫn file đã tạo.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        if custom_filename:
            filename = custom_filename
            if not filename.endswith(".csv"):
                filename += ".csv"
        else:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"DataLog_{timestamp_str}.csv"

        self.file_path = os.path.join(output_dir, filename)
        self._file = open(self.file_path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._file)

        # Ghi dòng tiêu đề
        header = [
            "Timestamp_s",
            "Time_ms",
            "CH1_V",
            "CH2_V",
            "CH3_V",
            "CH4_V",
            "CH5_V",
            "CH6_V",
            "CH7_V",
            "CH8_V",
        ]
        self._csv_writer.writerow(header)

        self._buffer = []
        self.total_rows_logged = 0
        self._start_time = time.time()
        self.is_logging = True
        return self.file_path

    def log_sample(self, timestamp_s: float, voltages: List[float]):
        """
        Ghi một mẫu dữ liệu vào bộ đệm. Tự động flush xuống đĩa khi đầy bộ đệm.
        """
        if not self.is_logging or not self._csv_writer:
            return

        elapsed_ms = (timestamp_s - self._start_time) * 1000.0
        row = [
            f"{timestamp_s:.4f}",
            f"{elapsed_ms:.1f}",
            *[f"{v:.4f}" for v in voltages],
        ]
        self._buffer.append(row)
        self.total_rows_logged += 1

        if len(self._buffer) >= self._buffer_size:
            self._flush()

    def _flush(self):
        """Ghi toàn bộ mảng đệm xuống file."""
        if self._file and self._buffer:
            self._csv_writer.writerows(self._buffer)
            self._file.flush()
            self._buffer.clear()

    def stop(self):
        """Dừng ghi log và đóng file an toàn."""
        if self.is_logging:
            self._flush()
            if self._file:
                self._file.close()
                self._file = None
            self._csv_writer = None
            self.is_logging = False

    def get_stats(self) -> dict:
        """Lấy thống kê ghi file hiện tại."""
        elapsed_sec = time.time() - self._start_time if self.is_logging else 0.0
        file_size_kb = 0.0
        if self.file_path and os.path.exists(self.file_path):
            file_size_kb = os.path.getsize(self.file_path) / 1024.0

        return {
            "is_logging": self.is_logging,
            "file_path": self.file_path or "",
            "elapsed_sec": elapsed_sec,
            "total_rows": self.total_rows_logged,
            "file_size_kb": file_size_kb,
        }

    @staticmethod
    def export_data(
        file_path: str,
        time_list: list,
        channels_data: list,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> int:
        """
        Xuất bộ nhớ đệm RAM (toàn bộ hoặc dải thời gian chọn lọc) ra tệp CSV.
        Trả về tổng số dòng đã xuất.
        """
        if not time_list or not channels_data:
            return 0

        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        rows_written = 0
        t0 = time_list[0]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Header
            header = [
                "Time_Relative_s",
                "Timestamp_s",
                "CH1_V",
                "CH2_V",
                "CH3_V",
                "CH4_V",
                "CH5_V",
                "CH6_V",
                "CH7_V",
                "CH8_V",
            ]
            writer.writerow(header)

            num_points = len(time_list)
            for idx in range(num_points):
                t = time_list[idx]
                # Lọc theo khoảng thời gian nếu có
                if start_time is not None and t < start_time:
                    continue
                if end_time is not None and t > end_time:
                    continue

                rel_t = t - t0
                row = [
                    f"{rel_t:.4f}",
                    f"{t:.4f}",
                    *[f"{channels_data[ch][idx]:.4f}" for ch in range(len(channels_data))],
                ]
                writer.writerow(row)
                rows_written += 1

        return rows_written
