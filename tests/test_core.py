# -*- coding: utf-8 -*-
"""基础单元测试（不依赖外部服务，仅使用标准库 unittest）。"""
import ast
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import_with_stubs(mod_name: str):
    """在未安装 flet/requests 的环境也能安全导入模块进行纯逻辑单测。"""
    added = []
    for dep in ("flet", "requests"):
        if dep not in sys.modules:
            try:
                importlib.import_module(dep)
            except Exception:
                sys.modules[dep] = types.ModuleType(dep)
                added.append(dep)
    try:
        if mod_name in sys.modules:
            return importlib.reload(sys.modules[mod_name])
        return importlib.import_module(mod_name)
    finally:
        for dep in added:
            sys.modules.pop(dep, None)


class TestPanelCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = _import_with_stubs("panel")

    def test_no_undefined_open_any_or_bar_a(self):
        src = (ROOT / "panel.py").read_text(encoding="utf-8")
        self.assertNotIn("open_any(", src)
        self.assertNotIn("self.bar_a", src)
        self.assertNotIn("self.bar_q", src)

    def test_kill_tree_windows_calls_taskkill_not_self(self):
        with mock.patch.object(self.panel, "IS_WIN", True), \
             mock.patch.object(self.panel.subprocess, "run") as m_run:
            ok = self.panel.kill_tree(12345)
            self.assertTrue(ok)
            m_run.assert_called_once()
            args = m_run.call_args[0][0]
            self.assertEqual(args[:3], ["taskkill", "/PID", "12345"])

    def test_pid_alive_posix_uses_os_kill(self):
        with mock.patch.object(self.panel, "IS_WIN", False), \
             mock.patch.object(self.panel.os, "kill") as m_kill:
            self.assertTrue(self.panel.pid_alive(9999))
            m_kill.assert_called_once_with(9999, 0)

        with mock.patch.object(self.panel, "IS_WIN", False), \
             mock.patch.object(self.panel.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(self.panel.pid_alive(9999))

    def test_hbytes_and_hspeed(self):
        self.assertEqual(self.panel.hbytes(512), "512.0 B")
        self.assertEqual(self.panel.hbytes(2048), "2.0 KiB")
        self.assertEqual(self.panel.hspeed(1024 * 1024), "1.0 MiB/s")

    def test_color_alpha(self):
        self.assertEqual(self.panel.A("#00ccff", "55"), "#5500CCFF")
        self.assertEqual(self.panel.A("#AA00CCFF", "55"), "#AA00CCFF")


class TestYtdlGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ytdl = _import_with_stubs("ytdl_gui")

    def test_clean_url_extracts_from_share_text(self):
        text = "复制打开抖音，看看【某某的作品】https://v.douyin.com/iRNB1234/ 很好看！"
        self.assertEqual(self.ytdl.clean_url(text), "https://v.douyin.com/iRNB1234/")

    def test_clean_url_passthrough(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(self.ytdl.clean_url("  " + url + "  "), url)


class TestScanSecrets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "scripts"))
        import scan_secrets
        cls.scanner = scan_secrets

    def test_catches_single_and_double_backslash_and_sh(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            sample = "C:" + "\\Users\\alice\\secret"
            (p / "leak.sh").write_text('echo "%s"\n' % sample, encoding="utf-8")
            (p / "clean.py").write_text("x = 1\n", encoding="utf-8")
            hits = self.scanner.scan(p)
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0][0], "leak.sh")


class TestMagnetTools(unittest.TestCase):
    def test_parse_magnet_hex_and_uri(self):
        import magnet_tools
        ih = "a" * 40
        res = magnet_tools.parse_magnet(ih)
        self.assertTrue(res["valid"])
        self.assertEqual(res["infohash"], ih)
        self.assertEqual(res["uri"], "magnet:?xt=urn:btih:" + ih)


class TestSyntaxAll(unittest.TestCase):
    def test_all_python_files_parse(self):
        for name in ("panel.py", "magnet_tools.py", "ytdl_gui.py", "setup_wizard.py", "scripts/scan_secrets.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            ast.parse(src, filename=name)


if __name__ == "__main__":
    unittest.main()
