/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // 暖纸+墨色编辑风，避开检测器点名的默认套路（Inter / 紫蓝渐变 / 卡片套卡片）
        paper: '#faf6ef',
        card: '#fffdf8',
        ink: '#221f1b',
        'ink-soft': '#5b544a',
        'ink-faint': '#8a8175',
        line: '#e6ddcd',
        accent: { DEFAULT: '#b23a24', deep: '#8f2c1a', soft: '#f3e0da' },
        ok: '#2e6b3f',
        warn: '#9a6b16',
      },
      fontFamily: {
        display: ['Georgia', '"Times New Roman"', '"Noto Serif SC"', '"Source Han Serif SC"', '"Songti SC"', 'SimSun', 'serif'],
        sans: ['system-ui', '-apple-system', '"Segoe UI"', 'Roboto', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        mono: ['ui-monospace', '"Cascadia Code"', 'Consolas', '"Courier New"', 'monospace'],
      },
      maxWidth: {
        content: '46rem',
      },
    },
  },
  plugins: [],
}
