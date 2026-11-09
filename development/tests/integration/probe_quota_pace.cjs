// Actual shared-card DOM: local unit switches must not fetch or replace pace/card nodes.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,navigate,checks}) => {
  for (const route of ['accounts','watch']) {
    await navigate(route);
    await evaluate(`window.paceCard=document.querySelector('.watch-subscription');
      window.paceRows=[...paceCard.querySelector('.watch-primary-details').children].slice(1);
      window.paceBar=paceCard.querySelector('progress');window.paceBefore=JSON.stringify(liveValue.view.accounts);
      window.paceFetches=probeFetches;window.paceFocus=paceCard.querySelector('.watch-quota-capacity span');paceFocus.focus();`);
    for (const theme of ['classic','web']) for (const unit of ['credits','usd','credits']) {
      await evaluate(`document.documentElement.dataset.theme='${theme}';ReportView.setUnit('${unit}',document.getElementById('result'));`);
      const result = await evaluate(`({text:paceRows.map(n=>n.textContent),
        card:paceCard===document.querySelector('.watch-subscription'),
        rows:paceRows.every((n,i)=>n===paceCard.querySelector('.watch-primary-details').children[i+1]),
        bar:paceBar===paceCard.querySelector('progress'),focus:document.activeElement===paceFocus,
        raw:paceBefore===JSON.stringify(liveValue.view.accounts),fetches:probeFetches-paceFetches,
        overflow:document.documentElement.scrollWidth>innerWidth})`);
      assert.deepEqual(result.text,unit==='usd' ? ['Remaining: $38.19/day','Remaining: $45.82/workday'] :
        ['Remaining: 3818/day','Remaining: 4582/workday']);
      for(const key of ['card','rows','bar','focus','raw'])assert.equal(result[key],true,`${route}/${theme}/${unit}: ${key}`);
      assert.equal(result.fetches,0);assert.equal(result.overflow,false);
    }
  }
  await evaluate(`document.documentElement.dataset.theme='web';ReportView.setUnit('usd',document.getElementById('result'));`);
  await navigate('accounts');
  checks.push('Reference pace on both routes/themes: local USD/Credits toggles retain card/pace/bar/focus/raw values with zero fetches');
};
