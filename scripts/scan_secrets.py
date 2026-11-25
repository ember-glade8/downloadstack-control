# -*- coding: utf-8 -*-
"""提交前体检：个人化命名、明文凭据、绝对用户路径、内网/代理端口。
用法: python scripts/scan_secrets.py [目录]
退出码 0=干净 1=有问题
"""
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", "state", "logs", "cache", "backups", "build", "dist", ".venv", "venv"}
SKIP_FILES = {"config.json", "pw.txt", "scan_secrets.py"}  # 扫描器自身的规则串不算泄露

PATTERNS = [
    (r"[A-Za-z]:\\\\Users\\\\[^\\\\\s\"']+", "Windows 用户目录绝对路径"),
    (r"\"pass\"\s*:\s*\"[^\"]+\"", "明文密码"),
    (r"rpc-secret=[0-9a-f]{32,}", "明文 RPC 密钥"),
    (r"127\.0\.0\.1:7\d{3}", "本机代理端口"),
    (r"\b(下载体系|YT下载壳|yt_dlp壳)\b", "个人化命名"),
    (r"[A-Za-z]:\\\\YTShell|[A-Za-z]:\\\\Video2X", "个人化工具路径"),
    (r"192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.", "内网 IP"),
]


def scan(root: Path):
    bad = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if any(p in SKIP_DIRS for p in f.parts) or f.name in SKIP_FILES:
            continue
        if f.suffix.lower() not in {".py", ".md", ".txt", ".bat", ".json", ".ps1", ".yml", ".yaml"}:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat, label in PATTERNS:
            for m in re.finditer(pat, text):
                bad.append((str(f.relative_to(root)), text[:m.start()].count("\n") + 1, label, m.group(0)[:60]))
    return bad


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    hits = scan(root)
    if not hits:
        print("[OK] 未发现敏感串")
        sys.exit(0)
    print("[!] %d 处可疑：" % len(hits))
    for f, ln, label, sample in hits:
        print("  %s:%d  %s -> %s" % (f, ln, label, sample))
    sys.exit(1)
