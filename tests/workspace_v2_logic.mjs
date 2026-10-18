import assert from 'node:assert/strict';
import {letterbox,screenToModel,modelToScreen,sourceToModel,modelToSource,encode,decode} from '../frontend/app/coordinates.js';
import {cleanMask} from '../frontend/app/mask-tools.js';
const memory=new Map();globalThis.localStorage=globalThis.sessionStorage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};Object.defineProperty(globalThis.navigator,'onLine',{value:true,configurable:true});
const {state,can}=await import('../frontend/app/state.js');
for(const [width,height]of [[640,479],[1200,900],[340,1000]]){const b=letterbox(width,height);assert.equal(b.width,Math.floor(width*Math.min(512/width,512/height)));for(const [x,y]of [[0,0],[width/2,height/2],[width-1,height-1]]){const p=sourceToModel(x,y,b),q=modelToSource(p.x,p.y,b);assert.ok(Math.abs(x-q.x)<1e-8&&Math.abs(y-q.y)<1e-8);const view={x:47,y:-23,scale:2.6},s=modelToScreen(p.x,p.y,view),m=screenToModel(s.x+20,s.y+80,{left:20,top:80},view);assert.ok(Math.abs(m.x-p.x)<1e-8&&Math.abs(m.y-p.y)<1e-8);}}
const mask=new Uint8Array(262144);mask.fill(1,1000,4000);assert.deepEqual(decode(encode(mask)),mask);assert.throws(()=>decode({shape:[512,512],counts:[-1,262145],first_val:0}));
const hole=new Uint8Array(262144);for(let y=100;y<110;y++)for(let x=100;x<110;x++)hole[y*512+x]=1;hole[105*512+105]=0;assert.equal(cleanMask(hole,'fill')[105*512+105],1);
state.user={id:'admin',role:'ADMIN'};assert.equal(can('viewer'),false);assert.equal(can('admin'),true);
state.user={id:'doctor',role:'DOCTOR'};assert.equal(can('intake'),true);assert.equal(can('admin'),false);

const {getCases}=await import('../frontend/app/cases.js');
let requestedUrl=null;
globalThis.fetch=async(url)=>{requestedUrl=url;return{ok:true,status:200,json:async()=>[{id:'study-123',study_code:'STD-001',patient_id:'PID-1',study_date:'2026-10-16',status:'PENDING',images:[{id:'img-1',laterality:'L'}]}]};};
state.capabilities={case_workflow:false};
const cases=await getCases();
assert.equal(requestedUrl,'/api/cases');
assert.equal(cases.length,1);
assert.equal(cases[0].study_id,'study-123');
assert.equal(cases[0].owner_id,null);
assert.equal(cases[0].images[0].laterality,'L');

console.log('PASS: source/model/screen round trips, backend letterbox rounding, RLE integrity, fill holes, RBAC and live case list fallback');
