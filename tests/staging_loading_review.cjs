const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('templates/index.html','utf8');
const pending=[],nodes={};
const context={currentTabKey:'sign',recordViewMode:'staging',stagingRows:[{id:99}],stagingSelection:new Set([99]),Set,
  apiRequest:()=>new Promise(resolve=>pending.push(resolve)),showStaging(){},renderStaging(){},setStatus(){},
  document:{getElementById:id=>nodes[id] ||= {textContent:''}}};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('var stagingLoadVersion ='),html.indexOf('function filteredStaging()')),context);
(async()=>{
  const old=context.loadStaging();
  assert.equal(context.stagingRows.length,0);
  assert.equal(context.stagingSelection.size,0);
  const latest=context.loadStaging();
  pending[1]({ok:true,data:{records:[{id:2}]}});await latest;
  pending[0]({ok:true,data:{records:[{id:1}]}});await old;
  assert.equal(context.stagingRows[0].id,2);
  const switched=context.loadStaging();context.currentTabKey='pavement';
  pending[2]({ok:true,data:{records:[{id:3}]}});await switched;
  assert.equal(context.stagingRows.length,0);
  console.log('PASS: staging clears old selection and rejects late and cross-tab responses.');
})().catch(error=>{console.error(error);process.exitCode=1;});
