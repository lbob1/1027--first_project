import { useInView, usePrefersReducedMotion } from '../hooks'

/** 手写 SVG 趋势折线：进入视口描线一次（reduced-motion 直出） */
export function TrendChart({ data, max = 40 }: { data: number[]; max?: number }) {
  const { ref, inView } = useInView<HTMLDivElement>()
  const reduced = usePrefersReducedMotion()
  const w = 340
  const h = 150
  const padX = 26
  const padTop = 20
  const padBottom = 26
  const xs = data.map((_, i) => padX + (i * (w - padX * 2)) / (data.length - 1))
  const ys = data.map((v) => padTop + (1 - v / max) * (h - padTop - padBottom))
  const points = xs.map((x, i) => `${x},${ys[i]}`).join(' ')
  const drawn = inView || reduced
  const latest = data.length - 1

  return (
    <div ref={ref}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={`最近 ${data.length} 次评审健康分趋势：${data.join('、')}，满分 ${max}`}
        className="w-full"
      >
        {/* 横向网格与刻度 */}
        {[0, 10, 20, 30, 40].map((v) => {
          const y = padTop + (1 - v / max) * (h - padTop - padBottom)
          return (
            <g key={v}>
              <line x1={padX} x2={w - padX} y1={y} y2={y} stroke="#e6ddcd" strokeWidth="1" strokeDasharray={v === 0 ? undefined : '3 4'} />
              <text x={padX - 6} y={y + 3} textAnchor="end" fontSize="9" fill="#8a8175" fontFamily="monospace">
                {v}
              </text>
            </g>
          )
        })}
        {/* 折线（pathLength 归一化描线动画） */}
        <polyline
          points={points}
          fill="none"
          stroke="#b23a24"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray="1"
          strokeDashoffset={drawn ? 0 : 1}
          style={{ transition: 'stroke-dashoffset 1.2s ease' }}
        />
        {/* 数据点 */}
        {xs.map((x, i) => (
          <g key={i}>
            <circle cx={x} cy={ys[i]} r={i === latest ? 4 : 3} fill={i === latest ? '#b23a24' : '#fffdf8'} stroke="#b23a24" strokeWidth="1.5" />
            <text x={x} y={ys[i] - 8} textAnchor="middle" fontSize="10" fontWeight={i === latest ? 700 : 400} fill={i === latest ? '#8f2c1a' : '#5b544a'} fontFamily="monospace">
              {data[i]}
            </text>
            <text x={x} y={h - 8} textAnchor="middle" fontSize="9" fill="#8a8175">
              第{i + 1}次
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
