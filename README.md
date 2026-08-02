# MARL-ECDSA Consensus Chain

## Blockchain-AI Synergistic Consensus for Multi-Agent Reinforcement Learning

> **CCF 第五届区块链竞赛 · 技术创新赛道** | Version 4.1 Stable | 300+ Source Files | 312+ Test Cases | 50+ Scripts & Tools

---

## 📖 Table of Contents

1. [Competition Highlights](#-competition-highlights)
2. [One-Click Reproduce](#-one-click-reproduce)
3. [System Architecture](#-system-architecture)
4. [Core Innovations](#-core-innovations)
5. [Experimental Results](#-experimental-results)
6. [Quick Start Guide](#-quick-start-guide)
7. [Project Structure](#-project-structure)
8. [All Commands Reference](#-all-commands-reference)
9. [API Reference](#-api-reference)
10. [Configuration Guide](#-configuration-guide)
11. [Testing](#-testing)
12. [Security](#-security)
13. [Performance Benchmarks](#-performance-benchmarks)
14. [Docker Deployment](#-docker-deployment)
15. [Industry Scenarios](#-industry-scenarios)
16. [Future Roadmap](#-future-roadmap)
17. [Academic References](#-academic-references)
18. [FAQ](#-faq)

---

## 🏆 Competition Highlights

| Metric | Value | Significance |
|--------|-------|-------------|
| **Total Reward Improvement** | **+42.2%** (3 agents) / **+40.4%** (5 agents) | BC-MARL vs pure MARL, Welch's t-test p < 0.001 |
| **Attack Interception Rate** | **100%** | Message tampering / Identity forgery / k-value reuse / Byzantine |
| **CW-PBFT Consensus Success** | **100%** (3-8 nodes) | Simulated complete 3-phase PBFT with failover |
| **ECDSA Signature Speed** | **0.12ms/sign**, **0.08ms/verify** | secp256r1 + RFC 6979 deterministic k |
| **Blockchain Overhead** | **< 5%** | Batch async upload every 10 steps |
| **Nash Equilibrium Margin** | **13.0** (safety margin 650%) | Cooperation = strict dominant strategy (mathematically proven) |
| **Test Coverage** | **90%+** (312+ tests) | Unit + Integration + Security + E2E |
| **Source Scale** | **300+ files, 15,000+ lines** | Modular architecture, clean separation of concerns |

---

## 🚀 One-Click Reproduce

### Judge Quick Start (3 commands, ~2 minutes)

```bash
# Step 1: Install dependencies
pip install cryptography numpy torch scipy tqdm matplotlib flask

# Step 2: Verify environment
python -c "from cryptography.hazmat.primitives.asymmetric import ec; import numpy, torch, scipy; print('✅ All dependencies OK')"

# Step 3: Quick demo (30 episodes, ~1 minute)
python main.py --demo
```

### Full Experiment Pipeline (automatic)

```bash
# Option A: Full competition experiment (3 modes × 3 seeds × 1000 episodes)
python scripts/one-click/run_full_experiment.py

# Option B: λ sensitivity sweep (6 λ values × 3 seeds)
python scripts/ablation/lambda_sweep.py

# Option C: Ablation experiment (4 conditions × 5 seeds)
python scripts/ablation/run_all.py

# Option D: Performance benchmark suite
python scripts/benchmark/run_all.py
python scripts/benchmark/run_scale.py       # Large-scale network benchmark
```

### Docker (fully isolated)

```bash
docker build -t marl-ecdsa-chain .
docker run -it --rm -p 9090:9090 marl-ecdsa-chain --demo
docker-compose up -d                         # Dashboard + training
docker-compose run experiment                # Full experiment
```

---

## 📐 System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                VISUALIZATION LAYER                               │
│  Flask + Chart.js 9-tab Dashboard | http://127.0.0.1:9090       │
│  Overview│Network│Security│Ledger│MARL│Compare│P2P│ECDSA│System │
├──────────────────────────────────────────────────────────────────┤
│                MARL COOPERATION LAYER                            │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐        │
│  │ IQL Trainer  │  │ Cooperation  │  │ Nash Equilibrium │        │
│  │ (TD-error)   │  │ Detector     │  │ Verifier         │        │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘        │
│         │          total = env + λ·bc_reward    │                │
├─────────┼──────────────────┼───────────────────┼─────────────────┤
│         ▼                  ▼                   ▼                  │
│                BLOCKCHAIN CORE LAYER                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ ECDSA    │→│ Security  │→│Transaction│→│ Block → Chain │    │
│  │ secp256r1│  │ Guard(3x)│  │ Pool      │  │ (Merkle Root) │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────┬───────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────▼──────────┐   │
│  │ Identity     │  │ Incentive    │  │ CW-PBFT Consensus   │   │
│  │ Contract     │  │ Contract     │  │ (Shapley-weighted)  │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
├──────────────────────────────────────────────────────────────────┤
│                DISTRIBUTED NETWORK LAYER                         │
│  ┌────────────┐  ┌─────────────┐  ┌────────────────────────┐    │
│  │ asyncio    │  │ P2P Flood   │  │ Gossip Dynamic         │    │
│  │ TCP Socket │  │ Broadcast   │  │ Discovery (Phase 2)    │    │
│  └────────────┘  └─────────────┘  └────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘

BIDIRECTIONAL SYNERGY LOOP:
  BC → MARL:  total_reward[t] = env_reward[t] + λ·bc_score/T
  MARL → BC:  agent behavior → contribution scores → CW-PBFT voting weights
```

### Core Data Flow (per training step)

```
Step Loop:
  1. Agent decision (IQL ε-greedy) → action
  2. SigningService → ECDSA signature (agent_id, action_hash, timestamp, nonce)
  3. SecurityGuard → 3-stage check (k-value reuse / nonce monotonic / timestamp window)
  4. ActionRecorder → buffer action
  5. CooperationDetector → classify cooperation/betrayal
  6. Every 10 steps: batch → Transaction → mempool

Episode Settlement:
  7. Flush buffer → ECDSA verify all → contribution scoring
  8. IncentiveContract → settlement (base reward + tier bonus + betrayal penalty)
  9. Block packaging → CW-PBFT consensus → chain append → weight update
  10. BC reward uniform distribution → replay buffer
  11. Adaptive λ update (EMA-smoothed closed-loop controller)
```

---

## 💡 Core Innovations

### Innovation 1: CA-Free Distributed ECDSA Identity Anchoring

**Problem**: Centralized CA = single point of failure. DigiNotar (2011): 500+ domain certs forged after CA key leak.

**Our Solution**: Blockchain replaces CA as trust root.
- Agent locally generates secp256r1 keypair (`KeyManager.generate_or_load()`)
- Public key self-registers on-chain via `IdentityContract`
- Every action carries ECDSA signature: `{agent_id, action_hash, timestamp, nonce} + DER sig`
- `SecurityGuard` 3-stage defense: k-value reuse (r-value) / nonce monotonic / timestamp ±30s window
- RFC 6979 deterministic k-value at the cryptographic layer

**Quantified**: Sign 0.12ms | Verify 0.08ms | 75,000 signatures per 1000-episode training | 100% interception

**Code**: `blockchain/crypto/ecdsa_utils.py`, `blockchain/crypto/security_guard.py`, `blockchain/crypto/key_manager.py`

---

### Innovation 2: CW-PBFT Contribution-Weighted Byzantine Fault Tolerance

**Problem**: Standard PBFT "one node = one vote" treats freeloaders and high-contributors equally.

**Our Solution**: Shapley-value weight derivation for fair contribution weighting.
```
κ_task = 1/3 + σ/3 ≈ 0.40     (σ = task variance, high variance → high marginal contribution)
κ_coop = 1/3 + φ/3 ≈ 0.35     (φ = cooperation externality, compensates positive externalities)
κ_compliance = 1/3 - σ/3 - φ/3 ≈ 0.25

weighted_score = 0.40·task + 0.35·coop + 0.25·compliance
w_node = 1.0 + 0.5·weighted_score
w_init = 0.3 (new nodes)   w_min = 0.1 (non-banned lower bound)
```

**Dynamic Failover** (Phase 2): Byzantine primary detection → automatic view change → healthy node promotion. Simulated 20-round attack → 100% detection + avg failover latency quantified.

**Code**: `blockchain/consensus/cw_pbft.py`, `blockchain/consensus/cw_pbft_failover.py`

---

### Innovation 3: Nash Equilibrium Incentive-Compatible Smart Contracts

**Theorem**: When λ ≥ 0.0667 and betrayal penalty β ≥ 2.0, **Cooperation(C) is a strict dominant strategy**, and (C,C) is the unique pure-strategy Nash equilibrium.

**Payoff Matrix** (λ=0.5, β=2.0):
```
                Opponent-C        Opponent-D
    Me-C        +10.00 ✅         +7.00
    Me-D         -4.00            -9.00
```

**Proof**: U(C,C)=+10 > U(D,C)=-4 ✓ | U(C,D)=+7 > U(D,D)=-9 ✓ → Cooperation strictly dominates defection in ALL opponent strategies.

**Margin**: 13.0 | **Safety Margin**: 650% | λ_min = 0.0667, λ_current = 0.5 (7.5× threshold)

**Code**: `marl/analysis/nash_verifier.py`, `blockchain/contracts/incentive_contract.py`

---

### Innovation 4-8: Summary

| # | Innovation | Key Mechanism | Quantified Result |
|---|-----------|---------------|:-----------------:|
| 4 | **Adaptive λ Controller** | Closed-loop PID: λ_t = clamp(λ_base + η·(κ_c·c_t + κ_k·k_t - κ_s·s_t), λ_min, λ_max) with EMA(α=0.9) | +6.3% vs static λ |
| 5 | **Batch Async Upload** | 10-step buffering → batch Transaction → episode-end Block + Consensus | Blockchain overhead <5% |
| 6 | **SecurityGuard 3-Stage Defense** | k-value reuse (r-registry) / nonce monotonic / timestamp ±30s window | 100% detection, µs-level latency |
| 7 | **Selfish Agent Adversarial Validation** | 0%-50% betrayal ratio → verifies anti-betrayal under worst-case | Performance quantified across ratios |
| 8 | **Full-Pipeline Cryptographic Verifiability** | Every step: signature → guard → transaction → block → consensus → chain | 75,000+ cryptographically verifiable actions |

### Phase 2 Extended Innovations

| # | Innovation | Key Mechanism | Status |
|---|-----------|---------------|:------:|
| 9 | **Gossip Dynamic Node Discovery** | HyParView-inspired partial view, O(log n) convergence, dead node auto-eviction, shuffle exchange | ✅ Code Complete |
| 10 | **Post-Quantum Dilithium Adapter** | Adapter pattern (zero API change), hybrid ECDSA+Dilithium dual-signature, NIST FIPS 204 compliant | ✅ Interface Ready |

**Code**: `blockchain/network/gossip_discovery.py`, `blockchain/crypto/dilithium_adapter.py`

---

## 📊 Experimental Results

### Core Comparison (5 seeds × 1000 episodes, λ=0.5)

| Agents | Mode | total_reward | env_reward | Coop Rate | BC Gain |
|:------:|:----:|:----------:|:----------:|:--------:|:------:|
| 3 | **bc_marl** | **-30.96±2.15** | -48.46±2.15 | 54.55% | **+42.2%** 🔥 |
| 3 | pure_marl | -53.56±1.06 | -53.56±1.06 | 50.73% | — |
| 5 | **bc_marl** | **-45.53±1.87** | -73.03±1.87 | 69.61% | **+40.4%** 🔥 |
| 5 | pure_marl | -76.34±0.82 | -76.34±0.82 | 68.44% | — |

**Statistical Test**: Welch's t-test, bc_marl vs pure_marl: **p < 0.001** ✓✓✓ (extremely significant)

### λ Robustness Sweep (6 values × 3 seeds)

| λ | Total Reward | Env Reward | Coop Rate | Recommendation |
|:--:|:----------:|:--------:|:--------:|:--------------|
| 0.0 | -53.56 | -53.56 | 50.73% | 📊 Pure MARL baseline |
| 0.1 | -30.41 | -35.11 | 52.1% | ✅ Effective |
| 0.3 | -28.90 | -33.50 | 53.8% | ✅ Good balance |
| **0.5** | **-30.96** | **-48.46** | **54.55%** | ✅ **Competition recommended** |
| 0.8 | -31.20 | -50.10 | 55.0% | ⚠️ Check env distortion |
| 1.0 | -32.50 | -52.30 | 55.3% | ⚠️ Excessive incentive |

**Robust λ Range**: λ ∈ [0.3, 0.8] maintains ≥90% of best total_reward.

### Ablation Study

| Condition | Mean Reward | vs Baseline | Key Finding |
|:---------|:----------:|:----------:|------------|
| Full Baseline | -31.6±2.3 | — | All modules enabled |
| -SecurityGuard | -32.1±1.6 | -1.5% | ECDSA signing is core, Guard is auxiliary |
| -CW-PBFT Weighting | -31.6±2.3 | +0.1% | IncentiveContract + ECDSA = core contribution |
| **-IncentiveContract** 🔥 | **-51.8±2.0** | **-63.9%** | **Incentive is THE critical module** |

### CW-PBFT Byzantine Failover (20 rounds, 4 Byzantine events)

| Metric | Value |
|--------|:-----:|
| Byzantine primaries detected | 100% (4/4) |
| Successful failovers | 100% (4/4) |
| Avg failover latency | < 3ms |
| Post-failover consensus recovery | 100% |

### Security: Four Attack Types

| Attack | Interception Rate | Detection Mechanism |
|--------|:----------------:|--------------------|
| Message Tampering | **100%** | ECDSA signature verification |
| Identity Forgery | **100%** | On-chain public key registration + verification |
| k-Value Reuse → Private Key Derivation | **100%** | SecurityGuard r-value registry (FIFO 1000 entries) |
| Byzantine Node Vote Splitting | **100%** | CW-PBFT ≥2/3 weight threshold + failover |

---

## 🏃 Quick Start Guide

### Environment Setup

| Component | Minimum | Recommended | Notes |
|-----------|:-------:|:-----------:|-------|
| Python | 3.10 | 3.12/3.13 | Primary development environment |
| Memory | 4GB | 8GB+ | Training loads PyTorch |
| Disk | 500MB | 1GB+ | Including dependencies + results |
| OS | — | Windows 11 / Ubuntu 22.04 | Cross-platform compatible |

### 5-Minute Quick Demo

```bash
# 1. Clone & enter
cd marl-ecdsa-consensus-chain

# 2. Install
pip install cryptography numpy torch scipy tqdm matplotlib flask

# 3. Verify
python -c "from cryptography.hazmat.primitives.asymmetric import ec; import numpy, torch, scipy; print('✅ OK')"

# 4. Quick demo (30 episodes, ~1 min)
python main.py --demo

# 5. Dashboard (open http://127.0.0.1:9090)
python main.py --dashboard
```

### Standard Training

```bash
# BC-MARL (competition recommended, λ=0.5)
python train.py --mode bc_marl --n_episodes 1000 --lambda_weight 0.5 --seed 42

# Pure MARL (control group)
python train.py --mode pure_marl --n_episodes 1000 --seed 42

# With selfish agents (30% betrayal ratio)
python train.py --mode selfish --n_episodes 1000 --selfish_ratio 0.3 --seed 42

# 5-agent experiment
python train.py --mode bc_marl --n_agents 5 --n_landmarks 5 --n_episodes 1000 --lambda_weight 0.5
```

### P2P Network Demo

```bash
# 3-node, 15-round consensus demo
python scripts/network_demo.py --nodes 3 --rounds 15

# 5-node, 50-round with verbose logging
python scripts/network_demo.py --nodes 5 --rounds 50 --verbose

# One-click P2P cluster
python scripts/one-click/start_p2p_cluster.py --nodes 4 --rounds 20
```

### Automated Experiments

```bash
# Full pipeline (3 modes × 3 seeds)
python scripts/one-click/run_full_experiment.py

# λ sensitivity sweep (6 λ × 3 seeds)
python scripts/ablation/lambda_sweep.py

# Ablation (4 conditions × 5 seeds)
python scripts/ablation/run_all.py

# Performance benchmark
python scripts/benchmark/run_all.py
python scripts/benchmark/run_scale.py
```

### Docker

```bash
docker build -t marl-ecdsa-chain .
docker run -it --rm -p 9090:9090 marl-ecdsa-chain --demo
docker run -it --rm -p 9090:9090 -v $(pwd)/results:/app/results \
    marl-ecdsa-chain python scripts/one-click/run_full_experiment.py
docker-compose up -d
```

---

## 📂 Project Structure

```
marl-ecdsa-consensus-chain/
│
├── blockchain/                              # Blockchain Core Layer
│   ├── crypto/
│   │   ├── ecdsa_utils.py                  # ECDSA sign/verify (secp256r1, RFC 6979, FIPS 186-5)
│   │   ├── key_manager.py                  # Keypair generation & PEM persistence
│   │   ├── security_guard.py               # 3-stage defense (k-value/nonce/timestamp)
│   │   └── dilithium_adapter.py            # [Phase 2] Post-quantum Dilithium adapter
│   ├── ledger/
│   │   ├── block.py                        # Block with Merkle root & proposer signature
│   │   ├── blockchain.py                   # Chain ledger (thread-safe, tx pool cap)
│   │   └── world_state.py                  # World state (agent scores, identities, actions)
│   ├── consensus/
│   │   ├── cw_pbft.py                      # CW-PBFT (Shapley-weighted, 2 modes)
│   │   ├── cw_pbft_failover.py             # [Phase 2] Dynamic primary failover
│   │   └── standard_pbft.py                # Standard PBFT comparison implementation
│   ├── contracts/
│   │   ├── identity_contract.py            # Identity registration (pubkey → on-chain)
│   │   ├── incentive_contract.py           # Contribution scoring + settlement
│   │   └── penalty_contract.py             # 3-tier penalty (warning→demotion→ban)
│   └── network/
│       ├── p2p_node.py                     # asyncio TCP P2P node
│       ├── network_consensus.py            # P2P network CW-PBFT
│       ├── message_protocol.py             # JSON + 4-byte length prefix protocol
│       └── gossip_discovery.py             # [Phase 2] Gossip dynamic node discovery
│
├── marl/                                    # MARL Cooperation Layer
│   ├── envs/
│   │   └── simple_spread.py                # SimpleSpreadEnv (NumPy self-implemented)
│   ├── algorithms/
│   │   └── qmix.py                         # IQL (primary) + QMIX/VDN (optional)
│   ├── integration/
│   │   ├── bc_integration.py               # BC-MARL Bridge (orchestrator)
│   │   ├── signing_service.py              # ECDSA signing + nonce management
│   │   ├── action_recorder.py              # Behavior buffer → Transaction → batch upload
│   │   ├── cooperation_detector.py         # Cooperation/betrayal classification
│   │   ├── settlement_coordinator.py       # Contribution scoring + reward settlement
│   │   ├── consensus_shaper.py             # CARS consensus-aware reward shaping
│   │   ├── adaptive_lambda.py             # Adaptive λ closed-loop controller
│   │   └── selfish_agent.py               # Selfish agent wrapper
│   └── analysis/
│       └── nash_verifier.py                # Nash equilibrium verifier (826 lines)
│
├── visualization/                           # Application Layer
│   ├── dashboard.py                        # Flask + Chart.js 9-tab dashboard v3.9
│   ├── plot_results.py                     # matplotlib static chart generator
│   └── start_dashboard.py                  # Dashboard launcher
│
├── experiments/                             # Experiment Scripts
│   └── run_experiment.py                   # Unified experiment runner
│
├── tests/                                   # Test Suite (312+ tests)
│   ├── test_crypto.py                      # 48 crypto tests
│   ├── test_blockchain.py                  # 52 blockchain tests
│   ├── test_consensus.py                   # 38 consensus tests
│   ├── test_contracts.py                   # 44 contract tests
│   ├── test_p2p_network.py                 # 10 P2P protocol tests
│   ├── test_env.py                         # 32 environment tests
│   ├── test_qmix.py                        # 28 algorithm tests
│   ├── test_bc_integration.py              # 36 integration tests
│   ├── test_rfc6979_security.py            # [Phase 2] 25 RFC 6979 + k-value leak tests
│   └── smoke_test_e2e.py                   # 8 end-to-end smoke tests
│
├── scripts/                                 # Utility Scripts
│   ├── one-click/                          # [R1] One-click reproduction
│   │   ├── run_full_experiment.py          # Full experiment pipeline
│   │   ├── start_p2p_cluster.py            # P2P cluster launcher
│   │   └── launch_dashboard.py             # Dashboard launcher
│   ├── benchmark/                          # [R2] Performance benchmarks
│   │   ├── run_all.py                      # Full benchmark (ECDSA/TPS/Consensus/Guard)
│   │   └── run_scale.py                    # [Phase 1] Large-scale benchmark (3/5/8 nodes)
│   ├── ablation/                           # [R2] Ablation automation
│   │   ├── run_all.py                      # 4-condition ablation × N seeds
│   │   └── lambda_sweep.py                # [Phase 1] λ multi-gradient sweep (6 values)
│   ├── network_demo.py                     # P2P consensus standalone demo
│   ├── generate_competition_ppt.py         # [R3] PPT programmatic generator
│   └── smoke_test_e2e.py                   # E2E smoke test
│
├── train.py                                 # Training entry (MARLBlockchainTrainer, 762 lines)
├── main.py                                  # CLI entry (argparse + modes)
├── config.json                              # Centralized configuration
├── requirements.txt                         # Dependency manifest
├── Dockerfile                               # Docker image
├── docker-compose.yml                       # Multi-container orchestration
├── pyproject.toml                           # Build configuration
├── pytest.ini                               # Pytest configuration
├── CHANGELOG.md                             # Complete version history
├── LICENSE                                  # MIT License
└── README.md                                # This file
```

---

## 📋 All Commands Reference

### Training Modes

| Command | Description |
|---------|------------|
| `python main.py` | Default: BC-MARL training |
| `python main.py --demo` | Quick demo (30 episodes) |
| `python main.py --mode pure_marl` | Pure MARL control |
| `python main.py --mode bc_marl --lambda_weight 0.5` | BC-MARL with custom λ |
| `python main.py --mode selfish --selfish_ratio 0.3` | 30% selfish agents |
| `python main.py --dashboard` | Training + real-time dashboard |

### Training (Advanced)

| Command | Description |
|---------|------------|
| `python train.py --n_agents 5 --n_landmarks 5` | 5-agent training |
| `python train.py --n_episodes 2000` | Extended training |
| `python train.py --ablate-security` | Ablation: disable SecurityGuard |
| `python train.py --ablate-consensus` | Ablation: CW-PBFT equal weight |
| `python train.py --ablate-incentive` | Ablation: disable IncentiveContract |
| `python train.py --no-adaptive-lambda` | Disable adaptive λ |
| `python train.py --consensus-shaping` | Enable CARS reward shaping |
| `python train.py --algorithm qmix` | Use QMIX instead of IQL |
| `python train.py --algorithm vdn` | Use VDN instead of IQL |

### Experiments

| Command | Description |
|---------|------------|
| `python scripts/one-click/run_full_experiment.py` | Full pipeline |
| `python scripts/one-click/run_full_experiment.py --quick` | Quick test (100 episodes) |
| `python scripts/one-click/run_full_experiment.py --agents 5` | 5-agent experiment |
| `python scripts/ablation/run_all.py` | Ablation (4 conditions × 5 seeds) |
| `python scripts/ablation/run_all.py --quick` | Quick ablation (1 seed) |
| `python scripts/ablation/lambda_sweep.py` | λ sweep (6 values × 3 seeds) |
| `python scripts/ablation/lambda_sweep.py --quick` | Quick λ sweep |
| `python scripts/ablation/lambda_sweep.py --agents 5` | 5-agent λ sweep |

### Benchmarks

| Command | Description |
|---------|------------|
| `python scripts/benchmark/run_all.py` | Full benchmark suite |
| `python scripts/benchmark/run_all.py --quick` | Quick benchmark |
| `python scripts/benchmark/run_scale.py` | Large-scale benchmark (3/5/8 nodes) |

### P2P Network

| Command | Description |
|---------|------------|
| `python scripts/network_demo.py --nodes 3 --rounds 15` | P2P consensus demo |
| `python scripts/network_demo.py --nodes 5 --rounds 50 --verbose` | Verbose large demo |
| `python scripts/one-click/start_p2p_cluster.py --nodes 4` | One-click P2P cluster |

### Testing

| Command | Description |
|---------|------------|
| `python -m pytest tests/ -v` | Run all 312+ tests |
| `python -m pytest tests/ -v -m crypto` | Crypto tests only |
| `python -m pytest tests/ -v -m security` | Security tests only |
| `python -m pytest tests/ -v -m blockchain` | Blockchain tests only |
| `python -m pytest tests/test_rfc6979_security.py -v` | RFC 6979 + k-value leak tests |
| `python scripts/smoke_test_e2e.py` | End-to-end smoke test |
| `python attack_defense_demo.py` | Security attack/defense demo |

### Dashboard & Visualization

| Command | Description |
|---------|------------|
| `python main.py --dashboard` | Launch dashboard (http://127.0.0.1:9090) |
| `python scripts/one-click/launch_dashboard.py` | One-click dashboard launcher |
| `python scripts/one-click/launch_dashboard.py --port 8080` | Custom port |
| `python scripts/generate_competition_ppt.py` | Generate PPT (requires python-pptx) |

---

## 📖 API Reference

### ECDSAUtils (`blockchain/crypto/ecdsa_utils.py`)

```python
from blockchain.crypto.ecdsa_utils import ECDSAUtils

# Key management
priv, pub = ECDSAUtils.generate_key_pair()
pem_bytes = ECDSAUtils.private_key_to_bytes(priv)
pub_hex = ECDSAUtils.public_key_to_hex(pub)

# Signing & verification
message = ECDSAUtils.build_message("agent_0", action, timestamp, nonce)
signature = ECDSAUtils.sign(private_key, message)
is_valid = ECDSAUtils.verify(public_key, message, signature)

# Full action signing pipeline
package = ECDSAUtils.sign_action("agent_0", private_key, [0.5, 0.3], nonce=42)
is_legit = ECDSAUtils.verify_action_package(package, public_key)

# DER signature parsing (for k-value reuse detection)
r, s = ECDSAUtils.extract_rs(signature)
```

### SecurityGuard (`blockchain/crypto/security_guard.py`)

```python
from blockchain.crypto.security_guard import SecurityGuard

guard = SecurityGuard()

# Full 3-stage check
is_safe, reason = guard.check_package({
    "agent_id": "agent_0",
    "timestamp": int(time.time() * 1000),
    "nonce": 42,
    "r": 0x8F3A2B...,
})

# Query
guard.get_risk_level("agent_0")        # NORMAL / WARNING / DANGER
guard.get_fail_count("agent_0")
guard.get_alerts(agent_id="agent_0")
guard.get_stats()
```

### CWPBFTConsensus (`blockchain/consensus/cw_pbft.py`)

```python
from blockchain.consensus.cw_pbft import CWPBFTConsensus

consensus = CWPBFTConsensus("node_0", ["node_0", "node_1", "node_2"])

# Consensus
ok = consensus.simulated_consensus(block_hash, proposer_id)

# Weight management
consensus.update_weight("node_1", new_weight=1.5)
weights = consensus.get_weights()

# Query
consensus.get_primary(block_height)
consensus.is_primary(block_height)
stats = consensus.get_consensus_stats()
```

### CWPBFTConsensusWithFailover (`blockchain/consensus/cw_pbft_failover.py`)

```python
from blockchain.consensus.cw_pbft_failover import CWPBFTConsensusWithFailover

consensus = CWPBFTConsensusWithFailover("node_0", node_ids)

# Consensus with failover
ok, failover_record = consensus.simulated_consensus_with_failover(
    block_hash, proposer,
    simulate_byzantine=True,    # Force proposer to act Byzantine
    simulate_timeout=False,     # Force proposer timeout
)

# Byzantine scenario simulation
results = consensus.simulate_byzantine_primary_attack(n_rounds=20)

# Statistics
stats = consensus.get_failover_stats()
```

### BlockchainMARLBridge (`marl/integration/bc_integration.py`)

```python
bridge = BlockchainMARLBridge(
    n_agents=3, n_landmarks=3,
    blockchain_node=bc_node,
    incentive_contract=incentive_contract,
    identity_contract=identity_contract,
    key_manager=key_manager,
    security_guard=security_guard,
    cw_pbft_consensus=cw_pbft,
    lambda_weight=0.5,
)

# Per-step
bridge.on_step(step, observations, actions, agent_ids, env_rewards)

# Episode end
deltas = bridge.on_episode_end(episode, agent_ids, env_rewards)

# Reward computation
total = bridge.compute_total_reward("agent_0", env_reward=1.5)

# Statistics
stats = bridge.get_stats()
bc_scores = bridge.get_bc_scores()
```

### NashEquilibriumVerifier (`marl/analysis/nash_verifier.py`)

```python
from marl.analysis.nash_verifier import NashEquilibriumVerifier, quick_verify

# Full verification
verifier = NashEquilibriumVerifier(lambda_weight=0.5)
payoff_matrix = verifier.compute_payoff_matrix(env_payoffs)
nash_equilibria = verifier.find_nash_equilibria(payoff_matrix)
dominant = verifier.verify_dominant_strategy(payoff_matrix)
bounds = verifier.compute_parameter_bounds(env_betrayal_advantage=2.0)
report = verifier.generate_report(n_agents=3)

# Quick one-liner
result = quick_verify(lambda_weight=0.5)
print(result.conclusion)
```

### GossipDiscovery (`blockchain/network/gossip_discovery.py`)

```python
from blockchain.network.gossip_discovery import GossipDiscovery

discovery = GossipDiscovery("node_0", max_peers=20, k_view=5)

# Start with seed peers
await discovery.start(seed_peers=[("127.0.0.1", 7001)])

# Query
peers = discovery.get_active_peers()
stats = discovery.get_stats()

# Notifications
discovery.notify_join("node_5", host="127.0.0.1", port=7006)
discovery.notify_leave("node_3")
```

### DilithiumAdapter (`blockchain/crypto/dilithium_adapter.py`)

```python
from blockchain.crypto.dilithium_adapter import (
    ECDSAAdapter, DilithiumAdapter, HybridSignatureAdapter,
    benchmark_signature_adapters
)

# Current ECDSA
ecdsa = ECDSAAdapter()
sig = ecdsa.sign(private_key, message)
ok = ecdsa.verify(public_key, message, sig)

# Future Dilithium (fallback mode until pqcrypto installed)
dilithium = DilithiumAdapter(use_fallback=True)

# Hybrid transition
hybrid = HybridSignatureAdapter()
dual_sig = hybrid.hybrid_sign(ecdsa_key, dilithium_key, message)
ok = hybrid.hybrid_verify(ecdsa_pub, dilithium_pub, message, **dual_sig)

# Comparison benchmark
bench = benchmark_signature_adapters(1000)
```

---

## ⚙️ Configuration Guide

### config.json

```json
{
  "modes": {
    "bc_marl": {
      "lambda_weight": 0.5,       // Competition recommended: λ=0.5
      "n_agents": 3,              // 3 or 5
      "n_episodes": 1000,         // Training episodes
      "max_steps": 25,            // Max steps per episode
      "hidden_dim": 128,          // Neural network hidden dimension
      "lr": 0.001,                // Learning rate
      "gamma": 0.8,               // Discount factor
      "batch_size": 64,           // Replay batch size
      "upload_interval": 10       // Batch upload every N steps
    }
  },
  "blockchain": {
    "consensus": "CW-PBFT",
    "penalty_thresholds": { "warning": 10, "demotion": 30, "ban": 50 },
    "token_economics": { "base_reward": 10.0, "betrayal_penalty_mult": 2.0 }
  },
  "experiments": {
    "adaptive_lambda": {
      "lambda_base": 0.1,
      "lambda_range": [0.05, 0.15],
      "kappa_c": 0.4, "kappa_k": 0.35, "kappa_s": 0.25
    }
  }
}
```

### Key Parameters

| Parameter | Default | Range | Description |
|-----------|:------:|:-----:|------------|
| `lambda_weight` | 0.5 | 0.0-1.0 | BC incentive weight. 0.5 = competition recommended |
| `gamma` | 0.8 | 0.5-0.99 | Discount factor. 0.8 optimal for SimpleSpread negative rewards |
| `lr` | 1e-3 | 1e-5-1e-2 | Learning rate |
| `hidden_dim` | 128 | 64-256 | Neural network size |
| `n_episodes` | 1000 | 100-5000 | Training episodes |
| `upload_interval` | 10 | 5-50 | Batch upload frequency |
| `seed` | 42 | any int | Random seed for reproducibility |

---

## 🧪 Testing

### Test Suite Overview

| Module | Tests | Coverage | Key Focus |
|--------|:-----:|:--------:|-----------|
| `test_crypto.py` | 48 | 95%+ | Key generation, sign/verify, serialization |
| `test_blockchain.py` | 52 | 92%+ | Block structure, chain validation, tx pool |
| `test_consensus.py` | 38 | 90%+ | CW-PBFT, standard PBFT, weight updates |
| `test_contracts.py` | 44 | 91%+ | Identity, incentive, penalty logic |
| `test_p2p_network.py` | 10 | 85%+ | Message protocol, encoding, CW-PBFT messages |
| `test_env.py` | 32 | 93%+ | Environment reset, step, reward calculation |
| `test_qmix.py` | 28 | 88%+ | IQL training, QMIX, VDN |
| `test_bc_integration.py` | 36 | 89%+ | Bridge, signing, recording, detection, settlement |
| `test_rfc6979_security.py` | 25 | — | RFC 6979 deterministic k, k-value leak simulation, nonce replay, timestamp spoofing |
| `smoke_test_e2e.py` | 8 | — | End-to-end pipeline |
| **Total** | **312+** | **90%+** | — |

### Running Tests

```bash
# All tests
python -m pytest tests/ -v --tb=short

# Specific module
python -m pytest tests/ -v -m crypto
python -m pytest tests/ -v -m blockchain
python -m pytest tests/ -v -m security

# RFC 6979 + k-value leak tests (Phase 2)
python -m pytest tests/test_rfc6979_security.py -v

# With coverage
pip install pytest-cov
python -m pytest tests/ --cov=. --cov-report=html
```

---

## 🔒 Security

### Cryptographic Standards Compliance

| Standard | Implementation |
|----------|---------------|
| **FIPS 186-5** | ECDSA secp256r1 (P-256) curve |
| **RFC 6979** | Deterministic k-value via HMAC_DRBG |
| **FIPS 204** (2024) | CRYSTALS-Dilithium adapter (Phase 2, migration-ready) |
| **SHA-256** | Message hashing and block identity |

### Defense-in-Depth Architecture

```
Layer 1 (Cryptographic):  ECDSA sign/verify → prevents forgery/tampering
Layer 2 (Behavioral):     SecurityGuard 3-stage → k-value/nonce/timestamp
Layer 3 (Consensus):      CW-PBFT 2/3 weight threshold → Byzantine tolerance
Layer 4 (Economic):       PenaltyContract → betrayal cost > cooperation gain
Layer 5 (Audit):          Full-chain traceability → every action cryptographically verifiable
```

### STRIDE Threat Coverage

| Category | Threats | Mitigations |
|----------|:-------:|------------|
| Spoofing | 3 | ECDSA verification + WorldState uniqueness + deterministic primary rotation |
| Tampering | 4 | ECDSA signature + SecurityGuard + chain hashing + Merkle root |
| Repudiation | 2 | On-chain signature evidence + vote record traceability |
| Information Disclosure | 3 | Private key never on-chain + action_hash only + limited public data |
| Denial of Service | 3 | Tx pool cap (10,000) + consensus timeout (5s) + r_registry FIFO (1,000) |
| Elevation of Privilege | 2 | w_init=0.3 + PenaltyContract finality (ban=50) |

---

## 📈 Performance Benchmarks

### ECDSA Cryptography

| Operation | Time | Throughput |
|-----------|:----:|:----------:|
| Key Generation | 0.8ms | — |
| Sign (raw) | 0.12ms | ~8,300 ops/s |
| Verify | 0.08ms | ~12,500 ops/s |
| Full Sign Pipeline | 0.14ms | ~7,100 ops/s |

### Blockchain Throughput

| Metric | Value |
|--------|:-----:|
| Transactions/sec (TPS) | ~120 (local) |
| Blocks/sec (BPS) | ~4.0 |
| CW-PBFT Consensus (3 nodes) | ~5ms/round |
| SecurityGuard Check | < 1µs |

### CW-PBFT Network Scalability

| Nodes | Success Rate | Avg Latency | P95 Latency | Throughput |
|:-----:|:----------:|:---------:|:---------:|:--------:|
| 3 | 100% | 5.2ms | 8.1ms | 192 rps |
| 5 | 100% | 8.7ms | 14.3ms | 115 rps |
| 8 | 100% | 15.3ms | 26.8ms | 65 rps |

### Training Overhead Breakdown (1000 episodes)

| Component | Time (s) | % of Total |
|-----------|:------:|:----------:|
| IQL Training | ~350.0 | 82.0% |
| Environment Interaction | ~55.0 | 13.0% |
| ECDSA Signing | ~9.0 | 2.1% |
| Batch Upload | ~6.0 | 1.4% |
| Block + Consensus | ~5.0 | 1.2% |
| SecurityGuard | ~1.5 | 0.3% |
| **Total** | **~426.5** | **100%** |

> **Blockchain overhead < 5%** — the MARL training itself (82%) is the dominant factor, not the blockchain.

---

## 🐳 Docker Deployment

### Single Container

```bash
docker build -t marl-ecdsa-chain .
docker run -it --rm -p 9090:9090 marl-ecdsa-chain --demo
docker run -it --rm -p 9090:9090 -v $(pwd)/results:/app/results \
    marl-ecdsa-chain python scripts/one-click/run_full_experiment.py
```

### Multi-Container (docker-compose)

```bash
# Start dashboard + training
docker-compose up -d

# Run experiment
docker-compose run experiment

# Dashboard only
docker-compose run dashboard

# P2P network demo
docker-compose run p2p-demo

# Stop all
docker-compose down
```

### Services

| Service | Profile | Port | Description |
|---------|:------:|:----:|------------|
| `app` | default | 9090 | Training + Dashboard |
| `experiment` | experiment | 9091 | Full experiment runner |
| `dashboard` | dashboard | 9090 | Dashboard only |
| `p2p-demo` | p2p | host | P2P network demo |

---

## 🏭 Industry Scenarios

### 1. Swarm Robotics Coordination

**Pain Point**: Multi-robot task allocation vulnerable to sensor deception; no audit trail for individual robot actions.

**Mapping**: ECDSA-anchored robot identity → blockchain behavior ledger → CW-PBFT weighted task priority voting.

**Value**: Byzantine Fault Tolerance (f=⌊(n-1)/3⌋); task completion integrity cryptographically provable; automated reward settlement.

### 2. Federated Learning Contribution Measurement

**Pain Point**: Malicious nodes upload fake gradients; honest nodes lack proportional reward; no way to prove contribution.

**Mapping**: CW-PBFT weighted gradient aggregation → on-chain immutable contribution records → smart contract automatic settlement.

**Value**: Gradient poisoning attacks detectable and punishable; fair contribution measurement with mathematical guarantees.

### 3. Distributed Computing Power Market

**Pain Point**: Untrusted compute providers may falsify results; no automated verification mechanism.

**Mapping**: ECDSA-signed computation attestations → on-chain verification → tiered penalty for false claims.

**Value**: 100% detection of duplicate/fake computation claims; fully automated settlement; reputation-based pricing.

---

## 🔮 Future Roadmap

### Phase 1 (0-6 months post-competition): Engineering Hardening
- Gossip dynamic node discovery (✅ code complete, pending real-network testing)
- SMAC environment adaptation (10+ agent scenarios)
- GPU CUDA acceleration
- Multi-process environment interaction

### Phase 2 (6-12 months): Deep Academic
- Post-quantum Dilithium migration (✅ adapter complete, pending pqcrypto integration)
- Sharding consensus prototype (100+ agent horizontal scaling)
- Multi-host deployment with real network conditions
- Formal security verification (ProVerif/Tamarin)

### Phase 3 (12-18 months): Frontier Breakthrough
- Full CRYSTALS-Dilithium implementation replacing ECDSA
- Cross-chain IBC protocol for multi-chain MARL
- Meta-learning λ scheduling (RL-learned λ policy)

### Phase 4 (18-24 months): Industry & Publications
- Industry PoC (robotics / federated learning / compute market)
- CCF-A/B conference paper submissions
- Open-source community release

---

## 📚 Academic References

[1] Nash J. Non-cooperative games[J]. *Annals of Mathematics*, 1951, 54(2): 286-295.

[2] Castro M, Liskov B. Practical Byzantine Fault Tolerance[C]. *OSDI*, 1999: 173-186.

[3] Johnson D, Menezes A, Vanstone S. The Elliptic Curve Digital Signature Algorithm (ECDSA)[J]. *International Journal of Information Security*, 2001, 1(1): 36-63.

[4] Pornin T. RFC 6979: Deterministic Usage of DSA and ECDSA[S]. *IETF*, 2013.

[5] Rashid T, Samvelyan M, de Witt C S, et al. QMIX: Monotonic Value Function Factorisation for Deep Multi-Agent Reinforcement Learning[C]. *ICML*, 2018: 4295-4304.

[6] Sunehag P, Lever G, Gruslys A, et al. Value-Decomposition Networks For Cooperative Multi-Agent Learning Based On Team Reward[C]. *AAMAS*, 2018: 2085-2087.

[7] Lowe R, Wu Y, Tamar A, et al. Multi-Agent Actor-Critic for Mixed Cooperative-Competitive Environments[C]. *NeurIPS*, 2017: 6379-6390.

[8] Tan M. Multi-Agent Reinforcement Learning: Independent vs. Cooperative Agents[C]. *ICML*, 1993: 330-337.

[9] National Institute of Standards and Technology. FIPS 186-5: Digital Signature Standard (DSS)[S]. 2023.

[10] Shapley L S. A Value for n-Person Games[J]. *Contributions to the Theory of Games*, 1953, 2(28): 307-317.

[11] Bowen C, Yang Y, Zhang K. Incentive Mechanism Design for Cooperative Multi-Agent Reinforcement Learning[C]. *NeurIPS*, 2023.

[12] Tian Y, et al. MRL-PoS: Multi-Agent Reinforcement Learning Based Proof of Stake Consensus[J]. *IEEE Transactions on Parallel and Distributed Systems*, 2025.

[13] Androulaki E, Barger A, Bortnikov V, et al. Hyperledger Fabric: A Distributed Operating System for Permissioned Blockchains[C]. *EuroSys*, 2018: 1-15.

[14] National Institute of Standards and Technology. FIPS 204: Module-Lattice-Based Digital Signature Standard (CRYSTALS-Dilithium)[S]. 2024.

[15] Foerster J, Farquhar G, Afouras T, et al. Counterfactual Multi-Agent Policy Gradients[C]. *AAAI*, 2018.

[16] Watkins C J C H, Dayan P. Q-learning[J]. *Machine Learning*, 1992, 8(3): 279-292.

[17] Tsitsiklis J N. Asynchronous Stochastic Approximation and Q-learning[J]. *Machine Learning*, 1994, 16(3): 185-202.

[18] Leitão J, Pereira J, Rodrigues L. HyParView: A Membership Protocol for Reliable Gossip-Based Broadcast[C]. *DSN*, 2007: 419-429.

[19] Vukolić M. The Quest for Scalable Blockchain Fabric: Proof-of-Work vs. BFT Replication[C]. *iNetSec*, 2015: 112-125.

[20] Dwork C, Naor M. Pricing via Processing or Combatting Junk Mail[C]. *CRYPTO*, 1992: 139-147.

---

## ❓ FAQ

<details>
<summary><b>Q: How do I reproduce the +42.2% result in 1 minute?</b></summary>

```bash
pip install cryptography numpy torch scipy tqdm matplotlib flask
python main.py --demo  # Quick 30-episode demo
python scripts/one-click/run_full_experiment.py  # Full experiment
```
Results auto-saved to `results/one_click/comparison_report.json`.
</details>

<details>
<summary><b>Q: What is the difference between total_reward and env_reward?</b></summary>

- **total_reward** = env_reward + λ·bc_reward — the composite metric including blockchain incentives. This is the competition primary metric (λ=0.5).
- **env_reward** = pure environment reward (no BC incentive) — used for fair comparison against pure_marl baseline. BC-marl env_reward ≈ pure_marl env_reward, proving BC doesn't distort learning.
</details>

<details>
<summary><b>Q: Why λ=0.5 and not 0.1?</b></summary>

Both are valid but serve different purposes:
- λ=0.5: Competition recommended. total_reward improvement +42.2%. Far above theoretical λ_min=0.0667 (650% safety margin).
- λ=0.1: Fair comparison baseline. env_reward BC gain +13.4%.

λ sensitivity sweep (`scripts/ablation/lambda_sweep.py`) shows λ ∈ [0.3, 0.8] is robust.
</details>

<details>
<summary><b>Q: What if I don't have PyTorch installed?</b></summary>

The code has a NumPy fallback for Q-learning. Install minimum: `pip install cryptography numpy`. The NumPy fallback supports basic training without GPU. For full IQL with neural networks, install `torch>=2.0.0`.
</details>

<details>
<summary><b>Q: How do I add a new consensus algorithm?</b></summary>

1. Implement in `blockchain/consensus/` following the CWPBFTConsensus interface
2. Add to `config.json` under `blockchain.consensus`
3. Wire into `bc_integration.py` via the consensus parameter
</details>

<details>
<summary><b>Q: How does the Nash equilibrium proof generalize to n>2 agents?</b></summary>

The 2-agent game extends to n-agent symmetric games via linear interpolation. Since payoff varies monotonically with the proportion of cooperating opponents, the boundary cases (all cooperate / all defect) verified in the 2-agent analysis guarantee all intermediate cases. See `marl/analysis/nash_verifier.py:208-251` for the n-agent payoff computation.
</details>

<details>
<summary><b>Q: Is the P2P network tested on real multi-host setups?</b></summary>

Current benchmarks are local single-machine simulations (localhost loopback). Multi-host deployment is planned in Phase 2 of the roadmap. All performance data is annotated with test environment. See `scripts/benchmark/run_scale.py` for the large-scale benchmark.
</details>

<details>
<summary><b>Q: What's the migration path for post-quantum security?</b></summary>

`blockchain/crypto/dilithium_adapter.py` provides an adapter-pattern interface. Install `pqcrypto` → set `DILITHIUM_AVAILABLE = True` → zero API changes needed. Hybrid ECDSA+Dilithium dual-signature is supported during the transition period. Target: NIST FIPS 204 (CRYSTALS-Dilithium2).
</details>

---

## 📄 License

MIT License. Academic research project — CCF 5th Blockchain Competition Entry.

**All documentation and code are anonymized for blind review compliance.**
