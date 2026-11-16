// Capture the real browser transfer page served by the app (running in the emulator).
// Usage: node capture-browser.mjs <origin> <code> <outDir> <profileDir>
import { spawn } from 'node:child_process';
import { writeFile, mkdir } from 'node:fs/promises';
import { once } from 'node:events';
import { join } from 'node:path';

const [origin, code, outDir, profile] = process.argv.slice(2);
await mkdir(outDir, { recursive: true });
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--user-data-dir=' + profile, '--remote-debugging-port=0', 'about:blank',
], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });

let socket;
try {
  const browserUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Browser startup timed out')), 20000);
    chrome.stderr.on('data', chunk => {
      const match = chunk.toString().match(/DevTools listening on ws:\/\/([^/]+)/);
      if (match) { clearTimeout(timer); resolve('http://' + match[1]); }
    });
  });
  const targets = await (await fetch(browserUrl + '/json')).json();
  socket = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
  await once(socket, 'open');
  let next = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    const msg = JSON.parse(event.data);
    if (!pending.has(msg.id)) return;
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(Error(msg.error.message)) : resolve(msg.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++next;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  };
  const waitFor = async (test, tries = 60) => {
    for (let i = 0; i < tries; i++) {
      if (await evaluate(test)) return;
      await new Promise(r => setTimeout(r, 200));
    }
    throw Error('Timed out waiting for: ' + test);
  };
  const shot = async name => {
    const image = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(join(outDir, name), Buffer.from(image.data, 'base64'));
  };
  const report = {};
  // Phone: code entry (code typed, before Connect)
  await send('Emulation.setDeviceMetricsOverride', { width: 412, height: 760, mobile: true, deviceScaleFactor: 2 });
  await send('Page.navigate', { url: origin + '/' });
  await waitFor('document.readyState === "complete" && !!document.querySelector("#code")');
  report.inputmode = await evaluate('document.querySelector("#code").inputMode');
  report.inputType = await evaluate('document.querySelector("#code").type');
  report.autocomplete = await evaluate('document.querySelector("#code").autocomplete');
  await evaluate(`document.querySelector('#code').value = ${JSON.stringify(code)}`);
  await shot('phone-enter-access-code.png');
  // Connect and show the file list
  await evaluate("document.querySelector('#connect').requestSubmit()");
  await waitFor('!document.querySelector("#panel").hidden && document.querySelectorAll("#listing li").length > 0');
  await send('Emulation.setDeviceMetricsOverride', { width: 412, height: 915, mobile: true, deviceScaleFactor: 2 });
  await new Promise(r => setTimeout(r, 300));
  report.connectedStatus = await evaluate('document.querySelector("#status").textContent');
  report.rows = await evaluate('[...document.querySelectorAll("#listing li")].map(li => li.innerText.replace(/\\n/g, " | "))');
  await shot('phone-transfer-page.png');
  // Desktop view of the same session
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 860, mobile: false, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 300));
  await shot('desktop-transfer-page.png');
  console.log(JSON.stringify(report));
} finally {
  if (socket) socket.close();
  chrome.kill();
}
