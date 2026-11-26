// Daily accounting must advance independently of failed/stale native quotas.
const assert = require('node:assert/strict');
module.exports = (vm, context, seed, helpText) => {
  context.todayCase = {accounts:{accounts:[structuredClone(seed)]}};
  vm.runInContext(`globalThis.todayAccounts=new AccountCards.View();todayAccounts.update(todayCase);
    globalThis.todayWatch=new WatchView.View({connection:'Live connected.'});
    todayWatch.update({state:'running',view:todayCase});`, context);
  const roots = [context.todayAccounts.grid];
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
        assert.match(root.textContent, new RegExp('CCost Today: ' + (amount === '—' ? 'N/A' : amount)));
        const card = root.querySelectorAll('h4')[0].parentNode;
        const cost = card.children[1];
        require('./ccost_definition.cjs')(helpText(cost.children[0]), /account.*local calendar day/);
        assert.equal(helpText(cost.children.at(-1)),"This account's reference cost for the local calendar day.");
        assert.equal(card.querySelectorAll('h4')[0].querySelectorAll('a')[0], targets[index]);
      });
      assert.doesNotMatch(context.todayWatch.accounts.textContent,/CCost Today:/,'Watch has one page-level daily band, not large account cards');
    }
  }
  vm.runInContext("ReportView.setTimezone('UTC')", context);
  context.todayCase.now_ms = Date.UTC(2026,10,14,12);
  const item = context.todayCase.accounts.accounts[0];
  const scope = item.ccost_scopes.find(scope => scope.name === 'today');
  for (const [amount, complete, expected] of [['125',false,'125'],[null,false,'125'],['0',false,'125'],['0',true,'0']]) {
    scope.cost={known_ccost:amount,complete,display:{account_ccost:amount ?? '0'}};
    vm.runInContext('todayAccounts.update(todayCase)',context);
    assert.match(context.todayAccounts.grid.textContent,new RegExp('CCost Today: '+expected));
  }
  scope.cost={known_ccost:'125',complete:true,display:{account_ccost:'125'}};
  vm.runInContext('todayAccounts.update(todayCase)',context);
  context.todayCase.now_ms += 86400000;
  scope.cost=null;
  vm.runInContext('todayAccounts.update(todayCase)',context);
  assert.match(context.todayAccounts.grid.textContent,/CCost Today: N\/A/,'new configured day cannot inherit yesterday');
  vm.runInContext('ReportView.setTimezone(null)',context);
};
