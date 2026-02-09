import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 如果你希望前端能自动打开浏览器，可以加上下面这行
    open: true
  }
})