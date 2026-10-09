const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const html=fs.readFileSync('templates/index.html','utf8');
let add, requests=[], stored=[], status='', permissions;
const file={name:'photo.png'};
const context={addRecordSaving:false,editingId:null,insertAfterId:null,currentTabKey:'sign',recordViewMode:'inventory',
  pendingImageFile:file,allRecords:[],collectRow:()=>({ST_ID:'A'}),
  document:{getElementById:()=>({addEventListener:(event,fn)=>{add=fn;}})},
  apiRequest:async(url,options)=>{requests.push(options.method);return {ok:true,data:{record:{ID:7,_CAN_EDIT:true},next_id:8}};},
  uploadRecordImage:async()=>{throw new Error('Upload connection failed');},uploadNightImage:r=>r,saveFormVisibility:r=>r,
  replaceLocalRecord:r=>stored.push(r),setRecordActionPermissions:(...args)=>{permissions=args;},updateInsertMode(){},
  setStatus:s=>{status=s;},clearForm(){throw new Error('Should preserve form');},loadRecords(){}};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf("document.getElementById('add-btn').addEventListener"),html.indexOf("document.getElementById('update-btn').addEventListener")),context);
(async()=>{
  add();await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(requests,['POST'],'Never delete the saved row after an upload failure');
  assert.equal(context.editingId,7);
  assert.equal(context.pendingImageFile,file);
  assert.equal(stored[0].ID,7);
  assert.deepEqual(permissions,[true,true]);
  assert.match(status,/was saved/);assert.match(status,/Update to retry/);
  add();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests.length,1,'Retry uses Update rather than inserting again');
  context.editingId=null;
  context.collectRow=()=>{throw new Error('Invalid form value');};
  add();await new Promise(resolve=>setImmediate(resolve));
  assert.match(status,/Invalid form value/);
  assert.equal(context.addRecordSaving,false);
  console.log('PASS: upload failure preserves the created record, selected file, and retry state.');
})().catch(error=>{console.error(error);process.exitCode=1;});
