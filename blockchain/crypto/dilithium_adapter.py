"""
Post-Quantum Dilithium Signature Adapter — ARCHITECTURE RESERVATION ONLY, NOT IMPLEMENTED
=========================================================================================
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!  WARNING — DO NOT MISREPRESENT THIS MODULE IN ANY PAPER / REPORT / DEFENSE       !!
!!                                                                                  !!
!!  STATUS: **NOT IMPLEMENTED**. This file contains NO post-quantum cryptography.   !!
!!  `DILITHIUM_AVAILABLE = False` is hard-coded; the real `import` is commented out. !!
!!  Every sign() / verify() call silently falls back to classical ECDSA.             !!
!!  get_security_level() returns "0-bit quantum (Shor-vulnerable)".                  !!
!!                                                                                  !!
!!  => The system provides **ZERO** post-quantum / quantum resistance today.         !!
!!  => Any performance figure for Dilithium in this file is a hard-coded ESTIMATE,   !!
!!     NOT a measurement on this machine, and must NOT be cited as experimental data.!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Lightweight compatibility interface *stub* for CRYSTALS-Dilithium (NIST FIPS 204).

What this module actually provides today (all classical ECDSA):
  1. An interface-compatible wrapper AROUND ECDSAUtils (Dilithium branch never taken)
  2. A hybrid dual-signature *skeleton* whose Dilithium half never executes
  3. Instrumentation hooks (benchmark scaffolding only)
  4. Same API surface as ECDSAUtils so that a future swap is a one-line change

Architecture (ASPIRATIONAL — the right-hand column does not exist yet):
  ECDSAUtils (current, ACTIVE)     DilithiumAdapter (RESERVED, INACTIVE)
  ───────────────────────────      ─────────────────────────────────────
  sign(private_key, msg)      →    sign(private_key, msg)      [falls back to ECDSA]
  verify(public_key, msg, sig)→    verify(public_key, msg, sig) [falls back to ECDSA]
  sign_action(agent_id, ...)  →    sign_action(agent_id, ...)  [falls back to ECDSA]

Note: This is an INTERFACE COMPATIBILITY LAYER ONLY — a migration *reservation*.
It does NOT implement, link, or call any post-quantum algorithm.
Full Dilithium support would require installing `pqcrypto` (or `dilithium-py`) and
wiring the DILITHIUM_AVAILABLE branch to the real library, plus real sign/verify
tests and **on-machine** benchmarks.

Correct wording for papers/reports/defense:
    "后量子签名（CRYSTALS-Dilithium / NIST FIPS 204）为架构预留，本项目未实现；
     当前所有签名均为经典 ECDSA，不具备抗量子能力。"
    ("Post-quantum signing is an architectural reservation and is NOT implemented;
      all signatures in this system are classical ECDSA and are not quantum-resistant.")

CCF 5th Blockchain Competition | V4.1 | Phase 2: Post-Quantum Migration Reservation (unimplemented)
"""
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Toggle for hybrid mode (currently uses ECDSA-only; future: ECDSA + Dilithium)
DILITHIUM_AVAILABLE = False
try:
    # Placeholder for future pqcrypto import
    # from pqcrypto.sign import dilithium
    DILITHIUM_AVAILABLE = False  # Set to True when pqcrypto is installed
except ImportError:
    pass


class SignatureAdapter(ABC):
    """Abstract signature adapter — defines the common interface."""

    @abstractmethod
    def sign(self, private_key: Any, message: bytes) -> bytes:
        """Sign a message with the private key."""
        ...

    @abstractmethod
    def verify(self, public_key: Any, message: bytes, signature: bytes) -> bool:
        """Verify a signature."""
        ...

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """Return the algorithm name for reporting."""
        ...

    @abstractmethod
    def get_security_level(self) -> str:
        """Return the security level description."""
        ...


