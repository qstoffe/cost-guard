'use strict';
// Real DOM/layout/selection over identical canonical fixtures, never user history.
(async () => {
  const checks = [];
  const check = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
  const state = {connection: 'Live connected.'};
  const output = document.getElementById('result');
  const data = structuredClone(INPUT);
  const draw = () => ReportView.renderLive(output, data, state);
  try {
    draw();
    const watch = state.watch;
    const rows = () => [...watch.body.children].filter(r => r.dataset.id?.startsWith('['));
    check(output.querySelectorAll('table').length === 1 && output.querySelectorAll('.watch-session').length === 2, 'one table, multiple inline sessions, no quota tables');
    check(JSON.stringify(rows().map(r => r.cells[2].textContent)) === JSON.stringify(data.view.rows.map(r => r.prompt.display.ccost)), 'canonical row order and shared display values');
    const row = rows()[0], cell = row.cells[0];
    const range = document.createRange(); range.selectNodeContents(cell);
    const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
    const selected = selection.toString();
    data.view.rows[0].prompt.preview = 'Changed running activity';
    draw();
    check(selection.toString() === selected && row.cells[0] === cell, 'selected text survives a changed publication');
    selection.removeAllRanges(); draw();
    check(watch.body.textContent.includes('Changed running activity'), 'latest pending values apply after selection');
    watch.filter.focus(); const filter = watch.filter; draw();
    check(document.activeElement === filter && filter === watch.filter, 'keyboard focus and controls persist');
    filter.value = 'Second synthetic session'; filter.dispatchEvent(new Event('input'));
    check(rows().length === 1, 'one stable session-aware filter');
    filter.value = ''; filter.dispatchEvent(new Event('input'));
    const sample = data.view.rows[0];
    data.view.rows = Array.from({length: 125}, (_, n) => ({...sample, prompt: {...sample.prompt, event_id: 'event-' + n, prompt_number: n}}));
    draw(); watch.next.click(); const anchor = rows()[0];
    watch.scroll.scrollTop = 150; const anchorTop = anchor.getBoundingClientRect().top; draw();
    check(watch.page === 1 && rows().length === 50 && rows()[0] === anchor && Math.abs(anchor.getBoundingClientRect().top - anchorTop) < 1, 'bounded pagination and scroll anchor persist');
    data.view.rows[50].prompt = {...data.view.rows[50].prompt, aborted: true, in_progress: false}; draw();
    check(watch.body.textContent.includes('Aborted'), 'aborted lifecycle remains explicit');
    data.view.rows[50].prompt = {...data.view.rows[50].prompt, is_compaction: true}; draw();
    check(watch.body.querySelector('.compaction'), 'compaction role remains visible');
    data.view.active_count = 0; draw();
    check(watch.status.textContent.includes('Idle'), 'idle is not completion');
    data.state = 'recovering'; draw();
    check(watch.status.textContent.includes('Stale / retained') && !watch.status.textContent.includes('Updating'), 'slow/unavailable source is not fresh');
    // Exercise shipped connection ordering and terminal closure in the real browser.
    const streams = []; let snapshot = {instance_id: 'fixture', sequence: 0, values: {live: data}};
    let publications = 0, statuses = [];
    const connection = LiveConnection.connect(async () => structuredClone(snapshot), value => {
      publications++; Object.assign(data, value); draw();
    }, message => { statuses.push(message); state.connection = message; draw(); }, () => {
      const stream = {listeners: {}, closed: false, close() { this.closed = true; },
        addEventListener(name, fn) { this.listeners[name] = fn; },
        emit(name, number, value) { this.listeners[name]({lastEventId: 'fixture:' + number, data: JSON.stringify(value)}); }};
      streams.push(stream); return stream;
    });
    for (let n = 0; n < 12; n++) await Promise.resolve();
    const stream = streams[0]; stream.onopen();
    for (let n = 0; n < 12; n++) await Promise.resolve();
    stream.emit('live', 1, data); const count = publications;
    stream.emit('live', 1, {view: null});
    check(publications === count, 'duplicate events cannot duplicate rows');
    snapshot.sequence = 9; stream.emit('live', 9, {view: null});
    for (let n = 0; n < 12; n++) await Promise.resolve();
    check(data.view && streams.length === 1, 'replay gap resync retains one connection owner');
    stream.onerror();
    check(watch.status.textContent.includes('offline') && rows().length === 50, 'offline retains accumulated rows');
    stream.onopen();
    for (let n = 0; n < 12; n++) await Promise.resolve();
    check(statuses.includes('Live connected.'), 'reconnect restores transport status');
    stream.emit('terminal', 20, {reason: 'source_changed'});
    check(stream.closed && watch.status.textContent.includes('host stopped') && rows().length === 50, 'terminal stop preserves rows and ends retry');
    connection.close();
    check(document.documentElement.scrollWidth <= innerWidth, 'no page overflow at measured viewport');
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'PASS', checks,
      width: innerWidth, background: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()});
  } catch (error) {
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'FAIL', checks, reason: error.message});
  }
})();
