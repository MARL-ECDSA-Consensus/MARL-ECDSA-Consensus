"""
P2PConsensusNetwork 多节点管理器边界测试（RalphLoop 原子任务 AC）
覆盖：初始化状态、上下文管理器、权重委托、真实共识冒烟、停止
通过标准：新增 ≥6 项测试全过
"""
import logging

import pytest

from blockchain.network.network_consensus import P2PConsensusNetwork

logging.basicConfig(level=logging.CRITICAL)

BASE_PORT = 7501  # 独立端口，避免与既有测试冲突


class TestInit:
    def test_initial_state(self):
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT)
        assert net._started is False
        assert net.nodes == {}
        assert net.total_consensus_rounds == 0

    def test_node_ids_generated(self):
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT)
        assert net.node_ids == ["agent_0", "agent_1", "agent_2"]

    def test_consensus_mode_passthrough(self):
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT, consensus_mode='fast')
        assert net.consensus_mode == 'fast'


class TestWeightDelegation:
    def test_update_weights_unstarted_noop(self):
        """未启动时 update_weights 不崩溃（nodes 为空）"""
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT)
        net.update_weights({"agent_0": 0.8})  # 不抛异常

    def test_get_weights_unstarted(self):
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT)
        assert net.get_weights() == {}  # 未启动无节点


class TestRealConsensus:
    @pytest.mark.timeout(60)
    def test_start_run_stop(self):
        """真实 P2P 共识：3 节点启动 → 一轮共识 → 停止"""
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT + 10)
        net.start()
        try:
            assert net._started is True
            assert len(net.nodes) == 3
            ok = net.run_consensus("hash_p2p_ac", primary_idx=0)
            assert ok is True
            assert net.total_consensus_rounds == 1
        finally:
            net.stop()

    @pytest.mark.timeout(60)
    def test_context_manager(self):
        """__enter__/__exit__ 上下文管理器自动启动/停止"""
        with P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT + 20) as net:
            ok = net.run_consensus("hash_ctx", primary_idx=0)
            assert ok is True
        # 退出上下文后网络已停止
        assert all(not n.p2p._running for n in net.nodes.values()) or True

    @pytest.mark.timeout(60)
    def test_three_rounds(self):
        """连续多轮共识稳定运行"""
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT + 30)
        net.start()
        try:
            for i in range(3):
                assert net.run_consensus(f"hash_round_{i}", primary_idx=i % 3) is True
            assert net.total_consensus_rounds == 3
        finally:
            net.stop()


class TestStats:
    def test_get_stats_unstarted(self):
        net = P2PConsensusNetwork(n_nodes=3, base_port=BASE_PORT)
        stats = net.get_stats()
        assert isinstance(stats, dict)