class ECDSAAdapter(SignatureAdapter):
    """Current ECDSA secp256r1 adapter (FIPS 186-5)."""

    def __init__(self):
        from blockchain.crypto.ecdsa_utils import ECDSAUtils
        self._utils = ECDSAUtils

    def sign(self, private_key, message: bytes) -> bytes:
        return self._utils.sign(private_key, message)

    def verify(self, public_key, message: bytes, signature: bytes) -> bool:
        return self._utils.verify(public_key, message, signature)

    def get_algorithm_name(self) -> str:
        return "ECDSA-secp256r1"

    def get_security_level(self) -> str:
        return "128-bit classical | 0-bit quantum (Shor-vulnerable)"


class DilithiumAdapter(SignatureAdapter):
    """
    CRYSTALS-Dilithium adapter (NIST FIPS 204).

    Currently uses ECDSA as fallback until pqcrypto is installed — and because
    `DILITHIUM_AVAILABLE` is hard-coded False, the fallback is ALWAYS taken.

    NOT IMPLEMENTED: no Dilithium sign/verify code path exists. The size constants
    below are FIPS 204 SPEC VALUES for reference only — this system never produces
    a Dilithium signature, so these are NOT measurements and must not be reported
    as experimental data.
    """

    DILITHIUM_SIGNATURE_SIZE = 2420   # FIPS 204 SPEC value only — NOT produced by this system
    DILITHIUM_PUBLIC_KEY_SIZE = 1312  # FIPS 204 SPEC value only — NOT produced by this system
    DILITHIUM_PRIVATE_KEY_SIZE = 2528 # FIPS 204 SPEC value only — NOT produced by this system

    def __init__(self, use_fallback: bool = True):
        """
        :param use_fallback: If True, use ECDSA as fallback when Dilithium unavailable
        """
        self._use_fallback = use_fallback
        if DILITHIUM_AVAILABLE:
            # In production: self._dilithium = dilithium.Dilithium2()
            self._dilithium = None
            logger.info("[Dilithium] CRYSTALS-Dilithium module loaded (FIPS 204)")
        else:
            self._dilithium = None
            if use_fallback:
                from blockchain.crypto.ecdsa_utils import ECDSAUtils
                self._fallback = ECDSAUtils
                logger.info("[Dilithium] Using ECDSA fallback (pqcrypto not installed)")
            else:
                raise ImportError(
                    "Dilithium not available and fallback disabled. "
                    "Install: pip install pqcrypto"
                )

    def sign(self, private_key, message: bytes) -> bytes:
        if self._dilithium is not None:
            # Real Dilithium: return self._dilithium.sign(message, private_key)
            pass
        # Fallback
        return self._fallback.sign(private_key, message)

    def verify(self, public_key, message: bytes, signature: bytes) -> bool:
        if self._dilithium is not None:
            # Real Dilithium: return self._dilithium.verify(message, signature, public_key)
            pass
        return self._fallback.verify(public_key, message, signature)

    def get_algorithm_name(self) -> str:
        return "CRYSTALS-Dilithium2" if DILITHIUM_AVAILABLE else "ECDSA(Dilithium-fallback)"

    def get_security_level(self) -> str:
        if DILITHIUM_AVAILABLE:
            return "128-bit classical | 128-bit quantum (NIST Level 2)"
        return "0-bit quantum (Shor-vulnerable) — currently ECDSA fallback"

    def get_migration_readiness(self) -> Dict:
        """Report migration readiness status."""
        return {
            "algorithm": self.get_algorithm_name(),
            "standard": "NIST FIPS 204 (2024)",
            "available": DILITHIUM_AVAILABLE,
            "fallback_active": self._use_fallback and not DILITHIUM_AVAILABLE,
            "signature_size_bytes": self.DILITHIUM_SIGNATURE_SIZE,
            "public_key_size_bytes": self.DILITHIUM_PUBLIC_KEY_SIZE,
            "quantum_resistant": DILITHIUM_AVAILABLE,
            "migration_effort": "LOW — Adapter pattern, no API changes needed",
            "affected_modules": ["SigningService", "ECDSAUtils → DilithiumAdapter"],
        }


