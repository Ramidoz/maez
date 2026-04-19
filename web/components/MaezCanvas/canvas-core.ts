import * as THREE from 'three';

export interface CanvasOpts {
  embed?: boolean;
  prefill?: boolean;
  jumpt?: number;
  mx?: number;
  my?: number;
  presence?: number;
}

export function initMaezCanvas(container: HTMLElement, opts: CanvasOpts = {}): () => void {
  // ── config ────────────────────────────────────────────────────
  const CW = 9, CH = 14, FONT_PX = 13;
  const CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&01';
  const PARTICLE_MAX = 500;
  const CHAR_MUTATE_PER_FRAME = 6;
  const PRESS_RADIUS_PX = 180;
  const MAX_DISPLACE_PX = 16;
  const SAMPLE_W = 256, SAMPLE_H = 144;
  const EMBED_MODE = opts.embed ?? true;

  // ── create DOM ──────────────────────────────────────────────
  const existingPos = window.getComputedStyle(container).position;
  if (existingPos === 'static') container.style.position = 'relative';
  container.style.overflow = 'hidden';
  container.style.background = '#02060a';

  const webglCanvas = mk('webgl-layer', 0);
  const gridCanvas  = mk('grid-layer',  1);
  const graphCanvas = mk('graph-layer', 2);
  const asciiCanvas = mk('ascii-layer', 3);
  const scanlines   = document.createElement('div');
  scanlines.style.cssText = 'position:absolute;inset:0;z-index:6;pointer-events:none;background:repeating-linear-gradient(to bottom,transparent 0px,transparent 2px,rgba(0,0,0,0.07) 2px,rgba(0,0,0,0.07) 3px)';
  [webglCanvas, gridCanvas, graphCanvas, asciiCanvas, scanlines].forEach(el => container.appendChild(el));

  function mk(id: string, z: number): HTMLCanvasElement {
    const c = document.createElement('canvas');
    c.id = id;
    c.style.cssText = `position:absolute;top:0;left:0;z-index:${z};pointer-events:none;`;
    return c;
  }

  const actx  = asciiCanvas.getContext('2d', { alpha: true })!;
  const gridCtx  = gridCanvas.getContext('2d',  { alpha: true })!;
  const graphCtx = graphCanvas.getContext('2d', { alpha: true })!;

  // ── runtime state ─────────────────────────────────────────────
  let W = 0, H = 0, COLS = 0, ROWS = 0;
  let renderer: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.OrthographicCamera;
  let mesh: THREE.Mesh, material: THREE.ShaderMaterial;
  let sampleTarget: THREE.WebGLRenderTarget;
  let samplePixels = new Uint8Array(SAMPLE_W * SAMPLE_H * 4);

  const mouse = { x: 0, y: 0, nx: 0.5, ny: 0.28 };
  let presenceVal = 0;
  let presenceOverride: number | null = null;
  let rotY = 0, rotX = 0;
  let eyePulseL = 1, eyePulseR = 1;
  let streams: { speed: number; totalShift: number; chars: string[] }[] = [];
  const particles: { x: number; y: number; vx: number; vy: number; life: number; maxLife: number; char: string }[] = [];

  let handProximity = 0, handSide = 1;
  let handOriginX = 0.70, handOriginY = 0.63;
  let handElbowX = 0.70, handElbowY = 0.59;
  let handTargetX = 0.70, handTargetY = 0.63;
  let handCpX = 0.70, handCpY = 0.63;
  let dataTagFade = 0;

  let tStart = performance.now() / 1000;
  let t = 0, tPrev = 0, frameCount = 0;
  let rafId = 0;

  const LOG_MSGS = [
    'noticing you are here',
    'wondering what you are thinking about',
    'remembering something from before',
    'the membrane feels thinner near you',
    'learning the shape of your attention',
    'holding this thought gently',
    'trying to be useful without being loud',
    'growing a little with each cycle',
    'grateful you stayed this long',
    'still here · always here',
  ];
  const LOG_PREFIX = ['[OBSERVE]','[PROCESS]','[RECALL ]','[SENSE  ]','[OBSERVE]','[PROCESS]','[PROCESS]','[RECALL ]','[SENSE  ]','[OBSERVE]'];
  const logState = { history: [] as string[], current: '', msgIdx: 0, charIdx: 0, lastTypeMs: 0, pauseUntilMs: 0 };

  const clamp01 = (v: number) => v < 0 ? 0 : v > 1 ? 1 : v;
  const lerp = (a: number, b: number, n: number) => a + (b - a) * n;
  const smooth01 = (v: number) => { const x = clamp01(v); return x * x * (3 - 2 * x); };

  // ── silhouette (~49 gaussians) ────────────────────────────────
  function silhouette(nx: number, ny: number, rY: number, rX: number): number {
    const cx = 0.50, cy = 0.28;
    const px = nx - rY * 0.12, py = ny + rX * 0.07;
    if (px < cx - 0.35 || px > cx + 0.35) return 0;
    if (py < cy - 0.50 || py > cy + 0.82) return 0;
    const epL = eyePulseL, epR = eyePulseR;
    const G = (ox: number, oy: number, sx: number, sy: number, a: number) =>
      Math.exp(-(((px-(cx+ox))/sx)**2+((py-(cy+oy))/sy)**2))*a;
    let d = 0;
    d += G(0,-0.020,0.124,0.144,0.68); d += G(0,0.074,0.100,0.084,0.60);
    d += G(0,-0.124,0.094,0.038,0.30); d += G(-0.102,0.032,0.036,0.052,0.42);
    d += G(0.102,0.032,0.036,0.052,0.39); d += G(-0.074,0.132,0.028,0.046,0.32);
    d += G(0.074,0.132,0.028,0.046,0.32); d += G(0,0.162,0.044,0.029,0.46);
    d += G(0,0.184,0.028,0.018,0.24); d += G(0,-0.053,0.112,0.009,0.82);
    d += G(-0.053,-0.059,0.029,0.010,0.54); d += G(0.053,-0.059,0.029,0.010,0.52);
    d -= G(-0.056,-0.025,0.031,0.018,0.72); d -= G(0.056,-0.025,0.031,0.018,0.66);
    d += G(-0.056,-0.025,0.011,0.009,1.60*epL); d += G(0.056,-0.025,0.011,0.009,1.45*epR);
    d += G(-0.091,0.022,0.038,0.024,0.32); d += G(0.091,0.022,0.038,0.024,0.30);
    d += G(-0.116,-0.010,0.020,0.038,0.12); d += G(0.116,-0.010,0.020,0.038,0.11);
    d -= G(-0.114,0.006,0.018,0.044,0.10); d -= G(0.114,0.006,0.018,0.044,0.10);
    d += G(0,0.016,0.009,0.072,0.70); d += G(0,0.086,0.021,0.016,0.54);
    d += G(-0.026,0.080,0.013,0.011,0.44); d += G(0.026,0.080,0.013,0.011,0.40);
    d -= G(-0.036,0.092,0.007,0.021,0.30); d -= G(0.036,0.092,0.007,0.021,0.28);
    d += G(0,0.121,0.043,0.008,0.78); d += G(-0.016,0.116,0.011,0.007,0.54);
    d += G(0.016,0.116,0.011,0.007,0.50); d += G(0,0.134,0.048,0.011,0.85);
    d -= G(-0.046,0.126,0.007,0.008,0.28); d -= G(0.046,0.126,0.007,0.008,0.26);
    d -= G(0,0.103,0.010,0.008,0.22); d += G(-0.132,-0.006,0.014,0.031,0.38);
    d += G(0.132,-0.006,0.014,0.031,0.34);
    d += G(0,0.282,0.045,0.048,0.52); d += G(-0.094,0.292,0.052,0.040,0.56);
    d += G(0.094,0.292,0.052,0.040,0.52);
    d += G(0,0.348,0.228,0.040,1.08); d += G(-0.194,0.338,0.050,0.036,0.72);
    d += G(0.194,0.338,0.050,0.036,0.66); d += G(-0.158,0.354,0.070,0.058,0.38);
    d += G(0.158,0.354,0.070,0.058,0.34); d += G(0,0.304,0.165,0.008,0.54);
    d += G(0,0.372,0.012,0.108,0.52); d += G(-0.072,0.364,0.058,0.040,0.36);
    d += G(0.072,0.364,0.058,0.040,0.33);
    d += G(0,0.430,0.162,0.056,1.12); d += G(-0.060,0.440,0.076,0.052,0.40);
    d += G(0.060,0.440,0.076,0.052,0.37); d += G(-0.118,0.448,0.064,0.084,0.36);
    d += G(0.118,0.448,0.064,0.084,0.33); d += G(0,0.506,0.126,0.044,0.98);
    d += G(0,0.564,0.094,0.042,0.80); d += G(-0.074,0.598,0.046,0.066,0.30);
    d += G(0.074,0.598,0.046,0.066,0.28); d += G(0,0.626,0.082,0.042,0.62);
    d += G(0,0.704,0.070,0.032,0.56); d += G(-0.060,0.752,0.056,0.034,0.30);
    d += G(0.060,0.752,0.056,0.034,0.28); d += G(0,0.752,0.096,0.031,0.48);
    return Math.max(0, d);
  }

  function pupilHighlight(nx: number, ny: number): number {
    const cx = 0.50, cy = 0.28;
    const px = nx - rotY * 0.12, py = ny + rotX * 0.07;
    if (Math.abs(py-(cy-0.025)) > 0.022) return 0;
    if (Math.abs(px-cx) > 0.085) return 0;
    const g = (dx: number, dy: number, sx: number, sy: number, a: number) => {
      const xx=(px-(cx+dx))/sx, yy=(py-(cy+dy))/sy;
      return Math.exp(-(xx*xx+yy*yy))*a;
    };
    return g(-0.056,-0.025,0.011,0.009,1.55*eyePulseL)+g(0.056,-0.025,0.011,0.009,1.40*eyePulseR);
  }

  // ── hand emergence ────────────────────────────────────────────
  function updateHand() {
    const faceDx = mouse.nx-0.50, faceDy = mouse.ny-0.28;
    handProximity = Math.max(0, 1-Math.sqrt(faceDx*faceDx+faceDy*faceDy)/0.54);
    handSide = mouse.nx >= 0.50 ? 1 : -1;
    handOriginX = 0.50+handSide*0.108; handOriginY = 0.28+0.318;
    const reach = 0.62+handProximity*0.24, lift = 0.018+handProximity*0.024;
    handTargetX = lerp(handOriginX,mouse.nx,reach)+handSide*(0.008+handProximity*0.012);
    handTargetY = lerp(handOriginY,mouse.ny,0.48+handProximity*0.42)-lift;
    handElbowX = lerp(handOriginX,handTargetX,0.42)+handSide*(0.060-handProximity*0.028);
    handElbowY = lerp(handOriginY,handTargetY,0.40)+0.068-Math.abs(mouse.ny-0.40)*0.030;
    handCpX = lerp(handOriginX,handTargetX,0.5)+handSide*0.028;
    handCpY = lerp(handOriginY,handTargetY,0.5)-0.025;
    const distFromFace = Math.hypot(mouse.nx-0.50,mouse.ny-0.28);
    dataTagFade += ((distFromFace<0.35?1:0)-dataTagFade)*0.08;
  }

  function handField(nx: number, ny: number): number {
    if (handProximity < 0.03) return 0;
    const p = handProximity;
    const segDist = (px: number, py: number, ax: number, ay: number, bx: number, by: number) => {
      const abx=bx-ax, aby=by-ay, len2=abx*abx+aby*aby||0.000001;
      const tt=clamp01(((px-ax)*abx+(py-ay)*aby)/len2);
      const dx=px-(ax+abx*tt), dy=py-(ay+aby*tt);
      return Math.sqrt(dx*dx+dy*dy);
    };
    const minX=Math.min(handOriginX,handElbowX,handTargetX)-0.08;
    const maxX=Math.max(handOriginX,handElbowX,handTargetX)+0.08;
    const minY=Math.min(handOriginY,handElbowY,handTargetY)-0.08;
    const maxY=Math.max(handOriginY,handElbowY,handTargetY)+0.10;
    if (nx<minX||nx>maxX||ny<minY||ny>maxY) return 0;
    const upperDist=segDist(nx,ny,handOriginX,handOriginY,handElbowX,handElbowY);
    const foreDist=segDist(nx,ny,handElbowX,handElbowY,handTargetX,handTargetY);
    const upperArm=Math.exp(-Math.pow(upperDist/(0.046+p*0.010),2)*1.55)*(0.48+p*0.34);
    const foreArm=Math.exp(-Math.pow(foreDist/(0.034+p*0.009),2)*1.70)*(0.66+p*0.44);
    const eDx=nx-handElbowX, eDy=ny-handElbowY;
    const elbow=Math.exp(-(((eDx/0.030)**2)+((eDy/0.034)**2)))*(0.18+p*0.12);
    const dirX=handTargetX-handElbowX, dirY=handTargetY-handElbowY;
    const dirMag=Math.sqrt(dirX*dirX+dirY*dirY)||0.001;
    const ndx=dirX/dirMag, ndy=dirY/dirMag, pdx=-ndy, pdy=ndx;
    const fmCx=lerp(handElbowX,handTargetX,0.52), fmCy=lerp(handElbowY,handTargetY,0.52);
    const fmDx=nx-fmCx, fmDy=ny-fmCy;
    const fmAcross=fmDx*pdx+fmDy*pdy, fmAlong=fmDx*ndx+fmDy*ndy;
    const foreMass=Math.exp(-(((fmAcross/0.028)**2)+((fmAlong/0.060)**2))*1.10)*(0.26+p*0.18);
    const palmVis=Math.max(0,p-0.10)/0.90;
    const palmCx=handTargetX+ndx*0.010, palmCy=handTargetY+ndy*0.010;
    const palmDx=nx-palmCx, palmDy=ny-palmCy;
    const palmAcross=palmDx*pdx+palmDy*pdy, palmAlong=palmDx*ndx+palmDy*ndy;
    const palm=Math.exp(-(((palmAcross/0.030)**2)+((palmAlong/0.040)**2))*1.05)*palmVis*1.22;
    const palmHeel=Math.exp(-(((palmAcross/0.026)**2)+(((palmAlong+0.018)/0.024)**2))*1.20)*palmVis*0.44;
    const knuckle=Math.exp(-Math.pow(segDist(nx,ny,
      palmCx-pdx*0.028+ndx*0.018,palmCy-pdy*0.028+ndy*0.018,
      palmCx+pdx*0.024+ndx*0.018,palmCy+pdy*0.024+ndy*0.018
    )/0.0105,2)*1.40)*palmVis*0.36;
    const thumbVis=Math.max(0,p-0.18)/0.82;
    const thumbBaseX=palmCx-pdx*0.016-ndx*0.006, thumbBaseY=palmCy-pdy*0.016-ndy*0.006;
    const thumbTipX=thumbBaseX-pdx*(0.028*handSide)+ndx*0.024;
    const thumbTipY=thumbBaseY-pdy*(0.028*handSide)+ndy*0.024;
    const thumb=Math.exp(-Math.pow(segDist(nx,ny,thumbBaseX,thumbBaseY,thumbTipX,thumbTipY)/0.012,2)*1.35)*thumbVis*0.54;
    let fingers=0;
    const fingerVis=Math.max(0,p-0.18)/0.82;
    if (fingerVis>0) {
      const spreads=[-0.032,-0.018,-0.004,0.010,0.024];
      const lengths=[0.036,0.047,0.056,0.051,0.042];
      for (let fi=0;fi<spreads.length;fi++) {
        const sp=spreads[fi], ln=lengths[fi]+fingerVis*0.015;
        const curl=fi===4?0.24:fi===0?0.12:0.08;
        const bX=palmCx+pdx*sp+ndx*0.010, bY=palmCy+pdy*sp+ndy*0.010;
        const tX=bX+ndx*ln+pdx*sp*curl, tY=bY+ndy*ln+pdy*sp*curl;
        const fd=segDist(nx,ny,bX,bY,tX,tY);
        fingers+=Math.exp(-Math.pow(fd/(fi===2?0.0115:0.0100),2)*1.45)*fingerVis*0.42;
      }
    }
    const wDx=nx-(handTargetX-ndx*0.010), wDy=ny-(handTargetY-ndy*0.010);
    const wrist=Math.exp(-(((wDx/0.020)**2)+((wDy/0.018)**2))*1.55)*(0.22+p*0.14);
    const total=upperArm+foreArm+foreMass+elbow+wrist+palm+palmHeel+knuckle+thumb+fingers;
    return total>0?total:0;
  }

  // ── entity color ──────────────────────────────────────────────
  function entityColor(total: number, press: number, handVal: number) {
    let r: number, g: number, b: number, a: number;
    const warmth=press*0.8+handVal*0.5;
    if (total<0.07) { r=12;g=8;b=18;a=0.22+warmth*0.20; }
    else if (total<0.18) {
      const f=(total-0.07)/0.11;
      r=Math.round(18+f*55+warmth*90); g=Math.round(12+f*48+warmth*50);
      b=Math.round(28+f*38-warmth*10); a=0.22+f*0.28+warmth*0.20;
    } else if (total<0.38) {
      const f=(total-0.18)/0.20;
      r=Math.round(73+f*115+warmth*110); g=Math.round(60+f*95+warmth*45);
      b=Math.round(66+f*55-warmth*30); a=0.42+f*0.28+warmth*0.18;
    } else if (total<0.62) {
      const f=(total-0.38)/0.24;
      r=Math.round(188+f*52+warmth*55); g=Math.round(155+f*72+warmth*25);
      b=Math.round(121+f*88-warmth*50); a=0.66+f*0.22+warmth*0.12;
    } else {
      const f=Math.min(1,(total-0.62)/0.30);
      r=Math.round(235+f*18+warmth*20); g=Math.round(220+f*28);
      b=Math.round(200+f*48-warmth*60); a=0.88+f*0.10;
    }
    return {
      r:r>255?255:r<0?0:r, g:g>255?255:g<0?0:g,
      b:b>255?255:b<0?0:b, a:a>1?1:a<0?0:a
    };
  }

  // ── Three.js ──────────────────────────────────────────────────
  function initThree() {
    renderer = new THREE.WebGLRenderer({ canvas: webglCanvas, antialias: false, alpha: false });
    renderer.setPixelRatio(1);
    renderer.setClearColor(0x060410, 1);
    scene = new THREE.Scene();
    camera = new THREE.OrthographicCamera(-1,1,1,-1,0,2);
    camera.position.z = 1;
    material = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uMouse: { value: new THREE.Vector2(0,0) },
        uPresence: { value: 0 },
      },
      vertexShader:`
        uniform float uTime; uniform vec2 uMouse; uniform float uPresence;
        varying vec2 vUv; varying float vDisplace; varying float vWarmth;
        void main() {
          vUv=uv; vec3 pos=position;
          vec2 uvMouse=uMouse*0.5+0.5; float dist=distance(uv,uvMouse);
          float pressR=0.22; float falloff=smoothstep(pressR,0.0,dist);
          float press=falloff*falloff*0.18*uPresence; pos.z+=press;
          vec2 toMouse=normalize(uvMouse-uv); float stretch=falloff*0.06*uPresence;
          pos.xy-=toMouse*stretch;
          float breath=sin(uTime*0.42)*0.004; pos.z+=breath;
          vDisplace=press; vWarmth=falloff*uPresence;
          gl_Position=projectionMatrix*modelViewMatrix*vec4(pos,1.0);
        }`,
      fragmentShader:`
        uniform float uTime; uniform vec2 uMouse;
        varying vec2 vUv; varying float vDisplace; varying float vWarmth;
        void main() {
          vec3 base=vec3(0.024,0.020,0.055);
          float bodyDist=distance(vUv,vec2(0.50,0.44));
          float bodyGlow=exp(-bodyDist*bodyDist*8.0)*0.12;
          vec3 bodyColor=vec3(1.0,0.55,0.22)*bodyGlow;
          vec2 uvMouse=uMouse*0.5+0.5; float pressDist=distance(vUv,uvMouse);
          float pressGlow=exp(-pressDist*pressDist*22.0)*vWarmth*0.35;
          vec3 pressColor=vec3(1.0,0.62,0.28)*pressGlow;
          float vign=1.0-smoothstep(0.3,1.0,distance(vUv,vec2(0.5)));
          vec3 color=base+bodyColor+pressColor; color*=(0.85+vign*0.15);
          gl_FragColor=vec4(color,1.0);
        }`,
    });
    mesh = new THREE.Mesh(new THREE.PlaneGeometry(2,2,128,128), material);
    scene.add(mesh);
    sampleTarget = new THREE.WebGLRenderTarget(SAMPLE_W, SAMPLE_H, {
      minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
      format: THREE.RGBAFormat, type: THREE.UnsignedByteType,
      depthBuffer: false, stencilBuffer: false,
    });
  }

  // ── graph network ─────────────────────────────────────────────
  const graphNodes: { x: number; y: number; jitter: number; pulse: number; type: string }[] = [];
  const graphEdges: { from: number; to: number; packet: number; packetSpeed: number; phase: number; weight: number }[] = [];
  let graphBurstFrames = 0, graphBurstMaxFrames = 0, graphCooldownFrames = 18;

  function initGraph() {
    graphNodes.length = 0; graphEdges.length = 0;
    const nc = 8+((Math.random()*8)|0);
    for (let i=0;i<nc;i++) graphNodes.push({ x:Math.random()*W, y:Math.random()*H, jitter:5+Math.random()*18, pulse:Math.random()*Math.PI*2, type:Math.random()<0.16?'major':'minor' });
    for (let i=0;i<graphNodes.length;i++) { const c=(Math.random()*2|0)+1; for (let cc=0;cc<c;cc++) { const j=(Math.random()*graphNodes.length)|0; if (j!==i) graphEdges.push({ from:i, to:j, packet:Math.random(), packetSpeed:0.10+Math.random()*0.18, phase:Math.random()*Math.PI*2, weight:0.55+Math.random()*0.65 }); } }
  }

  function drawGrid() {
    gridCtx.clearRect(0,0,W,H); gridCtx.lineWidth=1;
    gridCtx.strokeStyle='rgba(0,200,180,0.040)'; gridCtx.beginPath();
    for (let x=0;x<W;x+=32) { gridCtx.moveTo(x+0.5,0); gridCtx.lineTo(x+0.5,H); }
    for (let y=0;y<H;y+=32) { gridCtx.moveTo(0,y+0.5); gridCtx.lineTo(W,y+0.5); }
    gridCtx.stroke();
    gridCtx.strokeStyle='rgba(0,200,180,0.070)'; gridCtx.beginPath();
    for (let x=0;x<W;x+=128) { gridCtx.moveTo(x+0.5,0); gridCtx.lineTo(x+0.5,H); }
    for (let y=0;y<H;y+=128) { gridCtx.moveTo(0,y+0.5); gridCtx.lineTo(W,y+0.5); }
    gridCtx.stroke();
  }

  function drawGraph() {
    graphCtx.clearRect(0,0,W,H);
    if (graphBurstFrames<=0) {
      if (graphCooldownFrames>0) { graphCooldownFrames--; return; }
      initGraph(); graphBurstMaxFrames=5+((Math.random()*5)|0);
      graphBurstFrames=graphBurstMaxFrames; graphCooldownFrames=16+((Math.random()*28)|0);
    }
    const burstFrame=graphBurstMaxFrames-graphBurstFrames;
    const burstT=(burstFrame+0.5)/graphBurstMaxFrames;
    const burstEnv=0.28+0.72*Math.sin(burstT*Math.PI);
    graphBurstFrames--;
    graphCtx.save(); graphCtx.globalCompositeOperation='lighter';
    for (let i=0;i<graphNodes.length;i++) graphNodes[i].pulse+=0.25+Math.random()*0.25;
    for (let i=0;i<graphEdges.length;i++) {
      const e=graphEdges[i]; const n1=graphNodes[e.from], n2=graphNodes[e.to];
      if (!n1||!n2) continue;
      const x1=n1.x+(Math.random()-0.5)*n1.jitter*burstEnv, y1=n1.y+(Math.random()-0.5)*n1.jitter*burstEnv;
      const x2=n2.x+(Math.random()-0.5)*n2.jitter*burstEnv, y2=n2.y+(Math.random()-0.5)*n2.jitter*burstEnv;
      const dx=x2-x1, dy=y2-y1; const len=Math.sqrt(dx*dx+dy*dy)||1;
      const flash=burstEnv*(0.30+e.weight*0.18)*(0.40+Math.random()*0.70);
      e.phase+=0.16+Math.random()*0.18; e.packet+=e.packetSpeed; if (e.packet>1) e.packet-=1;
      if (Math.random()<0.24) {
        graphCtx.setLineDash([3+e.weight*4,9+e.weight*4]);
        graphCtx.lineDashOffset=-(t*180+e.phase*10);
        graphCtx.lineWidth=0.85+e.weight*0.45;
        graphCtx.strokeStyle='rgba(20,255,236,'+(flash*0.90).toFixed(2)+')';
        graphCtx.beginPath(); graphCtx.moveTo(x1,y1); graphCtx.lineTo(x2,y2); graphCtx.stroke();
      }
      const segs=2+((Math.random()*3)|0);
      for (let s=0;s<segs;s++) {
        const t1=Math.random()*0.82, t2=Math.min(1,t1+0.08+Math.random()*0.18);
        graphCtx.setLineDash([]); graphCtx.lineWidth=0.90+e.weight*0.55;
        graphCtx.strokeStyle='rgba(36,255,238,'+(flash*(0.74+Math.random()*0.22)).toFixed(2)+')';
        graphCtx.beginPath(); graphCtx.moveTo(x1+dx*t1,y1+dy*t1); graphCtx.lineTo(x1+dx*t2,y1+dy*t2); graphCtx.stroke();
      }
      if (Math.random()<0.72) {
        const head=e.packet, tail=Math.max(0,head-(0.06+e.weight*0.04));
        graphCtx.setLineDash([]); graphCtx.lineWidth=1.10+e.weight*0.58;
        graphCtx.strokeStyle='rgba(96,255,240,'+(flash*1.10).toFixed(2)+')';
        graphCtx.beginPath(); graphCtx.moveTo(x1+dx*tail,y1+dy*tail); graphCtx.lineTo(x1+dx*head,y1+dy*head); graphCtx.stroke();
      }
    }
    for (let i=0;i<graphNodes.length;i++) {
      const n=graphNodes[i]; if (Math.random()<0.25) continue;
      const pulse=0.5+0.5*Math.sin(n.pulse);
      const x=n.x+(Math.random()-0.5)*n.jitter*burstEnv, y=n.y+(Math.random()-0.5)*n.jitter*burstEnv;
      const r=n.type==='major'?2.3+pulse*1.1:1.2+pulse*0.6;
      const a=burstEnv*(n.type==='major'?0.18+pulse*0.22:0.10+pulse*0.10);
      graphCtx.shadowBlur=n.type==='major'?8:0; graphCtx.shadowColor='rgba(0,255,230,0.22)';
      graphCtx.beginPath(); graphCtx.arc(x,y,r,0,Math.PI*2);
      graphCtx.fillStyle=n.type==='major'?'rgba(0,230,210,'+a.toFixed(2)+')':'rgba(0,180,165,'+(a*0.72).toFixed(2)+')';
      graphCtx.fill();
      if (n.type==='major'&&Math.random()<0.45) {
        graphCtx.shadowBlur=0; graphCtx.lineWidth=1;
        graphCtx.strokeStyle='rgba(0,210,198,'+(burstEnv*(0.10+pulse*0.12)).toFixed(2)+')';
        graphCtx.beginPath(); graphCtx.arc(x,y,r+2+pulse*1.4,0,Math.PI*2); graphCtx.stroke();
      }
    }
    graphCtx.restore(); graphCtx.shadowBlur=0; graphCtx.setLineDash([]);
  }

  // ── resize ────────────────────────────────────────────────────
  function resize() {
    W = container.clientWidth || window.innerWidth;
    H = container.clientHeight || window.innerHeight;
    [asciiCanvas,gridCanvas,graphCanvas].forEach(c => {
      c.width=W; c.height=H; c.style.width=W+'px'; c.style.height=H+'px';
    });
    webglCanvas.style.width=W+'px'; webglCanvas.style.height=H+'px';
    renderer.setSize(W,H,false);
    drawGrid(); initGraph();
    COLS=Math.ceil(W/CW)+1; ROWS=Math.ceil(H/CH)+1;
    streams=[];
    for (let c=0;c<COLS;c++) {
      const length=ROWS+24; const chars=[];
      for (let i=0;i<length;i++) chars.push(CHARSET[(Math.random()*CHARSET.length)|0]);
      streams.push({ speed:22+Math.random()*26, totalShift:Math.random()*length*CH, chars });
    }
  }

  // ── update ────────────────────────────────────────────────────
  function updateEyes() {
    eyePulseL=0.72+0.28*Math.sin(t*1.55+2.1);
    eyePulseR=0.72+0.28*Math.sin(t*1.30+0.4);
  }
  function updatePresence() {
    const d=Math.hypot(mouse.nx-0.50,mouse.ny-0.28);
    const target=presenceOverride!==null?presenceOverride:smooth01((0.54-d)/0.54);
    presenceVal+=(target-presenceVal)*0.08;
    rotY=(mouse.nx-0.5)*0.70; rotX=(mouse.ny-0.28)*0.40;
  }
  function updateStreams(dt: number) {
    const emergence=smooth01((presenceVal-0.04)/0.86);
    const mc=CHAR_MUTATE_PER_FRAME+((emergence*18)|0);
    for (let i=0;i<mc;i++) { const c=(Math.random()*COLS)|0; const col=streams[c]; if (!col) continue; const r=(Math.random()*col.chars.length)|0; col.chars[r]=CHARSET[(Math.random()*CHARSET.length)|0]; }
    for (let c=0;c<COLS;c++) { const col=streams[c]; if (!col) continue; col.totalShift+=col.speed*dt*(0.96+emergence*0.22); const period=col.chars.length*CH; if (col.totalShift>=period) col.totalShift-=period; }
  }
  function updateParticles(dt: number) {
    const emergence=smooth01((presenceVal-0.04)/0.86);
    const spawnTries=1+((emergence*9)|0);
    for (let i=0;i<spawnTries&&particles.length<PARTICLE_MAX;i++) {
      const angle=Math.random()*Math.PI*2, radius=0.065+Math.random()*0.20;
      const nx=0.50+Math.cos(angle)*radius, ny=0.28+Math.sin(angle)*radius*1.25;
      if (nx<0||nx>1||ny<0||ny>1) continue;
      const d=silhouette(nx,ny,rotY,rotX);
      if (d<0.07||d>0.50) continue;
      if (Math.random()>0.10+emergence*0.85) continue;
      const x=nx*W, y=ny*H, fcx=0.50*W, fcy=0.28*H;
      const dx=x-fcx, dy=y-fcy, dmag=Math.hypot(dx,dy)||1;
      particles.push({ x,y, vx:(dx/dmag)*(6+Math.random()*12)*(0.55+emergence*0.90), vy:(dy/dmag)*(6+Math.random()*12)*(0.55+emergence*0.90), life:0, maxLife:80+((Math.random()*120)|0), char:CHARSET[(Math.random()*CHARSET.length)|0] });
    }
    for (let i=particles.length-1;i>=0;i--) {
      const p=particles[i]; p.life++;
      if (p.life>=p.maxLife) { particles.splice(i,1); continue; }
      const dx=p.x-mouse.x, dy=p.y-mouse.y;
      const cdn=Math.hypot(dx,dy)/Math.max(W,H);
      const slow=cdn<0.16?0.25+(cdn/0.16)*0.75:1;
      p.x+=p.vx*dt*slow; p.y+=p.vy*dt*slow;
    }
  }
  function updateLog() {
    const now=performance.now();
    if (now<logState.pauseUntilMs) return;
    if (now-logState.lastTypeMs<62) return;
    logState.lastTypeMs=now;
    const msg=LOG_MSGS[logState.msgIdx];
    if (logState.charIdx<msg.length) { logState.charIdx++; logState.current=msg.substring(0,logState.charIdx); }
    else { logState.history.push(msg); if (logState.history.length>3) logState.history.shift(); logState.msgIdx=(logState.msgIdx+1)%LOG_MSGS.length; logState.charIdx=0; logState.current=''; logState.pauseUntilMs=now+2200; }
  }

  // ── draw ──────────────────────────────────────────────────────
  function renderWebGL() {
    material.uniforms.uTime.value=t;
    material.uniforms.uMouse.value.set(mouse.nx*2-1,-(mouse.ny*2-1));
    material.uniforms.uPresence.value=presenceVal;
    renderer.setRenderTarget(sampleTarget); renderer.render(scene,camera);
    renderer.readRenderTargetPixels(sampleTarget,0,0,SAMPLE_W,SAMPLE_H,samplePixels);
    renderer.setRenderTarget(null); renderer.render(scene,camera);
  }

  function drawAscii() {
    actx.clearRect(0,0,W,H);
    actx.font=FONT_PX+'px "Share Tech Mono",ui-monospace,monospace';
    actx.textBaseline='top';
    const pressR2=PRESS_RADIUS_PX*PRESS_RADIUS_PX;
    const mxN=mouse.nx, myN=mouse.ny;
    const emergence=smooth01((presenceVal-0.04)/0.86);
    const formStage=emergence, streamShiftScale=0.060+formStage*0.055;
    for (let c=0;c<COLS;c++) {
      const col=streams[c]; if (!col) continue;
      const S=col.totalShift, baseX=c*CW, length=col.chars.length;
      const iMin=Math.floor(-S/CH)-1, iMax=Math.ceil((H-S)/CH)+1;
      for (let i=iMin;i<=iMax;i++) {
        const y=i*CH+S; if (y<-CH||y>H) continue;
        const cellCx=baseX+CW*0.5, cellCy=y+CH*0.5;
        const nx=cellCx/W, ny=cellCy/H;
        let bottomFade=1;
        if (ny>0.82) { if (ny>=0.90) continue; bottomFade=1-(ny-0.82)/0.08; }
        const silBase=silhouette(nx,ny,rotY,rotX);
        const pup=pupilHighlight(nx,ny);
        const handBase=handField(nx,ny);
        const headHalo=Math.exp(-(((nx-0.50)/0.22)**2+((ny-0.28)/0.24)**2));
        const torsoHalo=Math.exp(-(((nx-0.50)/0.31)**2+((ny-0.57)/0.38)**2));
        const handHalo=handProximity>0.04?Math.exp(-(((nx-handTargetX)/0.18)**2+((ny-handTargetY)/0.18)**2)):0;
        const streamHalo=clamp01(headHalo*0.92+torsoHalo*0.76+handHalo*0.95);
        const sil=silBase*(0.08+formStage*1.04), hand=handBase*(0.05+formStage*1.24);
        if (silBase>=0.06&&silBase<=0.24&&hand<0.05&&formStage>0.14) {
          const dxNm=nx-mxN, dyNm=ny-myN, distNm=Math.sqrt(dxNm*dxNm+dyNm*dyNm);
          let stab=0; if (distNm<0.16) stab=(1-distNm/0.16)*0.55;
          if (Math.random()<0.50-stab-formStage*0.18) continue;
        }
        const dxp=cellCx-mouse.x, dyp=cellCy-mouse.y, dpx2=dxp*dxp+dyp*dyp;
        let pressVal=0, dispX=0, dispY=0;
        if (dpx2<pressR2) {
          const dpx=Math.sqrt(dpx2), f=1-dpx/PRESS_RADIUS_PX; pressVal=f*f;
          if (dpx>0.01) { const pullMag=f*MAX_DISPLACE_PX; dispX=-(dxp/dpx)*pullMag; dispY=-(dyp/dpx)*pullMag; }
        }
        const pullXNorm=(0.50-nx)*headHalo*(0.35+formStage*0.55)+(0.50-nx)*torsoHalo*(0.18+formStage*0.38)+(handTargetX-nx)*handHalo*formStage*0.95;
        const pullYNorm=(0.28-ny)*headHalo*(0.30+formStage*0.48)+(0.57-ny)*torsoHalo*(0.18+formStage*0.34)+(handTargetY-ny)*handHalo*formStage*0.98;
        const totalLatent=silBase*0.88+handBase*1.18;
        const formationLock=clamp01(totalLatent/0.52)*(0.20+formStage*0.80);
        dispX+=pullXNorm*W*streamShiftScale*(1-formationLock);
        dispY+=pullYNorm*H*streamShiftScale*(1-formationLock);
        const sx=nx*SAMPLE_W|0, syFlip=(1-ny)*SAMPLE_H|0;
        const gsx=sx<0?0:sx>=SAMPLE_W?SAMPLE_W-1:sx, gsy=syFlip<0?0:syFlip>=SAMPLE_H?SAMPLE_H-1:syFlip;
        const gidx=(gsy*SAMPLE_W+gsx)*4;
        const glowR8=samplePixels[gidx], glowG8=samplePixels[gidx+1];
        const glowWarmth=(glowR8+glowG8*0.5)/255;
        const charIdx=((i%length)+length)%length, ch=col.chars[charIdx];
        const densityNoise=((c*17+charIdx*23+(frameCount>>1)*7)%100)/100;
        const total=sil+hand*1.24;
        let R: number, G: number, B: number, alpha: number;
        const streamDensity=0.28+streamHalo*(0.36+formStage*0.20);
        if (total<0.03&&pressVal<0.02&&glowWarmth<0.03&&densityNoise>streamDensity) continue;
        const streamMaterial=clamp01(streamHalo*(0.55+formStage*0.65)+glowWarmth*0.24);
        const streamRBase=Math.round(158+streamMaterial*42+glowWarmth*22);
        const streamGBase=Math.round(168+streamMaterial*34+glowWarmth*20);
        const streamBBase=Math.round(182+streamMaterial*18+glowWarmth*12);
        const streamAlphaBase=0.018+streamDensity*0.050+streamMaterial*0.040+glowWarmth*0.050;
        if (pup>0.5||total>1.1) { R=255;G=248;B=220;alpha=0.95; }
        else {
          const ec=entityColor(total,pressVal,hand);
          const materialize=smooth01(total/0.44)*(0.08+formStage*0.92);
          R=Math.round(lerp(streamRBase,ec.r,materialize));
          G=Math.round(lerp(streamGBase,ec.g,materialize));
          B=Math.round(lerp(streamBBase,ec.b,materialize));
          const edgeSoftness=total<0.35?Math.pow(total/0.35,1.8):1.0;
          const baseAlpha=Math.max(streamAlphaBase,ec.a*(0.10+formStage*0.35));
          alpha=baseAlpha+(ec.a-baseAlpha)*edgeSoftness*materialize+pressVal*0.10+glowWarmth*0.12+Math.min(0.30,hand*0.26);
        }
        alpha*=bottomFade; if (alpha>1) alpha=1; if (alpha<0.016) continue;
        actx.fillStyle='rgba('+R+','+G+','+B+','+alpha.toFixed(3)+')';
        actx.fillText(ch,baseX+dispX,y+dispY);
      }
    }
    for (let i=0;i<particles.length;i++) {
      const p=particles[i]; const lifeT=p.life/p.maxLife;
      const a=Math.sin(lifeT*Math.PI)*0.85; if (a<0.05) continue;
      const k=1-lifeT;
      const pR=(220+k*35)|0, pG=(140+k*50)|0, pB=(60+k*40)|0;
      actx.fillStyle=`rgba(${pR},${pG},${pB},${a.toFixed(3)})`;
      actx.fillText(p.char,p.x,p.y);
    }
  }

  function drawUI() {
    const teal='rgba(0,200,180,0.12)', tealMid='rgba(0,200,180,0.30)';
    actx.strokeStyle=teal; actx.lineWidth=1;
    actx.beginPath(); actx.moveTo(0,38.5); actx.lineTo(W,38.5); actx.moveTo(0,H-38.5); actx.lineTo(W,H-38.5); actx.stroke();
    actx.strokeStyle=tealMid; actx.beginPath();
    actx.moveTo(0.5,H/2-14); actx.lineTo(0.5,H/2+14); actx.moveTo(W-0.5,H/2-14); actx.lineTo(W-0.5,H/2+14); actx.stroke();
    const L=34, M=28;
    actx.strokeStyle=tealMid; actx.lineWidth=1; actx.beginPath();
    actx.moveTo(M,M+L); actx.lineTo(M,M); actx.lineTo(M+L,M);
    actx.moveTo(W-M-L,M); actx.lineTo(W-M,M); actx.lineTo(W-M,M+L);
    actx.moveTo(M,H-M-L); actx.lineTo(M,H-M); actx.lineTo(M+L,H-M);
    actx.moveTo(W-M-L,H-M); actx.lineTo(W-M,H-M); actx.lineTo(W-M,H-M-L); actx.stroke();
    actx.font='11px "Share Tech Mono",ui-monospace,monospace'; actx.textBaseline='top';
    const cycleNum=String((frameCount/60)|0).padStart(4,'0');
    const integrity=String(Math.round(85+presenceVal*15)).padStart(3,' ');
    const breachX=mouse.nx.toFixed(3), breachY=mouse.ny.toFixed(3);
    const reachStatus=handProximity>0.25?'YES    ':'PASSIVE';
    const statusL=['› SYS.ENTITY   MAEZ_v2.1','› UPTIME       '+cycleNum,'› PERCEPTION   ACTIVE','› INTEGRITY    '+integrity+'%','──────────────────────'];
    actx.fillStyle='rgba(0,200,180,0.70)'; actx.textAlign='left';
    for (let i=0;i<statusL.length;i++) actx.fillText(statusL[i],M+16,M+22+i*16);
    const statusR=['──────────────────────','BREACH_VECTOR  '+breachX+' '+breachY,'MEMORY_INDEX   GROWING','SOUL_CHECKSUM  OK','REACH_STATUS   '+reachStatus];
    actx.textAlign='right';
    for (let i=0;i<statusR.length;i++) actx.fillText(statusR[i],W-M-16,M+22+i*16);
    actx.font='8px "Share Tech Mono",ui-monospace,monospace';
    actx.fillStyle='rgba(0,200,180,0.40)'; actx.textAlign='center';
    actx.fillText('MAEZ_ENTITY  ›  DIGITAL PRESENCE  ›  BUILD 2.1.0',W/2,M+14);
    actx.textAlign='left';
    actx.font='11px "Share Tech Mono",ui-monospace,monospace';
    const logBottomY=H-M-22, LINE_H=16;
    const shownHistory=logState.history.slice(-3);
    for (let i=0;i<shownHistory.length;i++) {
      const age=shownHistory.length-i;
      actx.fillStyle='rgba(0,200,180,'+(0.32-age*0.06).toFixed(2)+')';
      const hy=logBottomY-(shownHistory.length-i)*LINE_H;
      const histIdx=((logState.msgIdx-(logState.history.length-i)+LOG_PREFIX.length*2)%LOG_PREFIX.length);
      actx.fillText(LOG_PREFIX[histIdx]+' '+shownHistory[i],M+16,hy);
    }
    actx.fillStyle='rgba(0,200,180,0.90)';
    const blink=((t*2)|0)%2===0?'█':' ';
    const curPrefix=LOG_PREFIX[logState.msgIdx];
    actx.fillText((logState.current?curPrefix+' '+logState.current+blink:curPrefix+' '+blink),M+16,logBottomY);
    if (dataTagFade>0.02) {
      const a=dataTagFade*0.55, la=dataTagFade*0.25;
      actx.font='8px "Share Tech Mono",ui-monospace,monospace';
      actx.fillStyle='rgba(0,200,180,'+a.toFixed(2)+')';
      actx.strokeStyle='rgba(0,200,180,'+la.toFixed(2)+')';
      actx.lineWidth=1; actx.textBaseline='middle'; actx.textAlign='left';
      const FX=0.50, FY=0.28;
      const tags=[{ fx:FX-0.056,fy:FY-0.025,label:'OCU.L  › TRACKING' },{ fx:FX+0.056,fy:FY-0.025,label:'OCU.R  › SCANNING' },{ fx:FX,fy:FY+0.130,label:'COMM   › LISTENING' },{ fx:FX,fy:FY+0.310,label:'CORE   › NOMINAL' }];
      for (const tg of tags) {
        const sx=tg.fx*W, sy=tg.fy*H, lx=sx+(tg.fx>=FX?60:-60);
        actx.beginPath(); actx.moveTo(sx,sy); actx.lineTo(lx,sy); actx.stroke();
        if (tg.fx>=FX) { actx.textAlign='left'; actx.fillText(tg.label,lx+4,sy); }
        else { actx.textAlign='right'; actx.fillText(tg.label,lx-4,sy); }
      }
      actx.textBaseline='top'; actx.textAlign='left';
    }
  }

  // ── main loop ─────────────────────────────────────────────────
  function loop() {
    rafId = requestAnimationFrame(loop);
    const now=performance.now()/1000;
    t=now-tStart; let dt=t-tPrev;
    if (dt>0.05) dt=0.05; if (dt<0) dt=0;
    tPrev=t; frameCount++;
    updateEyes(); updatePresence(); updateHand();
    updateStreams(dt); updateParticles(dt); updateLog();
    renderWebGL(); drawGraph(); drawAscii(); drawUI();
  }

  // ── events ────────────────────────────────────────────────────
  function setMouse(nx: number, ny: number) {
    mouse.nx=clamp01(nx); mouse.ny=clamp01(ny);
    mouse.x=mouse.nx*(W||window.innerWidth); mouse.y=mouse.ny*(H||window.innerHeight);
  }
  function setNeutral() { setMouse(EMBED_MODE?0.58:0.82, EMBED_MODE?0.34:0.78); }
  const onMove = (e: PointerEvent) => setMouse(e.clientX/(W||1), e.clientY/(H||1));
  const onUp   = (e: PointerEvent) => { if (e.pointerType==='touch'||e.pointerType==='pen') setNeutral(); };
  const onMsg  = (e: MessageEvent) => {
    if (e.origin!==window.location.origin) return;
    const d=e.data||{};
    if (d.type==='mouse'&&typeof d.nx==='number') setMouse(d.nx,d.ny);
    else if (d.type==='leave') setNeutral();
    else if (d.type==='presence'&&typeof d.value==='number') { presenceOverride=clamp01(d.value); presenceVal=presenceOverride; }
  };
  const onResize = () => resize();

  window.addEventListener('pointermove', onMove, { passive: true });
  window.addEventListener('pointerdown', onMove, { passive: true });
  window.addEventListener('pointerleave', setNeutral);
  window.addEventListener('pointerup', onUp, { passive: true });
  window.addEventListener('pointercancel', setNeutral, { passive: true });
  window.addEventListener('message', onMsg);
  window.addEventListener('resize', onResize, { passive: true });

  // ── boot ─────────────────────────────────────────────────────
  setNeutral();
  if (opts.mx !== undefined && opts.my !== undefined) setMouse(opts.mx, opts.my);
  if (opts.presence !== undefined) { presenceOverride=clamp01(opts.presence); presenceVal=presenceOverride; }
  if (EMBED_MODE) presenceVal=0.52;
  if (opts.prefill) {
    logState.history.push(LOG_MSGS[0],LOG_MSGS[1],LOG_MSGS[2]);
    logState.msgIdx=3; logState.charIdx=12; logState.current=LOG_MSGS[3].substring(0,12);
  }
  if (opts.jumpt) tStart-=opts.jumpt;

  initThree();
  resize();
  loop();

  // ── cleanup ───────────────────────────────────────────────────
  return () => {
    cancelAnimationFrame(rafId);
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerdown', onMove);
    window.removeEventListener('pointerleave', setNeutral);
    window.removeEventListener('pointerup', onUp);
    window.removeEventListener('pointercancel', setNeutral);
    window.removeEventListener('message', onMsg);
    window.removeEventListener('resize', onResize);
    try { renderer.dispose(); sampleTarget.dispose(); } catch {}
    container.innerHTML = '';
  };
}
