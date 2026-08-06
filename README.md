<!-- README.md (English) | 中文版见 README.zh.md -->
# MARL-ECDSA Consensus Chain

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-435%20passed-brightgreen)](https://github.com/MARL-ECDSA-Consensus/MARL-ECDSA-Consensus/actions)
[![Consensus](https://img.shields.io/badge/Consensus-CW--PBFT-00d4ff)](blockchain/consensus/cw_pbft.py)

**中文版**: [README.zh.md](README.zh.md)

> A Blockchain–AI synergistic consensus mechanism for Multi-Agent Reinforcement Learning (MARL): contribution-weighted consensus (CW-PBFT) secured by ECDSA identities, with a formal Nash equilibrium proof.
>
> **CCF 5th Blockchain Technology & Innovation Competition · Technical Innovation Track** | Version 4.1

---

## 📖 Table of Contents

1. [Highlights](#-highlights)
2. [Architecture](#-architecture)
3. [Key Innovations](#-key-innovations)
4. [Quick Start](#-quick-start)
5. [Experiments & Results](#-experiments--results)
6. [Repository Layout](#-repository-layout)
7. [Testing](#-testing)
8. [CI / Automation](#-ci--automation)
9. [Citation](#-citation)
10. [License](#-license)

---

## ✨ Highlights

- **Deep Blockchain ↔ MARL loop**: blockchain incentives shape MARL rewards (BC→MARL), while MARL behavior feeds contribution scores that weight consensus (MARL→BC).
- **ECDSA identity without a CA**: on-chain public-key registration + SecurityGuard three-tier defense (k-reuse detection, nonce anti-replay, timestamp validation).
- **Contribution-Weighted PBFT (CW-PBFT)**: Shapley-style weight derivation (three axioms) with dynamic primary failover; configurable modes `cw_pbft` / `standard_pbft` / `fast`.
- **Formal Nash equilibrium proof**: strict proof with parameter bounds and 650% safety margin; post-quantum Dilithium adapter with zero-API-change migration.
- **Self-built Gossip discovery**: asyncio-based dynamic peer discovery tuned for MARL scenarios.
- **Full-chain cryptographic auditability**: sign → Guard → Tx → Block → consensus.
- **Rigorous experiments**: ablation matrix, λ-sensitivity, multi-seed statistics (p < 0.001).

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Application Layer                         │
│   MARL training (IQL / QMIX) · Web Dashboard · Attack Demo    │
├──────────────────────────────────────────────────────────────┤
│                     Smart Contract Layer                      │
│   IdentityContract · IncentiveContract · PenaltyContract      │
├──────────────────────────────────────────────────────────────┤
│                     Consensus Layer                           │
│   CW-PBFT (weighted) · Standard PBFT · Fast · Failover        │
├──────────────────────────────────────────────────────────────┤
│                     Network & Crypto Layer                    │
│   P2P (asyncio TCP) · Gossip discovery · ECDSA · SecurityGuard│
└──────────────────────────────────────────────────────────────┘
```

Data flow: `ECDSA sign → SecurityGuard check → Transaction → Block → CW-PBFT consensus → append to chain`

---

## 🔑 Key Innovations

| Dimension | Baseline (known projects) | This project |
|---|---|---|
| Blockchain ↔ MARL two-way loop | ❌ none / weak | ✅ deep closed loop |
| ECDSA CA-less identity | ❌ none or CA-based | ✅ on-chain key registration + 3-tier guard |
| Contribution-weighted consensus | ❌ equal-weight PBFT / PoS | ✅ CW-PBFT (Shapley axioms + failover) |
| Nash equilibrium proof | ❌ none | ✅ strict proof + 650% safety margin |
| Post-quantum (Dilithium) | ❌ none | ✅ adapter, zero API change |
| Gossip dynamic discovery | ⚠ libp2p only, MARL-unrelated | ✅ self-built + asyncio + MARL-tuned |
| Full-chain crypto auditability | ❌ none | ✅ sign→Guard→Tx→Block→consensus |
| Ablation + λ + multi-seed stats | ⚠ partial | ✅ full matrix, p < 0.001 |

---

## 🚀 Quick Start

```bash
# 1. Install dependencies (Python 3.11+)
pip install -r requirements.txt

# 2. Run full test suite (435 tests)
python -m pytest tests/ -q

# 3. Run a training experiment (pure vs bc vs selfish)
python main.py --mode bc_marl --episodes 200

# 4. Launch the interactive Web Dashboard
python -c "from visualization.dashboard import start_dashboard; start_dashboard()"
# open http://127.0.0.1:9090

# 5. Run the attack-defense demo (4 attack types)
python attack_defense_demo.py
```

### Multi-consensus mode switching

Set `consensus_mode` in `config.json`: `cw_pbft` (default) / `standard_pbft` / `fast`.

---

## 📊 Experiments & Results

| Mode | Mean Reward | Last-50 | Cooperation | Betrayal | Significance |
|---|---|---|---|---|---|
| **BC-MARL** | **-31.0 ± 1.4** | -20.8 ± 8.2 | 54.4% | 0% | baseline |
| Pure-MARL | -52.2 ± 0.9 | -41.4 ± 5.0 | 51.4% | 0% | p < 0.000001 |
| Selfish | -51.5 ± 1.4 | -40.2 ± 5.1 | 34.9% | 33.3% | p < 0.000001 |

- **BC overall improvement**: +40.6% vs Pure-MARL (5 seeds, p < 0.001)
- **Anti-betrayal**: blockchain incentive suppresses selfish betrayal (34.9% → 0% cooperation gap restored)
- **CW-PBFT vs PBFT**: +10–23% consensus success at 33% Byzantine ratio
- **Attack defense**: 100% interception for observation forgery / message tampering / replay / Byzantine primary

---

## 📁 Repository Layout

```
marl-ecdsa-consensus-chain/
├── blockchain/
│   ├── consensus/    # CW-PBFT, Standard PBFT, Fast, Failover, factory
│   ├── crypto/       # ECDSA, SecurityGuard, KeyManager, Dilithium adapter
│   ├── contracts/    # Identity / Incentive / Penalty
│   ├── ledger/       # Block, Blockchain, WorldState
│   └── network/      # P2P, Gossip, MessageProtocol
├── marl/
│   ├── algorithms/   # QMIX etc.
│   ├── envs/         # SimpleSpread
│   └── integration/  # Bridge, SelfishAgent, CooperationDetector, AdaptiveLambda
├── visualization/    # Flask Dashboard (attack demo, consensus animation)
├── scripts/          # export_dataset.py, benchmark, one-click launchers
├── tests/            # 435 test cases
└── docs/             # Verification & coverage docs
```

---

## 🧪 Testing

- **435 tests** across 24 test modules: consensus, crypto security (RFC 6979, k-reuse, replay), blockchain, MARL integration, P2P network, dashboard attack API.
- Static checks: `python -m compileall -q blockchain/ marl/ visualization/`.

---

## 🤖 CI / Automation

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | push / PR / daily cron `15 2 * * *` | Run 435 tests (py3.11/3.12) + append review log |
| `hourly-heartbeat.yml` | cron `0 * * * *` / manual | Hourly activity heartbeat log |
| `daily-contribution.yml` | cron `30 1 * * *` | Daily activity commit |

---

## 📖 Citation

If you use this project in research, please cite:

```bibtex
@misc{marl-ecdsa-consensus-chain,
  title  = {MARL-ECDSA Consensus Chain: Blockchain--AI Synergistic Consensus for Multi-Agent Reinforcement Learning},
  author = {{TrueFurina}},
  year   = {2026},
  howpublished = {\url{https://github.com/MARL-ECDSA-Consensus/MARL-ECDSA-Consensus}}
}
```

---

## 📄 License

Released under the [MIT License](LICENSE).
