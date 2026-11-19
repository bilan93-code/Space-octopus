import a from '../data/input-supplies-mcu-driver-inverter.json';
import b from '../data/sensing-fault-interfaces-brake.json';
import m from '../data/mechanical.json';
import f from '../footprints/catalog.json';
import xy from '../data/placement.json';
export interface Part {
 ref:string; sheet:string; kind:string; value:string; mpn?:string; lcsc?:string; footprint:string;
 pins:Record<string,string|null>; pinLabels:Record<string,string>; notes:string;
 dnp:boolean; provisional:boolean; provisionalReason?:string;
}
export interface Footprint { elements:Record<string,unknown>[]; box:number[]; pads:string[] }
export interface Placement {x:number;y:number;rotation:number;courtyard:number[];bodyCenter:number[];fixed:boolean;layer:'top'|'bottom';occupiesLayers:string[]}
export const parts=[...a,...b,...m] as Part[];
export const footprints=f as unknown as Record<string,Footprint>;
export const placement=xy as Record<string,Placement>;
export const sheets=['00_Input','01_Supplies','02_MCU','03_GateDriver','04_Inverter','05_Sensing','06_FaultLogic','07_Interfaces','08_Brake'];
export const sheetNotes=[
 '48 V nominal • 54 V assumed maximum • upstream precharge and polarity protection',
 'VBUS → 12 V → 5 V → 3.3 V • 12 V → protected 9 V sensor branch • REF25 = 2.5 V • verify effective capacitor values',
 'STM32G431RBT6 • HSE bypass 8 MHz • SWD • external default-off controls',
 'DRV8353S • SPI • three current amplifiers • EP 41 to GND • C304 floats above VBUS',
 'Three half bridges • 100 V MOSFETs • 1 mΩ shunts • true Kelvin branches at shunt pads',
 'Current window ±39.9 A nominal • bus UV 39.68 V / OV 60.83 V • two NTC inputs',
 'Faults clear latched permission • deliberate arm pulse required • permit is local 3.3 V',
 'FLUX BiSS-C • robot host CAN • Bota EtherCAT to Jetson; power from J12 • termination jumper OPEN',
 'Independent chopper • nominal ON 57.57 V / OFF 55.59 V • resistor external at J11',
];
export function electricalValue(text:string):number {
 const s=text.replaceAll('µ','u');const match=s.match(/^([\d.]+)\s*([pnumkKM])?/);
 if(!match)throw Error(`Missing numerical value: ${text}`);
 return Number(match[1])*({p:1e-12,n:1e-9,u:1e-6,m:1e-3,k:1e3,K:1e3,M:1e6}[match[2]]??1);
}
