"""
Module: protocol.py
Đặc tả giao thức truyền thông nhị phân UART 21 bytes giữa STM32H7 và máy tính.
"""

import struct
from typing import Tuple, List, Optional

HEADER_1 = 0xAA
HEADER_2 = 0x55
TAIL = 0x0D
FRAME_SIZE = 21
NUM_CHANNELS = 8

# Mặc định: VREF vi điều khiển = 3.3V, tỉ lệ phân áp đầu vào = 12.0V / 3.3V
DEFAULT_VREF = 3.3
DEFAULT_DIVIDER_RATIO = 12.0 / 3.3


def calculate_checksum(data: bytes) -> int:
    """
    Tính checksum XOR từ Byte 2 (Packet Counter) đến Byte 18 (Channel 8 High Byte).
    """
    checksum = 0
    for b in data[2:19]:
        checksum ^= b
    return checksum


def parse_frame(
    raw_frame: bytes,
    vref: float = DEFAULT_VREF,
    divider_ratio: float = DEFAULT_DIVIDER_RATIO,
) -> Optional[Tuple[int, List[float], List[int]]]:
    """
    Giải mã khung tin 21 bytes:
    Trả về: (packet_counter, voltages[8], raw_adcs[8]) nếu hợp lệ, ngược lại trả về None.
    """
    if len(raw_frame) != FRAME_SIZE:
        return None

    # Kiểm tra Header và Tail
    if raw_frame[0] != HEADER_1 or raw_frame[1] != HEADER_2:
        return None
    if raw_frame[20] != TAIL:
        return None

    # Kiểm tra Checksum
    expected_checksum = calculate_checksum(raw_frame)
    if raw_frame[19] != expected_checksum:
        return None

    # Lấy Packet Counter
    packet_counter = raw_frame[2]

    # Giải mã 8 kênh 16-bit unsigned int (Little-Endian)
    # Byte 3 đến 18 = 16 bytes
    raw_adcs = list(struct.unpack("<8H", raw_frame[3:19]))

    # Tính điện áp đầu vào thực tế (0.0V - 12.0V)
    voltages = [
        (adc / 65535.0) * vref * divider_ratio for adc in raw_adcs
    ]

    return packet_counter, voltages, raw_adcs


def build_simulated_frame(
    packet_counter: int,
    raw_adcs: List[int]
) -> bytes:
    """
    Tạo một khung tin 21 bytes giả lập dùng cho chế độ mô phỏng kiểm thử giao diện.
    """
    frame = bytearray(FRAME_SIZE)
    frame[0] = HEADER_1
    frame[1] = HEADER_2
    frame[2] = packet_counter & 0xFF
    
    # 8 channels
    struct.pack_into("<8H", frame, 3, *raw_adcs)
    
    # Checksum
    frame[19] = calculate_checksum(bytes(frame))
    frame[20] = TAIL
    
    return bytes(frame)
