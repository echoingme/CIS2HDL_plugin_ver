"""BinaryReader — 位置跟踪的二进制 Buffer 读取器（DSN Parser Layer 2）。

从 openOrCadParser 的 DataStream.hpp/DataStream.cpp 移植为纯 Python。
所有整数读取均为 little-endian。

参考：
    - openOrCadParser C++: DataStream.hpp
    - universal-netlist TypeScript: BinaryReader.ts
"""

from __future__ import annotations

import struct
from typing import overload


class BinaryReadError(Exception):
    """二进制读取错误。"""

    def __init__(self, message: str, position: int = 0) -> None:
        pos_info = f" at offset 0x{position:04X}" if position else ""
        super().__init__(f"Binary read error{pos_info}: {message}")


class BinaryReader:
    """类型化二进制 Buffer 读取器，跟踪当前读取位置。

    Usage:
        reader = BinaryReader(buffer)
        count = reader.read_uint32()
        name = reader.read_string_zero_term()
    """

    def __init__(self, buffer: bytes, offset: int = 0) -> None:
        """初始化二进制读取器。

        Args:
            buffer: 原始字节缓冲区。
            offset: 起始读取偏移量。
        """
        self._buf = memoryview(buffer)
        self._pos: int = offset
        self._size: int = len(buffer)

    # ── Position helpers ──────────────────────────────────────────────

    def tell(self) -> int:
        """返回当前读取位置。"""
        return self._pos

    def seek(self, offset: int) -> None:
        """设置读取位置到绝对偏移量。"""
        if offset < 0 or offset > self._size:
            raise BinaryReadError(
                f"seek {offset} out of range [0, {self._size}]",
                position=self._pos,
            )
        self._pos = offset

    def skip(self, n: int) -> None:
        """从当前位置跳过 n 字节。"""
        new_pos = self._pos + n
        if new_pos < 0 or new_pos > self._size:
            raise BinaryReadError(
                f"skip {n} would exceed buffer", position=self._pos
            )
        self._pos = new_pos

    def peek(self, n: int) -> bytes:
        """查看接下来的 n 字节但不移动位置。"""
        if self._pos + n > self._size:
            raise BinaryReadError(
                f"peek {n} exceeds buffer", position=self._pos
            )
        return bytes(self._buf[self._pos : self._pos + n])

    def remaining(self) -> int:
        """返回剩余可读字节数。"""
        return self._size - self._pos

    def is_eof(self) -> bool:
        """检查是否已到缓冲区末尾。"""
        return self._pos >= self._size

    # ── Unsigned integer readers ─────────────────────────────────────

    def read_uint8(self) -> int:
        """读取 1 字节无符号整数。"""
        if self._pos >= self._size:
            raise BinaryReadError("read_uint8 at end of buffer", position=self._pos)
        val: int = self._buf[self._pos]
        self._pos += 1
        return val

    def read_uint16(self) -> int:
        """读取 2 字节无符号整数（little-endian）。"""
        val: int = struct.unpack_from("<H", self._buf, self._pos)[0]
        self._pos += 2
        return val

    def read_uint32(self) -> int:
        """读取 4 字节无符号整数（little-endian）。"""
        val: int = struct.unpack_from("<I", self._buf, self._pos)[0]
        self._pos += 4
        return val

    # ── Signed integer readers ───────────────────────────────────────

    def read_int8(self) -> int:
        """读取 1 字节有符号整数。"""
        val: int = struct.unpack_from("<b", self._buf, self._pos)[0]
        self._pos += 1
        return val

    def read_int16(self) -> int:
        """读取 2 字节有符号整数（little-endian）。"""
        val: int = struct.unpack_from("<h", self._buf, self._pos)[0]
        self._pos += 2
        return val

    def read_int32(self) -> int:
        """读取 4 字节有符号整数（little-endian）。"""
        val: int = struct.unpack_from("<i", self._buf, self._pos)[0]
        self._pos += 4
        return val

    # ── Raw bytes ────────────────────────────────────────────────────

    def read_bytes(self, n: int) -> bytes:
        """读取 n 字节原始数据。"""
        if self._pos + n > self._size:
            raise BinaryReadError(
                f"read_bytes {n} exceeds buffer", position=self._pos
            )
        val = bytes(self._buf[self._pos : self._pos + n])
        self._pos += n
        return val

    # ── String readers ───────────────────────────────────────────────

    def read_string_zero_term(self) -> str:
        """读取以 NUL 结尾的字符串（ISO-8859-1 编码）。

        用于大多数 DSN 流中的字符串字段。
        """
        start = self._pos
        while self._pos < self._size and self._buf[self._pos] != 0:
            self._pos += 1
        result = bytes(self._buf[start : self._pos]).decode("latin-1")
        # Skip the NULL terminator
        if self._pos < self._size:
            self._pos += 1
        return result

    def read_string_len_term(self) -> str:
        """读取长度前缀 + NUL 结尾的字符串。

        长度前缀是 uint16，字符串以 NUL 结尾。
        """
        length = self.read_uint16()
        if length > self.remaining():
            raise BinaryReadError(
                f"String length {length} exceeds remaining {self.remaining()} bytes",
                position=self._pos,
            )
        result = bytes(self._buf[self._pos : self._pos + length - 1]).decode("latin-1")
        self._pos += length  # Includes NULL terminator
        return result

    def read_string_len_zero_term(self) -> str:
        """读取长度前缀 + 零结尾字符串（uint32 长度前缀）。

        用于 Page 流中的字符串字段（如器件名、属性值）。
        """
        length = self.read_uint32()
        if length == 0:
            return ""
        if length > self.remaining():
            # Some DSN files have inconsistent length fields;
            # fall back to zero-terminated read.
            self._pos -= 4
            return self.read_string_zero_term()
        result = bytes(self._buf[self._pos : self._pos + length - 1]).decode("latin-1")
        self._pos += length  # Moves past NULL terminator
        return result

    def read_string_byte_len(self) -> str:
        """读取单字节长度前缀的字符串。

        先读 uint8 长度，然后读对应数量的字节。
        """
        length = self.read_uint8()
        if length == 0:
            return ""
        result = bytes(self._buf[self._pos : self._pos + length]).decode("latin-1")
        self._pos += length
        return result

    def read_string_uint16_len(self) -> str:
        """读取 uint16 长度前缀的字符串（RTL DSN 格式，无 NUL 终止符）。

        RTL DSN 变体格式中字符串的编码方式为：
        uint16 长度前缀 + 原始字节（无 NUL 终止）。

        与 read_string_len_term() 的区别：后者期望长度包含一个 NUL 终止字节。
        """
        length = self.read_uint16()
        if length == 0:
            return ""
        if length > self.remaining():
            raise BinaryReadError(
                f"String length {length} exceeds remaining {self.remaining()} bytes",
                position=self._pos,
            )
        result = bytes(self._buf[self._pos : self._pos + length]).decode("latin-1")
        self._pos += length
        return result

    # ── Debug ─────────────────────────────────────────────────────────

    def hexdump(self, n: int = 64) -> str:
        """返回当前位置的十六进制转储。"""
        end = min(self._pos + n, self._size)
        data = bytes(self._buf[self._pos : end])
        return data.hex(" ")
