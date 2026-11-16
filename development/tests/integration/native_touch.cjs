// CDP acknowledges touchEnd before Blink's deferred tap-active release (~150ms).
// Keep the single subsequent mouse arrival out of that native timer's lifetime.
// This is harness pacing, not a product hover retry, redraw or presence override.
// Both main harnesses retain COST_GUARD_UNPACED_TOUCH=1 for the original FAIL.
const TOUCH_SETTLE_MS=250;
function nativeTouch(command,settle,wait=ms=>new Promise(resolve=>setTimeout(resolve,ms))) {
  return async (method,params={},sessionId)=>{
    const result=await command(method,params,sessionId);
    if(settle&&method==='Input.dispatchTouchEvent'&&params.type==='touchEnd')await wait(TOUCH_SETTLE_MS);
    return result;
  };
}
module.exports={nativeTouch,TOUCH_SETTLE_MS};
