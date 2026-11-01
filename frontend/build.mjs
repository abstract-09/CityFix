// Dependency-free production build:
//   1. syntax-checks every module,
//   2. verifies index.html only references files that exist,
//   3. copies the app (without tests) into dist/, which the backend serves when present.
// Set API_BASE_URL to point a separately hosted frontend at the backend.
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const dist = join(root, 'dist');
const APP_DIRS = ['components', 'pages', 'services', 'styles'];
const APP_FILES = ['index.html', 'main.js', 'config.js'];

function jsFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name);
    return e.isDirectory() ? jsFiles(p) : /\.m?js$/.test(e.name) ? [p] : [];
  });
}

let failed = false;
const sources = [...APP_FILES.filter((f) => f.endsWith('.js')).map((f) => join(root, f)), ...APP_DIRS.flatMap((d) => jsFiles(join(root, d)))];
for (const file of sources) {
  const r = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' });
  if (r.status !== 0) { failed = true; console.error(`Syntax error in ${file}\n${r.stderr}`); }
}

const html = readFileSync(join(root, 'index.html'), 'utf8');
for (const [, ref] of html.matchAll(/(?:src|href)="\.\/([^"]+)"/g)) {
  if (!existsSync(join(root, ref))) { failed = true; console.error(`index.html references missing file: ${ref}`); }
}
if (failed) process.exit(1);

rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });
for (const f of APP_FILES) cpSync(join(root, f), join(dist, f));
for (const d of APP_DIRS) cpSync(join(root, d), join(dist, d), { recursive: true });
if (process.env.API_BASE_URL) {
  writeFileSync(join(dist, 'config.js'), `window.CITYFIX_CONFIG = ${JSON.stringify({ apiBase: process.env.API_BASE_URL.replace(/\/$/, '') })};\n`);
}
writeFileSync(join(dist, 'build.json'), JSON.stringify({ builtAt: new Date().toISOString(), modules: sources.length }));
console.log(`Frontend build OK: ${sources.length} modules checked, output in frontend/dist`);
