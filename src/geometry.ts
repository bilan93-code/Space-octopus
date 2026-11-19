import config from '../data/board-geometry.json';

export const geometry = config;
// A regular polygon keeps the same circular outline in the tscircuit editor,
// Circuit JSON, exported SVGs and the placement validator.
export const circularOutline = Array.from({length: config.outlineSegments}, (_, i) => {
  const angle = 2 * Math.PI * i / config.outlineSegments;
  return {x: config.outerDiameterMm / 2 * Math.cos(angle), y: config.outerDiameterMm / 2 * Math.sin(angle)};
});
