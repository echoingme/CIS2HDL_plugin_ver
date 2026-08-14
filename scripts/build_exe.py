#!/usr/bin/env python3
"""CIS2HDL PyInstaller 打包脚本。

用法:
    python scripts/build_exe.py              # 默认 --onedir
    python scripts/build_exe.py --onefile    # 单文件模式
    python scripts/build_exe.py --clean      # 清理后重新构建

输出:
    dist/CIS2HDL/   (--onedir)
    dist/CIS2HDL.exe (--onefile, Windows only)
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def find_spec_file(root: Path) -> Path:
    """查找项目根目录下的 spec 文件。"""
    candidates = list(root.glob("*.spec"))
    if not candidates:
        raise FileNotFoundError(f"No .spec file found in {root}")
    if len(candidates) > 1:
        logger.warning(
            "Multiple .spec files found: %s — using %s",
            [c.name for c in candidates],
            candidates[0].name,
        )
    return candidates[0]


def clean_build_artifacts(root: Path) -> None:
    """清理 PyInstaller 构建产物。"""
    for name in ("build", "dist", "__pycache__"):
        path = root / name
        if path.exists():
            logger.info("Removing: %s", path)
            shutil.rmtree(path)

    # Remove .spec cache
    for pattern in ("*.pyc", "*.pyo"):
        for pyc in root.rglob(pattern):
            pyc.unlink()
            logger.debug("Removed: %s", pyc)


def run_pyinstaller(root: Path, onefile: bool = False) -> int:
    """运行 PyInstaller 打包。

    Args:
        root: 项目根目录。
        onefile: 是否使用 --onefile 模式。

    Returns:
        PyInstaller 进程的返回码。
    """
    spec_file = find_spec_file(root)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--noconfirm",
    ]

    if onefile:
        # Override spec: build as single-file EXE
        cmd.append("--onefile")

    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(root), check=False)

    if result.returncode == 0:
        logger.info("Build successful!")
        dist_dir = root / "dist"
        if dist_dir.exists():
            items = list(dist_dir.iterdir())
            for item in items:
                if item.is_file():
                    size_mb = item.stat().st_size / (1024 * 1024)
                    logger.info("  Output: %s (%.1f MB)", item.name, size_mb)
                elif item.is_dir():
                    logger.info("  Output: %s/ (directory)", item.name)
    else:
        logger.error("Build failed with code %d", result.returncode)

    return result.returncode


def main() -> None:
    """CLI entry point for the build script."""
    parser = argparse.ArgumentParser(
        description="CIS2HDL PyInstaller 打包工具",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="构建为单文件可执行文件 (--onefile)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理构建产物后重新构建",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )

    root = Path(__file__).parent.parent.absolute()
    logger.info("Project root: %s", root)

    if args.clean:
        clean_build_artifacts(root)

    returncode = run_pyinstaller(root, onefile=args.onefile)
    sys.exit(returncode)


if __name__ == "__main__":
    main()
