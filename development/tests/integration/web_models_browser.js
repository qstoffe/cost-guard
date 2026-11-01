'use strict';
// Real layout and controls over frozen canonical synthetic data; no price arithmetic.
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
      const names = () => rows().map(row => row.cells[1].textContent);
      const inputs = output.querySelectorAll('input[type="checkbox"]');
      const toggle = (index, value) => { inputs[index].checked = value; inputs[index].dispatchEvent(new Event('change')); };
      const header = index => table.tHead.rows[0].cells[index].querySelector('button');
      check(inputs.length === 2 && output.querySelector('.model-filters').querySelectorAll('button').length === 0 && !('additive' in state.models), 'two filters without additive-mode control or state');
      check(table.tHead.rows[0].cells.length === 4 && controls.children.length === 0, 'one four-column view without catalog links');
      check(!inputs[0].checked && inputs[1].checked && header(2).textContent === 'Relative CCost ↓', 'fresh filter and descending sort defaults');
      check(!names().includes('GPT-5.1') && names().includes('Unknown'), 'latest-only retains unknown prices');
      check(names().includes('Unselectable') === (view.kind === 'all-models'), 'selectable scope from frozen source');
      toggle(0, true); toggle(1, false);
      check(rows().length === view.model_catalog.rows.length, 'all priced rows, all versions, no paging');
      const old = rows().find(row => row.cells[1].textContent === 'GPT-5.1');
      check(!old.classList.contains('superseded') && old.querySelector('.promotion'), 'old stable full contrast with promotion');
      check(old.cells[2].textContent === (view.model_comparison_sample_size ? '*1 8.0x → 16.0x (>200K) → 32.0x (≥1M)' : '*1 '), 'canonical tiers and blank fallback');
      const details = output.querySelector('details');
      check(!details.open && details.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_PRECEDING, 'collapsed More information below table');
      check(output.textContent.includes('*1 Fixture promotional terms'), 'visible matching promotion note');
      check(table.tBodies[0].scrollHeight <= table.tBodies[0].clientHeight + 1, 'no nested vertical body scrolling');
      check(document.documentElement.scrollWidth <= innerWidth, 'no document horizontal overflow');
      const scroll = output.querySelector('.overview-models');
      if (innerWidth < 500) {
        check(scroll.scrollWidth > scroll.clientWidth, 'necessary narrow horizontal overflow');
        scroll.scrollLeft = scroll.scrollWidth;
        check(scroll.scrollLeft > 0, 'horizontal scrolling works');
      } else {
        const main = document.querySelector('main'), style = getComputedStyle(main), box = scroll.getBoundingClientRect();
        const available = main.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
        check(Math.abs(box.width - available) < 1, 'wide table uses full main content width');
      }
      const long = rows().find(row => row.cells[1].textContent.startsWith('Precision-'));
      check(long.cells[1].textContent.length > 100, 'long name remains complete');
      header(1).click();
      check(header(1).textContent === 'Model ↑' && header(2).textContent === 'Relative CCost ↕', 'ordinary click replaces sort');
      header(0).dispatchEvent(new MouseEvent('click', {shiftKey: true}));
      header(3).dispatchEvent(new KeyboardEvent('keydown', {key: ' ', shiftKey: true, cancelable: true}));
      check(header(0).textContent === 'Publisher ↑ 2' && header(3).textContent === 'Release date ↑ 3', 'Shift mouse and keyboard additive keys');
      check(table.tHead.rows[0].cells[1].getAttribute('aria-sort') === 'ascending' && table.tHead.rows[0].cells[0].getAttribute('aria-sort') === 'none', 'primary-only aria-sort');
      header(3).dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', shiftKey: true, cancelable: true}));
      check(header(3).textContent === 'Release date ↓ 3', 'Shift Enter toggles tertiary direction');
      toggle(1, true);
      check(!names().includes('GPT-5.1') && header(1).textContent === 'Model ↑ 1', 'filter preserves custom sort');
    }
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'PASS', checks,
      width: innerWidth, background: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()});
  } catch (error) {
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'FAIL', checks, reason: error.message});
  }
})();
