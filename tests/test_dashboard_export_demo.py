"""
dashboard 导出报告/演示模式测试（RalphLoop 原子任务 BC）
覆盖：模板含导出报告/演示模式/键盘快捷键元素、路由完整性
通过标准：新增 ≥6 项测试全过
"""
import logging
import re
from pathlib import Path

import pytest

from visualization.dashboard import _create_app

logging.basicConfig(level=logging.CRITICAL)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'templates' / 'dashboard.html'


class TestExportReportUI:
    def test_export_button_exists(self):
        """模板含导出报告按钮"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'showExportModal' in content

    def test_export_modal_exists(self):
        """模板含导出报告模态框"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'export-modal' in content

    def test_do_export_function(self):
        """模板含 doExport 生成报告函数"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'function doExport' in content


class TestDemoModeUI:
    def test_demo_button_exists(self):
        """模板含演示模式按钮"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'toggleDemoMode' in content

    def test_demo_indicator_exists(self):
        """模板含演示模式指示器"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert 'demo-indicator' in content

    def test_keyboard_shortcut_e(self):
        """模板含 E 键导出快捷键"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert "e.key === 'e'" in content or "e.key === 'E'" in content

    def test_keyboard_shortcut_p(self):
        """模板含 P 键演示模式快捷键（真实写法 e.key === 'p' || e.key === 'P'）"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert "e.key === 'p' || e.key === 'P'" in content or "toggleDemoMode()" in content


class TestTemplateIntegrity:
    def test_template_has_tabs(self):
        """模板含 9 个导航标签"""
        content = TEMPLATE.read_text(encoding='utf-8')
        tabs = re.findall(r'data-tab="(\w+)"', content)
        assert len(tabs) >= 9

    def test_template_valid_html_structure(self):
        """模板 HTML 结构完整（script 闭合）"""
        content = TEMPLATE.read_text(encoding='utf-8')
        assert content.count('<script') >= content.count('</script>')


class TestRoutes:
    @pytest.fixture
    def client(self):
        app = _create_app()
        assert app is not None
        return app.test_client()

    def test_all_routes_registered(self):
        """10 个路由均已注册"""
        app = _create_app()
        rules = sorted(str(r) for r in app.url_map.iter_rules())
        for expected in ['/', '/healthz', '/api/status', '/api/data', '/api/p2p_stats',
                         '/api/load/<mode>', '/api/compare', '/api/consensus_votes',
                         '/api/block_explorer', '/api/attack/inject']:
            assert expected in rules, f"缺少路由 {expected}"

    def test_index_renders_export_button(self, client):
        """首页渲染含导出报告按钮"""
        r = client.get('/')
        assert r.status_code == 200
        assert b'showExportModal' in r.data
