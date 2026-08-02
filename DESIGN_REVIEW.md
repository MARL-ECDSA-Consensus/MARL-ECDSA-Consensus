# MARL-ECDSA 共识链 Dashboard — 视觉设计审查报告

> 审查对象：`templates/dashboard.html`(2212 行) · `static/dashboard.css`(376 行) · `training_results_*.json` · `static/chart.umd.min.js`
> 审查方法：静态代码核对 + 配色/字体/图表令牌比对 + 数据文件实测
> 说明：本次审查时 `http://127.0.0.1:8093/` 未运行（curl 返回 000），无法截图；以下结论均基于源码与数据文件，可 100% 复现。
> 设计语言定位：**深色科幻风（Deep-space sci-fi dashboard）**——深空蓝底 + 青/靛/绿 三主色 + 红/琥珀 语义色。

---

## 一、设计系统现状（优点）

- 已建立 CSS 变量设计令牌（`--bg-deep / --accent / --accent2 / --accent3 / --danger / --warn / --text*`），基调统一。
- 卡片统一 `16px` 圆角、统一边框与 hover 发光，层次清晰；顶栏 + 双 sticky 导航（标签栏）结构专业。
- 交互完整：加载遮罩、演示模式（P 键轮播）、导出报告、数字动画、快捷键。
- 图表基座配置 `baseOpts` 统一了坐标轴/图例/tooltip 风格，是良好的统一性基础。
- 架构 SVG、对比表格等信息呈现有"国赛演示"的专业感。

---

## 二、问题清单（按严重度）

### 🔴 Critical（视觉严重问题）

**C1 · 配色令牌被"并行霓虹色"打破（图表 / 共识 / 浏览器 / P2P 标签页）**
- 现象：CSS 令牌为 `#38bdf8 / #34d399 / #fbbf24 / #f87171 / #818cf8`，但以下位置使用了更亮、更"荧光"的离谱色：
  - 共识投票页权重柱状图 / 区块浏览器（趋势线、出块者饼图）：`#00d4ff`、`#00ff88`、`#ffaa00`、`#ff6b6b`、`#a78bfa`
  - P2P 拓扑 Canvas（手绘）：`#0f3`、`#08f`、`#06a`、`#889` 等缩写十六进制
- 影响：同一仪表盘出现"两套配色"，主色辨识度被稀释，专业感下降，像"未完成统一"的模板。
- 建议：
  1. 建立统一取色工具，所有图表颜色回退到令牌：
     ```js
     const C = { cyan:'#38bdf8', indigo:'#818cf8', green:'#34d399', red:'#f87171', amber:'#fbbf24', slate:'#94a3b8' };
     function chartColor(i){ return [C.cyan, C.red, C.green, C.indigo, C.amber][i%5]; }
     ```
  2. P2P 拓扑改用 `C.cyan / C.green` + 透明度，端口标签提到 `#94a3b8`。

**C2 · 空状态图表（0 值 / 无数据）没有兜底**
- 现象：**实测** `training_results_pure.json` 与 `training_results_bc.json` 均不含 `bc_scores_history`（长度 0）。因此：
  - 「训练监控」页的 **区块链积分变化**（`chart-bc`，行 1404–1422）在 `bcDatasets=[]` 时只渲染坐标轴网格、无线条；
  - 「区块链」页的 **智能体链上积分趋势**（`chart-bc-history`，行 1694–1707）同样为空；
  - 切到 `pure` / `selfish` 模式查看监控时该图亦为空。
- 影响：用户看到"空白图"，误以为 Bug / 数据丢失，是答辩现场最致命的视觉问题。
- 建议：数据集为空时绘制统一占位（**详细规范与文案定稿见第五章**），或渲染前拦截：
  ```js
  const noDataPlugin = {
    id:'noData',
    afterDraw(chart){
      const ds = chart.data.datasets||[];
      if(!ds.length || ds.every(d=>(d.data||[]).length===0)){
        const {ctx,chartArea:{left,top,right,bottom}}=chart;
        ctx.save();ctx.fillStyle='#64748b';ctx.textAlign='center';ctx.font='14px sans-serif';
        ctx.fillText('暂无数据',(left+right)/2,(top+bottom)/2);ctx.restore();
      }
    }
  };
  // createOrUpdateChart 时 options.plugins 注册 noDataPlugin；空数据也显式传 []
  ```

