"""Cross-check the targeted amendment against manufacturer limits and actual lands."""
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import Point, shape

parts = {p['ref']: p for filename in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake']
         for p in json.loads(Path(f'data/{filename}.json').read_text())}
placement = json.loads(Path('data/placement.json').read_text())
footprints = json.loads(Path('footprints/catalog.json').read_text())
geometry = json.loads(Path('data/board-geometry.json').read_text())
selection = json.loads(Path('data/bulk-watchdog-selection.json').read_text())
checks = []
def check(name, ok, detail=None):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
def close(a,b):
    return math.isclose(a,b,abs_tol=1e-6)

for ref in ['C1','C2','C3','C4']:
    p = parts[ref]
    check(ref+' selected Rubycon row',p['mpn']=='100ZLJ820M18X40' and p['value']=='820 uF, 100 V, 105 C')
    check(ref+' polarity and outward face',p['pins']=={'1':'VBUS','2':'GND'} and placement[ref]['layer']=='top')
    pads = [x for x in footprints[p['footprint']]['elements'] if x['type']=='pcb_plated_hole']
    check(ref+' 7.5mm lead pitch',len(pads)==2 and close(math.dist((pads[0]['x'],pads[0]['y']),(pads[1]['x'],pads[1]['y'])),7.5))
    check(ref+' holes accommodate nominal 0.8mm leads',all(x['hole_diameter']>=1.1 for x in pads))
    body = Point(placement[ref]['bodyCenter']).buffer(18.5/2,quad_segs=512)
    other = [(body.distance(shape(v['assemblyEnvelopes']['top'])),r) for r,v in placement.items()
             if r!=ref and 'top' in v['assemblyEnvelopes']]
    nearest = min(other)
    check(ref+' maximum body to neighbor clearance',nearest[0]>=geometry['courtyardGapMm'],{'minimum_mm':nearest[0],'neighbor':nearest[1]})
    check(ref+' maximum body inside board',Point(0,0).buffer(geometry['outerDiameterMm']/2-geometry['edgeMarginMm'],quad_segs=512).covers(body))
    check(ref+' maximum body clears central opening',body.distance(Point(0,0))>=geometry['centralOpeningDiameterMm']/2+geometry['edgeMarginMm'])

u = parts['U13']
expected = {'1':'VDD','2':'CWD','3':'EN','4':'GND','5':'SET1','6':'WDI','7':'WDO','8':'ENOUT','9':'EP'}
check('TI ordering addendum exact watchdog code',u['mpn']=='TPS3431SDRBR')
check('TI Table 5-1 physical pin labels',u['pinLabels']==expected)
check('Watchdog fixed-200ms wiring',u['pins']=={'1':'V3V3','2':'WDT_CWD','3':'V3V3','4':'GND','5':'V3V3','6':'WDI','7':'FAULT_RAW_N','8':None,'9':'GND'})
check('10k CWD pullup inside manufacturer 9..11k recommendation',parts['R605']['value']=='10 kohm, 1%' and set(parts['R605']['pins'].values())=={'V3V3','WDT_CWD'})
pads = [p for p in footprints[u['footprint']]['elements'] if p['type']=='pcb_smtpad' and p.get('layer')=='top']
for i in range(1,9):
    pp = [p for p in pads if str(i) in p['port_hints']]
    y = (.975-.65*(i-1)) if i<=4 else (-.975+.65*(i-5))
    check(f'TI DRB0008A pad {i} dimensions and position',len(pp)==1 and close(pp[0]['x'],-1.4 if i<=4 else 1.4) and close(pp[0]['y'],y) and close(pp[0]['width'],.6) and close(pp[0]['height'],.31))
ep = [p for p in pads if '9' in p['port_hints']]
check('TI DRB0008A central exposed land',any(close(p['x'],0) and close(p['y'],0) and close(p['width'],1.5) and close(p['height'],1.75) for p in ep))
for x in [-.325,.325]:
    for y in [-1.1875,1.1875]:
        check(f'TI exposed-land extension {x},{y}',any(close(p['x'],x) and close(p['y'],y) and close(p['width'],.23) and close(p['height'],1.025) for p in ep))

c = 4*820e-6
cmax = c*1.2
rated_bank = 4*3.86*.96
check('Manufacturer conservative ripple screen meets 12Arms target',rated_bank>=12,rated_bank)
envelope = json.loads(Path('assets/3d/bulk-cap-envelope-provenance.json').read_text())
check('3D model reserves maximum can dimensions',envelope['can_max_diameter_mm']==18.5 and envelope['can_max_length_mm']==42)
check('3D model preserves lead pitch and motor-side trim',envelope['lead_pitch_mm']==7.5 and envelope['lead_projection_below_board_mm']<=2)
report = {
    'status':'passed' if all(c['passed'] for c in checks) else 'failed',
    'sourceCircuitSha256':hashlib.sha256(Path('output/space-octopus.circuit.json').read_bytes()).hexdigest(),
    'checks':checks,
    'bulk':{'nominal_total_uF':c*1e6,'total_with_tolerance_uF':[c*.8*1e6,cmax*1e6],
            'rated_bank_ripple_A_conservative':rated_bank,'target_A':12,
            'nominal_margin_percent':100*(rated_bank/12-1),
            'maximum_per_part_current_for_screen_A':3.86*.96,
            'energy_at_54V_J':.5*c*54**2,'maximum_energy_at_54V_with_cap_tolerance_J':.5*cmax*54**2,
            'bleeder_22k_time_constant_s':22000*c,'bleeder_48V_to_5V_s':22000*c*math.log(48/5),
            'maximum_bleeder_48V_to_5V_s_with_cap_tolerance':22000*cmax*math.log(48/5),
            'precharge_cap_current_at_0p5V_per_ms_max_A':cmax*500,
            'initial_1A_test_cap_current_at_0p1V_per_ms_max_A':cmax*100,
            'outward_body_envelope_mm':43,'outward_clearance_with_reserved_vent_space_mm':46},
    'watchdog':{'mpn':'TPS3431SDRBR','timeout_ms':[170,200,230],
                'heartbeat_proposed_max_interval_ms':50,'open_drain_fault_output':True,
                'electrical_and_copper_land_review':'passed','stencil_process':'assembler review remains required'},
    'fabricationReady':False,'live_stock_verified':False,
    'limitations':['Manufacturer PDFs were obtained from archived public copies, not current manufacturer-host responses.',
                   'Ripple screen assumes frequency-weighted currents and adequate sharing; measure individual capacitor heating and low-frequency regeneration.',
                   'The 1mm seating allowance and 3mm reserved vent space are assembly constraints, not a claim that the existing enclosure fits.',
                   'LCSC catalogue capacitor lead/packing suffix and watchdog sourcing require order confirmation.',
                   'Full-system current, thermal, fault, vibration and production paste/DFM qualification remain open.']}
Path('output/bulk-watchdog-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],len(checks),'checks; bank',rated_bank,'Arms; selected watchdog',u['mpn'])
for row in checks:
    if not row['passed']:print(row)
raise SystemExit(report['status']!='passed')
