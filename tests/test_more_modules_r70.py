"""
更多模块剩余边界测试（RalphLoop 原子任务 EN）
覆盖：signing_service 签名校验、incentive 结算排名（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging
import shutil
import tempfile
import time

import pytest

from marl.integration.signing_service import SigningService
from blockchain.crypto.key_manager import KeyManager
from blockchain.crypto.security_guard import SecurityGuard
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.incentive_contract import IncentiveContract, ContributionScore

logging.basicConfig(level=logging.CRITICAL)


@pytest.fixture
def keyed():
    key_dir = tempfile.mkdtemp(prefix="test_en_")
    km = KeyManager(key_dir=key_dir)
    guard = SecurityGuard()
    for i in range(3):
        km.generate_or_load(f"agent_{i}")
    svc = SigningService(key_manager=km, security_guard=guard, n_agents=3)
    yield svc, km
    shutil.rmtree(key_dir, ignore_errors=True)


class TestSigning:
    def test_sign_verify_success(self, keyed):
        """正常签名+校验 → verified True"""
        svc, _ = keyed
        pkg = svc.sign_and_verify("agent_0", [0.1], 1, int(time.time() * 1000))
        assert pkg is not None
        assert pkg.get('verified') is True

    def test_sign_missing_key(self, keyed):
        """缺失密钥 → None"""
        svc, _ = keyed
        pkg = svc.sign_and_verify("ghost", [0.1], 1, int(time.time() * 1000))
        assert pkg is None

    def test_stats_count(self, keyed):
        """签名计数"""
        svc, _ = keyed
        for nonce in range(1, 3):
            svc.sign_and_verify("agent_0", [0.1], nonce, int(time.time() * 1000))
        assert svc.get_stats()['ecdsa_sign_count'] == 2

    def test_replay_blocked(self, keyed):
        """重复 nonce 拦截"""
        svc, _ = keyed
        ts = int(time.time() * 1000)
        svc.sign_and_verify("agent_0", [0.1], 1, ts)
        pkg2 = svc.sign_and_verify("agent_0", [0.2], 1, ts)
        assert pkg2.get('verified') is False


class TestIncentiveSettle:
    def test_settle_ranked(self):
        """排名结算：最高分获得加成"""
        ws = WorldState()
        for i in range(4):
            ws.register_agent(f"agent_{i}", f"0x{'ab' * 32}")
        contract = IncentiveContract(ws)
        scores = [
            ContributionScore("agent_0", 1.0, 1.0, 1.0),
            ContributionScore("agent_1", 0.8, 1.0, 1.0),
            ContributionScore("agent_2", 0.5, 1.0, 1.0),
            ContributionScore("agent_3", 0.2, 1.0, 1.0),
        ]
        deltas = contract.settle_rewards(1, scores)
        # 排名1 加成 ≥ 排名2（top_n = max(1, 4*0.3)=1 → 仅排名1 有加成）
        assert deltas["agent_0"] >= deltas["agent_1"]

    def test_settle_empty(self):
        """空评分 → 空增量"""
        ws = WorldState()
        contract = IncentiveContract(ws)
        assert contract.settle_rewards(1, []) == {}

    def test_settle_betrayal_penalty(self):
        """背叛惩罚 -20"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 0.0, 0.0)
        deltas = contract.settle_rewards(1, [cs])
        assert deltas["agent_0"] == -20.0

    def test_history_query(self):
        """结算历史查询"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        cs = ContributionScore("agent_0", 0.5, 1.0, 1.0)
        contract.settle_rewards(5, [cs])
        history = contract.get_settlement_history(5)
        assert len(history) == 1
        assert history[0]["agent_id"] == "agent_0"


class TestLeaderboardStats:
    def test_leaderboard_desc(self):
        """排行榜降序"""
        ws = WorldState()
        for i in range(3):
            ws.register_agent(f"agent_{i}", f"0x{'ab' * 32}")
        ws.add_score("agent_0", 5.0)
        ws.add_score("agent_1", 15.0)
        contract = IncentiveContract(ws)
        board = contract.get_leaderboard()
        assert board[0][0] == "agent_1"  # 最高分
        assert board[1][0] == "agent_0"

    def test_stats_fields(self):
        """统计字段完整"""
        ws = WorldState()
        ws.register_agent("agent_0", "0x" + "ab" * 32)
        contract = IncentiveContract(ws)
        stats = contract.get_stats()
        for key in ['total_agents', 'avg_score', 'max_score',
                    'min_score', 'settled_blocks']:
            assert key in stats
