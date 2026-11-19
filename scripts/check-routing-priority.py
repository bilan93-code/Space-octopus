"""A fallback escape must preserve completed nets with higher priority."""
import ast,collections,math,os
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon,box
from shapely.strtree import STRtree

module=ast.parse(Path('scripts/finish-routing.py').read_text())
functions=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in ['route_rank','immutable','terminal_escape']]
assert len(functions)==3
pad=Point(-20,0).buffer(.25,quad_segs=32)
ring=LineString([(-20.55,-.55),(-19.45,-.55),(-19.45,.55),(-20.55,.55),(-20.55,-.55)]).buffer(.075,quad_segs=32)
assert pad.distance(ring)>=.2
port={'pcb_port_id':'test_port','x':-20,'y':0,'layers':['bottom']}
os.environ['ROUTING_FREEZE_EQUAL_RANK']='1'
os.environ['ROUTING_RIPUP']='1'
os.environ.pop('ROUTING_THAW_NETS',None)
os.environ.pop('ROUTING_LOCAL_REPAIR',None)
results=[]
for foreign_name,allowed in [('GND',False),('ARM_PULSE',False),('UART_TX',True)]:
    s={'math':math,'os':os,'Point':Point,'LineString':LineString,'STRtree':STRtree,
       'thaw_names':set(),'locked_nets':set(),'wide_trace_ids':set(),
       'nets':{'signal':'ENC_CLK_N','foreign':foreign_name},'protected_pickup_ids':set(),
       'j':[],'layers':['top','inner1','inner2','bottom'],'board':box(-30,-10,-10,10),
       'npth':Polygon(),'hardware':Polygon(),'scope':{'portlabel':lambda p:'RTEST.1'},
       'sense_guard':collections.defaultdict(lambda:collections.defaultdict(list)),
       'items':[{'id':'pad','kind':'pad','net':'signal','layer':'bottom','g':pad},
                {'id':'finish_0:1','kind':'track','net':'foreign','layer':'top','g':box(-22,-2,-18,2)},
                {'id':'finish_1:1','kind':'track','net':'foreign','layer':'bottom','g':ring}]}
    exec(compile(ast.Module(body=functions,type_ignores=[]),'routing_priority','exec'),s)
    # The router escapes a small open island toward a distinct larger one.
    # It deliberately skips the largest island to avoid redundant via farms.
    target=box(-28,-1,-26,1)
    terminals={0:[port],1:[{**port,'pcb_port_id':'target_a'},{**port,'pcb_port_id':'target_b'}]}
    result,reason=s['terminal_escape']('signal',{0:{'bottom':pad},1:{'inner2':target}},terminals)
    assert (result is not None)==allowed,(foreign_name,reason)
    if allowed:assert result[3]=={'finish_0'}
    os.environ['ROUTING_RIPUP']='0'
    assert s['terminal_escape']('signal',{0:{'bottom':pad},1:{'inner2':target}},terminals)[0] is None,'Explicit no-rip mode must retain foreign copper'
    os.environ['ROUTING_RIPUP']='1'
    assert s['terminal_escape']('signal',{0:{'bottom':pad}},{0:[port]})[0] is None,'A sole connected island needs no extra fanout'
    results.append({'foreignNet':foreign_name,'escapeMayRipIt':allowed})
print('Routing priority checks passed:',results)
