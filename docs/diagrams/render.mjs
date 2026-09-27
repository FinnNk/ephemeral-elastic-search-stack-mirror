// Run from any working directory. Dependencies are explicit; nothing is installed here.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const dir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(dir, '../..');
const pins = JSON.parse(fs.readFileSync(path.join(dir, 'tooling.json'), 'utf8'));
const args = new Set(process.argv.slice(2));
for (const arg of args) {
  if (!['--c4', '--archify', '--browser'].includes(arg)) throw new Error(`Unknown option: ${arg}`);
}
const all = !args.has('--c4') && !args.has('--archify');
function run(command, parameters, capture = false) {
  const result = spawnSync(command, parameters, {
    cwd: root, encoding: 'utf8', stdio: capture ? 'pipe' : 'inherit',
    env: {...process.env, ARCHIFY_UPDATE_CHECK_DISABLED: '1'},
  });
  if (result.error || result.status !== 0) {
    throw new Error(result.error?.message || `${command} failed (${result.status})\n${result.stdout || ''}\n${result.stderr || ''}`);
  }
  return result.stdout;
}
function docker(parameters) {
  run('docker', ['run', '--rm', '--mount', `type=bind,source=${dir},target=/usr/local/structurizr`, pins.structurizrImage, ...parameters]);
}
if (all || args.has('--c4')) {
  docker(['validate', '-workspace', 'workspace.dsl']);
  docker(['export', '-workspace', 'workspace.dsl', '-format', 'json', '-output', '.structurizr']);
  run(process.execPath, [path.join(dir, 'layout.mjs')]);
  docker(['export', '-workspace', '.structurizr/workspace-layout.json', '-format', 'svg', '-output', 'rendered']);
  if (args.has('--browser')) docker(['export', '-workspace', '.structurizr/workspace-layout.json', '-format', 'png', '-output', 'qa/c4']);
}
if (all || args.has('--archify')) {
  const checkout = path.join(root, '.diagram-tools/archify');
  if (!fs.existsSync(checkout)) throw new Error('Archify checkout missing. Follow README.md in this directory.');
  const revision = run('git', ['-c', `safe.directory=${checkout.replaceAll('\\', '/')}`, '-C', checkout, 'rev-parse', 'HEAD'], true).trim();
  if (revision !== pins.archifyCommit) throw new Error(`Archify revision differs from tooling.json: ${revision}`);
  const cli = path.join(checkout, 'archify/bin/archify.mjs');
  fs.mkdirSync(path.join(dir, 'receipts'), {recursive: true});
  fs.mkdirSync(path.join(dir, 'interactive'), {recursive: true});
  for (const [name, type] of [['change-to-comparison', 'workflow'], ['pr-to-verdict', 'workflow'], ['release-promotion', 'workflow'], ['observability-investigation', 'workflow'], ['environment-lifecycle', 'lifecycle'], ['evaluation-dataflow', 'dataflow'], ['shared-index-reuse', 'architecture'], ['result-regression', 'workflow'], ['performance-check', 'workflow'], ['traffic-workload', 'workflow'], ['schema-evolution', 'workflow'], ['live-index-clone', 'workflow'], ['snapshot-restore', 'workflow']]) {
    const input = path.join(dir, 'archify', `${name}.json`);
    const output = path.join(dir, 'interactive', `${name}.html`);
    run(process.execPath, [cli, 'validate', type, input, '--quality', 'showcase']);
    const receipt = run(process.execPath, [cli, 'deliver', type, input, output, '--quality', 'showcase', '--json'], true);
    fs.writeFileSync(path.join(dir, 'receipts', `${name}.delivery.json`), receipt, 'utf8');
    if (args.has('--browser')) {
      run(process.execPath, [cli, 'visual-check', output, '--json'], true);
      const base = output.slice(0, -5);
      fs.copyFileSync(`${base}.visual-check.json`, path.join(dir, 'receipts', `${name}.browser.json`));
      fs.copyFileSync(`${base}.visual-check.1440x900.light.png`, path.join(dir, 'rendered', `${name}.png`));
    }
    console.log(`Delivered ${name}${args.has('--browser') ? ' with browser evidence' : ''}.`);
  }
}
console.log('Rendering complete. Inspect images before updating the separate visual-review record.');
