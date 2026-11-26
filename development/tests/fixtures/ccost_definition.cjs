const assert = require('node:assert/strict');

// Independent product copy, not imported from the Web renderer.
module.exports = function ccostDefinition(help, scope) {
  const opening = 'Comparative Cost Based on GitHub Reference Price List';
  const [first, ...context] = help.split('\n');
  assert.equal(first, opening);
  const remainder = context.join('\n');
  assert.ok(!remainder.includes(opening), 'definition is not repeated');
  assert.match(remainder, scope);
};
