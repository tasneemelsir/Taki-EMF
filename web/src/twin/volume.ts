// Ray-marched rendering of the coarse 3-D field volume: a soft "field glow"
// around the conductors and a shaded iso-surface at a chosen field level.
// The volume is log-encoded 8-bit, so a texture value t in [0,1] means
// field = lo * (hi / lo) ^ t.

import * as THREE from 'three';

const VERT = /* glsl */ `
out vec3 vWorld;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`;

const COMMON = /* glsl */ `
precision highp float;
precision highp sampler3D;
uniform sampler3D uVol0;
uniform sampler3D uVolS;
uniform vec3 uMin;
uniform vec3 uMax;
uniform vec3 uDim;
uniform float uUseShield;
uniform float uShieldZc;
uniform float uShieldZh;
in vec3 vWorld;
out vec4 fragColor;

float fieldAt(vec3 p) {
  vec3 f = clamp((p - uMin) / (uMax - uMin), 0.0, 1.0);
  vec3 uvw = (0.5 + f * (uDim - 1.0)) / uDim;
  if (uUseShield > 0.5 && abs(p.z - uShieldZc) <= uShieldZh) return texture(uVolS, uvw).r;
  return texture(uVol0, uvw).r;
}

bool boxHit(vec3 ro, vec3 rd, out float tn, out float tf) {
  vec3 inv = 1.0 / rd;
  vec3 a = (uMin - ro) * inv;
  vec3 b = (uMax - ro) * inv;
  vec3 lo = min(a, b);
  vec3 hi = max(a, b);
  tn = max(max(lo.x, lo.y), max(lo.z, 0.0));
  tf = min(min(hi.x, hi.y), hi.z);
  return tf > tn;
}

float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
`;

const GLOW_FRAG = COMMON + /* glsl */ `
uniform float uT0;
uniform float uT1;
uniform float uStrength;
uniform vec3 uColA;
uniform vec3 uColB;
void main() {
  vec3 ro = cameraPosition;
  vec3 rd = normalize(vWorld - ro);
  float tn; float tf;
  if (!boxHit(ro, rd, tn, tf)) discard;
  const int N = 64;
  float dt = (tf - tn) / float(N);
  float j = hash(gl_FragCoord.xy);
  vec3 col = vec3(0.0);
  float alpha = 0.0;
  float scale = uStrength * dt / 22.0;
  for (int i = 0; i < N; i++) {
    vec3 p = ro + rd * (tn + (float(i) + j) * dt);
    float t = clamp((fieldAt(p) - uT0) / (uT1 - uT0), 0.0, 1.0);
    float d = t * t * t * t * scale;
    vec3 c = mix(uColA, uColB, t * t);
    col += (1.0 - alpha) * d * c;
    alpha += (1.0 - alpha) * d;
    if (alpha > 0.97) break;
  }
  if (alpha < 0.004) discard;
  fragColor = vec4(col / max(alpha, 1e-4), alpha);
}`;

