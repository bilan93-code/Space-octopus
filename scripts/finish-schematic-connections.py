"""Separate presentation wires; electrical connectivity and PCB copper are unchanged."""
import bisect, collections, json, math, subprocess, time
from pathlib import Path

root=Path(__file__).resolve().parent.parent
work=root/'routing-work/schematic-view'
symbols=json.loads((root/'output/connected-schematic/symbols.json').read_text())
traces=json.loads((work/'overlap-checkpoint.json').read_text())
sources={e['source_component_id']:e for e in symbols if e['type']=='source_component'}
ports={e['schematic_port_id']:e for e in symbols if e['type']=='schematic_port'}
pin_net={p:n['netId'] for n in json.loads((root/'output/connected-schematic/solver-input.json').read_text())['netConnections'] for p in n['pinIds']}
EPS=1e-6
def segs(t):
    for a,b in zip(t['tracePath'],t['tracePath'][1:]):
        if abs(a['x']-b['x'])+abs(a['y']-b['y'])>EPS:yield a,b
def simplify(path):
    out=[]
    for p in path:
        if out and abs(out[-1]['x']-p['x'])+abs(out[-1]['y']-p['y'])<EPS:continue
        if len(out)>1:
            a,b=out[-2:]
            if (abs(a['x']-b['x'])<EPS and abs(b['x']-p['x'])<EPS) or (abs(a['y']-b['y'])<EPS and abs(b['y']-p['y'])<EPS):out.pop()
        out.append(p)
    return out
for t in traces:
    for i,pin in enumerate(t['pins']):
        actual=ports[pin['pinId']]['center'];pin.update(actual)
        if i==0:t['tracePath'].insert(0,dict(actual))
        else:t['tracePath'].append(dict(actual))
    t['tracePath']=simplify(t['tracePath'])
net_ports=collections.defaultdict(list)
for pid,net in pin_net.items():net_ports[net].append(pid)
def graph_groups(net,paths):
    parent={}
    def key(p):return (round(p['x'],6),round(p['y'],6))
    def find(p):
        parent.setdefault(p,p)
        while parent[p]!=p:parent[p]=parent[parent[p]];p=parent[p]
        return p
    def join(a,b):parent[find(a)]=find(b)
    lines=[(a,b) for t in paths if t['userNetId']==net for a,b in segs(t)]
    for a,b in lines:join(key(a),key(b))
    def on(p,a,b):return min(a['x'],b['x'])-EPS<=p['x']<=max(a['x'],b['x'])+EPS and min(a['y'],b['y'])-EPS<=p['y']<=max(a['y'],b['y'])+EPS and abs((b['x']-a['x'])*(p['y']-a['y'])-(b['y']-a['y'])*(p['x']-a['x']))<1e-5
    for i,(a,b) in enumerate(lines):
        for c,d in lines[i+1:]:
            if any(on(q,a,b) for q in (c,d)) or any(on(q,c,d) for q in (a,b)):join(key(a),key(c));continue
            ah=abs(a['y']-b['y'])<EPS;ch=abs(c['y']-d['y'])<EPS
            if ah!=ch:
                p={'x':c['x'] if ah else a['x'],'y':a['y'] if ah else c['y']}
                if on(p,a,b) and on(p,c,d):join(key(a),key(c))
    groups=collections.defaultdict(list)
    for pid in net_ports[net]:
        p=ports[pid]['center'];find(key(p))
        for a,b in lines:
            if on(p,a,b):join(key(p),key(a))
    for pid in net_ports[net]:groups[find(key(ports[pid]['center']))].append(pid)
    return list(groups.values())
missing=[]
for net in net_ports:
    groups=graph_groups(net,traces)
    while len(groups)>1:
        choices=[]
        for i in range(len(groups)):
            for j in range(i+1,len(groups)):
                for a in groups[i]:
                    for b in groups[j]:
                        pa,pb=ports[a]['center'],ports[b]['center'];choices.append((abs(pa['x']-pb['x'])+abs(pa['y']-pb['y']),i,j,a,b))
        _,i,j,a,b=min(choices);pa,pb=ports[a]['center'],ports[b]['center']
        t={'mspPairId':f'completed_{a}_{b}','userNetId':net,'globalConnNetId':net,'pins':[{'pinId':a,**pa},{'pinId':b,**pb}],'pinIds':[a,b],'tracePath':[dict(pa),{'x':pa['x'],'y':pb['y']},dict(pb)]}
        t['tracePath']=simplify(t['tracePath']);missing.append(t)
        groups[i]+=groups[j];groups.pop(j)
