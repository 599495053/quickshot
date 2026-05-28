"""模块复杂度监控脚本。

检查超过行数/函数数阈值的模块，用于 CI 告警。

用法：python scripts/check_complexity.py [--warn-lines 500] [--warn-funcs 30]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_WARN_LINES = 600
DEFAULT_WARN_FUNCS = 35


def scan_package(package_dir: Path):
    results = []
    for py_file in sorted(package_dir.rglob("*.py")):
        if "__pycache__" in py_file.as_posix():
            continue
        lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        n_lines = len(lines)
        n_funcs = sum(1 for l in lines if l.strip().startswith("def "))
        n_classes = sum(1 for l in lines if l.strip().startswith("class "))
        rel = py_file.relative_to(package_dir.parent)
        results.append((rel.as_posix(), n_lines, n_funcs, n_classes))
    return results


def main():
    parser = argparse.ArgumentParser(description="Check module complexity")
    parser.add_argument("--warn-lines", type=int, default=DEFAULT_WARN_LINES)
    parser.add_argument("--warn-funcs", type=int, default=DEFAULT_WARN_FUNCS)
    parser.add_argument("--package", default="quickshot")
    args = parser.parse_args()

    results = scan_package(Path(args.package))
    warnings = []
    for name, n_lines, n_funcs, n_classes in results:
        issues = []
        if n_lines > args.warn_lines:
            issues.append(f"{n_lines} lines (limit {args.warn_lines})")
        if n_funcs > args.warn_funcs:
            issues.append(f"{n_funcs} funcs (limit {args.warn_funcs})")
        if issues:
            warnings.append((name, issues))

    if warnings:
        print(f"Complexity warnings ({len(warnings)} modules):")
        for name, issues in warnings:
            print(f"  {name}: {', '.join(issues)}")
        sys.exit(1)
    else:
        print(f"All {len(results)} modules within complexity limits.")
        sys.exit(0)


if __name__ == "__main__":
    main()
