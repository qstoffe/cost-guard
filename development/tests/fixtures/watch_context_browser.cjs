// Actual-DOM assertions for session-scoped inline guidance and focus-safe updates.
const assert = require('node:assert/strict');
module.exports = async function checkContext(evaluate) {
  const result = await evaluate(`(() => {
    const original=structuredClone(INPUT.view.active_cards);
    const card=INPUT.view.active_cards[0], item=card.rows[0], value=card.session_summary;
    const root=()=>document.querySelector('.watch-active .watch-card');
    const summary=()=>root().querySelector('.watch-session-summary');
    const icon=()=>summary().firstChild;
    const context=()=>summary().querySelector('.watch-session-context');
    const impact=()=>summary().lastChild.children[1];
    const color=node=>getComputedStyle(node).color;
    const rgb=color=>color.match(/[\\d.]+/g).slice(0,3).map(Number);
    const luminance=color=>rgb(color).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
      .reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
    const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
    const background=getComputedStyle(document.body).backgroundColor;
    try {
      const earlier=document.querySelector('.watch-history .watch-session-summary');
      const both=[summary(),earlier].every(node=>node.textContent.startsWith('Session Context / CCost: 120k / 4583 ('));
      const ectx=root().querySelector('tbody td:nth-child(9)').textContent;
      const undecorated=!/[~≈⚠]/.test(ectx) && !root().querySelector('.watch-context-warning');
      const transitions=[], ordinaryColor=color(summary());
      for (const severity of ['approaching','exceeded','none','approaching']) {
        icon().focus({preventScroll:true}); const focused=icon(), protectedFocus=document.activeElement===focused;
        value.context.warning.severity=severity;
        value.context.warning.text=severity==='approaching'?'[Approaching price threshold >100.0K]':'[Price threshold >100.0K exceeded]';
        redraw();
        const line=summary().textContent, neutral=color(summary());
        transitions.push({severity,actual:summary().dataset.severity,visible:!icon().hidden,
          stable:!protectedFocus||icon()===focused,color:neutral,iconColor:color(icon()),contextColor:color(context()),
          impactColor:color(impact()),points:icon().querySelector('polygon').getAttribute('points').split(' ').length,
          neutral:[summary().children[1],summary().children[3],summary().children[4],summary().lastChild.firstChild]
            .every(node=>color(node)===ordinaryColor && getComputedStyle(node).fontWeight===getComputedStyle(summary()).fontWeight),
          placement:severity==='none'?!line.includes('threshold'):
            /^Session Context \\/ CCost: 120k \\/ 4583 \\([^()]*price threshold[^()]*; 2.4x more expensive\\)$/i.test(line),
          single:(line.match(/price threshold/gi)||[]).length===(severity==='none'?0:1) && !icon().title && !icon().hasAttribute('aria-describedby'),
          accessible:severity==='none'||(icon().tabIndex===0 && /^(Caution|Stop):/.test(icon().getAttribute('aria-label')) &&
            icon().getAttribute('role')==='img' && icon().querySelector('svg').getAttribute('aria-hidden')==='true'),
          contrast:contrast(color(context()),background),
          overflow:summary().scrollWidth>summary().clientWidth});
      }
      value.context.watch_next_context_tokens=null;value.context.display.watch_next_context_tokens='N/A';redraw();
      const invalidated=summary().textContent==='Session Context / CCost: N/A / 4583' && icon().hidden && summary().dataset.severity==='none';
      value.context.watch_next_context_tokens=120000;value.context.display.watch_next_context_tokens='120k';
      value.context.warning.severity='none';redraw();
      const plain=summary().textContent==='Session Context / CCost: 120k / 4583' && color(context())===ordinaryColor;
      const originalCost=value.cost.display.known_ccost;
      ReportView.setUnit('usd',document.getElementById('result'));
      const usd=summary().textContent.includes('$');
      ReportView.setUnit('credits',document.getElementById('result'));
      const credits=summary().textContent.includes(originalCost);
      value.context.warning.severity='exceeded'; value.context.warning.multiplier=null;
      value.context.warning.text='[Price threshold >100.0K exceeded]';
      value.context.warning.display.warning_cost='(Next Ictx CCost 0.3–3)';redraw();
      const range=color(impact())===ordinaryColor && summary().textContent.endsWith('; Next Ictx CCost 0.3–3)');
      value.context.warning.display.warning_cost='';redraw();
      const noImpact=summary().textContent.endsWith('(Price threshold >100.0K exceeded)') && !impact().textContent;
      const help=summary().children[1].getAttribute('aria-description').includes('not an accumulated session CCost spending budget');
      return {both,undecorated,transitions,ordinaryColor,invalidated,plain,usd,credits,range,noImpact,help};
    } finally {
      document.activeElement?.blur();INPUT.view.active_cards=original;redraw();
    }
  })()`);
  for (const key of ['both','undecorated','invalidated','plain','usd','credits','range','noImpact','help']) assert.equal(result[key],true,key);
  for (const sample of result.transitions) {
    assert.equal(sample.actual,sample.severity);assert.equal(sample.visible,sample.severity!=='none');
    assert.equal(sample.stable,true);assert.equal(sample.accessible,true);assert.equal(sample.placement,true);
    assert.equal(sample.neutral,true,'labels, slash, session cost and boundary remain neutral');
    assert.equal(sample.color,result.ordinaryColor);assert.equal(sample.single,true);assert.equal(sample.overflow,false);
    assert.ok(sample.contrast>=4.5,'readable context contrast: '+sample.contrast);
    if (sample.severity==='none') assert.equal(sample.contextColor,result.ordinaryColor);
    else {
      assert.notEqual(sample.contextColor,result.ordinaryColor);assert.equal(sample.contextColor,sample.iconColor);
      assert.equal(sample.points,sample.severity==='exceeded'?8:3);
    }
    assert.equal(sample.impactColor,sample.severity==='exceeded'?sample.contextColor:result.ordinaryColor);
  }
  assert.notEqual(result.transitions[0].iconColor,result.transitions[1].iconColor);
  return result;
};
