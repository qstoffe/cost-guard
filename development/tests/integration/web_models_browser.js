'use strict';
// Real browser layout and interactions; pricing and membership come from Python fixtures.
(() => {
  const checks = [];
  const check = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
  const output = document.getElementById('result'), controls = document.getElementById('scope-controls');
  try {
    for (const view of INPUT) {
      const state = {pages: {}, section: 'models'};
      ReportRoutes.controls(controls, {section: 'models', request: {kind: view.kind}});
      ReportView.render(output, {view, observed_at_ms: 1, source: {status: 'acquired'}}, state);
      const table = output.querySelector('table'), rows = () => [...table.tBodies[0].rows];
      const expected = view.model_comparison.map(row => row.model);
      check(JSON.stringify(rows().map(row => row.cells[1].textContent.split(' · ')[0])) === JSON.stringify(expected), 'CLI membership/default order ' + view.kind);
      check(controls.querySelectorAll('[aria-current="page"]').length === 1, 'one active catalog control');
      const old = rows().find(row => row.cells[1].textContent.startsWith('GPT-5.1'));
      check(old.classList.contains('superseded') && old.querySelector('.promotion'), 'superseded and promotion roles coexist');
      check(old.cells[2].textContent === (view.model_comparison_sample_size ? '*1 8.0x → 16.0x (>200K) → 32.0x (≥1M)' : '*1 '), 'formatted multipliers and blank fallback');
      const positions = rows().map(row => row.querySelector('.model-ratio').getBoundingClientRect().right);
      check(Math.max(...positions) - Math.min(...positions) < 1, 'base ratios right aligned across tiers');
      check(getComputedStyle(old.cells[1]).textAlign === 'left' && getComputedStyle(old.cells[2]).textAlign === 'right', 'name/numeric alignment');
      check(document.documentElement.scrollWidth <= innerWidth, 'no document overflow ' + view.kind);
      const scroll = output.querySelector('.table-scroll');
      if (innerWidth < 500) {
        check(scroll.scrollWidth > scroll.clientWidth, 'narrow table scrolls internally');
        scroll.scrollLeft = scroll.scrollWidth;
        check(scroll.scrollLeft > 0, 'horizontal table scrolling works');
      }
      if (view.kind === 'all-models') check(table.textContent.includes('2.1234567890123456789'), 'exact native published digits');
      const modelButton = [...table.querySelectorAll('th button')].find(button => button.textContent === 'Model');
      modelButton.click(); modelButton.click(); modelButton.click();
      check(JSON.stringify(rows().map(row => row.cells[1].textContent.split(' · ')[0])) === JSON.stringify(expected), 'sort cycle restores server order');
      const filter = output.querySelector('input');
      filter.value = 'Precision-'; filter.dispatchEvent(new Event('input'));
      check(rows().length === 1 && rows()[0].cells[1].textContent.length > 100, 'long model stays complete under filter');
      filter.value = ''; filter.dispatchEvent(new Event('input'));
    }
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'PASS', checks,
      width: innerWidth, background: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()});
  } catch (error) {
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'FAIL', checks, reason: error.message});
  }
})();