### 🟠 Major（明显偏差）

**M1 · 字体 `Inter` 声明但未加载**
- 现象：`body` 首位是 `'Inter'`，但无 `@font-face`、无 Google Fonts 链接；图表默认字体也未指定 Inter。中文回退到 `'Microsoft YaHei'`。
- 影响：跨平台字体不一致（Windows=雅黑 / macOS=苹方·SF），"Inter 几何感"意图落空，数字观感漂移。
- 建议：二选一——① 自托管 `Inter.woff2` 或引 Google Fonts；② 改为系统无衬线栈 `'Segoe UI','PingFang SC','Microsoft YaHei',system-ui`，并在 `Chart.defaults.font.family` 同步。

**M2 · 部分图表信息密度过高（拥挤）**
- 现象：「奖励曲线对比（50 回合平滑）」单图叠加 差异区间(2 层) + Pure 虚线 + BC 粗线 + BC 均值虚线 = 5 个 dataset（行 1514–1559）；「训练监控」4 张图挤在 2 列 / 300px 高度内，且其中 BC 积分图又为空，更显空洞。
- 影响：重点被稀释，"提升幅度"反而看不清。
- 建议：差异区间合并为单条半透明带；均值参考线用更淡 dotted；监控页空图按 C2 改写为"该模式无链上积分"。

**M3 · P2P 拓扑 Canvas 依赖手工尺寸修复**
- 现象：`p2p-canvas` 为原生 Canvas 手绘，隐藏标签页下 `width=0`，需 `fix canvas dimensions` hack（行 2072–2139）反复校正；端口标签 `#889` 对比度低。
- 建议：改用固定逻辑尺寸 + CSS 缩放；或重写为 Chart.js 图；标签色提至 `#94a3b8`。

### 🟡 Minor（细节优化）

- **m1 间距基数不统一**：图表网格 `gap:14px`、stat 行 `gap:12px`、`margin-bottom` 12/14/20 混用 → 统一为 8 的倍数（12/16/24）。
- **m2 架构 SVG 内 8–9px 微文字难读** → 提到 ≥10px 或移出图外作图注。
- **m3 对比度**：`--text-dim:#64748b` 在深底上约 3.9:1，低于 WCAG AA 4.5（用于标签/表头/刻度）→ 提亮到 `#94a3b8` 或 `#7c8aa0`（本模板已采用 `#94a3b8`）。
- **m4 粒子背景**：80 个 + 连线、`opacity:0.45`，在 Hero 低透明度卡片后略有噪点 → 降到 0.25 或限制连线距离。
- **m5 加载动画**：`blink` + `pulse` 略显"AI 模板感" → 保留其一即可。

---

## 三、改进优先级

| 优先级 | 项 | 工作量 |
|--------|----|--------|
| **P0** | C1 统一图表配色到令牌 · C2 空状态占位 | 小（改 JS 取色 + 加 plugin） |
| **P1** | M1 字体加载 · M2 图表减密度 | 中 |
| **P2** | M3 · m1–m5 间距/对比度/微文字打磨 | 小 |

---

## 四、建议固化的设计令牌（DESIGN.md 源文件）

```css
:root{
  --bg-deep:#040810;
  --bg-card:rgba(12,20,40,0.88);
  --border:rgba(56,189,248,0.12);
  --border-glow:rgba(56,189,248,0.38);
  --accent:#38bdf8;   /* 青 · 主色 / BC-MARL */
  --accent2:#818cf8;  /* 靛 · 区块链层 */
  --accent3:#34d399;  /* 绿 · 成功 / 合作 */
  --danger:#f87171;   /* 红 · 自私 / 错误 */
  --warn:#fbbf24;     /* 琥珀 · 告警 / 参考 */
  --text:#cbd5e1;
  --text-dim:#94a3b8; /* 提亮后满足对比度 */
  --text-bright:#f1f5f9;
  --radius:16px;
}
/* 图表专用取色（严禁再出现 #00d4ff/#00ff88/#ffaa00/#ff6b6b/#a78bfa/#0f3 等离谱色） */
```

