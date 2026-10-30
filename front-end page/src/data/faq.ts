export interface FaqItem {
  q: string
  a: string
}

/** FAQ 与排障内容（基于上游 commit 02523ae 的机制说明） */
export const FAQS: FaqItem[] = [
  {
    q: '安装后输入 /impeccable 没有反应？',
    a: '按顺序检查：1) 安装后是否重启了 Trae（或所用的编码工具）——skill 列表在启动时加载；2) skill 目录是否位于项目的 .trae/skills/impeccable 下；3) 运行 /impeccable doctor 做环境自检，它会报告 skill 安装与依赖状态。',
  },
  {
    q: 'live 模式连不上浏览器？',
    a: 'live 要求本地 dev server 且带 HMR——Vite、Next、SvelteKit、Astro、Nuxt、纯 HTML 均可；仅限本地 checkout，不会注入生产站点。排查：dev server 是否在跑、端口是否与 agent 报告的一致、浏览器是否打开了对应地址、防火墙是否拦截了本地回环连接。',
  },
  {
    q: '检测器误报了怎么办？',
    a: '检测器是 62 条确定性规则（无 LLM、无 API key），宁可错报也不放过。处理：1) 在 .impeccable/ 配置中按规则或路径忽略（以上游文档为准）；2) 若是 brief 明确要求的美学（如刻意复古），brief 优先原则会保护它，评审阶段不会被当作套路扣分。',
  },
  {
    q: 'CSP（内容安全策略）有什么注意点？',
    a: 'live 模式会在页面注入脚手架脚本与 overlay，若 dev 环境配置了严格的 CSP 需为本地放行；生产构建不包含任何注入产物，无需为上线环境调整。',
  },
  {
    q: '会收集我的代码或遥测数据吗？',
    a: '检测器与命令本身不依赖云端 LLM、不需要 API key；关于遥测与配置的准确说明，以上游仓库与 impeccable.style/docs 为准。',
  },
  {
    q: '为什么我的 agent 改完还是「套路脸」？',
    a: '常见原因：1) 没先跑 init，agent 缺少产品事实只能套默认；2) 指令太模糊（"make it pop"），应换成具体命令+目标（/impeccable bolder 定价卡片）；3) 改完没跑 critique——独立评审是防止 agent 自我感觉良好的关键一环。',
  },
]
