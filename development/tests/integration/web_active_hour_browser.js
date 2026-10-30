'use strict';
// Approval-only browser checks over synthetic HTTP. No valuation or rate calculation.
(async () => {
  const checks = [], output = document.getElementById('result');
  const check = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
  const until = async (condition, name) => {
    for (let i = 0; i < 200; i++) {
      if (condition()) return;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    throw new Error('timeout: ' + name);
  };
  const fixture = state => fetch('/fixture/state', {method: 'POST', body: JSON.stringify(state)});
  const requests = async () => (await fetch('/fixture/requests')).json();
  const captures = async () => (await requests()).filter(r => r.path === '/api/reports');
  try {
    await until(() => !document.getElementById('refresh').disabled, 'host ready');
    check((await captures()).length === 0, 'opening hourly page does not acquire history');
    const button = document.getElementById('refresh');
    button.focus(); check(document.activeElement === button && button.tagName === 'BUTTON', 'capture uses focusable semantic button');
    button.click();
    await until(() => output.textContent.includes('Reference cost per active hour:'), 'captured rates');
    check(['Today', 'Month to date', 'Rolling 30 days'].every(name => output.textContent.includes(name)), 'three visible scopes');
    check(document.documentElement.scrollWidth <= innerWidth, 'hourly document fits viewport');
    const cards = [...output.querySelectorAll('.report-concepts > div')];
    check(cards.length === 3 && cards.every(card => card.getBoundingClientRect().width > 100), 'readable responsive scope cards');
    const frozen = output.textContent, node = output.firstChild;
    document.getElementById('ccost-unit').value = 'usd';
    document.getElementById('ccost-unit').dispatchEvent(new Event('change'));
    check(output.textContent.includes('/h') && output.textContent.includes('$'), 'USD rate rendered from Python display tokens');
    check(node === output.firstChild && (await captures()).length === 1, 'unit toggle retains DOM without acquisition');
    document.getElementById('ccost-unit').value = 'credits';
    document.getElementById('ccost-unit').dispatchEvent(new Event('change'));
    check(output.textContent === frozen, 'credits restored without recomputation');
    const nav = document.querySelector('a[href="#/cost-per-hour"]');
    nav.focus(); check(document.activeElement === nav, 'hourly navigation is focusable link');
    location.hash = '#/reports'; await until(() => document.getElementById('heading').textContent === 'Date reports', 'navigate away');
    nav.click(); await until(() => document.getElementById('heading').textContent === 'Cost per Active Hour', 'navigate back');
    check(output.textContent === frozen && (await captures()).length === 1, 'navigation reuses frozen scope');
    await fixture({fail: true}); button.click();
    await until(() => document.getElementById('notice').textContent.includes('STALE'), 'failed refresh stale');
    check(output.textContent === frozen, 'failed capture retains previous rates as stale');
    await fixture({fail: false, slow: true}); button.click();
    await until(() => !document.getElementById('cancel').disabled, 'cancellable capture');
    document.getElementById('cancel').click();
    await until(() => document.getElementById('notice').textContent.includes('cancelled'), 'cancel complete');
    check(output.textContent === frozen, 'cancel retains frozen evidence');
    const calls = await requests();
    check(calls.filter(r => r.path === '/api/reports').every(r => r.kind === 'cost-per-hour'), 'view scoped jobs never request account or Watch captures');
    location.hash = '#/sessions/root/live';
    await until(() => current?.detail?.id === 'root' && current.detail.data && !current.detail.busy &&
      document.getElementById('heading').textContent === 'Session root', 'loaded session route and rate');
    const detail = current.detail;
    check(detail.data.result.view.prompt_blocks[0].active_hour.status === 'provisional', 'running session visibly provisional');
    const initial = detail.hourly.textContent;
    await detail.switchMode();
    check(detail.mode === 'snapshot', 'Freeze snapshot mode');
    await fixture({advanced: true}); await detail.load();
    check(detail.hourly.textContent === initial, 'frozen rate does not advance with source');
    await detail.switchMode();
    check(detail.mode === 'live' && detail.hourly.textContent !== initial, 'Follow live captures updated Python rate');
    await fixture({unavailable: true}); await detail.load();
    check(detail.hourly.textContent.includes('source_unavailable') && detail.hourly.textContent.includes('not proof of completion'), 'same-revision source loss marks retained rate stale');
    check(document.documentElement.scrollWidth <= innerWidth, 'session document fits viewport');
    check(detail.scroll.tabIndex === 0, 'session table has keyboard-scrollable region');
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'PASS', checks, width: innerWidth,
      background: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()});
    detail.detach(); liveConnection?.close();
  } catch (error) {
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'FAIL', checks, reason: error.message});
  }
})();
