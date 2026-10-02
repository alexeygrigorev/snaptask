'use strict';
const $ = (id) => document.getElementById(id);
let toastTimer;
function toast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 6000);
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin', ...options,
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers }
  });
  const result = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) throw new Error('Your session has expired. Sign in again to continue.');
    throw new Error(result.error?.message || result.message || (typeof result.error === 'string' ? result.error : '') || `Request failed (${response.status})`);
  }
  return result;
}
function secret(containerId, title, value) {
  const container = $(containerId);
  container.replaceChildren();
  container.className = 'secret';
  const label = document.createElement('strong');
  label.textContent = title;
  const code = document.createElement('code');
  code.textContent = value;
  const copy = document.createElement('button');
  copy.type = 'button'; copy.className = 'button secondary small'; copy.textContent = 'Copy';
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(value); toast('Copied to clipboard.'); }
    catch { toast('Select the token text and copy it manually.'); }
  });
  container.append(label, code, copy);
  container.hidden = false;
}
function renderList(containerId, items, kind) {
  const container = $(containerId); container.replaceChildren();
  if (!items.length) {
    const p = document.createElement('p'); p.textContent = kind === 'tokens' ? 'No tokens yet.' : 'No webhooks connected yet.';
    container.append(p); return;
  }
  for (const item of items) {
    const row = document.createElement('div'); row.className = 'connection-item';
    const name = document.createElement('span'); name.textContent = item.name || item.url || 'Unnamed token';
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = kind === 'tokens' ? 'Revoke' : 'Remove';
    remove.addEventListener('click', async () => {
      if (!window.confirm(kind === 'tokens' ? `Revoke "${item.name || 'this token'}"? Apps using it will need a new token.` : `Remove webhook ${item.url}?`)) return;
      remove.disabled = true;
      try { await api(`/api/${kind}/${encodeURIComponent(item.id)}`, { method: 'DELETE' }); row.remove(); toast(kind === 'tokens' ? 'Token revoked.' : 'Webhook removed.'); }
      catch (error) { toast(error.message); remove.disabled = false; }
    });
    row.append(name, remove); container.append(row);
  }
}
async function loadConnections() {
  const results = await Promise.allSettled([api('/api/tokens'), api('/api/webhooks')]);
  for (let i = 0; i < results.length; i++) {
    const kind = i === 0 ? 'tokens' : 'webhooks';
    if (results[i].status === 'fulfilled') {
      const data = results[i].value;
      renderList(i === 0 ? 'token-list' : 'webhook-list', Array.isArray(data) ? data : data[kind] || [], kind);
    } else { $(i === 0 ? 'token-list' : 'webhook-list').textContent = results[i].reason.message; }
  }
}
$('token-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.target.querySelector('button'); button.disabled = true;
  try {
    const data = await api('/api/tokens', { method: 'POST', body: JSON.stringify({ name: $('token-name').value.trim() }) });
    if (!data.token) throw new Error('The server did not return a token.');
    secret('token-secret', 'Save this token. You will not see it again.', data.token);
    $('token-name').value = '';
    await loadConnections();
  } catch (error) { toast(error.message); } finally { button.disabled = false; }
});
$('webhook-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.target.querySelector('button'); button.disabled = true;
  try {
    const url = $('webhook-url').value.trim();
    if (new URL(url).protocol !== 'https:') throw new Error('Use an HTTPS URL for your webhook.');
    const data = await api('/api/webhooks', { method: 'POST', body: JSON.stringify({ url }) });
    if (data.secret) secret('webhook-secret', 'Save the webhook signing secret.', data.secret);
    $('webhook-url').value = ''; await loadConnections(); toast('Webhook connected.');
  } catch (error) { toast(error.message); } finally { button.disabled = false; }
});
(async () => {
  try {
    const data = await api('/api/me');
    const user = data.user || data;
    if (!user || data.authenticated === false) return;
    $('landing').hidden = true; $('capture-workspace').hidden = false; $('connections-toggle').hidden = false;
    $('account').replaceChildren();
    const name = document.createElement('span'); name.className = 'user-name'; name.textContent = user.name || user.email || 'Your workspace';
    const logout = document.createElement('a'); logout.href = '/auth/logout'; logout.className = 'nav-button'; logout.textContent = 'Sign out';
    $('account').append(name, logout);
    await initializeCapture(user);
    await loadConnections();
  } catch (error) { /* Public onboarding remains available without a session. */ }
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
})();

