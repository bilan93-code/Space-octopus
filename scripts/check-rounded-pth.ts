import assert from 'node:assert/strict';
import {checkPadTraceClearance} from '@tscircuit/checks';
const nestedModule='../node_modules/tscircuit/node_modules/@tscircuit/checks/dist/index.js';
const nested=await import(nestedModule);
const test=(check:any,angle:number,start:number)=>{
 const rad=angle*Math.PI/180;
 const point=(x:number,y:number)=>({x:x*Math.cos(rad)-y*Math.sin(rad),y:x*Math.sin(rad)+y*Math.cos(rad)});
 const pad:any={type:'pcb_plated_hole',pcb_plated_hole_id:'rounded_fixture',shape:'circular_hole_with_rect_pad',x:0,y:0,hole_diameter:.8,rect_pad_width:2.4,rect_pad_height:1.6,rect_border_radius:.25,rect_ccw_rotation:angle,layers:['top','bottom']};
 const trace:any={type:'pcb_trace',pcb_trace_id:'trace_fixture',route:[{route_type:'wire',...point(start,start-.4),width:.15,layer:'top'},{route_type:'wire',...point(2,1.6),width:.15,layer:'top'}]};
 return check([pad,trace],{connMap:{areIdsConnected:()=>false} as any,minClearance:.2});
};
for(const check of [checkPadTraceClearance,nested.checkPadTraceClearance])for(const angle of [0,37,90]){
 assert.equal(test(check,angle,1.33).length,0,'Rounded-corner gap exceeds 0.2 mm');
 assert.equal(test(check,angle,1.25).length,1,'A real gap below 0.2 mm must still fail');
}
console.log('Rounded PTH: real clearance violations detected at 0, 37 and 90 degrees.');
