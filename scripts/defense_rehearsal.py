"""
答辩演练辅助脚本
================
1. 15分钟路演计时器（按逐页讲稿分配时间）
2. 50问抽问模拟（随机抽取问题，显示标准答案）

用法:
  python scripts/defense_rehearsal.py timer     # 计时器模式
  python scripts/defense_rehearsal.py quiz       # 抽问模式
  python scripts/defense_rehearsal.py quiz --n 5 # 抽5题
"""
import sys
import os
import time
import random
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# 15分钟路演时间分配（按逐页讲稿）
ROADSHOW_TIMELINE = [
    (0, 60, "封面 + 自我介绍", "项目名 + 团队 + 一句话定位"),
    (60, 150, "问题定义", "多智能体为什么需要区块链？3个核心挑战"),
    (150, 270, "方案总览", "四层架构 + 双向赋能闭环图"),
    (270, 390, "创新一：ECDSA身份锚定", "无CA分布式 + RFC6979 + STRIDE"),
    (390, 510, "创新二：CW-PBFT共识", "贡献加权 + Shapley推导 + vs标准PBFT"),
    (510, 630, "创新三：Nash均衡", "激励相容证明 + 安全裕度650%"),
    (630, 750, "实验一：核心对比", "🏆 +53.1% env_reward, d=2.03 巨大效应"),
    (750, 840, "实验二：消融+攻防", "激励模块贡献最大 + 100%防护"),
    (840, 900, "实验三：扩展性+自适应λ", "3/5/8智能体 + 自适应λ +6.3%"),
    (900, 960, "Dashboard演示", "9标签页 + P键演示模式"),
    (960, 1020, "产业落地", "仓储/供应链/医疗 3场景"),
    (1020, 1080, "总结展望", "核心成果4条 + 未来3方向"),
    (1080, 1140, "Q&A缓冲", "评委提问预留"),
]


def cmd_timer():
    """15分钟路演计时器"""
    print("=" * 60)
    print("15分钟路演计时器（按逐页讲稿分配时间）")
    print("按 Enter 开始，每页结束按 Enter 跳转下一页")
    print("=" * 60)
    input("准备就绪后按 Enter 开始...")
    
    for i, (start, end, title, desc) in enumerate(ROADSHOW_TIMELINE):
        duration = end - start
        print(f"\n{'='*60}")
        print(f"📍 [{i+1}/{len(ROADSHOW_TIMELINE)}] {title}")
        print(f"   时长: {duration}s ({start//60}:{start%60:02d} - {end//60}:{end%60:02d})")
        print(f"   要点: {desc}")
        print(f"{'='*60}")
        
        for remaining in range(duration, 0, -1):
            mm, ss = divmod(remaining, 60)
            sys.stdout.write(f"\r⏱  剩余 {mm}:{ss:02d}  ")
            sys.stdout.flush()
            time.sleep(1)
        
        print(f"\n✅ {title} 完成!")
        if i < len(ROADSHOW_TIMELINE) - 1:
            input("按 Enter 进入下一页...")
    
    print(f"\n{'='*60}")
    print("🎉 路演完成！总用时 19 分钟（含 Q&A 缓冲）")
    print(f"{'='*60}")


