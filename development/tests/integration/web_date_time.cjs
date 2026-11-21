// Shared Python/browser vectors. Runs without a browser in the ordinary unit suite.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const vectors = require('../fixtures/date_time_vectors.json');

function checkVectors() {
  return vectors.flatMap(({utc, calendar, zone, expected}) =>
    Object.entries(expected).map(([mode, wanted]) => ({
      zone, mode, utc, calendar, wanted: wanted ?? 'N/A',
      actual: ReportView.formatDateTime(utc ? Date.parse(utc) : calendar, ReportView.DateTimeMode[mode], zone)
    })));
}

const expression = `(${checkVectors})()`;
function verify(results) {
  for (const {actual, wanted, ...vector} of results)
    assert.equal(actual, wanted, JSON.stringify(vector));
}

module.exports = {expression, verify, vectors};

if (require.main === module) {
  const source = fs.readFileSync('src/web/assets/render.js', 'utf8');
  verify(vm.runInNewContext(`${source}\nconst vectors = ${JSON.stringify(vectors)};\n${expression}`));
}
