const assert=require('node:assert/strict');
const {nativeTouch,TOUCH_SETTLE_MS}=require('./native_touch.cjs');
(async()=>{
  const calls=[],waits=[],result={ack:true},session='owned-target';
  const command=nativeTouch(async (...args)=>{calls.push(args);return result;},true,
    async ms=>{waits.push(ms);assert.equal(calls.at(-1)[1].type,'touchEnd');});
  for(const [method,params] of [
    ['Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:10,y:10}]}],
    ['Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]}],
    ['Input.dispatchMouseEvent',{type:'mouseMoved',x:20,y:20}],
    ['Runtime.evaluate',{expression:'true'}],
    ['Input.dispatchTouchEvent',{type:'touchCancel',touchPoints:[]}]]) {
    assert.equal(await command(method,params,session),result);
    assert.deepEqual(calls.at(-1),[method,params,session]);
  }
  assert.deepEqual(waits,[250]);assert.equal(TOUCH_SETTLE_MS,250);
  let release,finished=false;
  const ordered=nativeTouch(async()=>result,true,()=>new Promise(resolve=>release=resolve));
  const ending=ordered('Input.dispatchTouchEvent',{type:'touchEnd'},session).then(()=>finished=true);
  await new Promise(setImmediate);assert.equal(finished,false);
  release();await ending;assert.equal(finished,true);
  const unpaced=nativeTouch(async()=>result,false,()=>assert.fail('unpaced control must not wait'));
  assert.equal(await unpaced('Input.dispatchTouchEvent',{type:'touchEnd'},session),result);
  const failed=nativeTouch(async()=>{throw Error('input rejected');},true,()=>assert.fail('failed input must not wait'));
  await assert.rejects(failed('Input.dispatchTouchEvent',{type:'touchEnd'},session),/input rejected/);
  console.log('Native touch: one bounded post-ACK wait, unchanged input/session/result, ordered completion, unpaced and failed controls passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
