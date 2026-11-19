export function isFitted(part) {
  return !part.dnp
    && part.assembly !== 'wire-termination'
    && part.ref !== 'JP701'
    && !['hole', 'fiducial', 'testpoint'].includes(part.kind);
}