let draft = null, draftDB, draftKey, saving = Promise.resolve(), uploading = false;
let photoUrls = [];
const uid = () => crypto.randomUUID();
function dbRequest(transaction, operation) {
  return new Promise((resolve, reject) => {
    const request = operation(transaction.objectStore('drafts'));
    let result;
    request.onsuccess = () => { result = request.result; };
    transaction.oncomplete = () => resolve(result);
    transaction.onerror = () => reject(transaction.error || new Error('Could not save this batch on your device.'));
    transaction.onabort = () => reject(transaction.error || new Error('Device storage is unavailable.'));
  });
}
async function persistDraft() {
  const snapshot = draft ? structuredClone(draft) : null;
  saving = saving.catch(() => {}).then(() => dbRequest(draftDB.transaction('drafts', 'readwrite'), (store) => snapshot ? store.put(snapshot, draftKey) : store.delete(draftKey)));
  try { await saving; $('draft-state').textContent = 'Saved on this device'; }
  catch (error) { $('draft-state').textContent = 'Not saved'; $('batch-status').textContent = 'Device storage is full or unavailable. Keep this page open and try again.'; throw error; }
}
function setBatchDisabled(disabled) {
  for (const id of ['batch-title', 'batch-notes', 'add-photo', 'add-files', 'discard-batch']) $(id).disabled = disabled;
  for (const button of $('batch-photos').querySelectorAll('button')) button.disabled = disabled || !!draft?.taskId;
  $('ready-batch').disabled = disabled || !draft?.photos.length;
  $('start-capture').disabled = disabled;
}
function renderDraft() {
  for (const url of photoUrls) URL.revokeObjectURL(url);
  photoUrls = [];
  $('batch').hidden = !draft;
  $('start-capture').disabled = uploading;
  $('batch-photos').replaceChildren();
  if (!draft) return;
  $('batch-title').value = draft.title;
  $('batch-notes').value = draft.notes;
  $('batch-count').textContent = `${draft.photos.length} ${draft.photos.length === 1 ? 'photo' : 'photos'}. One task.`;
  $('ready-batch').textContent = draft.taskId ? 'Retry sending →' : 'Ready →';
  for (const photo of draft.photos) {
    const card = document.createElement('div'); card.className = 'batch-photo';
    const img = document.createElement('img'); img.alt = photo.name;
    img.src = URL.createObjectURL(photo.blob); photoUrls.push(img.src);
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', `Remove ${photo.name}`);
    remove.addEventListener('click', async () => {
      if (uploading || draft.taskId) return;
      draft.photos = draft.photos.filter((item) => item.id !== photo.id);
      try { await persistDraft(); renderDraft(); } catch (error) { toast(error.message); }
    });
    const name = document.createElement('span'); name.textContent = photo.complete ? '✓ Uploaded' : photo.name;
    card.append(img, remove, name); $('batch-photos').append(card);
  }
  setBatchDisabled(uploading);
  if (draft.taskId) {
    $('batch-title').disabled = true; $('batch-notes').disabled = true;
    $('add-photo').disabled = true; $('add-files').disabled = true;
    $('batch-status').textContent = 'Sending was interrupted. Tap Retry to finish this same task.';
  }
}
async function startCapture(openCamera = true) {
  if (!draftDB) { toast('Device storage is unavailable. Enable browser storage and reload.'); return; }
  if (!draft) {
    draft = { id: uid(), title: '', notes: '', photos: [], taskId: null };
    try { await persistDraft(); } catch (error) { toast(error.message); return; }
  }
  renderDraft(); $('batch').scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (openCamera && !draft.taskId) $('camera-input').click();
}
async function addPhotos(input) {
  const files = Array.from(input.files || []); input.value = '';
  if (!draft || uploading || draft.taskId) return;
  for (const file of files) {
    if (!file.type.startsWith('image/')) { toast(`${file.name} is not an image.`); continue; }
    if (file.size > 25 * 1024 * 1024) { toast(`${file.name} is larger than 25 MB.`); continue; }
    if (draft.photos.length >= 50) { toast('A batch can contain up to 50 photos. Send this batch before adding more.'); break; }
    draft.photos.push({ id: uid(), name: file.name || 'capture.jpg', type: file.type, size: file.size, blob: file, complete: false });
  }
  try { await persistDraft(); renderDraft(); } catch (error) { toast(error.message); renderDraft(); }
}
async function sendBatch() {
  if (uploading || !draft?.photos.length) return;
  uploading = true; setBatchDisabled(true);
  const current = draft;
  try {
    current.title = $('batch-title').value.trim() || `Photo capture · ${new Date().toLocaleDateString()}`;
    current.notes = $('batch-notes').value;
    await persistDraft();
    $('batch-status').textContent = 'Creating your task…';
    if (!current.taskId) {
      const response = await api('/api/tasks', { method: 'POST', headers: { 'Idempotency-Key': current.id }, body: JSON.stringify({ title: current.title, notes: current.notes, status: 'uploading' }) });
      current.taskId = (response.task || response).id;
      if (!current.taskId) throw new Error('The server did not return a task ID.');
      await persistDraft();
    }
    for (let index = 0; index < current.photos.length; index++) {
      const photo = current.photos[index];
      if (photo.complete) continue;
      $('batch-status').textContent = `Sending photo ${index + 1} of ${current.photos.length}… Keep this page open.`;
      const reservation = await api(`/api/tasks/${encodeURIComponent(current.taskId)}/uploads`, { method: 'POST', headers: { 'Idempotency-Key': photo.id }, body: JSON.stringify({ name: photo.name, content_type: photo.type, size: photo.size }) });
      photo.fileId = reservation.file_id; await persistDraft();
      if (!reservation.completed) {
        const response = await fetch(reservation.upload_url, { method: 'PUT', headers: { 'Content-Type': photo.type }, body: photo.blob });
        if (!response.ok) throw new Error(`Photo ${index + 1} failed to upload. Your batch is saved; tap Retry.`);
        await api(`/api/tasks/${encodeURIComponent(current.taskId)}/uploads/${encodeURIComponent(photo.fileId)}/complete`, { method: 'POST', body: '{}' });
      }
      photo.complete = true; await persistDraft();
    }
    $('batch-status').textContent = 'Making the task ready for your agents…';
    await api(`/api/tasks/${encodeURIComponent(current.taskId)}`, { method: 'PATCH', body: JSON.stringify({ status: 'todo', publish: true }) });
    draft = null; await persistDraft(); renderDraft(); toast('Ready. Your photos are one task in the queue.'); await loadTasks();
  } catch (error) {
    $('batch-status').textContent = `${error.message} Your batch is saved. Tap Retry to continue.`;
    toast(error.message);
  } finally {
    uploading = false; renderDraft();
    if (draft) $('batch-status').textContent = draft.taskId ? 'Your batch is saved. Tap Retry to finish sending it.' : 'Your batch is saved. Tap Ready to try again.';
  }
}
const taskCards = new Map();
let tasksRequest = null, taskPollTimer = null;
function updateTaskCard(task) {
  let entry = taskCards.get(task.id);
  if (!entry) {
    const card = document.createElement('article'); card.className = 'task-card';
    const body = document.createElement('div'); body.className = 'task-body';
    const meta = document.createElement('div'); meta.className = 'task-meta';
    const status = document.createElement('span');
    const count = document.createElement('span'); meta.append(status, count);
    const title = document.createElement('h3');
    const notes = document.createElement('p'); notes.className = 'task-notes';
    const id = document.createElement('div'); id.className = 'task-bottom task-id'; id.textContent = `Task ${task.id}`;
    body.append(meta, title, notes, id); card.append(body);
    entry = { card, body, status, count, title, notes, previewId: null, preview: null, files: null, filesSignature: null };
    taskCards.set(task.id, entry);
  }
  // Update individual fields without detaching the image, even when an agent changes status.
  const statusText = ({ todo: 'To do', claimed: 'In progress', done: 'Done' })[task.status] || task.status;
  if (entry.status.textContent !== statusText) entry.status.textContent = statusText;
  if (entry.status.className !== `status ${task.status}`) entry.status.className = `status ${task.status}`;
  const countText = `${(task.files || []).length} photos`;
  if (entry.count.textContent !== countText) entry.count.textContent = countText;
  if (entry.title.textContent !== task.title) entry.title.textContent = task.title;
  const notesText = task.notes || 'Ready for your agent.';
  if (entry.notes.textContent !== notesText) entry.notes.textContent = notesText;
  const firstPhoto = (task.files || []).find((file) => file.content_type?.startsWith('image/'));
  if (entry.previewId !== (firstPhoto?.id || null)) {
    entry.preview?.remove(); entry.preview = null; entry.previewId = firstPhoto?.id || null;
    if (firstPhoto) {
      const preview = document.createElement('div'); preview.className = 'task-image';
      const image = document.createElement('img'); image.alt = task.title; image.loading = 'lazy';
      preview.append(image); entry.card.prepend(preview); entry.preview = preview;
      const invalidatePreview = () => {
        if (entry.preview !== preview) return;
        preview.remove(); entry.preview = null; entry.previewId = null;
      };
      // Retry failed URL requests or expired lazy-image URLs on the next normal poll.
      image.addEventListener('error', invalidatePreview);
      // A signed URL is needed only when the attachment changes, not for each inbox poll.
      api(`/api/tasks/${encodeURIComponent(task.id)}/files/${encodeURIComponent(firstPhoto.id)}`).then((data) => {
        if (entry.preview === preview) image.src = data.download_url;
      }).catch(invalidatePreview);
    }
  } else if (entry.preview) {
    const image = entry.preview.querySelector('img');
    if (image.alt !== task.title) image.alt = task.title;
  }
  const filesSignature = JSON.stringify((task.files || []).map((file) => [file.id, file.name]));
  if (filesSignature !== entry.filesSignature) {
    entry.files?.remove(); entry.files = null; entry.filesSignature = filesSignature;
    if ((task.files || []).length) {
      const files = document.createElement('div'); files.className = 'task-files';
      for (const file of task.files) {
        const button = document.createElement('button'); button.className = 'text-link'; button.textContent = file.name || 'Open photo';
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            const data = await api(`/api/tasks/${encodeURIComponent(task.id)}/files/${encodeURIComponent(file.id)}`);
            const link = document.createElement('a'); link.href = data.download_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.click();
          } catch (error) { toast(error.message); } finally { button.disabled = false; }
        });
        files.append(button);
      }
      entry.body.append(files); entry.files = files;
    }
  }
  return entry.card;
}
async function loadTasks() {
  // Coalesce overlapping manual refreshes and polls to prevent stale response reordering.
  if (tasksRequest) return tasksRequest;
  tasksRequest = (async () => {
    try {
      const data = await api('/api/tasks');
      const tasks = (data.tasks || []).filter((task) => task.status !== 'uploading').slice(0, 12);
      $('empty').hidden = tasks.length > 0;
      $('live-label').textContent = 'Live queue';
      const activeIds = new Set(tasks.map((task) => task.id));
      for (const [id, entry] of taskCards) {
        if (!activeIds.has(id)) { entry.card.remove(); taskCards.delete(id); }
      }
      for (const [index, task] of tasks.entries()) {
        const card = updateTaskCard(task);
        // Leave correctly ordered cards in place; only insert new or reordered tasks.
        if ($('tasks').children[index] !== card) $('tasks').insertBefore(card, $('tasks').children[index] || null);
      }
    } catch (error) { $('live-label').textContent = 'Reconnecting'; if (!$('tasks').children.length) toast(error.message); }
    finally { tasksRequest = null; }
  })();
  return tasksRequest;
}
async function initializeCapture(user) {
  draftKey = user.id || user.sub || user.email;
  if (!draftKey) throw new Error('The server did not identify your workspace.');
  try {
    draftDB = await new Promise((resolve, reject) => {
      const request = indexedDB.open('snaptask-drafts', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('drafts');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    draft = await dbRequest(draftDB.transaction('drafts', 'readonly'), (store) => store.get(draftKey)) || null;
    renderDraft();
  } catch (error) { toast('Browser storage is unavailable. Enable it to save photo batches.'); }
  await loadTasks();
  if (taskPollTimer) clearInterval(taskPollTimer);
  taskPollTimer = setInterval(() => { if (!document.hidden && !$('capture-workspace').hidden && !uploading) loadTasks(); }, 10000);
}
$('start-capture').addEventListener('click', () => startCapture());
$('empty-capture').addEventListener('click', () => startCapture());
$('add-photo').addEventListener('click', () => $('camera-input').click());
$('add-files').addEventListener('click', () => $('file-input').click());
$('camera-input').addEventListener('change', () => addPhotos($('camera-input')));
$('file-input').addEventListener('change', () => addPhotos($('file-input')));
$('ready-batch').addEventListener('click', () => {
  if (navigator.locks) navigator.locks.request('snaptask-send-batch', { ifAvailable: true }, (lock) => lock ? sendBatch() : toast('This batch is already sending in another tab.'));
  else sendBatch();
});
for (const id of ['batch-title', 'batch-notes']) $(id).addEventListener('input', () => {
  if (!draft || uploading || draft.taskId) return;
  draft.title = $('batch-title').value; draft.notes = $('batch-notes').value;
  persistDraft().catch((error) => toast(error.message));
});
$('discard-batch').addEventListener('click', async () => {
  if (uploading || !draft || !window.confirm('Discard this batch and its locally saved photos?')) return;
  try {
    if (draft.taskId) await api(`/api/tasks/${encodeURIComponent(draft.taskId)}`, { method: 'DELETE' });
    draft = null; await persistDraft(); renderDraft();
  } catch (error) { toast(error.message); }
});
$('connections-toggle').addEventListener('click', () => {
  const show = $('workspace').hidden;
  $('workspace').hidden = !show; $('capture-workspace').hidden = show;
  $('connections-toggle').textContent = show ? 'Captures' : 'Connections';
  window.scrollTo(0, 0);
});
$('back-capture').addEventListener('click', () => {
  $('workspace').hidden = true; $('capture-workspace').hidden = false;
  $('connections-toggle').textContent = 'Connections'; window.scrollTo(0, 0); loadTasks();
});
