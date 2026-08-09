"""
docs 文档完整性测试（RalphLoop 原子任务 AV）
覆盖：文档存在性、非空、标题/表格结构、关键内容、README 双语
通过标准：新增 ≥6 项测试全过
"""
import logging
from pathlib import Path

import pytest

logging.basicConfig(level=logging.CRITICAL)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'

DOC_FILES = ['24H_COVERAGE.md', 'AUTOMATION_EVIDENCE.md', 'QUALITY_AUDIT_LOG.md',
             'RECORDS_AND_FORECAST.md', 'VERIFICATION_INDEX.md']


class TestDocExistence:
    @pytest.mark.parametrize('fname', DOC_FILES)
    def test_doc_exists(self, fname):
        assert (DOCS / fname).exists()

    @pytest.mark.parametrize('fname', DOC_FILES)
    def test_doc_non_empty(self, fname):
        content = (DOCS / fname).read_text(encoding='utf-8')
        assert len(content.strip()) > 100  # 非空且有实质内容


class TestDocStructure:
    @pytest.mark.parametrize('fname', DOC_FILES)
    def test_doc_has_heading(self, fname):
        content = (DOCS / fname).read_text(encoding='utf-8')
        assert any(line.startswith('#') for line in content.splitlines())

    @pytest.mark.parametrize('fname', DOC_FILES)
    def test_doc_has_table(self, fname):
        content = (DOCS / fname).read_text(encoding='utf-8')
        assert any(line.startswith('|') for line in content.splitlines())


class TestKeyContent:
    def test_verification_index_has_url(self):
        """VERIFICATION_INDEX 含目标 URL"""
        content = (DOCS / 'VERIFICATION_INDEX.md').read_text(encoding='utf-8')
        assert 'github.com' in content

    def test_24h_coverage_has_cron(self):
        """24H_COVERAGE 含 cron 调度"""
        content = (DOCS / '24H_COVERAGE.md').read_text(encoding='utf-8')
        assert 'cron' in content or '*' in content

    def test_quality_audit_has_rounds(self):
        """QUALITY_AUDIT_LOG 含质检轮次"""
        content = (DOCS / 'QUALITY_AUDIT_LOG.md').read_text(encoding='utf-8')
        assert 'R1' in content or 'R2' in content

    def test_automation_evidence_has_workflows(self):
        """AUTOMATION_EVIDENCE 含工作流说明"""
        content = (DOCS / 'AUTOMATION_EVIDENCE.md').read_text(encoding='utf-8')
        assert 'heartbeat' in content.lower() or 'ci' in content.lower()


class TestReadme:
    def test_bilingual_readme_exists(self):
        """README 双语存在"""
        assert (ROOT / 'README.md').exists()
        assert (ROOT / 'README.zh.md').exists()

    def test_readme_english_links_zh(self):
        """英文 README 链接中文版"""
        content = (ROOT / 'README.md').read_text(encoding='utf-8')
        assert 'README.zh.md' in content

    def test_readme_has_badges(self):
        content = (ROOT / 'README.md').read_text(encoding='utf-8')
        assert 'shields.io' in content or 'badge' in content.lower()