const ISO_FRAG = COMMON + /* glsl */ `
uniform float uIso;
uniform vec3 uIsoColor;
uniform float uOpacity;
uniform vec3 uLight;
uniform mat4 uViewProj;
void main() {
  vec3 ro = cameraPosition;
  vec3 rd = normalize(vWorld - ro);
  float tn; float tf;
  if (!boxHit(ro, rd, tn, tf)) discard;
  const int N = 112;
  float dt = (tf - tn) / float(N);
  float j = hash(gl_FragCoord.xy);
  float prev = fieldAt(ro + rd * tn);
  float tPrev = tn;
  bool found = false;
  vec3 hit = vec3(0.0);
  for (int i = 1; i <= N; i++) {
    float tt = tn + (float(i) - 1.0 + j) * dt;
    float v = fieldAt(ro + rd * tt);
    if ((prev - uIso) * (v - uIso) < 0.0) {
      float f = (uIso - prev) / (v - prev);
      hit = ro + rd * mix(tPrev, tt, f);
      found = true;
      break;
    }
    prev = v; tPrev = tt;
  }
  if (!found) discard;
  vec3 e = (uMax - uMin) / uDim * 0.75;
  vec3 g = vec3(
    fieldAt(hit + vec3(e.x, 0.0, 0.0)) - fieldAt(hit - vec3(e.x, 0.0, 0.0)),
    fieldAt(hit + vec3(0.0, e.y, 0.0)) - fieldAt(hit - vec3(0.0, e.y, 0.0)),
    fieldAt(hit + vec3(0.0, 0.0, e.z)) - fieldAt(hit - vec3(0.0, 0.0, e.z))) / (2.0 * e);
  vec3 n = normalize(-g + vec3(1e-6));
  if (dot(n, rd) > 0.0) n = -n;
  float diffuse = 0.42 + 0.58 * max(dot(n, normalize(uLight)), 0.0);
  float rim = pow(1.0 - max(dot(n, -rd), 0.0), 2.5);
  vec3 c = uIsoColor * diffuse + vec3(1.0) * rim * 0.28;
  fragColor = vec4(c, clamp(uOpacity + rim * 0.35, 0.0, 0.95));
  vec4 clip = uViewProj * vec4(hit, 1.0);
  gl_FragDepth = clamp(clip.z / clip.w * 0.5 + 0.5, 0.0, 1.0);
}`;

export function volumeTexture(data: Uint8Array, nx: number, ny: number, nz: number): THREE.Data3DTexture {
  const t = new THREE.Data3DTexture(data as unknown as BufferSource, nx, ny, nz);
  t.format = THREE.RedFormat;
  t.type = THREE.UnsignedByteType;
  t.minFilter = THREE.LinearFilter;
  t.magFilter = THREE.LinearFilter;
  t.wrapS = t.wrapT = t.wrapR = THREE.ClampToEdgeWrapping;
  t.unpackAlignment = 1;
  t.needsUpdate = true;
  return t;
}

/** A colour whose components are passed to the shader exactly as written (no sRGB -> linear conversion). */
export function rawColor(hex: string): THREE.Color {
  return new THREE.Color().setStyle(hex, THREE.LinearSRGBColorSpace);
}

function common() {
  return {
    uVol0: { value: null as THREE.Data3DTexture | null },
    uVolS: { value: null as THREE.Data3DTexture | null },
    uMin: { value: new THREE.Vector3() },
    uMax: { value: new THREE.Vector3(1, 1, 1) },
    uDim: { value: new THREE.Vector3(2, 2, 2) },
    uUseShield: { value: 0 },
    uShieldZc: { value: 0 },
    uShieldZh: { value: 0 },
  };
}

export function glowMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    vertexShader: VERT,
    fragmentShader: GLOW_FRAG,
    uniforms: {
      ...common(),
      uT0: { value: 0.3 }, uT1: { value: 0.9 }, uStrength: { value: 1 },
      uColA: { value: rawColor('#FFB454') }, uColB: { value: rawColor('#FFF3C4') },
    },
    side: THREE.BackSide, transparent: true, depthTest: false, depthWrite: false,
  });
}

export function isoMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    vertexShader: VERT,
    fragmentShader: ISO_FRAG,
    uniforms: {
      ...common(),
      uIso: { value: 0.5 }, uIsoColor: { value: rawColor('#6B3FA0') }, uOpacity: { value: 0.5 },
      uLight: { value: new THREE.Vector3(-0.4, 0.8, 0.5) }, uViewProj: { value: new THREE.Matrix4() },
    },
    side: THREE.BackSide, transparent: true, depthTest: true, depthWrite: true,
  });
}

/** Texture value for a field level in a log-encoded volume. */
export function encodeLevel(v: number, lo: number, hi: number): number {
  if (!(v > 0)) return -1;
  return Math.log10(v / lo) / Math.log10(hi / lo);
}
