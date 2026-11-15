// FR739: stable shells, uniform unresolved values and whole-observation retention.
module.exports = (selector, root = 'document', expectedCosts = 'null') => `(() => {
  const cards=[...${root}.querySelectorAll(${JSON.stringify(selector)})];
  const cost=new Set(['hourly-rate','total-cost','subagent-cost','average-cost','expensive-session']);
  const expected=${expectedCosts};
  return cards.length===13 && cards.every(card => {
    const values=[...card.querySelectorAll('.ai-stat-value')]
      .map(value=>value.textContent);
    return values.length>0 && !!card.querySelector('h4') && !!card.querySelector('.ai-stat-icon') &&
      !/N\\/A|Not Applicable/i.test(card.textContent) &&
      (expected ? cost.has(card.dataset.metric) ?
        JSON.stringify(values)===JSON.stringify(expected[card.dataset.metric]) :
        values.every(value=>value!=='Loading…') :
        values.every(value=>value==='Loading…') && !card.querySelector('.ai-stat-racer'));
  });
})()`;
