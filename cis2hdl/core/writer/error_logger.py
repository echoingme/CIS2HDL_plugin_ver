"""转换错误/警告日志自动生成器。

每次 CIS→HDL 转换自动输出:
    {project_name}_errors.log    — 结构化错误日志（HTML 可读）
    {project_name}_errors.txt    — 纯文本版（grep 友好）

日志级别:
    ERROR   — 阻断性错误（文件缺失、解析失败）
    WARNING — 可继续但需注意（未匹配器件、信息损失、模糊匹配）
    INFO    — 统计摘要
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConversionLogger:
    """转换日志记录器。每次转换自动生成错误和警告日志文件。"""

    _events: list[dict[str, Any]] = []
    _start_time: datetime | None = None

    @classmethod
    def reset(cls) -> None:
        """每次转换前重置。"""
        cls._events = []
        cls._start_time = datetime.now()

    @classmethod
    def log(cls, level: str, category: str, message: str, detail: str = "",
            file_path: str = "", line: int = 0) -> None:
        """通用日志记录方法。

        Args:
            level: 日志级别 (ERROR/WARNING/INFO)。
            category: 日志类别 (PARSE/MATCH/VALIDATE 等)。
            message: 日志消息。
            detail: 附加详情。
            file_path: 相关文件路径。
            line: 相关行号。
        """
        cls._events.append({
            "time": datetime.now(),
            "level": level.upper(),
            "category": category,
            "message": message,
            "detail": detail,
            "file": file_path,
            "line": line,
        })

    @classmethod
    def log_error(cls, category: str, message: str, detail: str = "",
                  file_path: str = "", line: int = 0) -> None:
        """记录 ERROR 级别日志。"""
        cls.log("ERROR", category, message, detail, file_path, line)

    @classmethod
    def log_warning(cls, category: str, message: str, detail: str = "",
                    file_path: str = "", line: int = 0) -> None:
        """记录 WARNING 级别日志。"""
        cls.log("WARNING", category, message, detail, file_path, line)

    @classmethod
    def log_info(cls, category: str, message: str, detail: str = "") -> None:
        """记录 INFO 级别日志。"""
        cls.log("INFO", category, message, detail)

    @classmethod
    def write(cls, output_dir: Path, project_name: str) -> tuple[Path, Path]:
        """写入错误日志文件。

        生成两个格式的日志文件:
            - HTML (.log): 浏览器可读的彩色表格。
            - 纯文本 (.txt): grep 友好的纯文本格式。

        Args:
            output_dir: 输出目录。
            project_name: 项目名称。

        Returns:
            (html_path, txt_path) 元组。
        """
        html_path = output_dir / f"{project_name}_errors.log"
        txt_path = output_dir / f"{project_name}_errors.txt"

        # 统计
        errors = [e for e in cls._events if e["level"] == "ERROR"]
        warnings = [e for e in cls._events if e["level"] == "WARNING"]
        infos = [e for e in cls._events if e["level"] == "INFO"]

        start_time_str = (
            cls._start_time.strftime("%Y-%m-%d %H:%M:%S")
            if cls._start_time else "unknown"
        )

        # ── HTML 日志 ───────────────────────────────────────────────
        html_lines = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            f"<title>{project_name} — 转换错误日志</title>",
            "<style>",
            "body{font-family:monospace;margin:20px;background:#1e1e1e;color:#d4d4d4}",
            ".error{color:#f44747} .warning{color:#cca700} .info{color:#6a9955}",
            "table{border-collapse:collapse;width:100%}",
            "td,th{border:1px solid #333;padding:4px 8px;font-size:12px}",
            ".summary{background:#252526;padding:12px;margin-bottom:16px}",
            "</style></head><body>",
            f"<h2>{project_name} — 转换错误日志</h2>",
            f"<div class='summary'>",
            f"<p>转换时间: {start_time_str}</p>",
            f"<p>错误: {len(errors)} | 警告: {len(warnings)} | 信息: {len(infos)}</p>",
            f"</div>",
        ]

        if cls._events:
            html_lines.append(
                "<table><tr><th>时间</th><th>级别</th><th>类别</th>"
                "<th>消息</th><th>详情</th><th>文件</th></tr>"
            )
            for e in cls._events:
                cls_name = e["level"].lower()
                html_lines.append(
                    f"<tr class='{cls_name}'>"
                    f"<td>{e['time'].strftime('%H:%M:%S')}</td>"
                    f"<td>{e['level']}</td>"
                    f"<td>{e['category']}</td>"
                    f"<td>{e['message']}</td>"
                    f"<td>{e['detail'][:200]}</td>"
                    f"<td>{e['file']}:{e['line']}</td>"
                    f"</tr>"
                )
            html_lines.append("</table>")

        html_lines.append("</body></html>")

        output_dir.mkdir(parents=True, exist_ok=True)
        html_path.write_text("\n".join(html_lines), encoding="utf-8")

        # ── 纯文本日志 ─────────────────────────────────────────────
        txt_lines = [
            f"=== {project_name} — 转换错误日志 ===",
            f"转换时间: {start_time_str}",
            f"错误: {len(errors)} | 警告: {len(warnings)} | 信息: {len(infos)}",
            "",
        ]
        for e in cls._events:
            txt_lines.append(
                f"[{e['time'].strftime('%H:%M:%S')}] [{e['level']}] "
                f"[{e['category']}] {e['message']}"
                + (f" | {e['detail'][:100]}" if e['detail'] else "")
                + (f" | {e['file']}:{e['line']}" if e['file'] else "")
            )

        txt_path.write_text("\n".join(txt_lines), encoding="utf-8")

        logger.info("Error log written: %s (%d events)", html_path, len(cls._events))
        return html_path, txt_path
