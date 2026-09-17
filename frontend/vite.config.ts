import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前端开发服务器配置：默认监听所有网卡方便局域网访问，端口 5173
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // 把 /api 请求代理到 FastAPI 后端
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})