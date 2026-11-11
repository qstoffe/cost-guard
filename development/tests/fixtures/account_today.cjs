// Daily accounting must advance independently of failed/stale native quotas.
const assert = require('node:assert/strict');
module.exports = (vm, context, seed, helpText) => {
  context.todayCase = {accounts:{accounts:[structuredClone(seed)]}};
  vm.runInContext(`globalThis.todayAccounts=new AccountCards.View();todayAccounts.update(todayCase);
    globalThis.todayWatch=new WatchView.View({connection:'Live connected.'});
    todayWatch.update({state:'running',view:todayCase});`, context);
  const roots = [context.todayAccounts.grid, context.todayWatch.accounts];
  const targets = roots.map(root => root.querySelectorAll('h4')[0].querySelectorAll('a')[0]);
  for (const availability of ['stale', 'unavailable', 'available']) {
    for (const amount of ['0', '125', '—']) {
      context.todayCase = structuredClone(context.todayCase);
      context.todayCase.quota_stale = availability === 'stale';
      const item = context.todayCase.accounts.accounts[0];
      item.observation.availability = availability;
      const scope = item.ccost_scopes.find(scope => scope.name === 'today');
      scope.cost = amount === '—' ? null : {display:{account_ccost:amount}};
      item.today_note = 'Current local day: ' + amount;
      vm.runInContext(`ReportView.setUnit('credits');todayAccounts.update(todayCase);
        todayWatch.update({state:'running',view:todayCase});`, context);
      roots.forEach((root, index) => {
        assert.match(root.textContent, new RegExp('CCost Today: ' + amount));
        const card = root.querySelectorAll('h4')[0].parentNode;
        assert.match(helpText(card.children[1].children[0]), new RegExp('Current local day: ' + amount));
        assert.equal(card.querySelectorAll('h4')[0].querySelectorAll('a')[0], targets[index]);
      });
    }
  }
};
