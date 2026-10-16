/* ===== AI Engineering Course Revision — Chat UI Logic ===== */

const $ = id => document.getElementById(id);
const state = {
  results: [], selected: null, time: 0, controller: null,
  player: null, playerReady: false, pendingPlay: null, playerTimer: null,
  history: JSON.parse(localStorage.getItem('search_history') || '[]')
};

const node = (tag, cls, text) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
};

const fmt = value => {
  const s = Math.floor(value || 0);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

const displayTitle = text => text.replace(/^\d+[.:]\s*/, '');

const videoURL = (id, time = 0) =>
  `https://www.youtube.com/watch?v=${encodeURIComponent(id)}${time > 0 ? `&t=${Math.floor(time)}s` : ''}`;

/* --- History --- */
function saveHistory(query) {
  const q = query.trim();
  if (!q) return;
  state.history = state.history.filter(h => h !== q);
  state.history.unshift(q);
  if (state.history.length > 50) state.history = state.history.slice(0, 50);
  localStorage.setItem('search_history', JSON.stringify(state.history));
}

function renderHistory() {
  const list = $('history-list');
  list.replaceChildren();
  if (!state.history.length) {
    list.append(node('p', 'history-empty', 'No search history yet.'));
    return;
  }
  for (const query of state.history) {
    const btn = node('button', 'history-item', query);
    btn.type = 'button';
    btn.onclick = () => {
      $('question').value = query;
      closeHistory();
      runSearch();
    };
    list.append(btn);
  }
}

function openHistory() {
  renderHistory();
  $('history-panel').hidden = false;
}

function closeHistory() {
  $('history-panel').hidden = true;
}

/* --- URL state --- */
function updateURL() {
  const url = new URL(location.href);
  const query = $('question').value.trim();
  if (query) url.searchParams.set('q', query); else url.searchParams.delete('q');
  if (state.selected) {
    url.searchParams.set('lecture', state.selected.lecture_id);
    if (state.time > 0) url.searchParams.set('t', Math.floor(state.time)); else url.searchParams.delete('t');
  } else {
    url.searchParams.delete('lecture');
    url.searchParams.delete('t');
  }
  history.replaceState(null, '', url);
}

/* --- Chat message helpers --- */
function addChatMessage(type, contentEl) {
  const container = $('chat-messages');
  // Remove placeholder if present
  const placeholder = container.querySelector('.chat-placeholder');
  if (placeholder) placeholder.remove();

  const wrapper = node('div', `chat-msg ${type}`);
  const label = node('div', 'msg-label', type === 'user' ? 'You' : 'AI Assistant');
  const bubble = node('div', 'chat-bubble');

  if (typeof contentEl === 'string') {
    bubble.textContent = contentEl;
  } else {
    bubble.append(contentEl);
  }

  wrapper.append(label, bubble);
  container.append(wrapper);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

function addTypingIndicator() {
  const container = $('chat-messages');
  const placeholder = container.querySelector('.chat-placeholder');
  if (placeholder) placeholder.remove();

  const wrapper = node('div', 'chat-msg ai');
  wrapper.id = 'typing-msg';
  const label = node('div', 'msg-label', 'AI Assistant');
  const bubble = node('div', 'chat-bubble');
  const indicator = node('div', 'typing-indicator');
  indicator.append(node('span', 'dot'), node('span', 'dot'), node('span', 'dot'));
  bubble.append(indicator);
  wrapper.append(label, bubble);
  container.append(wrapper);
  container.scrollTop = container.scrollHeight;
  return wrapper;
}

function removeTypingIndicator() {
  const el = $('typing-msg');
  if (el) el.remove();
}

/* --- Player --- */
function closePlayer() {
  clearTimeout(state.playerTimer);
  state.pendingPlay = null;
  state.selected = null;
  state.time = 0;
  if (state.playerReady) state.player.stopVideo();
  $('player-info').hidden = true;
  $('player-placeholder').style.display = 'grid';
  $('no-video-msg').hidden = false;
  $('poster-play').hidden = true;
  $('video-thumbnail').hidden = true;
  document.querySelectorAll('.source-chip').forEach(el => el.classList.remove('is-selected'));
  updateURL();
}

function selectMoment(lecture, start = null, play = true) {
  clearTimeout(state.playerTimer);
  state.selected = lecture;
  state.time = start !== null ? Math.max(0, start - 4) : 0;

  $('player-info').hidden = false;
  $('player-title').textContent = displayTitle(lecture.title);
  $('player-note').textContent = start !== null
    ? `Starting near ${fmt(start)} · approximate time`
    : 'Exact moment unavailable. This opens from the beginning.';
  $('youtube-link').href = videoURL(lecture.video_id, state.time);

  const image = $('video-thumbnail');
  if (lecture.video_id) {
    image.hidden = false;
    image.src = `https://i.ytimg.com/vi/${encodeURIComponent(lecture.video_id)}/hqdefault.jpg`;
    $('poster-play').hidden = false;
    $('no-video-msg').hidden = true;
  } else {
    image.hidden = true;
    $('poster-play').hidden = true;
    $('no-video-msg').hidden = true;
  }

  $('player-placeholder').style.display = 'grid';
  document.querySelectorAll('.source-chip').forEach(el =>
    el.classList.toggle('is-selected', el.dataset.lectureId === lecture.lecture_id)
  );

  if (state.playerReady) state.player.stopVideo();
  updateURL();
  if (play) playSelected();
}

function fallback() {
  clearTimeout(state.playerTimer);
  $('player-placeholder').style.display = 'grid';
  $('player-note').textContent = 'Video cannot play here. Use Open on YouTube.';
}

function youtubeReady() {
  if (window.YT?.Player) return Promise.resolve();
  if (window.youtubePromise) return window.youtubePromise;
  window.youtubePromise = new Promise((resolve, reject) => {
    window.onYouTubeIframeAPIReady = resolve;
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    script.onerror = () => reject(new Error());
    document.head.append(script);
    setTimeout(() => { if (!window.YT?.Player) { window.youtubePromise = null; reject(new Error()); } }, 12000);
  });
  return window.youtubePromise;
}

async function playSelected() {
  if (!state.selected?.video_id) return;
  state.pendingPlay = { videoId: state.selected.video_id, startSeconds: state.time };
  clearTimeout(state.playerTimer);
  state.playerTimer = setTimeout(() => { if (!state.playerReady) fallback(); }, 12000);
  try {
    await youtubeReady();
    if (!state.pendingPlay) return;
    $('player-placeholder').style.display = 'none';
    if (state.playerReady) {
      state.player.loadVideoById(state.pendingPlay);
    } else if (!state.player) {
      state.player = new YT.Player('youtube-player', {
        host: 'https://www.youtube-nocookie.com',
        videoId: state.pendingPlay.videoId,
        playerVars: {
          start: Math.floor(state.pendingPlay.startSeconds),
          origin: location.origin, rel: 0, playsinline: 1
        },
        events: {
          onReady: e => {
            clearTimeout(state.playerTimer);
            state.playerReady = true;
            if (state.pendingPlay) e.target.loadVideoById(state.pendingPlay);
            else e.target.stopVideo();
          },
          onError: fallback
        }
      });
    }
  } catch { fallback(); }
}

/* --- Build source chips for chat --- */
function buildSourceChips(results) {
  if (!results.length) return null;
  const container = node('div', 'sources-in-chat');
  for (const result of results) {
    const chip = node('div', 'source-chip');
    chip.dataset.lectureId = result.lecture_id;
    chip.append(node('span', 'source-chip-title', displayTitle(result.title)));

    const moments = node('div', 'source-chip-moments');
    const seen = new Set();
    for (const passage of result.passages || []) {
      const start = passage.start;
      const key = start === null ? 'lecture' : start;
      if (seen.has(key)) continue; seen.add(key);
      const btn = node('button', 'moment-btn');
      btn.type = 'button';
      btn.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>${start !== null ? `≈ ${fmt(start)}` : 'Watch'}`;
      btn.title = start !== null ? 'Play this approximate moment' : 'Opens from the beginning';
      btn.onclick = (e) => { e.stopPropagation(); selectMoment(result, start); };
      moments.append(btn);
    }
    if (!moments.children.length) {
      const btn = node('button', 'moment-btn');
      btn.type = 'button';
      btn.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>Watch`;
      btn.onclick = (e) => { e.stopPropagation(); selectMoment(result); };
      moments.append(btn);
    }
    chip.append(moments);
    chip.onclick = () => {
      const firstPassage = result.passages?.[0];
      selectMoment(result, firstPassage?.start ?? null);
    };
    container.append(chip);
  }
  return container;
}

/* --- Load AI Answer into chat --- */
async function loadAnswer(query, controller) {
  const typingEl = addTypingIndicator();
  try {
    const response = await fetch('/api/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 3 }),
      signal: controller.signal
    });
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (state.controller !== controller) return;

    removeTypingIndicator();

    if (data.status !== 'answered') {
      const msg = data.status === 'no_evidence'
        ? "I couldn't find a clear enough explanation to answer this. You can explore the related videos below."
        : 'A short answer is unavailable right now. You can still watch the related explanation below.';
      const fragment = document.createDocumentFragment();
      fragment.append(node('p', 'answer-muted', msg));
      // Still show source chips
      const chips = buildSourceChips(state.results);
      if (chips) fragment.append(chips);
      addChatMessage('ai', fragment);
      return;
    }

    const citations = new Map(data.citations.map(c => [c.id, c]));
    const fragment = document.createDocumentFragment();

    for (const point of data.points) {
      const paragraph = node('p', '', point.text);
      paragraph.style.marginBottom = '8px';
      paragraph.style.lineHeight = '1.75';
      for (const id of point.sources) {
        const citation = citations.get(id);
        if (!citation) continue;
        const ref = node('button', 'answer-ref', `[${id.slice(1)}]`);
        ref.type = 'button';
        ref.title = displayTitle(citation.title);
        ref.onclick = () => {
          const lecture = state.results.find(r => r.lecture_id === citation.lecture_id);
          if (lecture) selectMoment(lecture, citation.start);
        };
        paragraph.append(ref);
      }
      fragment.append(paragraph);
    }

    // Add source chips
    const chips = buildSourceChips(state.results);
    if (chips) fragment.append(chips);

    addChatMessage('ai', fragment);

  } catch (error) {
    if (error.name !== 'AbortError' && state.controller === controller) {
      removeTypingIndicator();
      addChatMessage('ai', 'A short answer is unavailable right now. You can still watch the related explanation below.');
    }
  }
}

/* --- Main Search --- */
async function runSearch(shared = null) {
  const query = $('question').value.trim();
  if (state.controller) state.controller.abort();
  state.controller = null;

  if (query.length < 2) {
    addChatMessage('ai', 'Please enter a question with at least 2 characters.');
    $('submit').disabled = false;
    return;
  }

  // Add user message to chat
  addChatMessage('user', query);
  saveHistory(query);

  const controller = new AbortController();
  state.controller = controller;

  $('submit').disabled = true;
  $('submit').textContent = '...';
  $('question').value = '';
  updateURL();

  // Show typing indicator while searching
  const typingEl = addTypingIndicator();

  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 3 }),
      signal: controller.signal
    });
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (state.controller !== controller) return;

    state.results = data.results;
    removeTypingIndicator();

    if (!data.results.length) {
      addChatMessage('ai', 'No clear match found. Try a more specific question.');
      return;
    }

    // Auto-select first result if shared
    if (shared) {
      const selected = data.results.find(r => r.lecture_id === shared.lecture);
      if (selected) {
        const time = Number(shared.time);
        const usable = selected.timestamp_status === 'approximate' && Number.isFinite(time) && time >= 0 && time < selected.duration;
        selectMoment(selected, usable && time > 0 ? time + 4 : null, false);
      }
    }

    // Load AI answer
    loadAnswer(query, controller);

  } catch (error) {
    if (error.name !== 'AbortError' && state.controller === controller) {
      removeTypingIndicator();
      addChatMessage('ai', "Couldn't search right now. Please try again.");
    }
  } finally {
    if (state.controller === controller) {
      $('submit').disabled = false;
      $('submit').textContent = 'Ask';
    }
  }
}

/* --- Event Listeners --- */
$('search-form').onsubmit = e => { e.preventDefault(); runSearch(); };
$('poster-play').onclick = playSelected;
$('close-player').onclick = closePlayer;
$('video-thumbnail').onerror = () => { $('video-thumbnail').hidden = true; };
$('history-btn').onclick = openHistory;
$('close-history').onclick = closeHistory;

// Close history on backdrop click
document.querySelector('.history-backdrop')?.addEventListener('click', closeHistory);

// URL params
const params = new URLSearchParams(location.search);
if (params.get('q')) {
  $('question').value = params.get('q').slice(0, 500);
  runSearch({ lecture: params.get('lecture'), time: params.get('t') });
}
