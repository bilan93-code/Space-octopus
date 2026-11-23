import assert from 'node:assert/strict';
import {attachRouteContacts} from '../src/route-contacts';

// The wide end cap contacts the electrode while its centerline ends outside.
// Pin tagging must not grow that already-audited copper toward the pad center.
const trace:any={type:'pcb_trace',pcb_trace_id:'wide_fixture',source_trace_id:'source_fixture',connection_name:'net_fixture',route:[
 {route_type:'wire',x:-1.75,y:0,layer:'bottom',width:2.4},
 {route_type:'wire',x:-6,y:0,layer:'bottom',width:2.4},
]};
const geometry=structuredClone(trace.route);
const json:any[]=[
 {type:'source_trace',source_trace_id:'source_fixture',connected_source_port_ids:['source_port_fixture'],connected_source_net_ids:['net_fixture']},
 {type:'pcb_port',pcb_port_id:'port_fixture',source_port_id:'source_port_fixture',x:0,y:0,layers:['bottom']},
 {type:'pcb_smtpad',pcb_smtpad_id:'pad_fixture',pcb_port_id:'port_fixture',shape:'circle',radius:1,x:0,y:0,layer:'bottom'},
];
const result=attachRouteContacts([trace],json);
assert.deepEqual(result.find(t=>t.pcb_trace_id==='wide_fixture')?.route,geometry,'Pin contacts must preserve audited wire coordinates and widths');
const anchor=result.find(t=>t.pcb_trace_id.startsWith('pad_contact_'));
assert(anchor,'Create a native pin identity anchor');
assert(anchor.route.some((p:any)=>p.start_pcb_port_id==='port_fixture'));
for(const p of anchor.route)assert(Math.hypot(p.x,p.y)+p.width/2<=1,'Contact anchor must remain inside pad copper');
// A remote fragment has no nearby pin to correct stale IDs. Both IDs below
// still exist after renumbering, but now belong to the other signal.
const live=[
 {type:'source_net',name:'VBUS',source_net_id:'net_1'},
 {type:'source_net',name:'GND',source_net_id:'net_0'},
 {type:'source_trace',source_trace_id:'trace_1',connected_source_port_ids:[],connected_source_net_ids:['net_1']},
 {type:'source_trace',source_trace_id:'trace_0',connected_source_port_ids:[],connected_source_net_ids:['net_0']},
];
const fragment={...trace,connection_name:'net_0',source_trace_id:'trace_0',route:structuredClone(geometry)};
const [remapped]=attachRouteContacts([fragment],live,{net_0:'VBUS'});
assert.equal(remapped.connection_name,'net_1');
assert.equal(remapped.source_trace_id,'trace_1');
assert.deepEqual(remapped.route,geometry);
console.log('Native contact regression: wide copper preserved; identity anchor inside electrode.');
