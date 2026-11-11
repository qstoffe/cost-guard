// Shared account heading navigation over the shipped Watch/Accounts/legacy DOM.
const assert = require('node:assert/strict');
module.exports = (vm, context, seed) => {
  const cases = [
    ['github-copilot', 'Pro', 'https://github.com/settings/copilot/features'],
    ['github-copilot', 'Business', 'https://github.com/settings/copilot/features'],
    ['github-copilot-enterprise', 'Enterprise', 'https://github.com/settings/copilot/features'],
    ['claude-code', 'Max', 'https://claude.ai/settings/usage'],
    ['claude-code', 'API pay as you go', 'https://console.anthropic.com/'],
    ['anthropic', 'API pay as you go', 'https://console.anthropic.com/'],
    ['anthropic', null, 'https://console.anthropic.com/'],
    ['anthropic', 'Pro', 'https://claude.ai/settings/usage'],
    ['openai', 'Plus', 'https://chatgpt.com/settings/usage'],
    ['openai', null, 'https://chatgpt.com/settings/usage'],
    ['openai', 'Pay as you go', 'https://platform.openai.com/usage'],
    ['openrouter', null, 'https://openrouter.ai/activity'],
    ['deepseek', null, 'https://platform.deepseek.com/'],
    ['minimax', null, 'https://platform.minimax.io/user-center/payment/balance'],
    ['minimax-cn', null, 'https://platform.minimax.cn/user-center/payment/balance'],
    ['minimax-coding-plan', 'Plus', 'https://platform.minimax.io/user-center/payment/token-plan'],
    ['minimax-cn-coding-plan', 'Plus', 'https://platform.minimax.cn/user-center/payment/token-plan'],
    ['unknown', 'OpenAI Pro', undefined], ['__proto__', null, undefined], ['constructor', null, undefined],
    ['https://untrusted.invalid/openai', 'Plus', undefined], ['javascript:alert(1)', null, undefined],
  ];
  const label = '<img src=x onerror=alert(1)> https://untrusted.invalid/ Claude / OpenAI';
  context.linkCase = {accounts:{accounts:cases.map(([provider_id, plan], index) => ({...structuredClone(seed),
    observation:{...structuredClone(seed.observation), provider_id, plan, id:'private-account-'+index,
      label, availability:index % 2 ? 'unavailable' : 'available', capacity_kind:'usage_limit'}}))}};
  const original = JSON.stringify(context.linkCase);
  vm.runInContext(`globalThis.linkAccounts = new AccountCards.View(true); linkAccounts.update(linkCase);
    globalThis.linkWatch = new WatchView.View({connection:'Live connected.'});
    linkWatch.update({state:'running',view:linkCase});
    globalThis.linkLegacy = ReportView.element('main'); ReportView.overviewAccounts(linkLegacy, linkCase.accounts);`, context);
  for (const root of [context.linkAccounts.grid, context.linkWatch.accounts, context.linkLegacy]) {
    const headings = root.querySelectorAll('h4');
    assert.equal(headings.length, cases.length);
    headings.forEach((heading, index) => {
      assert.equal(heading.textContent, label);
      const links = heading.querySelectorAll('a'), expected = cases[index][2];
      assert.equal(links.length, expected ? 1 : 0, cases[index][0]);
      if (expected) {
        const link = links[0];
        assert.equal(link.href, expected); assert.equal(link.target, '_blank'); assert.equal(link.rel, 'noopener noreferrer');
        assert.equal(link.children.length, 2, 'one decorative icon followed by literal account text');
        const [icon, name] = link.children;
        assert.equal(icon.tag, 'svg'); assert.equal(icon.namespaceURI, 'http://www.w3.org/2000/svg');
        assert.equal(icon.attributes['aria-hidden'], 'true'); assert.equal(icon.attributes.focusable, 'false');
        assert.equal(icon.tabIndex, undefined); assert.equal(name.tag, 'span'); assert.equal(name.textContent, label);
        assert.equal(name.children.length, 0, 'source HTML remains literal heading text');
        assert.equal(link.attributes['aria-label'], label+' — provider usage or settings (opens in a new tab)');
        assert.equal(new URL(link.href).protocol, 'https:'); assert.doesNotMatch(link.href, /private-account|untrusted/);
      }
      assert.equal(heading.querySelectorAll('svg').length, expected ? 1 : 0);
      assert.equal(heading.events.click, undefined, 'header padding is not a click target');
    });
  }
  assert.equal(JSON.stringify(context.linkCase), original, 'navigation never mutates canonical values');
  const card = context.linkAccounts.grid.children[8], heading = card.children[0], anchor = heading.children[0];
  context.linkCase.accounts.accounts[8].observation.plan = 'Pay as you go';
  context.linkCase.accounts.accounts[8].observation.label = 'Changed account';
  vm.runInContext('linkAccounts.update(linkCase)', context);
  assert.equal(card.children[0], heading); assert.equal(heading.children[0], anchor, 'plan/label refresh retains focus owner');
  assert.equal(anchor.querySelectorAll('svg').length, 1, 'refresh never duplicates or removes the icon');
  assert.equal(anchor.href, 'https://platform.openai.com/usage'); assert.equal(anchor.textContent, 'Changed account');
  context.linkCase.accounts.accounts[8].primary.quota.label = 'Changed track';
  context.linkCase.accounts.accounts[8].primary.quota.reset_at_ms = null;
  vm.runInContext('linkAccounts.update(linkCase)', context);
  assert.equal(card.children[0], heading, 'track shape redraw never detaches the heading');
  assert.equal(heading.children[0], anchor);
  assert.equal(card.querySelectorAll('h4')[0].querySelectorAll('a')[0].href, 'https://platform.openai.com/usage', 'shape redraw retains correct destination');
  context.linkCase.accounts.accounts[8].observation.provider_id = 'unknown';
  vm.runInContext('linkAccounts.update(linkCase)', context);
  assert.equal(context.linkAccounts.grid.children[8].querySelectorAll('h4')[0].querySelectorAll('a').length, 0);
  // Also test linked/plain transitions on a bound heading, independent of keyed card replacement.
  context.linkObservation = {provider_id:'unknown', label:'Plain'};
  vm.runInContext('globalThis.linkHeading=ReportView.accountHeading(()=>linkObservation)', context);
  context.linkObservation.provider_id = 'openrouter';
  vm.runInContext('ReportView.syncUnits(linkHeading)', context);
  assert.equal(context.linkHeading.querySelectorAll('a')[0].href, 'https://openrouter.ai/activity');
  context.linkObservation.provider_id = 'unknown';
  vm.runInContext('ReportView.syncUnits(linkHeading)', context);
  assert.equal(context.linkHeading.querySelectorAll('a').length, 0);
  assert.equal(context.linkWatch.accounts.querySelectorAll('h4')[8].textContent, label);
};
