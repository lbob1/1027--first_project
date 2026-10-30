/* 光谱六色（与彩虹主题同族）；文档名哈希取色，同一文档恒定一色 */
export const SPECTRUM = ['#9c5c0b', '#c2453a', '#b83d78', '#7a4dd8', '#3f5fc4', '#1f7a6e']

export function colorFor(name: string): string {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  return SPECTRUM[h % SPECTRUM.length]
}
