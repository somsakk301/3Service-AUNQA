// Compile the real clients using the Portal's production Vite definitions.
import { build } from 'vite';

const result = await build({
  configFile: 'vite.config.js',
  build: { ssr: 'tests/api-routing.entry.js', write: false, minify: false },
});
const entry = result.output.find(item => item.type === 'chunk' && item.isEntry);
await import('data:text/javascript;base64,' + Buffer.from(entry.code).toString('base64'));
