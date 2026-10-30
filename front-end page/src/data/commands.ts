export type CommandCategory = 'steer' | 'review' | 'finish' | 'iterate' | 'setup' | 'deprecated'

export interface Command {
  name: string
  category: CommandCategory
  purpose: string
  scene: string
  example: string
}

export const CATEGORY_LABELS: Record<CommandCategory, string> = {
  steer: 'Steer 操控',
  review: 'Review 评审',
  finish: 'Finish 收尾',
  iterate: 'Iterate live 实时迭代',
  setup: 'Plan & set up 规划配置',
  deprecated: '弃用别名',
}

export const CATEGORY_ORDER: CommandCategory[] = ['steer', 'review', 'finish', 'iterate', 'setup', 'deprecated']

/**
 * 24 命令单一数据源，对齐上游 pbakaus/impeccable（commit 02523ae）
 * skill/SKILL.src.md 命令表与 README「24 commands」。上游更新时只改此文件。
 */
export const COMMANDS: Command[] = [
  // Steer 操控（9）
  { name: 'bolder', category: 'steer', purpose: '放大过于保守或平淡的设计', scene: '页面能用但四平八稳，想要更强的视觉主张', example: '/impeccable bolder 定价卡片' },
  { name: 'quieter', category: 'steer', purpose: '让过于吵闹、过度刺激的设计收敛', scene: '色彩/动效/字重过载，用户感到疲劳', example: '/impeccable quieter 落地页' },
  { name: 'distill', category: 'steer', purpose: '提炼本质，移除页面不需要的东西', scene: '信息堆砌、说不清主次', example: '/impeccable distill 设置页' },
  { name: 'colorize', category: 'steer', purpose: '给单色界面加入有策略的色彩', scene: '整站灰蒙蒙，想用色彩引导注意', example: '/impeccable colorize 仪表盘' },
  { name: 'typeset', category: 'steer', purpose: '修正字体、层级与字号', scene: '标题正文无差别，阅读节奏混乱', example: '/impeccable typeset 博客文章页' },
  { name: 'layout', category: 'steer', purpose: '修正间距、节奏与视觉层级', scene: '元素挤压或松散，扫描困难', example: '/impeccable layout 首页' },
  { name: 'animate', category: 'steer', purpose: '添加有目的的动效与交互反馈', scene: '状态变化生硬，缺少反馈', example: '/impeccable animate 导航栏' },
  { name: 'delight', category: 'steer', purpose: '添加个性与令人记住的细节', scene: '功能完备但毫无记忆点', example: '/impeccable delight 空状态' },
  { name: 'overdrive', category: 'steer', purpose: '冲破常规极限：着色器、弹簧物理、滚动驱动效果', scene: '活动页/概念页需要惊艳首屏', example: '/impeccable overdrive 活动页' },
  // Review 评审（2）
  { name: 'critique', category: 'review', purpose: '带启发式打分的 UX 设计评审（双独立评审，满分 /40）', scene: '改完之后想知道到底好不好，先改什么', example: '/impeccable critique 首页' },
  { name: 'audit', category: 'review', purpose: '技术质量报告：无障碍、性能、响应式，按 P0~P3 分级', scene: '上线前的技术体检', example: '/impeccable audit 结账流程' },
  // Finish 收尾（6）
  { name: 'polish', category: 'finish', purpose: '上线前的最终质量打磨', scene: '功能齐了，差最后一遍细抠', example: '/impeccable polish settings' },
  { name: 'harden', category: 'finish', purpose: '生产就绪：错误态、i18n、边界情况', scene: '真实数据与异常输入下的健壮性', example: '/impeccable harden checkout' },
  { name: 'clarify', category: 'finish', purpose: '改写不清的文案、标签与错误提示', scene: '用户看不懂提示在说什么', example: '/impeccable clarify 注册表单' },
  { name: 'adapt', category: 'finish', purpose: '适配不同设备与屏幕尺寸', scene: '桌面正常、移动端散架', example: '/impeccable adapt 营销页' },
  { name: 'optimize', category: 'finish', purpose: '诊断并修复 UI 加载与渲染性能', scene: '页面能看但慢', example: '/impeccable optimize 图片画廊' },
  { name: 'onboard', category: 'finish', purpose: '设计首跑流程与空状态', scene: '新用户第一次进来不知从哪开始', example: '/impeccable onboard 新用户引导' },
  // Iterate live 实时迭代（2）
  { name: 'live', category: 'iterate', purpose: '浏览器内点选元素、循环切换变体的实时模式', scene: '说不如选：看着真实页面挑方案', example: '/impeccable live' },
  { name: 'generate', category: 'iterate', purpose: '为指定元素批量生成变体供挑选，无需手动点选', scene: '想一次看到同一元素的多套方案', example: '/impeccable generate 3 bolder hero' },
  // Plan & set up 规划与配置（4）
  { name: 'shape', category: 'setup', purpose: '写代码前先规划 UX/UI，产出可确认的 brief', scene: '方向未定，避免直接开写返工', example: '/impeccable shape 定价页' },
  { name: 'init', category: 'setup', purpose: '把持久的产品上下文写入 PRODUCT.md（每项目一次）', scene: '新接入 skill，先建立产品事实层', example: '/impeccable init' },
  { name: 'document', category: 'setup', purpose: '从既有项目代码生成 DESIGN.md 视觉系统', scene: '已有品牌风格，希望后续改动保持一致', example: '/impeccable document' },
  { name: 'extract', category: 'setup', purpose: '把可复用的 token 与组件抽取成设计系统', scene: '样式散落各处，想沉淀为系统', example: '/impeccable extract 按钮' },
  // 弃用别名（1）
  { name: 'craft', category: 'deprecated', purpose: '普通构建请求的旧别名（已弃用，直接自然语言描述即可）', scene: '仅旧会话/旧文档中还会出现', example: '/impeccable craft hero（已弃用）' },
]
