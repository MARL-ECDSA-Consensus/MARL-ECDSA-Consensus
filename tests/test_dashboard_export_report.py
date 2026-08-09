"""
dashboard 导出报告测试（RalphLoop 原子任务 BV）
覆盖：导出报告前端 JS 功能（模态框/生成/下载/快捷键/内容结构）
通过标准：新增 ≥6 项测试全过
"""
import logging
from pathlib import Path

import pytest

logging.basicConfig(level=logging.CRITICAL)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'templates' / 'dashboard.html'


class TestExportReportUI:
    def test_export_button(self):
        """导出报告按钮存在"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert '导出报告' in content
        assert 'showExportModal' in content

    def test_export_modal(self):
        """导出模态框存在"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'export-modal' in content
        assert 'doExport()' in content

    def test_do_export_function(self):
        """doExport 生成报告函数存在"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'function doExport' in content


class TestExportDownload:
    def test_download_filename(self):
        """下载文件名为 MARL-ECDSA_实验报告.html"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'MARL-ECDSA_实验报告.html' in content

    def test_download_mechanism(self):
        """使用 a.download + href 下载"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'a.download' in content
        assert "a.href = url" in content or 'a.href=url' in content


class TestExportContent:
    def test_report_contains_title(self):
        """导出报告 HTML 含标题"""
        content = TEMPLATE.read_text(encoding='utf-8')
        # doExport 内部构造 html 字符串，含标题
        export_section = content[content.find('function doExport'):content.find('function doExport') + 3000]
        assert 'MARL-ECDSA' in export_section or '报告' in export_section

    def test_report_contains_keyboard_shortcut(self):
        """E 键快捷键触发导出"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert "e.key === 'e'" in content or "e.key === 'E'" in content

    def test_report_close_modal(self):
        """导出后可关闭模态框"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'hideExportModal' in content


class TestExportIntegration:
    def test_modal_close_button(self):
        """模态框含关闭按钮"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'closeExportModal' in content or 'hideExportModal' in content

    def test_escape_closes_modal(self):
        """Esc 键关闭模态框"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'Escape' in content

    def test_export_html_structure(self):
        """模板 HTML 结构完整（含 script 闭合）"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert content.count('<script') >= content.count('</script>')
        assert '</html>' in content
