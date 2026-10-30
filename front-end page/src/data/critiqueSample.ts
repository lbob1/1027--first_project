/**
 * critique 演示用的模拟报告数据（非真实评审结果）。
 * 机制对齐上游 reference/critique.md：Nielsen 10 启发式 0~4 打分（满分 /40）、
 * 双独立评审、P0~P3 优先问题、persona 红旗、最近 5 次快照趋势、收尾推荐命令序列（最后一步总是 polish）。
 */

export interface HeuristicScore {
  name: string
  score: number // 0~4
  note: string
}

/** 合计 32/40（Good 档） */
export const HEURISTICS: HeuristicScore[] = [
  { name: '系统状态可见性', score: 3, note: '加载中缺少进度反馈' },
  { name: '贴近真实世界', score: 4, note: '用语符合用户心智' },
  { name: '用户控制与自由', score: 3, note: '弹窗缺少明显的退出路径' },
  { name: '一致性与标准', score: 3, note: '两处按钮主次颠倒' },
  { name: '防错', score: 3, note: '删除无二次确认' },
  { name: '识别而非回忆', score: 3, note: '图标含义需猜测' },
  { name: '灵活与效率', score: 3, note: '高频操作缺快捷方式' },
  { name: '美学与极简', score: 4, note: '版面克制、无冗余装饰' },
  { name: '错误恢复', score: 3, note: '错误提示给了原因' },
  { name: '帮助与文档', score: 3, note: '空状态有下一步引导' },
]

/** 最近 5 次评审健康分快照（满分 40） */
export const TREND = [24, 28, 32, 29, 32]

export interface Issue {
  level: 'P0' | 'P1' | 'P2' | 'P3'
  title: string
  detail: string
  command: string
}

export const ISSUES: Issue[] = [
  { level: 'P0', title: '阻断：移动端下单按钮被遮挡', detail: '390px 宽度下底部悬浮条压住主 CTA，关键操作不可达。', command: '/impeccable layout 首页' },
  { level: 'P1', title: '严重：表单错误仅靠颜色区分', detail: '红色描边是唯一错误信号，色觉障碍用户不可感知。', command: '/impeccable harden 表单' },
  { level: 'P2', title: '一般：图标按钮缺少可读名称', detail: '三个纯图标按钮无可访问名称与 tooltip，含义靠猜。', command: '/impeccable clarify 工具栏' },
  { level: 'P3', title: '打磨：圆角/阴影/间距尺度不统一', detail: '同一卡片内混用 4px 与 12px 圆角，观感松散。', command: '/impeccable polish 全站' },
]

/** 评审收尾给出的推荐命令序列（最终一步总是 polish） */
export const NEXT_COMMANDS = ['/impeccable layout 首页', '/impeccable harden 表单', '/impeccable clarify 工具栏', '/impeccable polish 全站']

export interface PersonaFlag {
  name: string
  trait: string
  flag: string
}

export const PERSONAS: PersonaFlag[] = [
  { name: 'Alex', trait: '急性子高手', flag: '首屏 3 秒内找不到下一步入口' },
  { name: 'Jordan', trait: '新手', flag: '术语没有解释，卡在第一步' },
  { name: 'Sam', trait: '无障碍依赖者', flag: '错误状态仅用颜色表达，读屏不可感知' },
  { name: 'Riley', trait: '边界测试者', flag: '超长标题溢出容器未截断' },
  { name: 'Casey', trait: '分心移动端', flag: '底部按钮被悬浮元素遮挡' },
]

/** 双独立评审的说明（防锚定） */
export const REVIEW_PANELS = [
  {
    tag: '评审 A · 设计评审',
    desc: '像设计总监一样独立看页面：Nielsen 10 启发式逐条 0~4 打分、认知负荷清单、情绪旅程、2~3 个 persona 走查。',
  },
  {
    tag: '评审 B · 检测器 + 浏览器证据',
    desc: '运行 62 条确定性规则，并在浏览器 overlay 上可视化标注 AI 套路特征与质量问题。',
  },
]