class HybridSignatureAdapter:
    """
    Hybrid ECDSA + Dilithium dual-signature adapter for transition period.

    During the post-quantum migration, both algorithms run in parallel:
      - ECDSA for backward compatibility with existing nodes
      - Dilithium for forward compatibility (quantum-resistant)

    A message is valid if BOTH signatures verify (defense-in-depth).
    """

    def __init__(self):
        self._ecdsa = ECDSAAdapter()
        self._dilithium = DilithiumAdapter(use_fallback=True)

    def hybrid_sign(
        self,
        ecdsa_private_key,
        dilithium_private_key,
        message: bytes,
    ) -> Dict[str, bytes]:
        """Generate dual ECDSA + Dilithium signatures."""
        ecdsa_sig = self._ecdsa.sign(ecdsa_private_key, message)
        dilithium_sig = self._dilithium.sign(dilithium_private_key, message)

        return {
            "ecdsa_signature": ecdsa_sig,
            "dilithium_signature": dilithium_sig,
        }

    def hybrid_verify(
        self,
        ecdsa_public_key,
        dilithium_public_key,
        message: bytes,
        ecdsa_signature: bytes,
        dilithium_signature: bytes,
    ) -> bool:
        """Verify both signatures (AND logic — both must pass)."""
        ecdsa_ok = self._ecdsa.verify(ecdsa_public_key, message, ecdsa_signature)
        dilithium_ok = self._dilithium.verify(dilithium_public_key, message, dilithium_signature)

        if not ecdsa_ok:
            logger.warning("[HybridSig] ECDSA verification failed")
        if not dilithium_ok:
            logger.warning("[HybridSig] Dilithium verification failed")

        return ecdsa_ok and dilithium_ok

    def get_transition_status(self) -> Dict:
        """Report hybrid transition status."""
        return {
            "phase": "Transition (dual-signature)",
            "ecdsa": self._ecdsa.get_security_level(),
            "dilithium": self._dilithium.get_security_level(),
            # NOT IMPLEMENTED / NOT MEASURED. Dilithium is an architectural
            # reservation; no post-quantum code path exists in this repository.
            # Previously this hard-coded "0.15"/"0.05" as a "NIST benchmark
            # estimate" — a literature figure that was NOT measured on this
            # machine and must never be cited as experimental data.
            "dual_signature_overhead_ms_estimate": None,  # NOT MEASURED — Dilithium not implemented
            "dilithium_status": "NOT IMPLEMENTED (architecture reservation only)",
            "total_signature_size_bytes": None,  # NOT MEASURED — hybrid mode never produces a Dilithium signature
            "verification_policy": "AND (both must pass)",
        }


# =============================================================================
# Performance Comparison
# =============================================================================

