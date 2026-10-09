const fs = require('fs'), vm = require('vm'), assert = require('node:assert/strict');
const html = fs.readFileSync('templates/index.html', 'utf8');
function element() {
  return {style:{}, classList:{remove(){}}, attributes:{}, appendChild(){}, insertBefore(){},
    setAttribute(k,v){this.attributes[k]=v;}, removeAttribute(k){delete this[k];}};
}
const requests = [];
const context = {document:{createElement:element}, Image:function(){requests.push(this);}};
vm.createContext(context);
vm.runInContext(html.slice(html.indexOf('function loadPreviewImage('), html.indexOf('function showNightImage(')), context);
(async () => {
  const img = element(); img.parentNode = element();
  const results = [];
  const load = url => context.loadPreviewImage(img, url, 'day image', ok => results.push(ok));
  load('first.jpg');
  assert.equal(img.style.visibility, 'hidden');
  assert.equal(img.previewFrame.attributes['aria-busy'], 'true');
  let decode;
  requests[0].decode = () => new Promise(resolve => {decode=resolve;});
  requests[0].onload();
  assert.equal(img.previewOverlay.hidden, false, 'Overlay stays until decoding completes');
  load('second.jpg');
  requests[1].onload();
  decode(); await Promise.resolve();
  assert.equal(img.src, 'second.jpg', 'Late decoding cannot restore previous image');
  assert.equal(img.previewOverlay.hidden, true);
  assert.deepEqual(results, [true]);
  load('broken.jpg'); requests[2].onerror();
  assert.equal(img.previewFrame.attributes['aria-busy'], 'false');
  assert.equal(img.previewSpinner.hidden, true);
  assert.match(img.previewMessage.textContent, /Could not load/);
  assert.equal(img.style.visibility, 'hidden');
  load('slow.jpg'); load(''); requests[3].onload();
  assert.equal(img.previewFrame.hidden, true, 'Empty record cancels pending preview');
  assert.equal(img.src, undefined);
  assert.deepEqual(results, [true, false]);
  const nodes = {};
  const radios = [{value:'Yes'}, {value:'No'}];
  context.document.getElementById = id => nodes[id] ||= {};
  context.document.querySelectorAll = () => radios;
  context.simulationSaving = false;
  context.simulationIndex = 0;
  context.simulationRecords = [{_CAN_EDIT:true}];
  context.simulationLoaded = {day:true, night:false};
  vm.runInContext(html.slice(html.indexOf('function simulationControls()'), html.indexOf('function showSimulationRecord()')), context);
  context.simulationControls();
  assert.equal(nodes['simulation-answer'].disabled, true);
  assert.equal(radios[0].disabled, true);
  assert.equal(radios[1].disabled, true);
  context.simulationLoaded.night = true;
  context.simulationControls();
  assert.equal(radios[0].disabled, false);
  assert.equal(radios[1].disabled, false);
  assert.equal(nodes['simulation-answer'].disabled, false);
  context.simulationLoaded = {day:false, night:true};
  context.simulationControls();
  assert.equal(nodes['simulation-answer'].disabled, true);
  context.simulationLoaded = {day:false, night:false};
  context.simulationControls();
  assert.equal(radios[0].disabled, true);
  assert.equal(radios[1].disabled, true);
  context.simulationSaving = true;
  context.simulationControls();
  assert.equal(nodes['simulation-answer'].disabled, true);
  context.simulationSaving = false;
  context.simulationRecords[0]._CAN_EDIT = false;
  context.simulationControls();
  assert.equal(nodes['simulation-answer'].disabled, true);
  vm.runInContext(html.slice(html.indexOf('var formSimulationLoaded ='), html.indexOf('function showNightImage(')), context);
  for (const day of [false, true]) {
    for (const night of [false, true]) {
      context.formSimulationLoaded = {day, night};
      context.updateFormVisibilityControls();
      assert.equal(radios[0].disabled, !(day && night));
      assert.equal(radios[1].disabled, !(day && night));
    }
  }
  console.log('PASS: image loading, decoding, rapid navigation, failure and empty records.');
})().catch(error => {console.error(error); process.exitCode=1;});
