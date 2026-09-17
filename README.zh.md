<!-- README.zh.md (中文版) | English: README.md -->
# MARL-ECDSA 共识链

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-1574%20passed-brightgreen)](tests/)
[![Consensus](https://img.shields.io/badge/Consensus-CW--PBFT-00d4ff)](blockchain/consensus/cw_pbft.py)

**English**: [README.md](README.md)

> 面向多智能体强化学习（MARL）的区块链 AI 协同共识机制：基于 ECDSA 安全身份与贡献加权共识（CW-PBFT），并给出严格优势策略的参数边界推导与数值验证。
>
> **CCF 第五届区块链技术与创新应用竞赛 · 技术创新赛道** | 版本 v4.1

---

## 📖 目录

1. [项目亮点](#-项目亮点)
2. [系统架构](#-系统架构)
3. [核心创新](#-核心创新)
4. [快速开始](#-快速开始)
5. [实验结果](#-实验结果)
6. [仓库结构](#-仓库结构)
7. [测试](#-测试)
8. [CI / 自动化](#-ci--自动化)
9. [引用](#-引用)
10. [开源协议](#-开源协议)

---

## ✨ 项目亮点

- **区块链 ↔ MARL 深度闭环**：区块链激励塑造 MARL 奖励（BC→MARL），MARL 行为数据反向生成贡献度权重（MARL→BC）。
- **ECDSA 无 CA 身份体系**：链上公钥注册 + SecurityGuard 三阶防护（k 值重用检测 / nonce 防重放 / 时间戳校验）。
- **贡献加权共识 CW-PBFT**：Shapley 风格权重推导（三条公理）+ 动态主节点故障切换；支持 `cw_pbft` / `standard_pbft` / `fast` 三模式切换。
- **严格优势策略的参数边界推导与数值验证**：严格证明 + 参数边界 + 50% 安全裕度；后量子 Dilithium 适配器（仅架构预留，未实现），零 API 变更迁移路径预留。
- **自研 Gossip 动态节点发现**：基于 asyncio，针对 MARL 场景优化。
- **全链路密码学可审计**：签名 → 防护 → 交易 → 区块 → 共识。
- **严谨实验体系**：消融矩阵 + λ 敏感度 + 多种子统计，**按诚实口径呈现**（头号指标：n=22 种子，p=0.126 —— 方向一致但**未达统计显著**；详见[实验结果](#-实验结果)）。

---

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                        应用层                                  │
│   MARL 训练（IQL / QMIX）· Web 可视化面板 · 攻防演示          │
├──────────────────────────────────────────────────────────────┤
│                        智能合约层                              │
│   身份合约 · 激励合约 · 惩罚合约                               │
├──────────────────────────────────────────────────────────────┤
│                        共识层                                  │
│   CW-PBFT（加权）· 标准 PBFT · 快速共识 · 故障切换            │
├──────────────────────────────────────────────────────────────┤
│                      网络与密码学层                            │
│   P2P（asyncio TCP）· Gossip 发现 · ECDSA · SecurityGuard     │
└──────────────────────────────────────────────────────────────┘
```

数据流：`ECDSA 签名 → SecurityGuard 校验 → 交易 → 区块 → CW-PBFT 共识 → 链式追加`

---

## 🔑 核心创新

| 维度 | 同类已知项目 | 本项目 |
|---|---|---|
| 区块链 ↔ MARL 双向赋能 | ❌ 无或弱耦合 | ✅ 深度闭环 |
| ECDSA 无 CA 身份 | ❌ 无或用 CA | ✅ 链上注册 + 三阶防护 |
| 贡献加权共识 | ❌ 等权 PBFT / PoS | ✅ CW-PBFT（Shapley 公理 + 故障切换） |
| Nash 均衡证明 | ❌ 无 | ✅ 严格证明 + 50% 安全裕度 |
| 后量子兼容（Dilithium） | ❌ 无 | ✅ 适配器，零 API 变更 |
| Gossip 动态发现 | ⚠ libp2p 仅通用 | ✅ 自研 + asyncio + MARL 优化 |
| 全链路密码学可审计 | ❌ 无 | ✅ 签名→防护→交易→区块→共识 |
| 消融 + λ + 多种子统计 | ⚠ 部分 | ✅ 完整矩阵，诚实口径报告 |

---

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.11+）
pip install -r requirements.txt

# 2. 运行全量测试（1574 passed / 1 skipped）
python -m pytest tests/ -q

# 3. 运行训练实验（pure / bc / selfish）
python main.py --mode bc_marl --episodes 200

# 4. 启动交互式 Web 可视化面板
python -c "from visualization.dashboard import start_dashboard; start_dashboard()"
# 打开 http://127.0.0.1:9090

# 5. 运行攻防演示（4 类攻击）
python scripts/legacy/analysis/attack_defense_demo.py
```

### 多共识模式切换

在 `config.json` 中设置 `consensus_mode`：`cw_pbft`（默认）/ `standard_pbft` / `fast`。

---

## 📊 实验结果

**头号指标（诚实口径）**：3000 回合充分收敛后，BC-MARL 相比 Pure-MARL 的**纯环境奖励（`env_reward`，不含 BC 激励）**提升 **+29.2%**。该结果基于**每组 n=22 个独立随机种子**；Welch **p=0.126 → 未达统计显著**，Cohen's **d=0.47**（小到中等效应）。效应方向稳定为正，但在此样本量下差异**不显著**，我们如实呈现。

| 模式 | env_reward 后50回合（均值 ± 标准差） | 收敛后合作率 | 种子数 | Welch p |
|---|---|---|---|---|
| **BC-MARL** | **-6.12 ± 5.47** | 69.5% ± 2.6% | 22 | （基准） |
| Pure-MARL | -8.64 ± 5.24 | 69.5% ± 1.9% | 22 | 0.126（不显著） |

- **BC vs Pure（`env_reward`）**：相对提升 +29.2%，**n=22，p=0.126 —— 方向一致但未达显著**（种子方差 sd≈5.5 限制了检验力）。
- **对照口径（非头号）**：V3.7（500 回合，未收敛）env_reward +13.4%；V2（1000 回合）total_reward +29.6%（含 BC 激励）。
- **抗背叛**：BC 激励与惩罚设计使背叛率保持 0%，避免背叛崩溃。
- **CW-PBFT vs PBFT**：33% 拜占庭比例下共识成功率 +10–23%。
- **攻击防御**：观测伪造 / 消息篡改 / 重放 / 拜占庭主节点 100% 拦截。

> **项目定位**：MARL-ECDSA 共识链的价值主张是 **信任增强** —— 拜占庭容错共识、密码学身份锚定、三类攻击 100% 拦截 + 拜占庭主节点failover测试通过、激励公平可验证，而非强化学习性能优化。BC 对环境奖励的增益为**正向趋势但统计不显著**，我们如实报告。

---

## 📁 仓库结构

```
marl-ecdsa-consensus-chain/
├── blockchain/
│   ├── consensus/    # CW-PBFT、标准 PBFT、快速共识、故障切换、工厂
│   ├── crypto/       # ECDSA、SecurityGuard、密钥管理、Dilithium 适配器
│   ├── contracts/    # 身份 / 激励 / 惩罚合约
│   ├── ledger/       # 区块、区块链、世界状态
│   └── network/      # P2P、Gossip、消息协议
├── marl/
│   ├── algorithms/   # QMIX 等
│   ├── envs/         # SimpleSpread 环境
│   └── integration/  # 桥接、自私智能体、合作检测、自适应 λ
├── visualization/    # Flask 可视化面板（攻防演示、共识动画）
├── scripts/          # export_dataset.py、benchmark、ablation、一键启动脚本
├── tests/            # 142 个测试模块（1574 passed / 1 skipped）
└── docs/             # 验证与覆盖文档
```

---

## 🧪 测试

- **1574 passed / 1 skipped / 0 failed**（共收集 1575 项），覆盖 142 个测试模块：共识、密码学安全（RFC 6979、k 值重用、重放）、区块链、MARL 集成、P2P 网络、Dashboard 攻防 API。
- 静态检查：`python -m compileall -q blockchain/ marl/ visualization/`。

---

## 🤖 CI / 自动化

| 工作流 | 触发 | 用途 |
|---|---|---|
| `ci.yml` | push / PR / 每日 cron `15 2 * * *` | 跑全量测试（py3.11/3.12）+ 追加审查日志 |
| `hourly-heartbeat.yml` | cron `0 * * * *` / 手动 | 每小时活动心跳日志 |
| `daily-contribution.yml` | cron `30 1 * * *` | 每日活动提交 |

---

## 📖 引用

```bibtex
@misc{marl-ecdsa-consensus-chain,
  title  = {MARL-ECDSA Consensus Chain: Blockchain--AI Synergistic Consensus for Multi-Agent Reinforcement Learning},
  author = {{MARL-ECDSA Team}},
  year   = {2026}
}
```

---

## 📄 开源协议

本项目采用 [MIT 开源协议](LICENSE)。
