const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('templates/index.html','utf8');
let scheduled,finish;
const values={LATITUDE:'38',LONGITUDE:'-121',POLE_ID:'',SIGN:''};
const context={currentTabKey:'sign',stagingEdit:null,fieldEls:{POLE_ID:{},SIGN:{}},getVal:key=>values[key]||'',setVal:(key,val)=>values[key]=val,refreshAutoFields(){},setTimeout:fn=>{scheduled=fn;},clearTimeout(){},URLSearchParams,fetch:()=>new Promise(resolve=>finish=resolve),parseApiResponse:value=>value};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('var suggestedSignIds ='),html.indexOf('function onFieldChanged(')),context);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 context.requestSignIds('LATITUDE');scheduled();finish({ok:true,data:{POLE_ID:'P1',SIGN:'S8'}});await flush();
 assert.equal(values.POLE_ID,'P1');assert.equal(values.SIGN,'S8');
 values.POLE_ID='P9';context.requestSignIds('POLE_ID');scheduled();finish({ok:true,data:{POLE_ID:'P9',SIGN:'S4'}});await flush();
 assert.equal(values.POLE_ID,'P9');assert.equal(values.SIGN,'S4');
 values.SIGN='CUSTOM';context.requestSignIds('SIGN');context.requestSignIds('LATITUDE');scheduled();finish({ok:true,data:{POLE_ID:'P9',SIGN:'S10'}});await flush();assert.equal(values.SIGN,'CUSTOM');
 context.requestSignIds('LATITUDE');scheduled();context.signSuggestionVersion++;finish({ok:true,data:{POLE_ID:'P2',SIGN:'S1'}});await flush();assert.equal(values.POLE_ID,'P9');
 console.log('PASS: suggestions, manual pole/sign overrides, and stale-response protection.');
})().catch(error=>{console.error(error);process.exitCode=1;});
