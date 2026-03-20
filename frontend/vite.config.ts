import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',  // 监听所有网卡，允许 Mac 等外部设备访问
    port: 5173,
    // 注意：WS 直连后端 8000 端口（useWebSocket.ts 用 window.location.hostname 动态拼接），
    // 此代理仅为本地 localhost 开发场景保留。
    proxy: {
      '/api/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
