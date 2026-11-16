#pragma once
namespace filelink {
constexpr char portalHtml[] = R"PORTAL(<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>TV File Link</title>
<meta name="theme-color" content="#0e131e">
<style>
:root{color-scheme:dark;background:#0e131e;color:#f5f4f0;font:16px "Segoe UI",Inter,system-ui,sans-serif;--panel:#171f2e;--row:#1d2738;--border:#303a4c;--muted:#aebacd;--gold:#f4d68c;--gold2:#e2b85c;--ok:#a7dfc2;--bad:#ffb4a8}
*{box-sizing:border-box}
body{max-width:820px;margin:auto;padding:clamp(18px,5vw,48px) clamp(16px,5vw,36px)}
.brand{display:flex;align-items:center;gap:15px;border-bottom:1px solid var(--border);padding-bottom:18px;margin-bottom:22px}
.brand img{width:64px;height:64px;flex:none;border:1px solid #645637;border-radius:15px}
h1,h2,p{margin:0}
h1{font-size:clamp(1.7rem,6vw,2.5rem);line-height:1.08;letter-spacing:-.03em}
h2{font-size:1.3rem;line-height:1.25;overflow-wrap:anywhere}
p{color:var(--muted);line-height:1.45}
.brand p{margin-top:4px;font-size:.9rem}
.surface{background:var(--panel);border:1px solid var(--border);border-radius:18px;padding:clamp(16px,5vw,26px)}
#connect{display:grid;gap:12px;max-width:460px}
label{font-weight:650}
input,button{font:inherit;max-width:100%}
#code{width:100%;background:#0b111c;border:1px solid #556278;color:var(--gold);border-radius:12px;padding:12px 14px;font:700 2rem ui-monospace,Consolas,monospace;letter-spacing:.42em;text-align:center}
#code::placeholder{color:#4a5568;letter-spacing:.42em}
button,a{touch-action:manipulation}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:10px;background:var(--gold);color:#1b160c;min-height:44px;padding:9px 16px;font-weight:700;cursor:pointer;text-decoration:none}
.btn:hover{background:#ffe3a3}
.btn:active{opacity:.85}
.btn:disabled{opacity:.45;cursor:default}
.secondary{background:#243044;color:#e9ecf2}
.secondary:hover{background:#2d3b53}
nav{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:12px 0 16px}
.crumb{color:var(--muted);font-size:.9rem;margin-top:2px;overflow-wrap:anywhere}
#upload{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 10px;align-items:center;background:var(--row);border:1px dashed #4a5873;border-radius:14px;padding:14px}
#upload label{grid-column:1/-1}
input[type=file]{width:100%;font-size:1rem;color:var(--muted)}
input::file-selector-button{margin-right:10px;padding:9px 12px;border:0;border-radius:8px;background:#243044;color:#edf0f5;cursor:pointer}
#progressBox{margin-top:12px}
#progressText{font-size:.9rem;color:var(--muted);overflow-wrap:anywhere}
progress{width:100%;height:12px;margin-top:6px;accent-color:var(--gold)}
ul{list-style:none;padding:0;margin:16px 0 0}
li{display:flex;align-items:center;gap:12px;padding:10px 4px;border-top:1px solid var(--border)}
li svg{flex:none;width:30px;height:30px}
.name{flex:1;min-width:0}
.name button,.name span{display:block;padding:0;border:0;background:none;color:#f5f4f0;font-weight:650;text-align:left;overflow-wrap:anywhere;cursor:pointer}
.name button{color:var(--gold)}
.name button:hover{text-decoration:underline}
small{color:var(--muted);display:block;margin-top:2px}
.dl{min-height:38px;padding:6px 12px;font-size:.9rem}
#status{margin-top:14px;padding:0;white-space:pre-line}
#status.ok{color:var(--ok)}
#status.bad{color:var(--bad)}
.foot{margin-top:24px;font-size:.8rem;color:#7d8aa0;text-align:center}
[hidden]{display:none!important}
:focus-visible{outline:3px solid var(--gold);outline-offset:3px}
@media(max-width:420px){#upload{grid-template-columns:minmax(0,1fr)}li{flex-wrap:wrap}.dl{margin-left:42px}}
</style>
<header class="brand"><img src="data:image/png;base64,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" alt="TV File Link logo"><div><h1>TV File Link</h1><p>Wi-Fi file transfer &middot; stays on your local network</p></div></header>
<form id="connect" class="surface" autocomplete="off">
<h2>Connect to your TV</h2><p>Enter the six-digit code shown on the TV screen, then select Connect.</p>
<label for="code">6-digit TV code</label>
<input id="code" type="text" inputmode="numeric" pattern="[0-9]{6}" required minlength="6" maxlength="6" autocomplete="one-time-code" spellcheck="false" placeholder="000000" aria-describedby="status">
<button class="btn" id="connectBtn">Connect</button>
</form>
<main id="panel" class="surface" hidden>
<h2 id="folder">My files</h2><div class="crumb" id="crumb">TV library</div>
<nav aria-label="Folder controls"><button class="btn secondary" id="up" type="button">&#8593; Up one folder</button><button class="btn secondary" id="refresh" type="button">&#8635; Refresh</button><button class="btn secondary" id="leave" type="button">Disconnect</button></nav>
<form id="upload"><label for="files">Send files to this folder</label><input id="files" type="file" multiple required><button class="btn" id="send">Upload</button></form>
<div id="progressBox" hidden><div id="progressText"></div><progress id="progress" max="1" value="0" aria-label="Upload progress"></progress></div>
<ul id="listing" aria-label="Files on the TV"></ul>
</main>
<p id="status" role="status" aria-live="polite"></p>
<p class="foot">Keep this page open while files transfer. Select Stop transfer on the TV when you are done.</p>
<script>
const byId = id => document.getElementById(id);
let key = '', path = '', busy = false, generation = 0;
const FOLDER = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#e2b85c" d="M2 6.5A2.5 2.5 0 0 1 4.5 4h4.2l2 2.2h8.8A2.5 2.5 0 0 1 22 8.7v8.8a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 17.5z"/><path fill="#f4d68c" d="M2 9h20v8.5a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 17.5z"/></svg>';
const FILE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#2a3650" stroke="#aebacd" stroke-width="1.4" d="M6 2.7h8l4.3 4.3v13.3a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3.7a1 1 0 0 1 1-1z"/><path fill="none" stroke="#aebacd" stroke-width="1.4" d="M14 2.7V7h4.3M8 12h8M8 15h8M8 18h5"/></svg>';
function status(message, kind) { const s = byId('status'); s.textContent = message || ''; s.className = kind || ''; }
const route = (endpoint, params) => '/api/' + endpoint + '?' + new URLSearchParams(params);
function size(bytes) {
  const units = ['bytes', 'KB', 'MB', 'GB'];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return (unit ? value.toFixed(value < 10 ? 1 : 0) : value) + ' ' + units[unit];
}
function ended(message) {
  key = ''; busy = false;
  byId('panel').hidden = true;
  byId('connect').hidden = false;
  byId('code').focus();
  status(message || 'This transfer session has ended. Enter the current code from your TV.', 'bad');
}
async function show(target) {
  if (busy) return;
  const request = ++generation;
  try {
    const response = await fetch(route('list', {path:target}), {headers:{'X-Transfer-Key':key}});
    if (response.status === 403) return ended(await response.text());
    if (!response.ok) throw Error(await response.text());
    const files = await response.json();
    if (request !== generation) return;
    path = target;
    byId('folder').textContent = target ? target.split('/').pop() : 'My files';
    byId('crumb').textContent = 'TV library' + (target ? ' / ' + target.split('/').join(' / ') : '');
    byId('up').disabled = !target;
    const rows = files.map(file => {
      const row = document.createElement('li');
      const child = [target, file.name].filter(Boolean).join('/');
      row.insertAdjacentHTML('beforeend', file.folder ? FOLDER : FILE);
      const name = document.createElement('div');
      name.className = 'name';
      const title = document.createElement(file.folder ? 'button' : 'span');
      title.textContent = file.name;
      if (file.folder) { title.type = 'button'; title.onclick = () => show(child); }
      const info = document.createElement('small');
      info.textContent = file.folder ? 'Folder' : size(file.size);
      name.append(title, info);
      row.append(name);
      if (!file.folder) {
        const link = document.createElement('a');
        link.className = 'btn secondary dl';
        link.href = route('download', {path:child, key});
        link.download = file.name;
        link.textContent = '↓ Download';
        link.setAttribute('aria-label', 'Download ' + file.name);
        row.append(link);
      }
      return row;
    });
    byId('listing').replaceChildren(...rows);
    byId('connect').hidden = true;
    byId('panel').hidden = false;
    if (!byId('status').classList.contains('ok')) status(files.length ? '' : 'This folder is empty. Upload files to add them.');
  } catch (error) {
    if (request === generation) status(error.message || 'Could not reach the TV. Check that both devices use the same Wi-Fi.', 'bad');
  }
}
byId('code').oninput = event => { event.target.value = event.target.value.replace(/[^0-9]/g, '').slice(0, 6); };
byId('connect').onsubmit = async event => {
  event.preventDefault();
  const button = byId('connectBtn');
  const code = byId('code').value;
  if (!/^[0-9]{6}$/.test(code)) return status('Enter all six digits, including any leading zeros.', 'bad');
  button.disabled = true;
  status('Connecting...');
  try {
    const response = await fetch('/api/connect', {method:'POST', headers:{'X-TV-Code':code}});
    if (!response.ok) throw Error(await response.text());
    key = await response.json();
    byId('code').value = '';
    status('Connected to your TV.', 'ok');
    await show('');
  } catch (error) {
    status(error.message || 'Could not reach the TV. Check that both devices use the same Wi-Fi.', 'bad');
  } finally {
    button.disabled = false;
  }
};
byId('up').onclick = () => { status(''); show(path.split('/').slice(0, -1).join('/')); };
byId('refresh').onclick = () => { status(''); show(path); };
byId('leave').onclick = () => { key = ''; byId('panel').hidden = true; byId('connect').hidden = false; status('Disconnected. Enter the code again to reconnect.'); };
function send(file, folder, index, total) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', route('upload', {path:folder, name:file.name}));
    request.setRequestHeader('X-Transfer-Key', key);
    request.setRequestHeader('Content-Type', 'application/octet-stream');
    request.upload.onprogress = event => {
      if (!event.lengthComputable || !event.total) return;
      const part = event.loaded / event.total;
      byId('progress').value = (index + part) / total;
      byId('progressText').textContent = 'File ' + (index + 1) + ' of ' + total + ': ' + file.name + ' (' + Math.round(part * 100) + '%)';
    };
    request.onload = () => request.status === 201 ? resolve() :
      reject(Object.assign(Error(request.responseText || 'Upload failed.'), {code: request.status}));
    request.onerror = () => reject(Error('Connection to the TV was lost.'));
    request.send(file);
  });
}
byId('upload').onsubmit = async event => {
  event.preventDefault();
  if (busy) return;
  const files = [...byId('files').files];
  if (!files.length) return;
  busy = true;
  generation++;
  const folder = path;
  byId('send').disabled = true;
  byId('progressBox').hidden = false;
  byId('progress').value = 0;
  status('');
  const problems = [];
  let saved = 0;
  for (const [index, file] of files.entries()) {
    try { await send(file, folder, index, files.length); saved++; }
    catch (error) {
      if (error.code === 403) { byId('send').disabled = false; byId('progressBox').hidden = true; event.target.reset(); return ended(error.message); }
      problems.push(file.name + ': ' + error.message);
    }
  }
  busy = false;
  byId('progressBox').hidden = true;
  byId('send').disabled = false;
  event.target.reset();
  status(problems.length ? 'Uploaded ' + saved + ' of ' + files.length + ' files.\n' + problems.join('\n') :
    'Upload complete: ' + saved + (saved === 1 ? ' file' : ' files') + ' saved.', problems.length ? 'bad' : 'ok');
  await show(folder);
};
</script></html>
)PORTAL";
}
