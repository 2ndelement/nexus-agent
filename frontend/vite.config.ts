import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      // Agent Engine API -> Gateway (8080 - Java Gateway 路由到 8011)
      '/api/v1/agent': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // Conversations API -> Gateway -> Session Service (8004)
      '/api/v1/conversations': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v1\/conversations/, '/api/session/conversations'),
      },
      // Session Service API (8004 - Java)
      '/api/session': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // Auth Service API (8081 - Java)
      '/api/auth': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // Admin API (租户、用户、Agent 管理) -> Gateway -> agent-engine
      '/api/v1/tenants': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/api/v1/users': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/api/v1/agents': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // Models API -> Gateway -> agent-engine
      '/api/v1/models': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // Media API -> Gateway -> agent-engine (沙箱文件代理)
      '/api/v1/media': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      // RAG Service API -> Gateway -> rag-service (8013)
      '/rag-api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/rag-api/, '/api/rag'),
      },
      // Tool Registry API -> Gateway -> tool-registry (8012)
      '/tools-api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/tools-api/, '/api/tools'),
      },
    },
  },
})
