// Rendered synthetic DTO matrix: real browser geometry, fonts, themes and zoom.
const assert=require('node:assert/strict');
const center=rect=>rect.x+rect.width/2;
// Runs in the browser; compare visible groups to the actual content width after zoom.
function measureZones(view,r) {
  return {band:r(view.band),daily:r(view.daily),accounts:r(view.accounts),
    controls:r(miniWatch.button.parentNode),button:r(miniWatch.button)};
}
function checkPlacement({band,daily,accounts,controls,button},label) {
  const detail=JSON.stringify({label,band,daily,accounts,controls,button});
  const row=accounts.y<daily.bottom&&controls.y<accounts.bottom;
  // Reference examples, not a required transition point: a phone cannot fit
  // these fixtures side by side, but a ~700 CSS-pixel header comfortably can.
  if(band.width<=330)assert.ok(!row,'expected stacked header: '+detail);
  if(band.width>=700)assert.ok(row,'expected three-zone row: '+detail);
  assert.ok(Math.abs(center(accounts)-center(band))<2,detail);
  if(row) {
    assert.ok(daily.right<accounts.x&&accounts.right<controls.x,detail);
    assert.ok(Math.abs(daily.y+daily.height/2-accounts.y-accounts.height/2)<2,detail);
  } else {
    assert.ok(daily.bottom<accounts.y&&accounts.bottom<controls.y,detail);
    for(const group of [daily,button])assert.ok(Math.abs(center(group)-center(band))<2,detail);
  }
  return row;
}
module.exports=async({evaluate,until,command,sessionId,layouts,checks,capture})=>{
  await evaluate(`location.hash='#/watch';window.headerOriginal=structuredClone(liveValue);
    window.headerTheme=document.documentElement.dataset.theme;`);
  await until('!!current.watch');
  for(const width of [360,520,768,1024,1366,1920]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
    for(const [theme,scheme] of [['classic','light'],['classic','dark'],['web','light'],['web','dark']]) {
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
          const zones=(${measureZones})(view,r);
          const style=getComputedStyle(view.band);
          return {...zones,
            dailyLines:[...view.daily.children].map(n=>({rect:r(n),font:getComputedStyle(n).fontSize,
              weight:getComputedStyle(n).fontWeight,color:getComputedStyle(n).color})),
            border:style.borderBottomWidth,shadow:style.boxShadow,
            pseudo:['::before','::after'].map(p=>getComputedStyle(view.band,p).content),
            bars:[...view.accounts.querySelectorAll('progress')].map(n=>({rect:r(n),label:r(n.previousElementSibling),
              max:n.max,value:n.value,hidden:n.hidden,aria:n.getAttribute('aria-valuetext')})),
            lines:view.accountCards.lines.size,parents:view.accounts.parentNode===view.band,
            only:view.root.querySelectorAll('.mini-accounts').length===1,
            cardsBelow:!view.active.children.length||r(view.active).y>=zones.band.bottom,
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
        assert.equal(value.border,'0px');assert.equal(value.shadow,'none');
        assert.ok(value.pseudo.every(content=>content==='none'||content==='normal'));
        const lines=value.dailyLines;
        assert.equal(lines.length,3);
        assert.ok(lines[0].rect.bottom<=lines[1].rect.y&&lines[1].rect.bottom<=lines[2].rect.y,
          JSON.stringify({label,lines}));
        for(const line of lines)assert.ok(Math.abs(center(line.rect)-center(value.daily))<1,
          JSON.stringify({label,lines}));
        assert.ok(parseFloat(lines[1].font)>parseFloat(lines[0].font)&&Number(lines[1].weight)>=600);
        assert.equal(lines[0].color,lines[2].color);
        checkPlacement(value,label);
        for(const bar of value.bars)if(!bar.hidden){
          assert.equal(bar.max,1);assert.ok(bar.value>=0&&bar.value<=1);
          assert.ok(bar.rect.width<=Math.min(value.accounts.width,211)+1);
          assert.ok(Math.abs(bar.rect.x-bar.label.x)<1&&Math.abs(bar.rect.x-value.accounts.x)<1,
            JSON.stringify({label,bar}));
          assert.ok(bar.aria);
        }
        layouts.push({case:'watch-header',...label,...value});
        if(unit==='usd'&&((width===1366&&count===3&&theme==='classic'&&scheme==='dark')||
            (width===360&&count===8&&theme==='web'&&scheme==='dark')))
          await capture('header-'+width+'-'+theme+'-'+scheme);
      }
    }
  }
  // Resize the same populated page without another DTO, navigation or explicit render.
  for(const [width,expectedRow] of [[360,false],[1920,true]]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
    const zones=await evaluate(`(${measureZones})(current.watch,n=>n.getBoundingClientRect().toJSON())`);
    assert.equal(checkPlacement(zones,{resizeTo:width}),expectedRow,`resize to ${width}`);
  }
  checks.push('Narrow headers center Today, subscriptions and Mini Watch in order; intermediate widths that fit retain a row; resizing the same populated page narrow then wide restores the row.');
  await command('Emulation.clearDeviceMetricsOverride',{},sessionId);
  await command('Emulation.setEmulatedMedia',{features:[]},sessionId);
  await evaluate(`liveValue=headerOriginal;document.documentElement.dataset.theme=headerTheme;
    ReportView.setUnit('credits');show(current);`);
  checks.push('360/520/768/1024/1366/1920px x Classic/Web light/dark x 0/1/2/3/6/8 accounts x Credits/USD: common left label/track baseline, centered collective group, three-line internally centered Today, no divider, long labels/large totals, compact bars, 44px target and no overflow');
};
