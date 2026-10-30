import { describe, expect, it } from 'vitest'
import { CATEGORY_LABELS, COMMANDS, CATEGORY_ORDER } from '../commands'

describe('commands 数据完整性（对齐上游 commit 02523ae）', () => {
  it('共 24 条命令', () => {
    expect(COMMANDS).toHaveLength(24)
  })

  it('命令名唯一且非空', () => {
    const names = COMMANDS.map((c) => c.name)
    expect(new Set(names).size).toBe(names.length)
    for (const n of names) expect(n.trim().length).toBeGreaterThan(0)
  })

  it('类别数量：steer 9 / review 2 / finish 6 / iterate 2 / setup 4 / deprecated 1', () => {
    const counts = Object.fromEntries(CATEGORY_ORDER.map((c) => [c, 0])) as Record<string, number>
    for (const c of COMMANDS) counts[c.category] += 1
    expect(counts).toEqual({ steer: 9, review: 2, finish: 6, iterate: 2, setup: 4, deprecated: 1 })
  })

  it('每条命令字段完整、示例以 /impeccable 开头', () => {
    for (const c of COMMANDS) {
      expect(CATEGORY_LABELS[c.category]).toBeTruthy()
      expect(c.purpose.trim().length).toBeGreaterThan(4)
      expect(c.scene.trim().length).toBeGreaterThan(4)
      expect(c.example.startsWith('/impeccable')).toBe(true)
    }
  })
})
