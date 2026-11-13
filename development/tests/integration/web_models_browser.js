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
      const inputs = output.querySelectorAll('.model-tools:not(.benchmark-tools) input[type="checkbox"]');
      const toggle = (index, value) => { inputs[index].checked = value; inputs[index].dispatchEvent(new Event('change')); };
      const header = index => table.tHead.rows[0].cells[index].querySelector('button');
      check(inputs.length === 2 && output.querySelector('.model-filters').querySelectorAll('button').length === 0 && !('additive' in state.models), 'two filters without additive-mode control or state');
      check(table.tHead.rows[0].cells.length === 4 && controls.children.length === 0, 'one four-column view without catalog links');
       check(!inputs[0].checked && inputs[1].checked && header(2).textContent === 'Relative Price List Cost ↓', 'fresh filter and descending sort defaults');
      check(!names().includes('GPT-5.1') && names().includes('Unknown'), 'latest-only retains unknown prices');
      check(names().includes('Unselectable') === (view.kind === 'all-models'), 'selectable scope from frozen source');
      toggle(0, true); toggle(1, false);
      check(rows().length === view.model_catalog.rows.length, 'all priced rows, all versions, no paging');
      const old = rows().find(row => row.cells[1].textContent === 'GPT-5.1');
      check(!old.classList.contains('superseded') && old.querySelector('.promotion'), 'old stable full contrast with promotion');
       check(old.cells[2].textContent === (view.model_comparison_sample_size ? '8.0x → 16.0x (>200K) → 32.0x (≥1M) *' : ' *'), 'canonical tiers and one postfix star');
       check(!output.querySelector('details:not(.effort-picker)') && !output.textContent.includes('More information'), 'Models explanation cards removed');
       const refresh = output.querySelector('[data-model-control="refresh"]');
         check(refresh.textContent === 'Refresh price list' && refresh.nextSibling.textContent.startsWith('Last fetched:'), 'button precedes true fetch timestamp');
       check(!output.textContent.includes('*1 Fixture promotional terms') && !old.cells[2].querySelector('[title]'), 'no promotion footer or native duplicate tooltip');
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
       check(header(1).textContent === 'Model ↑' && header(2).textContent === 'Relative Price List Cost ↕', 'ordinary click replaces sort');
      header(0).dispatchEvent(new MouseEvent('click', {shiftKey: true}));
      header(3).dispatchEvent(new KeyboardEvent('keydown', {key: ' ', shiftKey: true, cancelable: true}));
      check(header(0).textContent === 'Publisher ↑ 2' && header(3).textContent === 'Release date ↑ 3', 'Shift mouse and keyboard additive keys');
      check(table.tHead.rows[0].cells[1].getAttribute('aria-sort') === 'ascending' && table.tHead.rows[0].cells[0].getAttribute('aria-sort') === 'none', 'primary-only aria-sort');
      header(3).dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', shiftKey: true, cancelable: true}));
      check(header(3).textContent === 'Release date ↓ 3', 'Shift Enter toggles tertiary direction');
      toggle(1, true);
       check(!names().includes('GPT-5.1') && header(1).textContent === 'Model ↑ 1', 'filter preserves custom sort');
       state.benchmark.data = BENCHMARK; state.benchmark.draw();
       const benchmark = output.querySelector('.benchmark-table');
       check(output.querySelectorAll('h2').length === 3 && benchmark.tHead.rows[0].cells.length === 5, 'two independent tables plus More Coding Benchmarks');
        const more = output.querySelector('.more-benchmarks'), external = more.querySelector('a'), appearance = getComputedStyle(more);
       check(more.className === 'more-benchmarks' && more.querySelectorAll('a').length === 1 && !more.querySelector('table,button,input'), 'final link-only section');
       check(appearance.borderTopWidth === '0px' && appearance.backgroundColor === 'rgba(0, 0, 0, 0)' && appearance.paddingTop === '0px', 'unboxed comparison link');
       check(external.href === 'https://artificialanalysis.ai/agents/coding-agents/' && external.target === '_blank' && external.rel === 'noopener noreferrer', 'safe official comparison destination');
       external.focus(); check(document.activeElement === external, 'keyboard-accessible external link');
       check(benchmark.tBodies[0].rows.length === 4 && benchmark.tBodies[0].rows[0].cells[3].textContent === '2.0x', 'matched configurations default solved descending');
       const before = names().join('|'), referenceSort = JSON.stringify(state.models);
       benchmark.tHead.querySelector('button').click();
       check(names().join('|') === before && JSON.stringify(state.models) === referenceSort, 'benchmark sorting cannot reorder reference pricing');
       check(!benchmark.querySelector('.promotion'), 'no benchmark price promotion');
       for (const theme of ['classic', 'web']) for (const zoom of [1, 1.25]) {
         document.documentElement.dataset.theme = theme; document.documentElement.style.zoom = zoom;
          const pan = output.querySelector('.benchmark-scroll');
          const sectionStyle = getComputedStyle(output.querySelector('.benchmark-section'));
          check(sectionStyle.borderTopWidth === '0px' && sectionStyle.backgroundColor === 'rgba(0, 0, 0, 0)' && sectionStyle.paddingTop === '0px', 'unboxed benchmark '+theme+' '+zoom);
          check(getComputedStyle(pan).borderTopWidth === getComputedStyle(scroll).borderTopWidth && parseFloat(getComputedStyle(pan).borderTopWidth)>0 && getComputedStyle(pan).backgroundColor === getComputedStyle(scroll).backgroundColor, 'shared table frame '+theme+' '+zoom);
          const last = benchmark.tHead.rows[0].cells[4].getBoundingClientRect(), first = benchmark.tHead.rows[0].cells[0].getBoundingClientRect();
          check(benchmark.tHead.rows[0].cells[0].scrollWidth === benchmark.tHead.rows[0].cells[0].clientWidth && last.width > 0 && first.width > 0, 'intrinsic readable tracks '+theme+' '+zoom);
         check(pan.clientHeight >= benchmark.clientHeight && getComputedStyle(pan).overflowY !== 'scroll', 'benchmark document vertical scrolling '+theme+' '+zoom);
         if (innerWidth < 500) {
           pan.scrollLeft = pan.scrollWidth;
           check(pan.scrollLeft > 0 && pan.scrollWidth > pan.clientWidth, 'benchmark narrow pan '+theme+' '+zoom);
         }
         for (const th of benchmark.tHead.rows[0].cells) {
           const button = th.querySelector('button'), label = button.querySelector('.help-label');
           check(!!label && getComputedStyle(label).cursor === 'pointer', 'intrinsic sortable benchmark help '+theme+' '+zoom);
           check(button.getBoundingClientRect().width >= label.getBoundingClientRect().width, 'header label fits action '+theme+' '+zoom);
         }
       }
        document.documentElement.style.zoom = 1;
        const b = state.benchmark, effortInputs = [...b.options.querySelectorAll('input')];
        effortInputs.forEach(input=>{input.checked=false;input.dispatchEvent(new Event('change'));});
        check(b.body.rows.length===0 && b.empty.textContent==='No matching benchmark rows','zero effort selection is retained');
        const high = [...b.options.querySelectorAll('label')].find(label=>label.textContent==='High').querySelector('input');
        high.checked=true;high.dispatchEvent(new Event('change'));
        check(b.body.rows.length===1 && b.body.rows[0].cells[2].textContent==='high','source-backed High only');
        b.picker.open=true; document.body.click(); check(!b.picker.open,'outside-click dismisses effort menu');
        b.picker.open=true;b.picker.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
        check(!b.picker.open && document.activeElement===b.summary,'Escape restores summary focus');
        check(b.body.rows[0].cells[1].querySelector('[tabindex="0"]') && b.body.rows[0].cells[3].querySelector('[tabindex="0"]'),'intrinsic model and task value keyboard help');
     }
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'PASS', checks,
      width: innerWidth, background: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()});
  } catch (error) {
    top.document.getElementById('probe').textContent = JSON.stringify({outcome: 'FAIL', checks, reason: error.message});
  }
})();