def benchmark_signature_adapters(num_iterations: int = 1000):
    """Benchmark all signature adapters and generate comparison data."""
    from blockchain.crypto.ecdsa_utils import ECDSAUtils

    results = {
        "iterations": num_iterations,
        "adapters": [],
    }

    # ECDSA
    priv, pub = ECDSAUtils.generate_key_pair()
    msg = b"post-quantum benchmark message"

    start = time.perf_counter()
    for _ in range(num_iterations):
        ECDSAUtils.sign(priv, msg)
    ecdsa_sign_ms = (time.perf_counter() - start) / num_iterations * 1000

    sig = ECDSAUtils.sign(priv, msg)
    start = time.perf_counter()
    for _ in range(num_iterations):
        ECDSAUtils.verify(pub, msg, sig)
    ecdsa_verify_ms = (time.perf_counter() - start) / num_iterations * 1000

    results["adapters"].append({
        "algorithm": "ECDSA-secp256r1",
        "sign_ms": round(ecdsa_sign_ms, 4),
        "verify_ms": round(ecdsa_verify_ms, 4),
        "sig_size_bytes": 70,
        "quantum_resistant": False,
        "standard": "FIPS 186-5",
    })

    # Dilithium — NOT IMPLEMENTED, therefore NOT MEASURED.
    # The 0.15 / 0.05 ms figures previously hard-coded here were "NIST benchmark
    # estimates" copied from literature, NOT measurements on this machine, and
    # MUST NOT be reported as experimental results. They are removed here so that
    # no downstream report can accidentally cite them as data.
    results["adapters"].append({
        "algorithm": "CRYSTALS-Dilithium2",
        "implemented": False,
        "status": "NOT IMPLEMENTED — architecture reservation only",
        "sign_ms": None,  # NOT MEASURED (was hard-coded 0.15 literature estimate — removed)
        "verify_ms": None,  # NOT MEASURED (was hard-coded 0.05 literature estimate — removed)
        "sig_size_bytes": None,  # NOT MEASURED (spec value 2420 not produced by this system)
        "quantum_resistant": None,  # N/A — no Dilithium code path exists; system is Shor-vulnerable
        "standard": "FIPS 204 (2024)",
    })

    # Hybrid
    results["adapters"].append({
        "algorithm": "Hybrid (ECDSA + Dilithium)",
        "implemented": False,
        "status": "NOT IMPLEMENTED — Dilithium half never executes; verify() degrades to ECDSA-only",
        "sign_ms": None,  # NOT MEASURED
        "verify_ms": None,  # NOT MEASURED
        "sig_size_bytes": None,  # NOT MEASURED
        "quantum_resistant": None,  # N/A
        "standard": "FIPS 186-5 + FIPS 204",
    })

    return results


# =============================================================================
# Demo
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("=" * 60)
    print("Post-Quantum Dilithium Adapter — Interface Demo (NOT IMPLEMENTED)")
    print("=" * 60)
    print("!! This module performs NO post-quantum cryptography. All operations")
    print("!! below fall back to classical ECDSA. Read as: architecture reservation.")

    # 1. Current ECDSA
    ecdsa = ECDSAAdapter()
    print(f"\n1. Current: {ecdsa.get_algorithm_name()}")
    print(f"   Security: {ecdsa.get_security_level()}")

    # 2. Dilithium (fallback mode)
    dilithium = DilithiumAdapter(use_fallback=True)
    print(f"\n2. Future: {dilithium.get_algorithm_name()}")
    print(f"   Security: {dilithium.get_security_level()}")
    print(f"   Migration readiness: {dilithium.get_migration_readiness()}")

    # 3. Hybrid mode
    hybrid = HybridSignatureAdapter()
    print(f"\n3. Transition: Hybrid dual-signature")
    print(f"   Status: {hybrid.get_transition_status()}")

    # 4. Performance comparison
    print(f"\n4. Performance Comparison:")
    bench = benchmark_signature_adapters(1000)
    for adapter in bench["adapters"]:
        pq_label = "🛡️ PQ" if adapter["quantum_resistant"] else "⚠️  Classic"
        print(f"   {adapter['algorithm']}: "
              f"sign={adapter['sign_ms']}ms, verify={adapter['verify_ms']}ms, "
              f"sig={adapter['sig_size_bytes']}B, {pq_label}")

    print(f"\n⚠️  STATUS: Dilithium / post-quantum signing is NOT IMPLEMENTED.")
    print(f"   `DILITHIUM_AVAILABLE` is hard-coded False; all sign/verify calls fall")
    print(f"   back to classical ECDSA. The system has NO quantum resistance today.")
    print(f"   This module is an architectural RESERVATION for a future migration.")
    print(f"   To make it real: install pqcrypto → set DILITHIUM_AVAILABLE = True,")
    print(f"   then add real Dilithium sign/verify tests and ON-MACHINE benchmarks.")
