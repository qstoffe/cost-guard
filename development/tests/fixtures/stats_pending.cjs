// FR707 changes CCost amounts only; other pending cards remain Loading-only.
module.exports = (selector, root = 'document') => `(() => {
  const cards=[...${root}.querySelectorAll(${JSON.stringify(selector)})];
  const cost=new Set(['hourly-rate','total-cost','average-cost','expensive-session']);
  return cards.length===12 && cards.every(card => cost.has(card.dataset.metric) ?
    [...card.querySelectorAll('.ai-stat-rate-value,.ai-stat-value:not(.ai-stat-rates)')]
      .every(value => value.textContent==='No workdays' && value.closest('.ai-stat-rate')?.getAttribute('aria-label')==='Workday average' ||
        /^\\$?[<\\d]/.test(value.textContent) && !/N\\/A|Loading|Unavailable/.test(value.textContent)) &&
      !!card.querySelector('.ai-stat-value') :
    card.textContent==='Loading…' && card.childNodes.length===1 && card.children.length===0);
})()`;