native_count=len(traces);traces.extend(missing)
def overlaps(all_traces):
    axes=collections.defaultdict(list);pairs=set();horizontal=[];vertical=[]
    for i,t in enumerate(all_traces):
        for a,b in segs(t):
            if abs(a['x']-b['x'])<EPS:key=('v',round(a['x'],6));lo,hi=sorted((a['y'],b['y']))
            elif abs(a['y']-b['y'])<EPS:key=('h',round(a['y'],6));lo,hi=sorted((a['x'],b['x']))
            else:raise ValueError('Non-orthogonal wire')
            axes[key].append((lo,hi,i,t['userNetId']))
            (vertical if key[0]=='v' else horizontal).append((a,b,i,t['userNetId']))
    for group in axes.values():
        for k,a in enumerate(group):
            for b in group[k+1:]:
                if a[3]!=b[3] and min(a[1],b[1])-max(a[0],b[0])>=-EPS:pairs.add(tuple(sorted((a[2],b[2]))))
    for a,b,i,net in horizontal:
        for c,d,j,other in vertical:
            if net==other:continue
            x,y=c['x'],a['y']
            if min(a['x'],b['x'])-EPS<=x<=max(a['x'],b['x'])+EPS and min(c['y'],d['y'])-EPS<=y<=max(c['y'],d['y'])+EPS:
                if any(abs(q['x']-x)+abs(q['y']-y)<EPS for q in [a,b,c,d]):pairs.add(tuple(sorted((i,j))))
    return pairs
bodies=[]
for c in [e for e in symbols if e['type']=='schematic_component']:
    x,y=c['center']['x'],c['center']['y'];w,h=c['size']['width'],c['size']['height']
    passive=sources[c['source_component_id']]['ftype'] in ['simple_resistor','simple_capacitor']
    if passive:w*=.75;h*=.55
    bodies.append((x-w/2-.025,x+w/2+.025,y-h/2-.025,y+h/2+.025))
def enters(a,b,r):
    l,rr,bot,top=r
    if abs(a['x']-b['x'])<EPS:return l+EPS<a['x']<rr-EPS and min(max(a['y'],b['y']),top)-max(min(a['y'],b['y']),bot)>EPS
    return bot+EPS<a['y']<top-EPS and min(max(a['x'],b['x']),rr)-max(min(a['x'],b['x']),l)>EPS
def body_hits(t):return sum(any(enters(a,b,r) for r in bodies) for a,b in segs(t))
def foreign_pin_hit(t):
    for pid,p in ports.items():
        if pin_net.get(pid)==t['userNetId']:continue
        q=p['center']
        for a,b in segs(t):
            if min(a['x'],b['x'])-EPS<=q['x']<=max(a['x'],b['x'])+EPS and min(a['y'],b['y'])-EPS<=q['y']<=max(a['y'],b['y'])+EPS:return True
    return False
initial_pairs=overlaps(traces);pending={i for i,t in enumerate(traces) if body_hits(t) or foreign_pin_hit(t)}|set(range(native_count,len(traces)))
remaining={p for p in initial_pairs if not(set(p)&pending)}
while remaining:
    counts=collections.Counter(i for p in remaining for i in p);i=counts.most_common(1)[0][0];pending.add(i);remaining={p for p in remaining if i not in p}
