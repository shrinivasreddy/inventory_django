// Run with node tests/frontend_review.cjs (no third-party dependencies).
const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('templates/index.html', 'utf8');
function extract(start, end) { return html.slice(html.indexOf(start), html.indexOf(end, html.indexOf(start))); }
function element() { return {children:[], value:'', textContent:'', appendChild(child){this.children.push(child);}, addEventListener(){}, set innerHTML(value){this.children=[];}}; }
const nodes = new Map();
const node = id => { if(!nodes.has(id)) nodes.set(id,element()); return nodes.get(id); };
const context = {
  document:{getElementById:node}, el:(tag,attrs={})=>Object.assign(element(),attrs),
  stagingRows:Array.from({length:5742},(_,i)=>({id:i+1,data:{ID:i+1,SIGN_UID:'S'+i},status:'OK'})),
  stagingSelection:new Set(),stagingPage:1,stagingBusy:false,spec:{columns:['ID','SIGN_UID'],image_origins:['https://stpaul.bluedometech.com']},
  URL,window:{location:{origin:'http://127.0.0.1:8000'}},
};
vm.createContext(context);
vm.runInContext(extract('function filteredStaging()', 'function stagingMutation('), context);
node('staging-filter').value='all';node('staging-sort').value='source';
context.renderStaging();assert.equal(node('staging-body').children.length,100);assert.equal(node('staging-page-position').textContent,'Page 1 of 58');assert.equal(node('staging-prev').disabled,true);
context.stagingPage=58;context.renderStaging();assert.equal(node('staging-body').children.length,42);assert.equal(node('staging-next').disabled,true);
context.stagingRows[0].status='Flagged: Condition unclear (?)';context.stagingRows[0].unclear=true;node('staging-filter').value='unclear';context.renderStaging();assert.equal(node('staging-body').children.length,1);
vm.runInContext(extract('function rejectFilteredStaged()', 'function editStagedRow('),context);
context.currentTabKey='sign';
node('staging-filter').options=[{text:'Condition unclear (?)'}];node('staging-filter').selectedIndex=0;
let rejected=null;context.stagingMutation=(url,method,body)=>{rejected={url,method,body};};
context.confirmDestructive=()=>{};context.rejectFilteredStaged();assert.equal(rejected,null);
context.confirmDestructive=(title,description,label,action)=>{assert.match(title,/Reject 1 staged rows/);action();};context.rejectFilteredStaged();assert.equal(rejected.body.rows.length,1);assert.equal(rejected.body.rows[0].id,1);
node('staging-filter').value='all';context.confirmDestructive=(title,description,label,action)=>action();context.rejectFilteredStaged();assert.equal(rejected.body.rows.length,5742);
assert.equal(rejected.url,'/api/sign/staging/reject');
vm.runInContext(extract('function accessibleImageUrl(', 'function uploadRecordImage('),context);
assert.equal(context.accessibleImageUrl('javascript:alert(1)'), '');
assert.equal(context.accessibleImageUrl('https://untrusted.example/photo.png'), '');
assert.equal(context.accessibleImageUrl('https://stpaul.bluedometech.com/SR/photo.png'), 'https://stpaul.bluedometech.com/SR/photo.png');
assert.equal(context.accessibleImageUrl('https://old.example/uploads/images/sign_inventory/1/image.png'), '/uploads/images/sign_inventory/1/image.png');
assert.equal(context.accessibleImageUrl('https://user:password@stpaul.bluedometech.com/SR/photo.png'), '');
console.log('PASS: 5,742-row pagination, boundaries, status filtering, and image URL policy.');
