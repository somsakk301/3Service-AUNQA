import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    dedupe: ['react', 'react-dom', 'react-router-dom'],
    alias: {
      '@monitor': root + 'services/monitor/frontend/src',
      '@generator': root + 'services/generator/frontend/src',
    },
  },
  define: {
    'import.meta.env.VITE_USE_MOCK_API': JSON.stringify('false'),
    'import.meta.env.VITE_DEV_GENERATE': JSON.stringify('false'),
    'import.meta.env.VITE_PORTAL': JSON.stringify('true'),
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api'),
  },
  css: {postcss: {plugins: [{
    postcssPlugin: 'scope-generator-css',
    Rule(rule) {
      if (!rule.source?.input.file?.replaceAll('\\', '/').includes('services/generator/frontend/')) return;
      if (rule.parent.type === 'atrule' && rule.parent.name.includes('keyframes')) return;
      if (rule.selector.includes('.generator-workspace')) return;
      rule.selector = rule.selector.split(',').map(s => {
        s = s.trim();
        return [':root','html','body','#root'].includes(s) ? '.generator-workspace' : '.generator-workspace ' + s;
      }).join(', ');
    }
  }] }},
});

