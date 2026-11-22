// A value slot in the VM DOM: no visible loading copy or second indicator.
const assert = require('node:assert/strict');
module.exports = (slot, name) => {
  assert.equal(slot.textContent, '');
  const [spinner] = slot.children;
  assert.equal(slot.children.length, 1);
  assert.equal(spinner.className, 'metric-spinner');
  assert.equal(spinner.getAttribute('role'), 'img');
  assert.equal(spinner.getAttribute('aria-label'), `Loading ${name}`);
  assert.equal(spinner.getAttribute('tabindex'), null);
  return spinner;
};
