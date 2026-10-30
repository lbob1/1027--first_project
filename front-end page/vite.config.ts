import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// base: './' + 单文件内联：dist/index.html 自包含全部 JS/CSS，
// file:// 双击直接打开（规避浏览器对 file:// 下 module 脚本的 CORS 拦截），也可挂任意静态服务
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  base: './',
})