> 注：随附的 `ppt_template/index.html` 已严格采用上述令牌，可作为统一视觉的参照样张。

---

## 五、空状态视觉规范（Empty-state Spec · 已与 QA 验收对齐）

> 与 @gstack-qa-lead 的 QA 报告 ④ 节结论重叠并达成一致：前端用 `|| []` 守护后不崩溃，但空白 canvas 国赛演示风险高。
> 数据侧彻底修复（`bc` 模式产出 `bc_scores_history`）由排障/team-lead 决策；本规范只负责"空状态不优雅"的**视觉定稿**，供实现方（Dashboard JS 修复）直接落地。

**适用范围**：所有"数据为空但不崩溃"的图表/面板 —— `chart-bc`、`chart-bc-history`、consensus 页、explorer 页（pure 模式下缺 `consensus_stats` / `blockchain_stats`）。统一占位，避免"看起来像 Bug"。

### 5.1 文案定稿（按场景分级）

| 位置 / 场景 | 分级 | 占位文案（定稿） |
|---|---|---|
| 区块链积分变化 / 智能体链上积分趋势（**pure / selfish** 模式） | 预期·未启用 | `本模式未启用区块链激励 · 无链上积分` |
| 上述两图（**bc 模式但数据缺失**） | 异常·需处理 | `BC 积分数据缺失 · 请重新生成 training_results_bc.json` |
| 共识投票页（pure 模式缺 `consensus_stats`） | 预期·未启用 | `本模式未启用区块链 · 共识数据不可用` |
| 区块浏览器页（pure 模式缺 `blockchain_stats`） | 预期·未启用 | `本模式未启用区块链 · 链上数据不可用` |

> 分级意义：pure/selfish 属"设计如此"，文案语气中性信息；bc 模式数据缺失属"需处理"，文案给出可操作提示（重新生成数据）。

### 5.2 视觉样式（统一）

- **触发**：Chart.js `afterDraw` plugin，当 `datasets` 为空（或全 0 长度）时绘制。
- **版式**：画布内**居中**；上方图标 `⬡`（22px，`--accent` `#38bdf8`），下方主文案。
- **文字**：`color: var(--text-dim) #94a3b8`；`font: 500 14px` 字体栈；`textAlign:center`、`textBaseline:middle`。
- **可选外框**：圆角虚线框 `border:1px dashed rgba(56,189,248,0.18)` 呼应卡片风格（非强制）。
- **非 Chart.js 面板**（consensus / explorer 的纯 HTML 卡片）：用统一 `.empty-state` 块，配色与图标同上，替代原 `innerHTML='等待数据…'` 内联样式，保证一致。

### 5.3 统一占位 plugin（可直接落地）

```js
const emptyStatePlugin = {
  id: 'emptyState',
  afterDraw(chart, _args, opts){
    const ds = chart.data.datasets || [];
    const empty = !ds.length || ds.every(d => !(d.data || []).length);
    if (!empty) return;
    const msg = (opts && opts.message) || '暂无数据';
    const {ctx, chartArea:{left,top,right,bottom}} = chart;
    const cx = (left+right)/2, cy = (top+bottom)/2;
    ctx.save();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#38bdf8'; ctx.font = '22px system-ui';
    ctx.fillText('⬡', cx, cy - 16);
    ctx.fillStyle = '#94a3b8'; ctx.font = '500 14px system-ui';
    ctx.fillText(msg, cx, cy + 12);
    ctx.restore();
  }
};
Chart.register(emptyStatePlugin);
// 调用示例（按场景传入分级文案）：
// createOrUpdateChart('chart-bc', 'line', {labels:bcLabels, datasets:bcDatasets},
//   Object.assign({}, baseOpts, {plugins:{emptyState:{message:'本模式未启用区块链激励 · 无链上积分'}}}));
```

> 落地建议：在 `createOrUpdateChart` 内统一挂 `emptyStatePlugin`，由调用处在 `options.plugins.emptyState.message` 传 5.1 分级文案；consensus / explorer 两页把 `innerHTML='等待数据…'` 改为统一 `.empty-state` 组件，文案沿用 5.1。