active=[t for i,t in enumerate(traces) if i not in pending]
queue=sorted(pending,key=lambda i:sum(abs(a['x']-b['x'])+abs(a['y']-b['y']) for a,b in segs(traces[i])))
print(f'{len(traces)} required wires; {len(missing)} missing branches recovered; {len(initial_pairs)} overlapping pairs; rerouting {len(queue)} wires.',flush=True)
def route(t,margin):
    start,end=t['pins'][0],t['pins'][-1]
    x0,x1=min(start['x'],end['x'])-margin,max(start['x'],end['x'])+margin
    y0,y1=min(start['y'],end['y'])-margin,max(start['y'],end['y'])+margin
    def nearby(r):return r[0]<x1 and r[1]>x0 and r[2]<y1 and r[3]>y0
    rects=[r for r in bodies if nearby(r)]
    for pid,p in ports.items():
        if pin_net.get(pid)==t['userNetId']:continue
        x,y=p['center']['x'],p['center']['y'];r=(x-.025,x+.025,y-.025,y+.025)
        if nearby(r):rects.append(r)
    wire=[]
    for other in active:
        if other['userNetId']==t['userNetId']:continue
        for a,b in segs(other):
            if max(a['x'],b['x'])<x0 or min(a['x'],b['x'])>x1 or max(a['y'],b['y'])<y0 or min(a['y'],b['y'])>y1:continue
            wire.append((a,b))
    xs={x0,x1,start['x'],end['x']};ys={y0,y1,start['y'],end['y']}
    for l,r,b,top in rects:xs.update([l-.09,l,r,r+.09]);ys.update([b-.09,b,top,top+.09])
    for a,b in wire:
        xs.update([a['x'],b['x']]);ys.update([a['y'],b['y']])
        if abs(a['x']-b['x'])<EPS:xs.update([a['x']-.09,a['x']+.09])
        else:ys.update([a['y']-.09,a['y']+.09])
    xs=sorted({round(v,7) for v in xs if x0-EPS<=v<=x1+EPS});ys=sorted({round(v,7) for v in ys if y0-EPS<=v<=y1+EPS})
    xi={v:i for i,v in enumerate(xs)};yi={v:i for i,v in enumerate(ys)}
    sx,sy,tx,ty=xi[round(start['x'],7)],yi[round(start['y'],7)],xi[round(end['x'],7)],yi[round(end['y'],7)]
    rectangles=[]
    for l,r,b,top in rects:
        a=bisect.bisect_left(xs,l-EPS);bb=bisect.bisect_right(xs,r+EPS)-1;c=bisect.bisect_left(ys,b-EPS);d=bisect.bisect_right(ys,top+EPS)-1
        if a<=bb and c<=d:rectangles.append((a,bb,c,d))
    horizontal=[];vertical=[]
    for a,b in wire:
        if abs(a['x']-b['x'])<EPS:
            col=xi.get(round(a['x'],7))
            if col is not None:vertical.append((col,bisect.bisect_left(ys,min(a['y'],b['y'])-EPS),bisect.bisect_right(ys,max(a['y'],b['y'])+EPS)-1))
        else:
            row=yi.get(round(a['y'],7))
            if row is not None:horizontal.append((row,bisect.bisect_left(xs,min(a['x'],b['x'])-EPS),bisect.bisect_right(xs,max(a['x'],b['x'])+EPS)-1))
    inp=work/'grid-input.txt'
    with inp.open('w') as f:
        f.write(f'{len(xs)} {len(ys)} {sx} {sy} {tx} {ty}\n');f.write(' '.join(map(str,xs))+'\n');f.write(' '.join(map(str,ys))+'\n')
        for rows in [rectangles,horizontal,vertical]:f.write(str(len(rows))+'\n');f.writelines(' '.join(map(str,r))+'\n' for r in rows)
    result=subprocess.run([str(work/'grid-route'),str(inp)],capture_output=True,text=True)
    if result.returncode:return None,result.stderr.strip()
    path=simplify(json.loads(result.stdout));path[0]={'x':start['x'],'y':start['y']};path[-1]={'x':end['x'],'y':end['y']}
    return path,f'{len(xs)}x{len(ys)}'
started=time.time()
for number,index in enumerate(queue,1):
    t=traces[index]
    for margin in [10,30,80,180]:
        path,info=route(t,margin)
        if path:break
    if not path:raise RuntimeError(f'Cannot route {t["mspPairId"]} {t["userNetId"]}: {info}')
    t['tracePath']=path
    if body_hits(t):raise RuntimeError(f'Body collision after reroute: {t["mspPairId"]}')
    active.append(t)
    (work/'finished-paths.json').write_text(json.dumps(active))
    print(f'{number}/{len(queue)} {t["userNetId"]} {info} {time.time()-started:.1f}s',flush=True)
assert len(active)==len(traces)
assert not overlaps(active),'Remaining ambiguous collinear wires'
assert not any(body_hits(t) for t in active),'Remaining symbol-body crossing'
assert not any(foreign_pin_hit(t) for t in active),'Wire touches an unrelated pin'
assert all(len(graph_groups(net,active))==1 for net in net_ports),'Disconnected schematic net'
(root/'output/connected-schematic/paths.json').write_text(json.dumps(active,indent=2)+'\n')
report={'requiredWires':len(traces),'completedWires':len(active),'nativeMissingBranchesCompleted':len(missing),'fullyConnectedSchematicNets':len(net_ports),'connectedPinsVerified':len(pin_net),'nativeAmbiguousContactsBefore':len(initial_pairs),'reroutedForPresentation':len(queue),'differentNetCollinearOverlaps':0,'differentNetTContacts':0,'unrelatedPinContacts':0,'symbolBodyCrossings':0,'routingChangesAffectPcb':False}
(root/'output/connected-schematic/presentation-routing-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
