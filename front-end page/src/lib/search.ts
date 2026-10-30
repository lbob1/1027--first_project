import { COMMANDS, CATEGORY_LABELS, type Command, type CommandCategory } from '../data/commands'
import { SECTIONS } from '../data/sections'

/** 命令速查表的过滤逻辑：关键字（名称/用途/场景/类别）+ 类别 */
export function filterCommands(query: string, category: CommandCategory | 'all'): Command[] {
  const q = query.trim().toLowerCase()
  return COMMANDS.filter((c) => {
    if (category !== 'all' && c.category !== category) return false
    if (!q) return true
    const haystack = `${c.name} ${c.purpose} ${c.scene} ${CATEGORY_LABELS[c.category]} ${c.example}`.toLowerCase()
    return haystack.includes(q)
  })
}

export interface SearchHit {
  type: 'section' | 'command'
  id: string
  title: string
  subtitle: string
  command?: Command
}

/** 顶部搜索：章节标题 + 命令 联合匹配 */
export function searchAll(query: string, limit = 8): SearchHit[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  const hits: SearchHit[] = []
  for (const s of SECTIONS) {
    if (s.label.toLowerCase().includes(q) || s.id.includes(q)) {
      hits.push({ type: 'section', id: s.id, title: s.label, subtitle: `章节 ${s.num}` })
    }
  }
  for (const c of COMMANDS) {
    const haystack = `${c.name} ${c.purpose} ${c.scene} ${CATEGORY_LABELS[c.category]}`.toLowerCase()
    if (haystack.includes(q)) {
      hits.push({ type: 'command', id: c.name, title: `/${c.name}`, subtitle: c.purpose, command: c })
    }
  }
  return hits.slice(0, limit)
}
