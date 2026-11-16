import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { once } from 'node:events';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = join(root, 'screenshots');
const logo = await readFile(join(root, 'shared', 'as-logo.png'));
const portal = (await readFile(join(root, 'shared', 'portal.html'), 'utf8'))
  .replace('{{AS_LOGO}}', logo.toString('base64'));
const preview = await readFile(join(root, 'work', 'tv-layout-preview.html'));
const fixtures = [
  { name: 'Photos', folder: true, size: 0 },
  { name: 'Holiday video.mp4', folder: false, size: 26843545 },
  { name: 'Travel itinerary.pdf', folder: false, size: 182485 },
];

const server = createServer((req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname;
  if (path === '/as-logo.png') {
    res.setHeader('Content-Type', 'image/png');
    res.end(logo);
    return;
  }
  if (path === '/api/connect' && req.method === 'POST') {
    if (req.headers['x-tv-code'] !== '042615') {
      res.writeHead(403).end('Enter the six-digit code shown on your TV.');
      return;
    }
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify('preview-session'));
    return;
  }
  if (path === '/api/list') {
    if (req.headers['x-transfer-key'] !== 'preview-session') {
      res.writeHead(403).end('Connect to the TV first.');
      return;
    }
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(fixtures));
    return;
  }
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(path === '/tv' ? preview : portal);
});
server.listen(0, '127.0.0.1');
await once(server, 'listening');
const origin = 'http://127.0.0.1:' + server.address().port;
await mkdir(output, { recursive: true });
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--disable-gpu', '--no-first-run',
  '--user-data-dir=' + join(root, 'work', 'screenshots-browser'),
  '--remote-debugging-port=0', 'about:blank',
], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });

let socket;
try {
  const browserUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Browser startup timed out')), 15000);
    chrome.once('error', error => {clearTimeout(timer); reject(error);});
    chrome.stderr.on('data', chunk => {
      const match = chunk.toString().match(/DevTools listening on ws:\/\/([^/]+)/);
      if (match) {clearTimeout(timer); resolve('http://' + match[1]);}
    });
  });
  const targets = await (await fetch(browserUrl + '/json')).json();
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
  await once(socket, 'open');
  let next = 0;
  const requests = new Map();
  socket.addEventListener('message', event => {
    const response = JSON.parse(event.data);
    if (!requests.has(response.id)) return;
    const {resolve, reject} = requests.get(response.id);
    requests.delete(response.id);
    if (response.error) reject(Error(response.error.message));
    else resolve(response.result);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++next;
    requests.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params}));
  });
  const evaluate = async expression => {
    const result = await send('Runtime.evaluate', {expression, returnByValue:true});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  async function waitFor(test) {
    for (let attempt = 0; attempt < 40; attempt++) {
      if (await evaluate(test)) return;
      await new Promise(resolve => setTimeout(resolve, 150));
    }
    throw Error('Page did not render the expected contents');
  }
  async function capture({page, width, height, mobile, filename, test, connect}) {
    await send('Emulation.setDeviceMetricsOverride', {width, height, mobile, deviceScaleFactor:1});
    await send('Page.navigate', {url:origin + page});
    await waitFor('location.pathname === ' + JSON.stringify(page) + ' && document.readyState === "complete"');
    if (connect) {
      await evaluate("document.querySelector('#code').value = '042615'; document.querySelector('#connect').requestSubmit()");
    }
    await waitFor(test);
    const image = await send('Page.captureScreenshot', {format:'png'});
    await writeFile(join(output, filename), Buffer.from(image.data, 'base64'));
  }
  await capture({page:'/tv', width:1280, height:720, mobile:false,
    filename:'tv-layout-preview.png', test:'document.body.innerText.includes("Stop transfer")'});
  await capture({page:'/', width:460, height:460, mobile:true,
    filename:'phone-enter-access-code.png', test:'!document.querySelector("#connect").hidden'});
  await capture({page:'/', width:460, height:790, mobile:true, connect:true,
    filename:'phone-transfer-page.png', test:'document.querySelectorAll("#listing li").length === 3'});
  console.log('Captured app screens in ' + output);
} finally {
  if (socket) socket.close();
  chrome.kill();
  server.close();
}
