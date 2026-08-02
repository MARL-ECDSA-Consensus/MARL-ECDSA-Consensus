"""
v3 优化重训脚本
参数调整：lambda=0.05（降方差），penalty从-20降至-8/-10（温和惩罚）
训练 2000 回合 × 3 模式，生成新的训练数据

运行: python retrain_v3.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
import time
from train import TrainingConfig, MARLBlockchainTrainer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('retrain_v3')

MODES = ['pure_marl', 'bc_marl', 'selfish']
N_EPISODES = 2000
LAMBDA = 0.05  # 从0.1降至0.05，降低区块链奖励方差
SELFISH_RATIO = 0.3

for mode in MODES:
    logger.info(f"\n{'='*60}")
    logger.info(f"v3 训练: mode={mode}, episodes={N_EPISODES}, lambda={LAMBDA}")
    logger.info(f"{'='*60}")

    config = TrainingConfig(
        n_agents=3,
        n_episodes=N_EPISODES,
        mode=mode,
        lambda_weight=LAMBDA,
        selfish_ratio=SELFISH_RATIO if mode == 'selfish' else 0.0,
        seed=42,
    )

    trainer = MARLBlockchainTrainer(config)
    t0 = time.time()
    stats = trainer.train()

    # 保存（命名含v3标记）
    outfile = f"training_results_{mode}_v3.json"
    trainer.export_results(outfile)
    logger.info(f"[Retrain] {mode} 完成，耗时 {time.time()-t0:.0f}s → {outfile}")
    trainer.cleanup()

logger.info("\n========== 全部完成 ==========")
