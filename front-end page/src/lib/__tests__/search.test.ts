import { describe, expect, it } from 'vitest'
import { COMMANDS } from '../../data/commands'
import { filterCommands, searchAll } from '../search'

describe('filterCommands', () => {
  it('无条件时返回全部 24 条', () => {
    expect(filterCommands('', 'all')).toHaveLength(24)
  })

  it('按类别过滤：steer 9 条', () => {
    const r = filterCommands('', 'steer')
    expect(r).toHaveLength(9)
    expect(r.every((c) => c.category === 'steer')).toBe(true)
  })

  it('关键字命中命令名', () => {
    const r = filterCommands('polish', 'all')
    expect(r.map((c) => c.name)).toContain('polish')
  })

  it('关键字命中中文用途（评审 → critique/audit）', () => {
    const r = filterCommands('评审', 'all')
    expect(r.map((c) => c.name)).toEqual(expect.arrayContaining(['critique', 'audit']))
  })

  it('类别 + 关键字联合过滤生效', () => {
    expect(filterCommands('zzz-none', 'steer')).toHaveLength(0)
  })
})

describe('searchAll（顶部联合搜索）', () => {
  it('命中章节标题', () => {
    const r = searchAll('安装')
    expect(r.some((h) => h.type === 'section' && h.id === 'install')).toBe(true)
  })

  it('命中命令并携带 Command 对象', () => {
    const r = searchAll('critique')
    const hit = r.find((h) => h.type === 'command')
    expect(hit?.command?.name).toBe('critique')
  })

  it('空查询返回空', () => {
    expect(searchAll('   ')).toHaveLength(0)
  })

  it('结果数不超过上限', () => {
    expect(searchAll('e', 3).length).toBeLessThanOrEqual(3)
    expect(COMMANDS.length).toBe(24) // 数据源未被污染
  })
})
