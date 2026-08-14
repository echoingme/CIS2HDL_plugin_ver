"""CIS2HDL 自定义异常层次。

所有自定义异常继承自 CIS2HDLError 基类，便于统一捕获和分类处理。
参考：ROADMAP D1.5 异常处理策略。
"""

from __future__ import annotations


class CIS2HDLError(Exception):
    """所有 CIS2HDL 异常的基类。

    可用于捕获框架内所有自定义异常，同时不干扰标准库异常
    （如 FileNotFoundError、OSError 等）。
    """
    pass


class CIS2HDLParseError(CIS2HDLError):
    """解析失败（DSN/EDIF/OLB 文件格式错误）。

    用于指示输入文件无法正确解析的情况，包括：
    - DSN 二进制流格式异常
    - EDIF 语法错误
    - OLB 文件结构损坏
    - 解析器注册表查找失败
    """

    def __init__(
        self,
        message: str,
        file_path: str = "",
        offset: int = 0,
    ) -> None:
        self.file_path: str = file_path
        self.offset: int = offset
        super().__init__(message)

    def __str__(self) -> str:
        base: str = super().__str__()
        parts: list[str] = [base]
        if self.file_path:
            parts.append(f"[file: {self.file_path}]")
        if self.offset:
            parts.append(f"[offset: 0x{self.offset:X}]")
        return " ".join(parts)


class CIS2HDLMatchError(CIS2HDLError):
    """器件匹配失败。

    当自动匹配流程无法为 CIS 器件找到对应的 HDL 器件时抛出。
    可用于精确匹配、模糊匹配和特征匹配任一阶段。
    """

    def __init__(
        self,
        message: str,
        source_library_id: str = "",
    ) -> None:
        self.source_library_id: str = source_library_id
        super().__init__(message)

    def __str__(self) -> str:
        base: str = super().__str__()
        if self.source_library_id:
            return f"{base} [source: {self.source_library_id}]"
        return base


class CIS2HDLConfigError(CIS2HDLError):
    """配置错误（路径无效/参数非法）。

    用于指示配置参数不合法的情况，包括：
    - 路径不存在或无权限
    - 编码声明无效
    - 页面/网格尺寸非法
    """
    pass
