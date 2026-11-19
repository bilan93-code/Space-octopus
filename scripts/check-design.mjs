#!/usr/bin/env node
/**
 * Independent Rev A electrical audit. Expectations are transcribed from the
 * source PDF (pp. 8, 13–27), NOT imported from the component generator, symbols,
 * rendered circuit, or footprint pin labels. A missing input never passes.
 *
 * node scripts/check-design.mjs [--self-test]
 * Exit 0: automated checks pass (manual release gates may remain unresolved).
 * Exit 1: electrical failure; exit 2: required audit input/check unavailable.
 * Only output/electrical-audit.json is written. Exported audit() is side-effect
 * free so mutation tests can exercise the checker without editing design data.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DATA_FILES = ['data/input-supplies-mcu-driver-inverter.json', 'data/sensing-fault-interfaces-brake.json', 'data/mechanical.json', 'data/external-parts.json'];
const seq = (prefix, start, end) => Array.from({ length: end - start + 1 }, (_, i) => `${prefix}${i + start}`);
const natural = (a, b) => a.localeCompare(b, 'en', { numeric: true });
const sorted = values => [...new Set(values)].sort(natural);
const sameSet = (a, b) => JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));
const isObject = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const hash = data => createHash('sha256').update(data).digest('hex');

// Expanded independently from every inventory row on PDF pages 13–21.
// ENC1 and R_BRAKE_EXT belong to the system inventory, not the PCB inventory.
const INVENTORY = {
  '00 Input': ['J1', 'F1', 'D1', ...seq('C', 1, 5), 'R1', 'TP1', 'TP2'],
  '01 Supplies': ['U3', 'U4', 'U5', 'U19', 'L101', 'L102', 'U21', 'J12', ...seq('C', 101, 117), ...seq('R', 101, 109), ...seq('TP', 3, 6)],
  '02 MCU': ['U1', 'Y1', ...seq('R', 201, 206), ...seq('C', 201, 211), 'FB201', 'J7', 'J9', 'SW1', 'D7', 'D8', 'D9'],
  '03 Gate driver': ['U2', ...seq('C', 301, 307), ...seq('R', 301, 312), ...seq('TP', 7, 9)],
  '04 Inverter': [...seq('Q', 1, 6), ...seq('R', 401, 415), ...seq('RSH', 1, 3), ...seq('C', 401, 409), 'J2', ...seq('TP', 10, 12)],
  '05 Sensing': ['U7', 'U8', ...seq('R', 501, 519), ...seq('C', 501, 513), 'NTC1', 'J3', ...seq('TP', 13, 15)],
  '06 Fault logic': [...seq('U', 9, 15), ...seq('C', 601, 608), ...seq('R', 601, 608), 'D10', 'D11', 'J8'],
  '07 Interfaces': ['U6', 'U18', 'U20', 'J4', 'F3', 'FB701', ...seq('C', 701, 708), ...seq('R', 701, 708), ...seq('D', 3, 6), 'D12', 'J5', 'J6', 'J10', 'JP701'],
  '08 Brake': ['U16', 'U17', 'Q7', 'F2', 'J11', 'D2', ...seq('R', 901, 908), ...seq('C', 901, 905)],
  Mechanical: [...seq('H', 1, 6), ...seq('FID', 1, 3)],
  External: ['ENC1', 'R_BRAKE_EXT', 'TORQUE1'],
};
const EXTERNAL_REFS = INVENTORY.External;
const PCB_REFS = Object.entries(INVENTORY).filter(([s]) => s !== 'External').flatMap(([, r]) => r);
const ALL_REFS = [...PCB_REFS, ...EXTERNAL_REFS];
const DNP_REFS = [...seq('R', 413, 415), ...seq('C', 407, 409), 'R708', 'C708'];

// A pin value beginning with @ is checked by an endpoint-based network rule.
const pinTable = text => Object.fromEntries(text.trim().split(/\s+/).map((net, i) => [String(i + 1), net === '-' ? null : net]));
const MCU_PINS = pinTable(`
 V3V3 - - - HSE_CLK - RESET_N VBUS_SENSE NTC_MOTOR_ADC NTC_BOARD_ADC REF25_MON IU_ADC IV_ADC IW_ADC GND V3V3
 BRAKE_ON ENC_CLK_EN ENC_CLK_LOGIC ENC_DATA_LOGIC - - DRV_ENABLE LED_FAULT EXP_PB1 EXP_PB2 GND VDDA3V3 VDDA3V3 FAULT_LATCH_OK GND V3V3
 EXP_PB11 FAULT_RAW_N PWM_UL PWM_VL PWM_WL MCU_RUN ARM_PULSE WDI PERMIT_OK PWM_UH PWM_VH PWM_WH CAN_RX CAN_TX GND V3V3
 SWDIO SWCLK - @SPI_SCK DRV_SDO @SPI_MOSI @SPI_CS SWO EXP_PB4 CAN_STB UART_TX UART_RX BOOT0 LED_STATUS GND V3V3`);
const MCU_LABELS = pinTable(`
 VBAT PC13 PC14 PC15 PF0 PF1 PG10_NRST PC0 PC1 PC2 PC3 PA0 PA1 PA2 VSS VDD
 PA3 PA4 PA5 PA6 PA7 PC4 PC5 PB0 PB1 PB2 VSSA VREF+ VDDA PB10 VSS VDD
 PB11 PB12 PB13 PB14 PB15 PC6 PC7 PC8 PC9 PA8 PA9 PA10 PA11 PA12 VSS VDD
 PA13 PA14 PA15 PC10 PC11 PC12 PD2 PB3 PB4 PB5 PB6 PB7 PB8 PB9 VSS VDD`);
const DRIVER_PINS = pinTable(`
 CP_L CP_H V12 VBUS VCP GH_U PH_U GL_U SHUNT_U_TOP GND GND SHUNT_V_TOP GL_V PH_V GH_V GH_W PH_W GL_W SHUNT_W_TOP GND
 IW_RAW IV_RAW IU_RAW VDDA3V3 GND FAULT_RAW_N DRV_SDO @SPI_MOSI @SPI_SCK @SPI_CS DRV_ENABLE
 PWM_UH_DRV PWM_UL_DRV PWM_VH_DRV PWM_VL_DRV PWM_WH_DRV PWM_WL_DRV DRV_DVDD GND DRV_VGLS GND`);
const DRIVER_LABELS = pinTable(`CPL CPH VM VDRAIN VCP GHA SHA GLA SPA SNA SNB SPB GLB SHB GHB GHC SHC GLC SPC SNC SOC SOB SOA VREF AGND nFAULT SDO SDI SCLK nSCS ENABLE INHA INLA INHB INLB INHC INLC DVDD GND VGLS EP`);
const IC_PINS = {
 U1: MCU_PINS, U2: DRIVER_PINS,
 U3: pinTable('GND VBUS VBUS @RON FB12 FAULT_RAW_N BST12 BUCK12_SW GND'),
 U4: pinTable('GND V12 V12 GND FB5 V5 BUCK5_SW FAULT_RAW_N'),
 U5: pinTable('V5 GND V5 - V3V3'),
 U6: pinTable('CAN_TX GND V5 CAN_RX V3V3 CANL CANH CAN_STB'),
 U7: pinTable('FAULT_RAW_N FAULT_RAW_N V3V3 I_LOW IU_ADC IU_ADC I_HIGH I_LOW IV_ADC IV_ADC I_HIGH GND FAULT_RAW_N FAULT_RAW_N'),
 U8: pinTable('FAULT_RAW_N FAULT_RAW_N V3V3 I_LOW IW_ADC IW_ADC I_HIGH VBUS_SENSE OV_REF UV_REF VBUS_SENSE GND FAULT_RAW_N FAULT_RAW_N'),
 U9: pinTable('ARM_PULSE V3V3 - GND FAULT_LATCH_OK FAULT_RAW_N V3V3 V3V3'),
 U10: pinTable('PWM_OE_N PWM_UH - PWM_UL - PWM_VH PWM_WL_DRV PWM_VL PWM_WH_DRV GND PWM_WH PWM_VL_DRV PWM_WL PWM_VH_DRV GND PWM_UL_DRV GND PWM_UH_DRV PWM_OE_N V3V3'),
 U11: pinTable('FAULT_LATCH_OK GND MCU_RUN PWM_OE_N V3V3 PERMIT_OK'),
 U12: pinTable('RESET_N GND @MR - V3V3 V3V3'),
 U13: pinTable('V3V3 @CWD V3V3 GND V3V3 WDI FAULT_RAW_N - GND'),
 U14: pinTable('- RESET_N GND RESET_BUF_N V3V3'),
 U15: pinTable('- PERMIT_FILT GND PERMIT_OK V3V3'),
 U16: pinTable('BRAKE_SENSE GND REF25 BRAKE_ON V3V3'),
 U17: pinTable('V12 @BRAKE_HIGH @BRAKE_LOW GND GND BRAKE_ON'),
 U18: pinTable('- V3V3 ENC_CLK_EN @ENC_CLOCK GND ENC_CLK_P ENC_CLK_N V3V3'),
 U21: pinTable('V12 V12 V12 - BOTA_IMAX BOTA_REF GND BOTA_ADJ BOTA_9V BOTA_9V GND'),
 U19: pinTable('V5 REF25 GND'),
 U20: pinTable('@ENC_DATA GND GND GND GND ENC_DATA_P ENC_DATA_N V3V3'),
};
const IC_MPNS = {
 U21: 'LT3065EDD#TRPBF', U1: 'STM32G431RBT6', U2: 'DRV8353SRTAR', U3: 'LM5164DDAR', U4: 'TPS62160DGKR', U5: 'TLV75533PDBVR',
 U6: 'TCAN1042HGVDR', U7: 'TLV1704AIPWR', U8: 'TLV1704AIPWR', U9: 'SN74LVC1G74DCTR', U10: 'SN74LVC244APWR',
 U11: 'SN74LVC1G10DBVR', U12: 'TPS3808G33QDBVRQ1', U13: 'TPS3431SDRBR', U14: 'SN74LVC1G17DBVR', U15: 'SN74LVC1G17DBVR',
 U16: 'TLV1701AIDBVR', U17: 'UCC27511DBVR', U18: 'THVD2450DR', U19: 'REF3025EAIDBZR', U20: 'THVD2450DR',
};
const CONNECTORS = {
 J12: pinTable('BOTA_9V GND'), J1: pinTable('DC_IN GND'), J2: pinTable('PH_U PH_V PH_W'), J3: pinTable('NTC_MOTOR_RAW GND'),
 J4: pinTable('ENC12 GND - - - - ENC_CLK_P ENC_CLK_N ENC_DATA_P ENC_DATA_N SHIELD'),
 J5: pinTable('CANH CANL GND SHIELD'), J6: pinTable('CANH CANL GND SHIELD'),
 J7: pinTable('V3V3 SWDIO GND SWCLK GND SWO - - GND RESET_N'), J8: pinTable('V3V3 PERMIT_IN GND'),
 J9: pinTable('GND UART_TX UART_RX V3V3'), J10: pinTable('GND V3V3 EXP_PB1 EXP_PB2 EXP_PB4 EXP_PB11'), J11: pinTable('BRAKE_PLUS BRAKE_DRAIN'),
};

// Parse engineering values without accepting a voltage/power rating as the value.
export function numericValue(value) {
 if (typeof value === 'number') return Number.isFinite(value) ? value : NaN;
 const s = String(value ?? '').trim().replaceAll('µ', 'u').replaceAll('μ', 'u').replaceAll('Ω', 'ohm');
 const inline = s.match(/^(\d+)([RrKkMm])([0-9]+)(?=\s|ohm|$)/);
 const scale = { p: 1e-12, n: 1e-9, u: 1e-6, m: 1e-3, k: 1e3, K: 1e3, M: 1e6, G: 1e9, R: 1, r: 1 };
 if (inline) return Number(`${inline[1]}.${inline[3]}`) * scale[inline[2]];
 const match = s.match(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s*([pnumkKMG])?/i);
 if (!match) return NaN;
 // "1 Mohm", "1 mOhm", "47 nF", "33 ohm" and raw SI numbers.
 return Number(match[1]) * (match[2] ? scale[match[2]] ?? NaN : 1);
}

class Missing extends Error {}
export function audit({ components = [], catalog = null, inputs = [], inputErrors = [] } = {}) {
 const checks = [];
 const byRef = new Map();
 for (const c of components) if (isObject(c) && typeof c.ref === 'string' && !byRef.has(c.ref)) byRef.set(c.ref, c);
 const add = (id, status, message, details = {}, blocking = true) => checks.push({ id, status, blocking, message, ...details });
 const run = (id, refs, fn, source = 'Rev A PDF §§18–21') => {
  const absent = refs.filter(r => !byRef.has(r));
  if (absent.length) return add(id, 'unresolved', 'Required component data is missing.', { refs, missing: absent, source });
  try {
   const result = fn();
   const detail = typeof result === 'boolean' ? { ok: result } : result;
   const { ok, ...evidence } = detail;
   add(id, ok ? 'passed' : 'failed', evidence.message ?? (ok ? 'Matches independent expectation.' : 'Does not match independent expectation.'), { refs, source, ...evidence });
  } catch (e) {
   add(id, e instanceof Missing ? 'unresolved' : 'failed', e.message, { refs, source });
  }
 };
 const part = ref => { if (!byRef.has(ref)) throw new Missing(`Missing component ${ref}`); return byRef.get(ref); };
 const net = (ref, pin) => {
  const p = part(ref);
  if (!isObject(p.pins) || !Object.hasOwn(p.pins, String(pin))) throw new Error(`${ref}.${pin}: physical pin is missing`);
  const n = p.pins[String(pin)];
  if (n !== null && (typeof n !== 'string' || !n.trim() || n !== n.trim() || /^(NC|N\/C|unconnected)$/i.test(n))) throw new Error(`${ref}.${pin}: use a real net string or null for NC`);
  return n;
 };
 const pins = ref => Object.keys(part(ref).pins ?? {});
 const val = ref => numericValue(part(ref).value);
 const entries = n => components.flatMap(c => Object.entries(c?.pins ?? {}).filter(([, v]) => v === n).map(([p]) => `${c.ref}.${p}`));
 const pair = (ref, a, b) => {
  const actual = pins(ref).map(p => net(ref, p));
  return { ok: actual.length === 2 && a !== null && b !== null && a !== b && sameSet(actual, [a, b]), expected: [a, b], actual };
 };
 const value = (ref, expected) => run(`value.${ref}`, [ref], () => ({ ok: Number.isFinite(val(ref)) && Math.abs(val(ref) - expected) <= Math.max(Math.abs(expected) * 1e-8, 1e-15), expected, actual: val(ref), valueText: part(ref).value }));
 const two = (ref, a, b, expected) => {
  run(`connection.${ref}`, [ref], () => pair(ref, a, b));
  if (expected !== undefined) value(ref, expected);
 };
 const exact = (ref, expected) => {
  run(`package.${ref}.pins`, [ref], () => ({ ok: sameSet(pins(ref), Object.keys(expected)), expected: Object.keys(expected), actual: pins(ref) }));
  for (const [p, n] of Object.entries(expected)) {
   if (typeof n === 'string' && n.startsWith('@')) continue;
   run(`pin.${ref}.${p}`, [ref], () => ({ ok: net(ref, p) === n, pin: p, expected: n, actual: net(ref, p) }));
  }
 };
 // Series rule is invariant under renaming the internal junction. Removing the
 // resistor must disconnect its endpoints; coincident nets are a hard failure.
 const series = (id, resistor, a, b, expected) => {
  run(id, [resistor, a[0], b[0]], () => {
   const na = net(...a), nb = net(...b);
   return { ...pair(resistor, na, nb), endpoints: [`${a[0]}.${a[1]}`, `${b[0]}.${b[1]}`], message: 'Series element must join two distinct endpoint nets.' };
  });
  value(resistor, expected);
 };
 const endpointPair = (id, ref, a, b) => run(id, [ref, a[0], b[0]], () => pair(ref, net(...a), net(...b)));
 const railFromEndpoint = (id, ref, a, rail) => run(id, [ref, a[0]], () => pair(ref, net(...a), rail));
 // A two-resistor chain has exactly one private junction. This catches a
 // shorted divider leg and an unintended third connection at the midpoint.
 const chain = (id, r1, r2, start, end, extra = []) => run(id, [r1, r2, ...extra.map(e => e[0])], () => {
  const x = pins(r1).map(p => net(r1, p)), y = pins(r2).map(p => net(r2, p));
  const common = sorted(x.filter(n => n !== null && y.includes(n)));
  const junction = common[0];
  const allowed = [`${r1}.1`, `${r1}.2`, `${r2}.1`, `${r2}.2`, ...extra.map(e => `${e[0]}.${e[1]}`)];
  return { ok: x.length === 2 && y.length === 2 && common.length === 1 && junction !== start && junction !== end && x.includes(start) && y.includes(end) && extra.every(e => net(...e) === junction) && entries(junction).every(e => allowed.includes(e)), start, end, junction, first: x, second: y };
 });

 for (const e of inputErrors) add(`input.${e.file}`, 'unresolved', e.message, { file: e.file });
 run('inventory.references', [], () => {
  const present = [...byRef.keys()];
  const missing = ALL_REFS.filter(r => !byRef.has(r));
  const unexpected = present.filter(r => !ALL_REFS.includes(r));
  const duplicates = components.map(c => c?.ref).filter((r, i, list) => list.indexOf(r) !== i);
  return { ok: !missing.length && !unexpected.length && !duplicates.length, expectedCount: ALL_REFS.length, actualCount: components.length, missing, unexpected, duplicates };
 });
 for (const c of components) {
  if (!isObject(c) || typeof c.ref !== 'string') { add('schema.invalid-component', 'failed', 'Every component must be an object with a reference.'); continue; }
  run(`schema.${c.ref}`, [c.ref], () => {
   const errors = [];
   for (const field of ['sheet', 'kind', 'value', 'pins', 'pinLabels', 'notes', 'provisional', 'dnp']) if (!Object.hasOwn(c, field)) errors.push(`Missing ${field}`);
   if (!isObject(c.pins)) errors.push('pins must be an object');
   if (!isObject(c.pinLabels)) errors.push('pinLabels must be an object');
   if (typeof c.dnp !== 'boolean') errors.push('dnp must be boolean');
   if (typeof c.provisional !== 'boolean') errors.push('provisional must be boolean');
   for (const [p, n] of Object.entries(c.pins ?? {})) if (!/^\d+$/.test(p) || (n !== null && (typeof n !== 'string' || !n.trim() || /^(NC|N\/C)$/i.test(n)))) errors.push(`Invalid pin/net ${p}`);
   if (!EXTERNAL_REFS.includes(c.ref) && typeof c.footprint !== 'string') errors.push('PCB component needs a footprint');
   return { ok: !errors.length, errors };
  });
 }

 for (const [ref, expected] of Object.entries(IC_PINS)) {
  exact(ref, expected);
  run(`mpn.${ref}`, [ref], () => ({ ok: part(ref).mpn === IC_MPNS[ref], expected: IC_MPNS[ref], actual: part(ref).mpn }));
 }
 for (const [ref, labels] of [['U1', MCU_LABELS], ['U2', DRIVER_LABELS]]) run(`package.${ref}.labels`, [ref], () => {
  const normal = s => String(s ?? '').replace(/[^a-z0-9+]/gi, '').toUpperCase();
  const mismatches = Object.entries(labels).filter(([p, label]) => normal(part(ref).pinLabels?.[p]) !== normal(label)).map(([p, expected]) => ({ pin: p, expected, actual: part(ref).pinLabels?.[p] }));
  return { ok: !mismatches.length, mismatches };
 });
 for (const [ref, expected] of Object.entries(CONNECTORS)) exact(ref, expected);
 const tpNets = 'VBUS GND V12 V5 V3V3 REF25 DRV_SCK DRV_SDO FAULT_RAW_N PH_U PH_V PH_W IU_ADC IV_ADC IW_ADC'.split(' ');
 tpNets.forEach((n, i) => {
  if (i === 6) run('testpoint.TP7', ['TP7', 'U1', 'U2'], () => ({ ok: pins('TP7').length === 1 && [net('U1', 52), net('U2', 29)].includes(net('TP7', 1)), actual: net('TP7', 1) }));
  else exact(`TP${i + 1}`, { 1: n });
 });

 // INPUT, SUPPLIES, MCU. Fixed nets come from the PDF; private junctions below
 // are checked through real pins rather than spelling conventions.
 two('F1', 'DC_IN', 'VBUS');
 for (const [ref, mpn] of [['F1', '0487020.MXEP'], ['F2', '0487015.MXEP']]) {
  run(`assembly.${ref}.axial-fuse`, [ref], () => {
   const fuse = part(ref);
   const lands = catalog?.[fuse.footprint]?.elements ?? [];
   const leads = lands.filter(land => land.type === 'pcb_plated_hole');
   const leadPitch = leads.length === 2 ? Math.hypot(leads[1].x - leads[0].x, leads[1].y - leads[0].y) : null;
   const ok = fuse.mpn === mpn && fuse.dnp === false && !fuse.holder && leadPitch !== null &&
    Math.abs(leadPitch - 37.5) < 0.001 && !lands.some(land => ['pcb_hole', 'pcb_smtpad'].includes(land.type));
   return { ok, expectedMpn: mpn, actualMpn: fuse.mpn, leadPitchMm: leadPitch };
  }, '19 November 2026 direct-solder Littelfuse 487 layout revision');
 }
 exact('D1', { 1: 'VBUS', 2: 'GND' });
 // 2026-11-17 manufacturer-backed bulk/watchdog amendment supersedes Rev A's 470uF placeholders.
 for (let i = 1; i <= 4; i++) { exact(`C${i}`, { 1: 'VBUS', 2: 'GND' }); value(`C${i}`, 820e-6); }
 two('C5', 'VBUS', 'GND', 4.7e-6); two('R1', 'VBUS', 'GND', 22e3);
 two('L101', 'BUCK12_SW', 'V12', 68e-6); two('L102', 'BUCK5_SW', 'V5', 2.2e-6);
 for (const ref of ['C101', 'C102']) two(ref, 'VBUS', 'GND', 2.2e-6);
 for (const ref of ['C103', 'C104']) two(ref, 'V12', 'GND', 22e-6);
 two('C105', 'BST12', 'BUCK12_SW', 2.2e-9);
 railFromEndpoint('supply.ron', 'R101', ['U3', 4], 'GND'); value('R101', 100e3);
 two('R102', 'V12', 'FB12', 448e3); two('R103', 'FB12', 'GND', 49.9e3);
 run('supply.ripple-injection', ['R104', 'C106', 'C107', 'U3'], () => {
  const a = pins('R104').map(p => net('R104', p));
  const junction = a.find(n => n !== 'BUCK12_SW');
  return { ok: pair('R104', 'BUCK12_SW', junction).ok && pair('C106', junction, 'V12').ok && pair('C107', junction, 'FB12').ok && !['GND', 'V12', 'FB12', null].includes(junction), junction };
 });
 value('R104', 453e3); value('C106', 3.3e-9); value('C107', 56e-12);
 two('C108', 'V12', 'GND', 10e-6); two('C109', 'V5', 'GND', 22e-6);
 two('R105', 'V5', 'FB5', 523e3); two('R106', 'FB5', 'GND', 100e3);
 two('C110', 'V5', 'GND', 1e-6); two('C111', 'V3V3', 'GND', 10e-6);
 two('C112', 'V5', 'GND', 100e-9); two('C113', 'REF25', 'GND', 1e-6);
 two('R107', 'BOTA_9V', 'BOTA_ADJ', 140e3); two('R108', 'BOTA_ADJ', 'GND', 10e3);
 two('R109', 'BOTA_IMAX', 'GND', 1.1e3);
 two('C114', 'V12', 'GND', 10e-6); two('C115', 'BOTA_9V', 'GND', 10e-6);
 two('C116', 'BOTA_IMAX', 'GND', 22e-9); two('C117', 'BOTA_REF', 'GND', 10e-9);
 exact('Y1', { 1: 'V3V3', 2: 'GND', 3: '@OSC', 4: 'V3V3' });
 series('mcu.oscillator-series', 'R201', ['Y1', 3], ['U1', 5], 33);
 for (const ref of [...seq('C', 201, 204), 'C209', 'C211']) two(ref, 'V3V3', 'GND', 100e-9);
 two('C205', 'V3V3', 'GND', 4.7e-6); two('FB201', 'V3V3', 'VDDA3V3');
 two('C206', 'VDDA3V3', 'GND', 1e-6);
 for (const ref of ['C207', 'C208']) two(ref, 'VDDA3V3', 'GND', 100e-9);
 two('C210', 'RESET_N', 'GND', 100e-9); two('R202', 'RESET_N', 'V3V3', 10e3); two('R203', 'BOOT0', 'GND', 10e3);
 railFromEndpoint('fault.manual-reset-switch', 'SW1', ['U12', 3], 'GND');
 for (const [i, n] of ['V3V3', 'LED_STATUS', 'LED_FAULT'].entries()) {
  const r = `R${204 + i}`, d = `D${7 + i}`;
  exact(d, { 1: 'GND', 2: '@LED_ANODE' });
  railFromEndpoint(`mcu.led-series.${d}`, r, [d, 2], n); value(r, 3.3e3);
 }

 // DRIVER: floating pump reservoir and separate SPI nets are critical.
 two('C301', 'V12', 'GND', 10e-6); two('C302', 'V12', 'GND', 100e-9);
 two('C303', 'CP_L', 'CP_H', 47e-9); two('C304', 'VCP', 'VBUS', 1e-6);
 two('C305', 'DRV_VGLS', 'GND', 1e-6); two('C306', 'DRV_DVDD', 'GND', 1e-6); two('C307', 'VDDA3V3', 'GND', 100e-9);
 run('driver.dvdd-no-load', ['U2', 'C306'], () => ({ ok: sameSet(entries('DRV_DVDD'), ['U2.38', ...pins('C306').filter(p => net('C306', p) === 'DRV_DVDD').map(p => `C306.${p}`)]), actual: entries('DRV_DVDD') }));
 two('R301', 'DRV_SDO', 'V3V3', 2.2e3); two('R303', 'DRV_ENABLE', 'GND', 10e3);
 for (const [name, r, mcu, drv] of [['SCK', 'R304', 52, 29], ['MOSI', 'R305', 54, 28], ['CS', 'R306', 55, 30]]) series(`driver.spi.${name}`, r, ['U1', mcu], ['U2', drv], 33);
 railFromEndpoint('driver.cs-pullup', 'R302', ['U2', 30], 'V3V3'); value('R302', 10e3);
 for (const [i, n] of ['UH', 'UL', 'VH', 'VL', 'WH', 'WL'].entries()) two(`R${307 + i}`, `PWM_${n}_DRV`, 'GND', 10e3);

 // INVERTER: each individual gate and source return, two-pad Kelvin shunts,
 // phase order, and isolated optional snubber junctions.
 const gatePins = [6, 8, 15, 13, 16, 18];
 for (let i = 0; i < 6; i++) {
  const q = `Q${i + 1}`, phase = ['U', 'V', 'W'][Math.floor(i / 2)], high = i % 2 === 0;
  exact(q, { 1: '@GATE', 2: high ? 'VBUS' : `PH_${phase}`, 3: high ? `PH_${phase}` : `SHUNT_${phase}_TOP` });
  run(`mpn.${q}`, [q], () => ({ ok: part(q).mpn === 'CSD19536KTT', expected: 'CSD19536KTT', actual: part(q).mpn }));
  series(`gate.${q}.series`, `R${401 + i}`, ['U2', gatePins[i]], [q, 1], 4.7);
  endpointPair(`gate.${q}.pulldown`, `R${407 + i}`, [q, 1], [q, 3]); value(`R${407 + i}`, 10e3);
 }
 for (let i = 0; i < 3; i++) {
  const phase = ['U', 'V', 'W'][i];
  two(`RSH${i + 1}`, `SHUNT_${phase}_TOP`, 'GND', 0.001);
  two(`C${401 + i}`, 'VBUS', 'GND', 4.7e-6); two(`C${404 + i}`, 'VBUS', 'GND', 100e-9);
  chain(`inverter.snubber.${phase}`, `R${413 + i}`, `C${407 + i}`, `PH_${phase}`, 'GND');
  value(`R${413 + i}`, 2.2); value(`C${407 + i}`, 1e-9);
 }

 // SENSING and all eight window comparator polarities are independent of
 // component pinLabels. Comparator outputs sink when IN+ is below IN-.
 for (let i = 0; i < 3; i++) {
  const phase = ['U', 'V', 'W'][i];
  two(`R${501 + i}`, `I${phase}_RAW`, `I${phase}_ADC`, 47);
  two(`C${501 + i}`, `I${phase}_ADC`, 'GND', 1e-9);
 }
 chain('sensing.bus-divider-chain', 'R504', 'R505', 'VBUS', 'VBUS_SENSE');
 value('R504', 150e3); value('R505', 150e3); two('R506', 'VBUS_SENSE', 'GND', 10e3); two('C504', 'VBUS_SENSE', 'GND', 1e-9);
 for (const [top, bottom, source, node, rt, rb, cap] of [
  ['R507', 'R508', 'VDDA3V3', 'I_LOW', 28.7e3, 10e3, 'C505'],
  ['R509', 'R510', 'VDDA3V3', 'I_HIGH', 10e3, 28.7e3, 'C506'],
  ['R511', 'R512', 'REF25', 'OV_REF', 27.4e3, 100e3, 'C507'],
  ['R513', 'R514', 'REF25', 'UV_REF', 95.3e3, 100e3, 'C508'],
 ]) { two(top, source, node, rt); two(bottom, node, 'GND', rb); two(cap, node, 'GND', 10e-9); }
 two('NTC1', 'NTC_BOARD_RAW', 'GND', 10e3);
 for (const [i, which] of ['MOTOR', 'BOARD'].entries()) {
  two(`R${515 + i}`, 'VDDA3V3', `NTC_${which}_RAW`, 10e3);
  two(`R${517 + i}`, `NTC_${which}_RAW`, `NTC_${which}_ADC`, 1e3);
  two(`C${509 + i}`, `NTC_${which}_ADC`, 'GND', 100e-9);
 }
 two('R519', 'REF25', 'REF25_MON', 1e3); two('C511', 'REF25_MON', 'GND', 1e-9);
 for (const c of ['C512', 'C513']) two(c, 'V3V3', 'GND', 100e-9);
 const comparators = [
  ['U-low', 'U7', 5, 4, 2, 'IU_ADC', 'I_LOW'], ['U-high', 'U7', 7, 6, 1, 'I_HIGH', 'IU_ADC'],
  ['V-low', 'U7', 9, 8, 14, 'IV_ADC', 'I_LOW'], ['V-high', 'U7', 11, 10, 13, 'I_HIGH', 'IV_ADC'],
  ['W-low', 'U8', 5, 4, 2, 'IW_ADC', 'I_LOW'], ['W-high', 'U8', 7, 6, 1, 'I_HIGH', 'IW_ADC'],
  ['bus-OV', 'U8', 9, 8, 14, 'OV_REF', 'VBUS_SENSE'], ['bus-UV', 'U8', 11, 10, 13, 'VBUS_SENSE', 'UV_REF'],
 ];
 for (const [name, ref, plus, minus, out, pn, mn] of comparators) run(`comparator.${name}.polarity`, [ref], () => ({ ok: net(ref, plus) === pn && net(ref, minus) === mn && net(ref, out) === 'FAULT_RAW_N', plus: { pin: plus, expected: pn, actual: net(ref, plus) }, minus: { pin: minus, expected: mn, actual: net(ref, minus) }, output: net(ref, out) }));

 // FAULT CHAIN: explicit polarity, wired-OR sink whitelist, passive defaults.
 for (const c of seq('C', 601, 607)) two(c, 'V3V3', 'GND', 100e-9);
 for (const [r, a, b, v] of [
  ['R601', 'FAULT_RAW_N', 'V3V3', 2.2e3], ['R602', 'ARM_PULSE', 'GND', 10e3], ['R603', 'MCU_RUN', 'GND', 10e3],
  ['R604', 'PWM_OE_N', 'V3V3', 10e3], ['R606', 'WDI', 'GND', 10e3], ['R607', 'PERMIT_IN', 'PERMIT_FILT', 1e3], ['R608', 'PERMIT_FILT', 'GND', 10e3],
 ]) two(r, a, b, v);
 railFromEndpoint('fault.watchdog-timeout-resistor', 'R605', ['U13', 2], 'V3V3'); value('R605', 10e3);
 two('C608', 'PERMIT_FILT', 'GND', 1e-9);
 for (const [ref, cathode] of [['D10', 'RESET_BUF_N'], ['D11', 'PERMIT_OK']]) {
  exact(ref, { 1: cathode, 2: 'FAULT_RAW_N' });
  run(`fault.${ref}.polarity`, [ref], () => ({ ok: net(ref, 1) === cathode && net(ref, 2) === 'FAULT_RAW_N' && /^K(?:ATHODE)?$|^CATHODE$/i.test(part(ref).pinLabels?.['1'] ?? '') && /^A(?:NODE)?$/i.test(part(ref).pinLabels?.['2'] ?? ''), expected: { 1: `K:${cathode}`, 2: 'A:FAULT_RAW_N' }, actual: part(ref).pins, labels: part(ref).pinLabels }));
 }
 run('fault.wired-or-members', ['U1', 'U2', 'U3', 'U4', 'U7', 'U8', 'U9', 'U13', 'R601', 'D10', 'D11', 'TP9'], () => {
  const expected = ['U1.34', 'U2.26', 'U3.6', 'U4.8', 'U7.1', 'U7.2', 'U7.13', 'U7.14', 'U8.1', 'U8.2', 'U8.13', 'U8.14', 'U9.6', 'U13.7', 'D10.2', 'D11.2', 'TP9.1', ...pins('R601').filter(p => net('R601', p) === 'FAULT_RAW_N').map(p => `R601.${p}`)];
  return { ok: sameSet(entries('FAULT_RAW_N'), expected), expected: sorted(expected), actual: sorted(entries('FAULT_RAW_N')), message: 'Fault net must contain only the specified open-drain/collector sinks, diode anodes, pullup, and inputs.' };
 });

 // ENCODER / CAN. Two 33-ohm digital series links and J4 are independently
 // checked against the eleven-position board-side harness assignment.
 two('F3', 'V12', 'ENC12_FUSED'); two('FB701', 'ENC12_FUSED', 'ENC12');
 two('C701', 'ENC12', 'GND', 10e-6); two('C702', 'ENC12', 'GND', 100e-9);
 exact('D12', { 1: 'ENC12', 2: 'GND' });
 for (const c of ['C703', 'C704', 'C706']) two(c, 'V3V3', 'GND', 100e-9);
 two('C705', 'V5', 'GND', 100e-9); two('C707', 'V5', 'GND', 1e-6);
 two('R701', 'ENC_DATA_P', 'ENC_DATA_N', 120); two('R702', 'ENC_CLK_EN', 'GND', 10e3); two('R703', 'ENC_CLK_LOGIC', 'V3V3', 10e3);
 series('encoder.clock-series', 'R704', ['U1', 19], ['U18', 4], 33);
 series('encoder.data-series', 'R705', ['U20', 1], ['U1', 20], 33);
 two('R706', 'CAN_STB', 'V3V3', 10e3);
 chain('can.termination-series-jumper', 'R707', 'JP701', 'CANH', 'CANL'); value('R707', 120);
 run('can.termination-default-open', ['JP701'], () => ({ ok: part('JP701').dnp === true || /open/i.test(String(part('JP701').value)), actual: { dnp: part('JP701').dnp, value: part('JP701').value } }));
 two('R708', 'SHIELD', 'GND', 1e6); two('C708', 'SHIELD', 'GND', 1e-9);
 for (const [ref, p, n] of [['D3', 'CANH', 'CANL'], ['D4', 'ENC_CLK_P', 'ENC_CLK_N'], ['D5', 'ENC_DATA_P', 'ENC_DATA_N']]) exact(ref, { 1: p, 2: n, 3: 'GND' });

 // BRAKE. The 200 W resistor is outside the board; only its connector is on it.
 two('F2', 'VBUS', 'BRAKE_PLUS'); exact('D2', { 1: 'BRAKE_PLUS', 2: 'BRAKE_DRAIN' });
 exact('Q7', { 1: '@BRAKE_GATE', 2: 'BRAKE_DRAIN', 3: 'GND' });
 chain('brake.bus-divider-chain', 'R901', 'R902', 'VBUS', 'BRAKE_SENSE');
 value('R901', 150e3); value('R902', 150e3); two('R903', 'BRAKE_SENSE', 'GND', 14e3);
 two('R904', 'BRAKE_ON', 'BRAKE_SENSE', 499e3); two('R905', 'BRAKE_ON', 'V3V3', 2.2e3);
 two('C901', 'BRAKE_SENSE', 'GND', 470e-12); two('C902', 'V3V3', 'GND', 100e-9);
 two('C903', 'V12', 'GND', 1e-6); two('C904', 'V12', 'GND', 100e-9); two('C905', 'VBUS', 'GND', 4.7e-6);
 series('brake.gate-source-series', 'R906', ['U17', 2], ['Q7', 1], 4.7);
 series('brake.gate-sink-series', 'R907', ['U17', 3], ['Q7', 1], 2.2);
 endpointPair('brake.gate-pulldown', 'R908', ['Q7', 1], ['Q7', 3]); value('R908', 10e3);
 run('brake.split-driver-outputs', ['U17'], () => ({ ok: net('U17', 2) !== net('U17', 3), outputs: [net('U17', 2), net('U17', 3)] }));

 // Independent numerical acceptance intervals, not values generated from the
 // checked object. Computed results use the actual BOM resistance values.
 const numerical = (id, refs, compute, bounds) => run(id, refs, () => {
  const actual = compute();
  return { ok: Object.entries(bounds).every(([key, [lo, hi]]) => Number.isFinite(actual[key]) && actual[key] >= lo && actual[key] <= hi), actual, bounds };
 });
 numerical('threshold.supplies', ['R102', 'R103', 'R105', 'R106'], () => ({ V12: 1.2 * (1 + val('R102') / val('R103')), V5: 0.8 * (1 + val('R105') / val('R106')) }), { V12: [11.97, 11.98], V5: [4.98, 4.99] });
 numerical('threshold.bus', seq('R', 504, 506).concat(seq('R', 511, 514)), () => {
  const ratio = (val('R504') + val('R505') + val('R506')) / val('R506');
  return { dividerRatio: ratio, OV: 2.5 * val('R512') / (val('R511') + val('R512')) * ratio, UV: 2.5 * val('R514') / (val('R513') + val('R514')) * ratio };
 }, { dividerRatio: [30.999, 31.001], OV: [60.82, 60.84], UV: [39.67, 39.69] });
 numerical('threshold.current-window', [...seq('R', 507, 510), ...seq('RSH', 1, 3)], () => {
  const low = 3.3 * val('R508') / (val('R507') + val('R508'));
  const high = 3.3 * val('R510') / (val('R509') + val('R510'));
  return { low, high, ...Object.fromEntries([1, 2, 3].flatMap(i => [[`positiveTrip${i}`, (1.65 - low) / (20 * val(`RSH${i}`))], [`negativeTrip${i}`, (1.65 - high) / (20 * val(`RSH${i}`))]])) };
 }, { low: [0.852, 0.854], high: [2.446, 2.448], ...Object.fromEntries([1, 2, 3].flatMap(i => [[`positiveTrip${i}`, [39.8, 40]], [`negativeTrip${i}`, [-40, -39.8]]])) });
 numerical('threshold.brake', seq('R', 901, 905), () => {
  const top = val('R901') + val('R902'), bottom = val('R903'), feedback = val('R904');
  const on = 2.5 * (1 + top / bottom + top / feedback), off = on - 3.3 * top / feedback;
  // Open-collector output is loaded by R904, so ideal 3.3 V is optimistic.
  const loadedHigh = (3.3 / val('R905') + 2.5 / feedback) / (1 / val('R905') + 1 / feedback);
  return { on, off, hysteresis: on - off, loadedOff: on - loadedHigh * top / feedback };
 }, { on: [57.56, 57.59], off: [55.58, 55.61], hysteresis: [1.98, 1.99], loadedOff: [55.58, 55.62] });

 for (const ref of DNP_REFS) run(`population.${ref}`, [ref], () => ({ ok: part(ref).dnp === true, expected: true, actual: part(ref).dnp }));
 for (const ref of PCB_REFS.filter(r => !DNP_REFS.includes(r) && r !== 'JP701')) run(`population.${ref}`, [ref], () => ({ ok: part(ref).dnp === false, expected: false, actual: part(ref).dnp }));
 for (const ref of EXTERNAL_REFS) run(`external.${ref}`, [ref], () => ({ ok: !part(ref).footprint && (/external/i.test(String(part(ref).sheet)) || part(ref).external === true || /external/i.test(String(part(ref).kind))), footprint: part(ref).footprint, sheet: part(ref).sheet, message: 'External assembly must be explicitly external and have no PCB footprint.' }));
 run('external.torque-host-ethercat', ['TORQUE1','J5'], () => ({
  ok: part('TORQUE1').mpn === 'BTS-T300-CAT' && part('TORQUE1').connectsTo === 'Jetson EtherCAT master and J12 power' && net('J5',1) === 'CANH' && net('J5',2) === 'CANL',
  message: 'The Jetson terminates Bota EtherCAT. The drive supplies J12 and takes commands over CAN.'
 }));
 if (byRef.has('R_BRAKE_EXT')) { two('R_BRAKE_EXT', 'BRAKE_PLUS', 'BRAKE_DRAIN', 4.7); }
 for (const ref of INVENTORY.Mechanical) run(`mechanical.${ref}.unconnected`, [ref], () => ({ ok: Object.values(part(ref).pins ?? {}).every(n => n === null), actual: part(ref).pins }));

 // Do not infer correctness from footprint matching alone: IC pin sets above
 // are a second independent reference and catch a mutually wrong symbol/land.
 for (const ref of PCB_REFS) run(`footprint.${ref}`, [ref], () => {
  if (!catalog) throw new Missing('footprints/catalog.json is not available.');
  const key = part(ref).footprint, fp = catalog[key];
  if (!fp) throw new Missing(`Footprint ${key} is absent from catalog.`);
  if (!Array.isArray(fp.pads) || !fp.pads.every(p => typeof p === 'string')) return { ok: false, message: 'Catalog pads must be an array of strings.', footprint: key };
  return { ok: sameSet(pins(ref), fp.pads), footprint: key, expectedPackagePins: pins(ref), actualFootprintPads: fp.pads, missingPads: pins(ref).filter(p => !fp.pads.includes(p)), extraPads: fp.pads.filter(p => !pins(ref).includes(p)) };
 });

 // Physical and datasheet-only gates are never claimed as verified by a
 // netlist. They remain in the machine-readable report even after a pass.
 const releaseGates = [
  ['provisional-packages', 'Manufacturer drawing review remains open for DRV8353 RTA; J4 requires FLUX harness verification; D2 and D3-D5 package numbering require independent verification. See data provisionalReason fields.'],
  ['motor-fit', 'Motor OD112 and six Ø4.5 holes on PCD104 are sourced from the motor study. The Ø28 PCB opening is proposed from the shoulder opening; axial clearance, standoffs, encoder mount and assembly fit remain unverified.'],
  ['layout', 'Kelvin routing, gate loops, decoupler placement, creepage, current paths, and thermal interfaces require PCB/layout review.'],
  ['ratings', 'Voltage/pulse/current/temperature ratings, capacitor bias/ripple derating, fuse coordination, TVS clamping, and MOSFET SOA require selected-part evidence and bench tests.'],
  ['threshold-tolerance', 'Threshold calculations are nominal (3.3 V, 2.5 V, CSA gain 20); worst-case reference/comparator/CSA/resistor tolerances and fault response time remain unverified.'],
  ['brake-energy', 'External 4.7-ohm / 200-W resistor energy, cooling, wiring inductance, duty cycle, and thermal cutoff remain system-level open items.'],
  ['firmware', 'MCU alternate functions, CSA register settings, dead time, ADC timing, BiSS framing, watchdog service, and no automatic rearm require firmware and hardware validation.'],
  ['encoder-harness', 'FLUX order code, connector orientation, 12-V startup current, remote clock termination, and mechanical fit require supplier/harness confirmation.'],
 ];
 for (const [id, message] of releaseGates) add(`release.${id}`, 'unresolved', message, {}, false);
 const counts = Object.fromEntries(['passed', 'failed', 'unresolved'].map(s => [s, checks.filter(c => c.status === s).length]));
 const blockingUnresolved = checks.filter(c => c.status === 'unresolved' && c.blocking).length;
 return {
  schemaVersion: 1, generatedAt: new Date().toISOString(),
  status: counts.failed ? 'failed' : blockingUnresolved ? 'incomplete' : 'passed',
  fabricationReady: false,
  scope: 'Independent component/netlist audit against Rev A PDF. A pass is not PCB, firmware, datasheet-limit, or fabrication approval.',
  source: { document: 'docs/Space_Octopus_Motor_PCB_Plan_RevA.pdf', inventoryPages: '13–21', pinPages: '22–27', harnessPage: 8, expectations: 'Hard-coded independent transcription; internal nets validated by endpoint topology.' },
  inputs, inventory: { expectedPCBCount: PCB_REFS.length, expectedExternalCount: EXTERNAL_REFS.length, expectedRefs: sorted(ALL_REFS), expectedBySheet: INVENTORY, actualCount: components.length },
  summary: { ...counts, blockingUnresolved, total: checks.length }, checks,
 };
}

function readInputs(root) {
 const components = [], inputs = [], inputErrors = [];
 let catalog = null;
 for (const file of [...DATA_FILES, 'footprints/catalog.json']) {
  try {
   const raw = fs.readFileSync(path.join(root, file));
   const parsed = JSON.parse(raw.toString('utf8'));
   if (file.startsWith('data/')) {
    if (!Array.isArray(parsed)) throw new Error('Expected a JSON array of components.');
    components.push(...parsed);
   } else {
    if (!isObject(parsed)) throw new Error('Expected a footprint catalog object.');
    catalog = parsed;
   }
   inputs.push({ file, sha256: hash(raw), bytes: raw.length });
  } catch (e) { inputErrors.push({ file, message: e.code === 'ENOENT' ? 'Required input has not been created yet.' : e.message }); }
 }
 for (const file of ['docs/Space_Octopus_Motor_PCB_Plan_RevA.pdf', 'docs/source-plan.txt']) {
  try { const raw = fs.readFileSync(path.join(root, file)); inputs.push({ file, sha256: hash(raw), bytes: raw.length }); }
  catch (e) { inputErrors.push({ file, message: e.message }); }
 }
 return { components, catalog, inputs, inputErrors };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
 const input = readInputs(ROOT);
 const report = audit(input);
 const dest = path.join(ROOT, 'output/electrical-audit.json');
 fs.mkdirSync(path.dirname(dest), { recursive: true });
 fs.writeFileSync(dest, `${JSON.stringify(report, null, 2)}\n`);
 console.log(`Electrical audit: ${report.status}; ${report.summary.passed} passed, ${report.summary.failed} failed, ${report.summary.blockingUnresolved} blocking unresolved.`);
 for (const c of report.checks.filter(c => c.status === 'failed' || (c.status === 'unresolved' && c.id.startsWith('input.')))) console.error(`${c.status.toUpperCase()} ${c.id}: ${c.message}`);
 console.log(`Report: ${path.relative(ROOT, dest)}`);
 process.exitCode = report.summary.failed ? 1 : report.summary.blockingUnresolved ? 2 : 0;
}
