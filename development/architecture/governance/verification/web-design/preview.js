'use strict';
const view = new URLSearchParams(location.search).get('view') || 'overview';
const state = {section: view, pages: {}};
const output = document.getElementById('result');
document.getElementById('heading').textContent = view[0].toUpperCase() + view.slice(1);
if (view === 'watch' && !document.querySelector('nav a[href="#/watch"]')) document.getElementById('heading').textContent = 'Live';
document.getElementById('status').textContent = 'Synthetic fixture · HTTP/source/account status not measured';
document.getElementById('notice').textContent = 'Visual review fixture only · no real accounts, source or acquisition';
output.setAttribute('aria-busy', 'false');
const draw = () => view === 'watch' ? ReportView.renderLive(output, WATCH, state) :
  ReportView.render(output, view === 'sessions' ? SESSIONS : NORMAL, state);
draw();
for (const a of document.querySelectorAll('nav a')) {
  if (a.hash === '#/' + view || view === 'watch' && a.hash === '#/live') a.setAttribute('aria-current', 'page');
  a.addEventListener('click', event => event.preventDefault());
}
document.getElementById('search').addEventListener('input', event => {state.search = event.target.value; state.pages = {}; draw();});
document.getElementById('skip').addEventListener('click', () => document.getElementById('content').focus());
