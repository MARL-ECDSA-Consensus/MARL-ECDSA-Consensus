<!-- README.zh.md (中文版) | English: README.md -->
# MARL-ECDSA 共识链

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-1585%20passed-brightgreen)](tests/)
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
- **严格优势策略的参数边界推导与数值验证**：严格证明 + 参数边界 + 50% 安全裕度；**后量子 ML-DSA-44（CRYSTALS-Dilithium2）适配器已实现**（`dilithium-py` 后端，真实密钥生成/签名/验签，签名 2420 字节，本机实测 签名≈24ms / 验签≈4.4ms），零 API 变更切换 + ECDSA+Dilithium 混合 AND 模式。注：默认签名链路仍为 ECDSA。
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
| Nash 均衡分析 | ❌ 无 | ✅ 参数边界推导 + 数值验证（非机器可验证的形式化证明） |
| 后量子兼容（ML-DSA-44 / Dilithium2） | ❌ 无 | ✅ 适配器已实现（`dilithium-py`；签名 2420B；实测 签名 24.3ms / 验签 4.4ms；混合 AND 模式）；默认链路仍为 ECDSA |
| Gossip 动态发现 | ⚠ libp2p 仅通用 | ✅ 自研 + asyncio + MARL 优化 |
| 全链路密码学可审计 | ❌ 无 | ✅ 签名→防护→交易→区块→共识 |
| 消融 + λ + 多种子统计 | ⚠ 部分 | ✅ 完整矩阵，诚实口径报告 |

---

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.11+）
pip install -r requirements.txt

# 2. 运行全量测试（1585 passed / 2 skipped）
python -m pytest tests/ -q

# 3. 运行训练实验（pure / bc / selfish）
python main.py --mode bc_marl --episodes 200

# 4. 启动交互式 Web 可视化面板
python -c "from visualization.dashboard import start_dashboard; start_dashboard()"
# 打开 http://127.0.0.1:9090

# 5. 运行攻防演示（3 类攻击：观测伪造 / 消息篡改 / 重放）
python scripts/legacy/analysis/attack_defense_demo.py
```

### 多共识模式切换

在 `config.json` 中设置 `consensus_mode`：`cw_pbft`（默认）/ `standard_pbft` / `fast`。

---

## 📊 实验结果

**头号指标（诚实口径）**：3000 回合充分收敛后，BC-MARL 相比 Pure-MARL 的**纯环境奖励（`env_reward`，不含 BC 激励）**提升 **+29.2%**。该结果基于**每组 n=22 个独立随机种子**；Welch **p=0.126 → 未达统计显著**，Cohen's **d=0.47**（小到中等效应）。效应方向稳定为正，但在此样本量下差异**不显著**，我们如实呈现。

| 模式 | env_reward 后50回合（均值 ± 标准差） | 合作率 后50回合（均值 ± 标准差） | 种子数 | Welch p |
|---|---|---|---|---|
| **BC-MARL** | **-6.12 ± 5.47** | 69.5% ± 2.6% | 22 | （基准） |
| Pure-MARL | -8.64 ± 5.24 | 69.5% ± 1.9% | 22 | 0.126（不显著） |

- **BC vs Pure（`env_reward`）**：相对提升 +29.2%，**n=22，p=0.126 —— 方向一致但未达显著**（种子方差 sd≈5.5 限制了检验力）。
- **对照口径（非头号）**：V3.7（500 回合，未收敛）env_reward +13.4%；V2（1000 回合）total_reward +29.6%（含 BC 激励）。
- **全程平均合作率 —— 唯一统计显著的正向结果**：3000 回合全程平均，BC 组 **0.6223 ± 0.0090** vs Pure 组 **0.6143 ± 0.0072**（每组 n=22），即 **+0.0080（+1.30%），Welch p=0.0022，Cohen d=0.985** —— **显著且为大效应**。⚠️ 此口径（全程平均）与头号指标的"后 50 回合"口径**不同，禁止混用**（后 50 回合口径下两组几乎相同：差 0.0005、p=0.939）。
- **抗背叛**：`avg_betrayal_rate` 在**全部 44 次运行中恒为 0.000**（22 种子 × 2 模式，各 3000 回合）；对照 `selfish` 模式约 0.35。BC 激励/惩罚设计可避免背叛崩溃。
- **CW-PBFT vs PBFT —— 优势的适用边界（如实报告）**：在**已把故障先验编码进权重**的合成权重下（展宽比 R≈8），CW-PBFT 在 40% 拜占庭时仍达 97–99%，而标准 PBFT 归零。但 **5 种子 × 2000 轮重复实验**表明：当权重为**均匀分布（R=1）**或由**真实 MARL 贡献度**导出（**R≈1.007**）时，CW-PBFT 与标准 PBFT **完全等价**。即**加权投票本身不提供额外容错**——安全条件为 `b < n/(2R+1)`，R≈1.007 时退化为经典 `n/3`。
- **攻击防御**：**3 类**签名层攻击（观测伪造 / 消息篡改 / 重放）**100% 拦截**（见 `attack_defense_report.json`）；拜占庭主节点场景由 failover 测试套件单独覆盖。

> **项目定位**：MARL-ECDSA 共识链的价值主张是 **信任增强** —— 拜占庭容错共识、密码学身份锚定、三类攻击 100% 拦截 + 拜占庭主节点failover测试通过、激励公平可验证，而非强化学习性能优化。BC 对环境奖励的增益为**正向趋势但统计不显著**，我们如实报告。**这不等于本项目没有显著结果**：激励机制的**设计目标**是塑造协作，而全程合作率的提升是**统计显著**的（p=0.0022，d=0.985）。**CW-PBFT 的容错优势同样有明确适用边界**（见上：R 判据，真实贡献度下无增益）。

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
├── tests/            # 144 个测试模块（1585 passed / 2 skipped）
```

---

## 🧪 测试

- **1585 passed / 2 skipped / 0 failed**（共收集 1587 项），覆盖 144 个测试模块：共识、密码学安全（RFC 6979、k 值重用、重放）、区块链、MARL 集成、P2P 网络、Dashboard 攻防 API。
- 静态检查：`python -m compileall -q blockchain/ marl/ visualization/`。

---

## 🤖 CI / 自动化

| 工作流 | 触发 | 用途 |
|---|---|---|
| `ci.yml` | push / PR | 跑全量测试（py3.11/3.12） |

> 本仓库**不含任何定时提交 / 自动提交工作流**，也不含任何活动量刷取（activity farming）自动化。

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
