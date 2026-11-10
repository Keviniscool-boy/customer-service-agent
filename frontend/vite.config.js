import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 前端构建入口配置：单文件组件的编译插件必须在这里注册才能生效。
export default defineConfig({
  plugins: [vue()],
})
