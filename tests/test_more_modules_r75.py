"""
更多模块剩余边界测试（RalphLoop 原子任务 EX）
覆盖：cw_pbft 状态判定、identity 注册校验（此前未单点覆盖）
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.consensus.cw_pbft import CWPBFTConsensus, ConsensusState
from blockchain.ledger.world_state import WorldState
from blockchain.contracts.identity_contract import IdentityContract

logging.basicConfig(level=logging.CRITICAL)

NODES = ['node_0', 'node_1', 'node_2']
VALID_PK = "04" + "ab" * 64


@pytest.fixture
def pbft():
    return CWPBFTConsensus('node_0', NODES)


class TestStateJudgment:
    def test_initial_idle(self, pbft):
        """初始 IDLE 且未达成"""
        assert pbft.get_state() == ConsensusState.IDLE
        assert pbft.is_consensus_reached() is False

    def test_after_start_pre_prepare(self, pbft):
        """start_consensus 后 PRE_PREPARE"""
        pbft.start_consensus('hash_s')
        assert pbft.get_state() == ConsensusState.PRE_PREPARE

    def test_after_fast_committed(self, pbft):
        """快速共识后 COMMITTED 达成"""
        pbft.fast_consensus('hash_fc', 'node_0')
        assert pbft.get_state() == ConsensusState.COMMITTED
        assert pbft.is_consensus_reached() is True

    def test_after_reset_idle(self, pbft):
        """reset 后回 IDLE"""
        pbft.fast_consensus('hash_r', 'node_0')
        pbft.reset()
        assert pbft.get_state() == ConsensusState.IDLE
        assert pbft.is_consensus_reached() is False


class TestRegisterValidation:
    def test_register_valid(self):
        """正常注册"""
        ws = WorldState()
        ic = IdentityContract(ws)
        assert ic.register("a0", VALID_PK)["success"] is True

    def test_register_none_agent(self):
        """None agent_id 拒绝（P3-11）"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.register(None, VALID_PK)
        assert r["success"] is False
        assert "不能为空" in r["error"]

    def test_register_none_pk(self):
        """None 公钥拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.register("a0", None)
        assert r["success"] is False
        assert "公钥" in r["error"]

    def test_register_bad_format(self):
        """非法公钥格式拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        r = ic.register("a0", "not_hex")
        assert r["success"] is False
        assert "格式" in r["error"]

    def test_register_duplicate(self):
        """重复注册拒绝"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        r = ic.register("a0", VALID_PK)
        assert r["success"] is False
        assert "已注册" in r["error"]

    def test_register_pubkey_query(self):
        """注册后公钥可查"""
        ws = WorldState()
        ic = IdentityContract(ws)
        ic.register("a0", VALID_PK)
        assert ic.get_public_key("a0") == VALID_PK


class TestPubkeyValidation:
    def test_validate_130_hex(self):
        """130 字符非压缩公钥合法"""
        assert IdentityContract._validate_public_key("04" + "ab" * 64) is True

    def test_validate_66_hex(self):
        """66 字符压缩公钥合法"""
        assert IdentityContract._validate_public_key("02" + "cd" * 32) is True

    def test_validate_bad(self):
        """非法长度/空拒绝"""
        assert IdentityContract._validate_public_key("04" + "ab" * 10) is False
        assert IdentityContract._validate_public_key("") is False
        assert IdentityContract._validate_public_key(None) is False
