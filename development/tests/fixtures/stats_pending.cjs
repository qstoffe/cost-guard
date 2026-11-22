// FR739: stable shells, uniform unresolved values and whole-observation retention.
module.exports = (selector, root = 'document', expectedCosts = 'null') => `(() => {
  const cards=[...${root}.querySelectorAll(${JSON.stringify(selector)})];
  const cost=new Set(['hourly-rate','total-cost','subagent-cost','average-cost','expensive-session']);
  const expected=${expectedCosts};
  return cards.length===13 && cards.every(card => {
    const slots=[...card.querySelectorAll('.ai-stat-value')];
    const values=slots.map(value=>value.textContent);
    return values.length>0 && !!card.querySelector('h4') && !!card.querySelector('.ai-stat-icon') &&
      !/N\\/A|Not Applicable/i.test(card.textContent) &&
      (expected ? !card.querySelector('.metric-spinner') && (cost.has(card.dataset.metric) ?
        JSON.stringify(values)===JSON.stringify(expected[card.dataset.metric]) :
        values.every(value=>value!=='Loading…')) :
        slots.every(slot=>slot.textContent==='' && slot.childElementCount===1 &&
          slot.firstElementChild?.matches('.metric-spinner[role="img"]') &&
          slot.firstElementChild.getAttribute('aria-label')==='Loading '+card.querySelector('h4 button').textContent) &&
          !card.querySelector('.ai-stat-racer'));
  });
})()`;
