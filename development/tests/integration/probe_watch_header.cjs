// Rendered synthetic DTO matrix: real browser geometry, fonts, themes and zoom.
const assert=require('node:assert/strict');
module.exports=async({evaluate,until,command,sessionId,layouts,checks,capture})=>{
  await evaluate(`location.hash='#/watch';window.headerOriginal=structuredClone(liveValue);
    window.headerTheme=document.documentElement.dataset.theme;`);
  await until('!!current.watch');
  for(const width of [360,520,768,1280,1920]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
    for(const [theme,scheme] of [['classic','light'],['web','light'],['web','dark']]) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},sessionId);
      for(const count of [0,1,2,3,6,8])for(const unit of ['credits','usd']) {
        const value=await evaluate(`(()=>{
          const publication=structuredClone(headerOriginal),v=publication.view;
          const template=v.accounts.accounts;
          v.accounts.accounts=Array.from({length:${count}},(_,index)=>{
            const item=structuredClone(template[index%template.length]);
            item.observation.id='header-'+index;
            if(${count}===3||${count}===8)item.observation.label='Synthetic long provider / account '+index+' with a deliberately unbroken-long-identity-abcdefghijklmnopqrstuvwxyz';
            return item;
          });
          if(${count}===0)v.active_cards=[];
          v.daily_usage.prompt_count=999999;
          for(const [kind,text] of [['credits','9 876 543 210'],['usd','$98,765,432.10']]){
            v.daily_usage.display_units[kind].daily_ccost=text;
            v.daily_usage.total.display_units[kind].known_ccost=text;
          }
          liveValue=publication;document.documentElement.dataset.theme='${theme}';
          ReportView.setUnit('${unit}');show(current);
          const view=current.watch,r=n=>{const b=n.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height,right:b.right,bottom:b.bottom};};
          const band=r(view.band),daily=r(view.daily),accounts=r(view.accounts),controls=r(miniWatch.button.parentNode);
          return {band,daily,accounts,controls,button:r(miniWatch.button),
            bars:[...view.accounts.querySelectorAll('progress')].map(n=>({rect:r(n),max:n.max,value:n.value,hidden:n.hidden})),
            lines:view.accountCards.lines.size,parents:view.accounts.parentNode===view.band,
            only:view.root.querySelectorAll('.mini-accounts').length===1,
            cardsBelow:!view.active.children.length||r(view.active).y>=band.bottom,
            overflow:document.documentElement.scrollWidth>innerWidth+1,
            headerOverflow:view.band.scrollWidth>view.band.clientWidth+1,
            amounts:[...view.daily.children].map(n=>n.textContent)};
        })()`);
        const label={width,theme,scheme,count,unit};
        assert.equal(value.lines,count,JSON.stringify(label));
        assert.ok(value.parents&&value.only&&value.cardsBelow,JSON.stringify(label));
        assert.equal(value.overflow||value.headerOverflow,false,JSON.stringify({label,value}));
        assert.ok(value.button.height>=44&&value.button.width>=44);
        assert.ok(value.amounts[2].includes('999999'));
        for(const bar of value.bars)if(!bar.hidden){
          assert.equal(bar.max,1);assert.ok(bar.value>=0&&bar.value<=1);
          assert.ok(bar.rect.width<=Math.min(value.accounts.width,211)+1);
        }
        if(value.accounts.y<value.daily.bottom&&value.controls.y<value.accounts.bottom) {
          assert.ok(Math.abs(value.accounts.x+value.accounts.width/2-value.band.x-value.band.width/2)<2);
          assert.ok(value.daily.right<=value.accounts.x&&value.accounts.right<=value.controls.x);
        } else {
          assert.ok(value.daily.bottom<=value.accounts.y+1&&value.accounts.bottom<=value.controls.y+1,
            JSON.stringify({label,value}));
        }
        layouts.push({case:'watch-header',...label,...value});
        if(unit==='usd'&&((width===1280&&count===3&&theme==='classic')||
            (width===360&&count===8&&theme==='web'&&scheme==='dark')))
          await capture('header-'+width+'-'+theme+'-'+scheme);
      }
    }
  }
  await command('Emulation.clearDeviceMetricsOverride',{},sessionId);
  await command('Emulation.setEmulatedMedia',{features:[]},sessionId);
  await evaluate(`liveValue=headerOriginal;document.documentElement.dataset.theme=headerTheme;
    ReportView.setUnit('credits');show(current);`);
  checks.push('360/520/768/1280/1920px × Classic/Web light/dark × 0/1/2/3/6/8 accounts × Credits/USD: centered/reflowed geometry, long labels, large totals, compact bars, 44px target and no overflow');
};