# 50问核心题库（精简版）
QUIZ_BANK = [
    ("BC提升的头号指标是多少？用什么口径？", "3000回合收敛验证，env_reward last50公平口径，BC提升+53.1%，Cohen's d=2.03（巨大效应），p=0.068（3种子边际显著）。这是BC信任增强机制有效性的最强证据。"),
    ("为什么500回合和3000回合的BC提升差距这么大？", "500回合agent未充分收敛，BC激励的长期塑形效果未显现（+13.4%）；3000回合收敛后跃升至+53.1%。这说明BC激励是长期协作塑形信号，需充分训练才能体现。这是科学发现，不是数据矛盾。"),
    ("Cohen's d=2.03意味着什么？", "Cohen's d是效应量指标：0.2小、0.5中、0.8大、1.3巨大。d=2.03远超巨大阈值，说明BC与Pure的差距在实际意义上非常显著，仅因3种子样本量限制未达p<0.05。"),
    ("CARS共识感知塑形为什么是负结果？", "CARS的Potential函数用'到最近路标距离'作为空间势能，而环境奖励基于'到分配路标距离'。当智能体被分配到非最近路标时，两者方向相反，产生系统性冲突。η=0.10时显著恶化24.2%（p=0.03）。这是诚实负结果，展示了奖励设计的深层挑战。"),
    ("CW-PBFT相比标准PBFT的优势是什么？", "贡献度加权：高贡献节点权重更大，少数节点即可达成共识。33%拜占庭时+10-23%优势，40%超极限时+67-71%。规模越大优势越明显。"),
    ("ECDSA签名用什么曲线？为什么不用RSA？", "NIST secp256r1 (P-256)。椭圆曲线密钥更短（256bit vs RSA 3072bit等效），签名更快，适合高频交易场景。已实现RFC6979确定性k值生成防重用。"),
    ("自适应λ相比静态λ提升多少？", "+6.3%（env_reward公平口径，p=0.10边际显著）。λ_t = clamp(λ_base + η·(κ_c·c_t + κ_k·k_t - κ_s·s_t), 0.05, 0.15)。系统对λ有±12.5%鲁棒性（R²=0.685）。"),
    ("消融实验哪个模块最重要？", "IncentiveContract（激励合约）贡献最大，消融后env_reward下降2.00。SecurityGuard和CW-PBFT加权各有正向贡献（-1.33/-0.83）。三模块均有贡献，验证架构合理性。"),
    ("攻击防御怎么实现100%拦截？", "SecurityGuard三阶防护：观测校验→消息ECDSA验签→重放检测。三种攻击（观测伪造/消息篡改/重放）全部被区块链层拦截。"),
    ("测试覆盖了多少用例？", "6026个测试用例全部通过，覆盖共识/密码学/MARL/网络/Dashboard全模块。使用pytest框架，CI流水线持续验证。"),
]


def cmd_quiz(n=5):
    """抽问模拟"""
    print("=" * 60)
    print(f"答辩抽问模拟（{n}题）")
    print("每题先显示问题，思考后按 Enter 看答案")
    print("=" * 60)
    
    questions = random.sample(QUIZ_BANK, min(n, len(QUIZ_BANK)))
    score = 0
    
    for i, (q, a) in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"📝 问题 {i}/{len(questions)}:")
        print(f"   {q}")
        print(f"{'='*60}")
        input("\n思考完毕后按 Enter 看标准答案...")
        
        print(f"\n💡 标准答案:")
        print(f"   {a}")
        
        # 自评
        while True:
            rating = input("\n自评（1=完全不会 2=不完整 3=基本ok 4=流畅）: ").strip()
            if rating in ['1','2','3','4']:
                score += int(rating)
                break
            print("请输入 1-4")
    
    print(f"\n{'='*60}")
    print(f"📊 演练结束！总分 {score}/{len(questions)*4}")
    avg = score / len(questions)
    if avg >= 3.5:
        print("🎉 优秀！答辩准备充分")
    elif avg >= 2.5:
        print("👍 良好，继续练习薄弱环节")
    else:
        print("⚠️ 需要加强练习，重点复习标准答案")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="答辩演练辅助")
    parser.add_argument("mode", choices=["timer", "quiz"], help="timer=路演计时器, quiz=抽问模拟")
    parser.add_argument("--n", type=int, default=5, help="抽问题数（默认5）")
    args = parser.parse_args()
    
    if args.mode == "timer":
        cmd_timer()
    elif args.mode == "quiz":
        cmd_quiz(args.n)


if __name__ == '__main__':
    main()
