/**
 * 管理端前端构建配置（方案 2：Django 管理接口 + Vue3 自建前端）
 *
 * - dev 端口 8081，proxy /admin/api → Django 管理端 8001（避免 CORS，P1-9 JWT 认证）
 * - 构建产物 dist/，可部署到 nginx 反代 /admin/api 到 Django
 */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/static/',
  server: {
    port: 8081,
    host: '0.0.0.0',
    proxy: {
      '/admin/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables.scss" as *;`
      }
    }
  },
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname
    }
  }
})
