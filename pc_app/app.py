"""
File: app.py
Điểm khởi chạy ứng dụng giám sát và thu thập dữ liệu 8 kênh STM32H7 (250 Hz).
"""

import sys
import os

# Thêm thư mục pc_app vào sys.path để đảm bảo import đúng trong mọi môi trường
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from main_window import MainWindow


def main():
    # Hỗ trợ High DPI trên các màn hình độ phân giải cao
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("STM32H7 8-Channel Data Logger")
    app.setApplicationDisplayName("Hệ thống thu thập dữ liệu 8 kênh STM32H7 (250 Hz)")

    # Đặt font chữ mặc định hiện đại và rõ nét
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
