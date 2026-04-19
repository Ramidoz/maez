'use client';
import { useEffect, useRef } from 'react';

type PType = 'amber' | 'purple' | 'white';

interface Particle {
  x: number; y: number;
  vx: number; vy: number;
  r: number;
  baseAlpha: number;
  type: PType;
  isPulse: boolean;
  phase: number;
}

const COLORS: Record<PType, [number, number, number]> = {
  amber:  [245, 158, 11],
  purple: [139,  92, 246],
  white:  [240, 237, 232],
};

function rgba([r, g, b]: [number, number, number], a: number) {
  return `rgba(${r},${g},${b},${a.toFixed(3)})`;
}

export function ParticleField({
  className,
  density = 9000,
  connectDist = 120,
  mouseRadius = 220,
}: {
  className?: string;
  density?: number;
  connectDist?: number;
  mouseRadius?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = 0, h = 0;
    const mouse = { x: -9999, y: -9999 };
    let animId = 0;
    let t = 0;
    let particles: Particle[] = [];

    const init = () => {
      w = canvas.width = canvas.offsetWidth;
      h = canvas.height = canvas.offsetHeight;
      const n = Math.min(160, Math.max(40, Math.floor((w * h) / density)));
      particles = Array.from({ length: n }, () => {
        const roll = Math.random();
        const type: PType = roll < 0.62 ? 'amber' : roll < 0.88 ? 'purple' : 'white';
        const isPulse = Math.random() < 0.09;
        return {
          x: Math.random() * w,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * (prefersReduced ? 0 : 0.38),
          vy: (Math.random() - 0.5) * (prefersReduced ? 0 : 0.38),
          r: isPulse ? Math.random() * 1.8 + 1.2 : Math.random() * 1.1 + 0.4,
          baseAlpha: Math.random() * 0.45 + 0.2,
          type,
          isPulse,
          phase: Math.random() * Math.PI * 2,
        };
      });
    };

    const tick = () => {
      t += prefersReduced ? 0 : 0.007;
      ctx.clearRect(0, 0, w, h);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        if (!prefersReduced) {
          const mdx = mouse.x - p.x;
          const mdy = mouse.y - p.y;
          const md = Math.sqrt(mdx * mdx + mdy * mdy);
          if (md < mouseRadius && md > 1) {
            const f = (1 - md / mouseRadius) * 0.022;
            p.vx += (mdx / md) * f;
            p.vy += (mdy / md) * f;
          }
          p.vx *= 0.985;
          p.vy *= 0.985;
          p.x += p.vx;
          p.y += p.vy;
          if (p.x < -10) p.x = w + 10;
          if (p.x > w + 10) p.x = -10;
          if (p.y < -10) p.y = h + 10;
          if (p.y > h + 10) p.y = -10;
        }

        const pulse = p.isPulse
          ? 0.45 + 0.55 * Math.sin(t * 1.8 + p.phase)
          : 0.72 + 0.28 * Math.sin(t * 0.9 + p.phase);
        const a = p.baseAlpha * pulse;

        // draw dot
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = rgba(COLORS[p.type], a);
        ctx.fill();

        // pulse ring
        if (p.isPulse && a > 0.28) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.r * 3.5, 0, Math.PI * 2);
          ctx.strokeStyle = rgba(COLORS[p.type], a * 0.28);
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }

        // connections
        for (let j = i + 1; j < particles.length; j++) {
          const q = particles[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < connectDist) {
            const la = (1 - d / connectDist) * 0.14 * Math.min(pulse, 1);
            if (la > 0.008) {
              const grad = ctx.createLinearGradient(p.x, p.y, q.x, q.y);
              grad.addColorStop(0, rgba(COLORS[p.type], la));
              grad.addColorStop(1, rgba(COLORS[q.type], la));
              ctx.beginPath();
              ctx.moveTo(p.x, p.y);
              ctx.lineTo(q.x, q.y);
              ctx.strokeStyle = grad;
              ctx.lineWidth = 0.55;
              ctx.stroke();
            }
          }
        }
      }

      animId = requestAnimationFrame(tick);
    };

    const onMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };
    const onLeave = () => { mouse.x = -9999; mouse.y = -9999; };
    const onResize = () => init();

    init();
    tick();

    window.addEventListener('mousemove', onMove);
    window.addEventListener('resize', onResize);
    canvas.addEventListener('mouseleave', onLeave);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('resize', onResize);
      canvas.removeEventListener('mouseleave', onLeave);
    };
  }, [density, connectDist, mouseRadius]);

  return <canvas ref={canvasRef} className={className} style={{ display: 'block' }} />;
}
