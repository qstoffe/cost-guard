// FR731: unknown costs are N/A; qualified same-scope costs retain exact amounts.
module.exports = (selector, root = 'document', expectedCosts = 'null') => `(() => {
  const cards=[...${root}.querySelectorAll(${JSON.stringify(selector)})];
  const cost=new Set(['hourly-rate','total-cost','subagent-cost','average-cost','expensive-session']);
  const expected=${expectedCosts};
  return cards.length===13 && cards.every(card => {
    if(!cost.has(card.dataset.metric))
      return card.textContent==='Loading…' && card.childNodes.length===1 && card.children.length===0;
    const values=[...card.querySelectorAll('.ai-stat-rate-value,.ai-stat-value:not(.ai-stat-rates)')]
      .map(value=>value.textContent);
    return values.length>0 && !!card.querySelector('.ai-stat-value') &&
      (expected ? JSON.stringify(values)===JSON.stringify(expected[card.dataset.metric]) :
        values.every(value=>value==='N/A'));
  });
})()`;
