<!-- README.zh.md (中文版) | English: README.md -->
# MARL-ECDSA 共识链

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-1575%20passed-brightgreen)](tests/)
[![Consensus](https://img.shields.io/badge/Consensus-CW--PBFT-00d4ff)](blockchain/consensus/cw_pbft.py)

**English**: [README.md](README.md)

> 面向多智能体强化学习（MARL）的区块链 AI 协同共识机制：基于 ECDSA 安全身份与贡献加权共识（CW-PBFT），并给出严格的 Nash 均衡形式化证明。
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
- **Nash 均衡形式化证明**：严格证明 + 参数边界 + 50% 安全裕度；后量子 Dilithium 适配器，零 API 变更迁移。
- **自研 Gossip 动态节点发现**：基于 asyncio，针对 MARL 场景优化。
- **全链路密码学可审计**：签名 → 防护 → 交易 → 区块 → 共识。
- **严谨实验体系**：消融矩阵 + λ 敏感度 + 多种子统计（p < 0.001）。

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
| 消融 + λ + 多种子统计 | ⚠ 部分 | ✅ 完整矩阵，p < 0.001 |

---

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.11+）
pip install -r requirements.txt

# 2. 运行全量测试（435 项）
python -m pytest tests/ -q

# 3. 运行训练实验（pure / bc / selfish）
python main.py --mode bc_marl --episodes 200

# 4. 启动交互式 Web 可视化面板
python -c "from visualization.dashboard import start_dashboard; start_dashboard()"
# 打开 http://127.0.0.1:9090

# 5. 运行攻防演示（4 类攻击）
python attack_defense_demo.py
```

### 多共识模式切换

在 `config.json` 中设置 `consensus_mode`：`cw_pbft`（默认）/ `standard_pbft` / `fast`。

---

## 📊 实验结果

| 模式 | 平均奖励 | 后50回合 | 合作率 | 背叛率 | 显著性 |
|---|---|---|---|---|---|
| **BC-MARL** | **-31.0 ± 1.4** | -20.8 ± 8.2 | 54.4% | 0% | 基线 |
| Pure-MARL | -52.2 ± 0.9 | -41.4 ± 5.0 | 51.4% | 0% | p < 0.000001 |
| Selfish | -51.5 ± 1.4 | -40.2 ± 5.1 | 34.9% | 33.3% | p < 0.000001 |

- **BC 整体提升**：较 Pure-MARL 提升 +40.6%（5 种子，p < 0.001）
- **抗背叛**：区块链激励抑制自私背叛（合作率 34.9% 回升至 54.4%）
- **CW-PBFT vs PBFT**：33% 拜占庭比例下共识成功率 +10–23%
- **攻击防御**：观测伪造 / 消息篡改 / 重放 / 拜占庭主节点 100% 拦截

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
├── scripts/          # export_dataset.py、benchmark、一键启动脚本
├── tests/            # 435 项测试
└── docs/             # 验证与覆盖文档
```

---

## 🧪 测试

- **435 项测试**，覆盖 24 个测试模块：共识、密码学安全（RFC 6979、k 值重用、重放）、区块链、MARL 集成、P2P 网络、Dashboard 攻防 API。
- 静态检查：`python -m compileall -q blockchain/ marl/ visualization/`。

---

## 🤖 CI / 自动化

| 工作流 | 触发 | 用途 |
|---|---|---|
| `ci.yml` | push / PR / 每日 cron `15 2 * * *` | 跑 435 项测试（py3.11/3.12）+ 追加审查日志 |
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
