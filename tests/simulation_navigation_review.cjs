const fs = require('fs'), vm = require('vm'), assert = require('node:assert/strict');
const html = fs.readFileSync('templates/index.html', 'utf8');
let click, displayed;
const context = {
  editingId: 5, stagingEdit: null, simulationRecords: [], simulationIndex: 0,
  document: {getElementById: () => ({addEventListener: (event, handler) => {click = handler;}})},
  apiRequest: async () => ({ok:true, data:{records:[{ID:1},{ID:5},{ID:9}]}}),
  simulationDialog: {open:false, showModal(){this.open=true;}},
  showSimulationRecord(){displayed=context.simulationRecords[context.simulationIndex].ID;},
  setStatus(message){context.status=message;}
};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function openSimulationComparison('), html.indexOf('function simulationCompareButton(')), context);
(async () => {
  click(); await new Promise(resolve=>setImmediate(resolve));
  assert.equal(displayed,5,'Open the currently edited record');
  context.editingId=9;
  click(); await new Promise(resolve=>setImmediate(resolve));
  assert.equal(displayed,9,'Read the current record on each click');
  context.editingId=null;
  click(); await new Promise(resolve=>setImmediate(resolve));
  assert.equal(displayed,1,'Start at the first record when no record is selected');
  context.editingId=50;
  click(); await new Promise(resolve=>setImmediate(resolve));
  assert.match(context.status,/no longer available/);
  console.log('PASS: comparison opens the current edit record and handles empty or stale selection.');
})().catch(error=>{console.error(error);process.exitCode=1;});
