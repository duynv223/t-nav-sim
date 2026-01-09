import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    // Full reload when map composables change (prevents HMR issues with map cleanup)
    {
      name: 'full-reload-map-composables',
      handleHotUpdate({ file, server }) {
        if (file.includes('/composables/map/') || file.includes('\\composables\\map\\')) {
          console.log('[HMR] Map composable changed, triggering full reload:', path.basename(file))
          server.ws.send({ type: 'full-reload' })
          return []
        }
      }
    }
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/sim': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  },
  build: {
    target: 'esnext',
    minify: false
  },
  optimizeDeps: {
    exclude: ['vue']
  }
})
