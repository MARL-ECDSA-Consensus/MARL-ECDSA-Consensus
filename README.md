<!-- README.md (English) | 中文版见 README.zh.md -->
# MARL-ECDSA Consensus Chain

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-1574%20passed-brightgreen)](tests/)
[![Consensus](https://img.shields.io/badge/Consensus-CW--PBFT-00d4ff)](blockchain/consensus/cw_pbft.py)

**中文版**: [README.zh.md](README.zh.md)

> A Blockchain–AI synergistic consensus mechanism for Multi-Agent Reinforcement Learning (MARL): contribution-weighted consensus (CW-PBFT) secured by ECDSA identities, with a parameter-boundary Nash equilibrium analysis (numerically verified, not a machine-checked formal proof).
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
- **Parameter-boundary derivation & numerical verification of strict-dominant-strategy Nash (NOT machine-checked formal proof)**: strict proof with parameter bounds and 50% safety margin; Dilithium adapter (architecture reservation ONLY, NOT implemented) for future post-quantum migration.
- **Self-built Gossip discovery**: asyncio-based dynamic peer discovery tuned for MARL scenarios.
- **Full-chain cryptographic auditability**: sign → Guard → Tx → Block → consensus.
- **Rigorous experiments**: ablation matrix, λ-sensitivity and multi-seed statistics, reported under an honest caliber (headline: n=22 seeds, p=0.126 — direction-consistent but **not significant**; see [Experiments & Results](#-experiments--results)).

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
| Nash equilibrium analysis | ❌ none | ✅ parameter-boundary derivation + numerical verification (50% margin) |
| Post-quantum (Dilithium) | ❌ none | ⚠️ architecture reservation only (adapter stub, NOT implemented) |
| Gossip dynamic discovery | ⚠ libp2p only, MARL-unrelated | ✅ self-built + asyncio + MARL-tuned |
| Full-chain crypto auditability | ❌ none | ✅ sign→Guard→Tx→Block→consensus |
| Ablation + λ + multi-seed stats | ⚠ partial | ✅ full matrix, honest reporting |

---

## 🚀 Quick Start

```bash
# 1. Install dependencies (Python 3.11+)
pip install -r requirements.txt

# 2. Run full test suite (1574 passed / 1 skipped)
python -m pytest tests/ -q

# 3. Run a training experiment (pure vs bc vs selfish)
python main.py --mode bc_marl --episodes 200

# 4. Launch the interactive Web Dashboard
python -c "from visualization.dashboard import start_dashboard; start_dashboard()"
# open http://127.0.0.1:9090

# 5. Run the attack-defense demo (4 attack types)
python scripts/legacy/analysis/attack_defense_demo.py
```

### Multi-consensus mode switching

Set `consensus_mode` in `config.json`: `cw_pbft` (default) / `standard_pbft` / `fast`.

---

## 📊 Experiments & Results

**Headline metric (honest caliber).** After **3000-episode** full convergence, BC-MARL improves the **pure environment reward (`env_reward`, excluding the BC incentive)** by **+29.2%** over Pure-MARL. This is based on **n = 22 independent random seeds per group**; Welch **p = 0.126 → not statistically significant**, Cohen's **d = 0.47** (small-to-medium). The direction is consistently positive, but the difference is **not significant** at this sample size — reported as such.

| Mode | env_reward last-50 (mean ± std) | Post-convergence coop. | Seeds | Welch p |
|---|---|---|---|---|
| **BC-MARL** | **-6.12 ± 5.47** | 69.5% ± 2.6% | 22 | (baseline) |
| Pure-MARL | -8.64 ± 5.24 | 69.5% ± 1.9% | 22 | 0.126 (n.s.) |

- **BC vs Pure (`env_reward`)**: +29.2% relative, **n=22, p=0.126 — direction-consistent but not significant** (test power limited by seed variance, sd ≈ 5.5).
- **Reference calibers (not headline)**: V3.7 (500 episodes, not converged) env_reward +13.4%; V2 (1000 episodes) total_reward +29.6% (includes the BC incentive).
- **Anti-betrayal**: the BC incentive and penalty design hold the betrayal rate at 0% and prevent defection collapse.
- **CW-PBFT vs PBFT**: +10–23% consensus success at a 33% Byzantine ratio.
- **Attack defense**: 100% interception for observation forgery / message tampering / replay / Byzantine primary.

> **Positioning**: the value proposition is **trust augmentation** — Byzantine-fault-tolerant consensus, cryptographic identity anchoring, 100% attack interception and verifiable incentive fairness — rather than RL performance optimization. The BC effect on `env_reward` is a positive trend that is **not statistically significant**, and we report it honestly.

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
├── scripts/          # export_dataset.py, benchmark, ablation, one-click launchers
├── tests/            # 142 test modules (1574 passed / 1 skipped)
└── docs/             # Verification & coverage docs
```

---

## 🧪 Testing

- **1574 tests passed / 1 skipped / 0 failed** (1575 collected) across 142 test modules: consensus, crypto security (RFC 6979, k-reuse, replay), blockchain, MARL integration, P2P network, dashboard attack API.
- Static checks: `python -m compileall -q blockchain/ marl/ visualization/`.

---

## 🤖 CI / Automation

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | push / PR / daily cron `15 2 * * *` | Run the full test suite (py3.11/3.12) + append review log |
| `hourly-heartbeat.yml` | cron `0 * * * *` / manual | Hourly activity heartbeat log |
| `daily-contribution.yml` | cron `30 1 * * *` | Daily activity commit |

---

## 📖 Citation

```bibtex
@misc{marl-ecdsa-consensus-chain,
  title  = {MARL-ECDSA Consensus Chain: Blockchain--AI Synergistic Consensus for Multi-Agent Reinforcement Learning},
  author = {{MARL-ECDSA Team}},
  year   = {2026}
}
```

---

## 📄 License

This project is released under the [MIT License](LICENSE).
