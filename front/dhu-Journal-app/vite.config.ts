import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server:{
    proxy:{
      '/api': {
        target: 'http://localhost:5000', // 后端 API 地址
        changeOrigin: true, // 修改请求头中的 Origin
        // rewrite: (path) => path.replace(/^\/api/, ''), // 重写路径
      },
    }
  }

})

