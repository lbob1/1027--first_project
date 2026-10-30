export interface SectionMeta {
  id: string
  num: string
  label: string
}

/** 页面 9 大章节（含 Hero），SideNav / scrollspy / 联合搜索共用 */
export const SECTIONS: SectionMeta[] = [
  { id: 'hero', num: '00', label: '是什么' },
  { id: 'install', num: '01', label: '安装' },
  { id: 'workflow', num: '02', label: '核心工作流' },
  { id: 'commands', num: '03', label: '命令速查' },
  { id: 'critique', num: '04', label: '评审循环' },
  { id: 'live', num: '05', label: '实时迭代' },
  { id: 'context', num: '06', label: '上下文文件' },
  { id: 'detector', num: '07', label: '检测器' },
  { id: 'faq', num: '08', label: 'FAQ 与排障' },
]
