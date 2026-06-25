const outputEl = document.getElementById('output');
const outputContainer = document.getElementById('output-container');
const btnRun = document.getElementById('btn-run');
const dryRunCb = document.getElementById('dry-run');
const resultCard = document.getElementById('result-card');
const rTitle = document.getElementById('r-title');
const rUrl = document.getElementById('r-url');

let running = false;

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function appendOutput(text, className) {
  if (outputEl.textContent === 'Ready. Click Run ACE to start.') {
    outputEl.textContent = '';
  }
  for (const line of text.split('\n')) {
    if (!line) continue;
    const span = document.createElement('div');
    if (className) span.className = className;
    span.textContent = line;
    outputEl.appendChild(span);
  }
  outputContainer.scrollTop = outputContainer.scrollHeight;
}

function colorizeLine(line) {
  if (/^══|^  ╔|^  ║|^  ╚/.test(line)) return 'text-cyan-400';
  if (/^Phase \d/.test(line))           return 'phase';
  if (/^  ✅/.test(line))               return 'ok';
  if (/^  ❌/.test(line))               return 'fail';
  if (/^  ⚠️/.test(line))               return 'warn';
  if (/^  🔍/.test(line) || /^  📤/.test(line) || /^  🤖/.test(line) || /^  🎨/.test(line) || /^  📱/.test(line) || /^  🎯/.test(line)) return 'info';
  if (/^✅ NATURALS ACE COMPLETE/.test(line)) return 'ok font-bold';
  if (/^❌ ACE failed/.test(line))      return 'fail font-bold';
  if (/^Cannot proceed/.test(line))     return 'fail';
  return '';
}

function clearOutput() {
  outputEl.innerHTML = '<span class="text-gray-400">Ready. Click <span class="text-cyan-400">Run ACE</span> to start.</span>';
  resultCard.classList.add('hidden');
}

// SSE parser: buffers raw bytes, yields events { type, data }
function createSSEParser() {
  let buf = '';
  return function parse(chunk) {
    buf += chunk;
    const events = [];
    while (true) {
      const idx = buf.indexOf('\n\n');
      if (idx === -1) break;
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let type = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) {
          type = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          data = line.slice(6);
        }
      }
      events.push({ type, data });
    }
    return events;
  };
}

async function onRun() {
  if (running) return;

  running = true;
  btnRun.disabled = true;
  btnRun.textContent = '⏳ Running...';
  resultCard.classList.add('hidden');
  clearOutput();

  try {
    const abortController = new AbortController();
    const abortOnNav = () => abortController.abort();
    window.addEventListener('beforeunload', abortOnNav);

    const response = await fetch('/api/ace', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dryRun: dryRunCb.checked }),
      signal: abortController.signal,
    });

    if (!response.ok) {
      appendOutput(`Server error: ${response.status} ${response.statusText}`, 'fail');
      return;
    }

    // Collect ALL output for final result parsing
    const allLines = [];

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const parseSSE = createSSEParser();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      const events = parseSSE(text);

      for (const evt of events) {
        if (evt.type === 'stdout' || evt.type === 'stderr') {
          appendOutput(evt.data, colorizeLine(evt.data));
          allLines.push(evt.data);
        } else if (evt.type === 'preflight') {
          appendOutput(evt.data, 'ok');
          allLines.push(evt.data);
        } else if (evt.type === 'error') {
          appendOutput(`❌ ${evt.data}`, 'fail');
          allLines.push(`❌ ${evt.data}`);
        } else if (evt.type === 'done') {
          appendOutput(`\n── ${evt.data} ──`, 'gray-400');
        }
      }
    }

    // Parse result from collected output
    const combined = allLines.join('\n');
    parseResult(combined);

  } catch (err) {
    if (err.name === 'AbortError') {
      appendOutput('⚠️ Cancelled', 'warn');
    } else {
      appendOutput(`❌ Error: ${err.message}`, 'fail');
    }
  } finally {
    running = false;
    btnRun.disabled = false;
    btnRun.textContent = '▶ Run ACE';
  }
}

function parseResult(text) {
  if (!text.includes('NATURALS ACE COMPLETE')) return;

  let title = '';
  let imageUrl = '';

  for (const line of text.split('\n')) {
    const t = line.trim();
    if (t.startsWith('Campaign:')) {
      title = t.replace('Campaign:', '').trim();
    } else if (t.startsWith('Image:')) {
      imageUrl = t.replace('Image:', '').trim();
    }
  }

  if (title || imageUrl) {
    resultCard.classList.remove('hidden');
    if (title) rTitle.textContent = title;
    if (imageUrl) { rUrl.textContent = imageUrl; rUrl.href = imageUrl; }
  }
}

// Pre-flight status badges on page load
document.addEventListener('DOMContentLoaded', async () => {
  const badgeStyles = {
    ok: 'bg-green-100 text-green-700',
    fail: 'bg-red-100 text-red-700',
    pending: 'bg-gray-200 text-gray-500',
  };

  function setBadge(id, status, text) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.className = `px-2.5 py-1 rounded-full text-xs font-medium ${badgeStyles[status] || badgeStyles.pending}`;
  }

  try {
    const checkRes = await fetch('/api/ace/status');
    if (checkRes.ok) {
      const d = (await checkRes.json()).data || {};
      setBadge('s-ollama', d.ollamaOk ? 'ok' : 'fail', d.ollamaOk ? '✅ Ollama' : '❌ Ollama');
      const genStatus = d.sdOk ? 'ok' : (d.genLabel?.includes('⏭') ? 'ok' : 'fail');
      setBadge('s-sd', genStatus, d.genLabel || (d.sdOk ? '✅ SD WebUI' : '❌ SD WebUI'));
      setBadge('s-stores', d.storesOk ? 'ok' : 'fail', d.storesOk ? '✅ stores.json' : '❌ stores.json');
      setBadge('s-adhoc',  d.adhocScript ? 'ok' : 'fail', d.adhocScript ? '✅ adhoc.py' : '❌ adhoc.py');
      setBadge('s-git',    d.aceScript  ? 'ok' : 'fail', d.aceScript  ? '✅ ACE script' : '❌ ACE script');
    }
  } catch {
    setBadge('s-ollama', 'fail', '❌ server');
  }
});
