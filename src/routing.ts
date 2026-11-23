// Route small groups in a reproducible order. This is routing geometry, not
// qualification of the 48 V / 13 Arms power stage or its thermal performance.
export const gateNets=['GH_U','GL_U','GH_V','GL_V','GH_W','GL_W','Q1_G','Q2_G','Q3_G','Q4_G','Q5_G','Q6_G','BRAKE_GATE'];
export const powerNets=['VBUS','PH_U','PH_V','PH_W','SHUNT_U_TOP','SHUNT_V_TOP','SHUNT_W_TOP','BRAKE_PLUS','BRAKE_DRAIN'];
export function routingPhase(net:string,nets:string[]) {
 if(gateNets.includes(net))return 0;
 if(powerNets.includes(net))return 20+powerNets.indexOf(net);
 if(net==='GND')return 30;
 const others=nets.filter(n=>!gateNets.includes(n)&&!powerNets.includes(n)&&n!=='GND');
 return 1+Math.floor(others.indexOf(net)/12);
}
