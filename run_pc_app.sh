#!/bin/bash
# Script khởi chạy ứng dụng Desktop Data Logger 8 kênh STM32H7 (250 Hz)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Tạo môi trường ảo Python .venv..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r pc_app/requirements.txt
fi

echo "Khởi chạy ứng dụng giám sát 8 kênh STM32H7..."
exec .venv/bin/python pc_app/app.py
