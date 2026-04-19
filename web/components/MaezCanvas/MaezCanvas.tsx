'use client';
import { useEffect, useRef } from 'react';
import { initMaezCanvas, type CanvasOpts } from './canvas-core';

interface Props extends CanvasOpts {
  className?: string;
}

export function MaezCanvas({ className, ...opts }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    return initMaezCanvas(ref.current, opts);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <div ref={ref} className={className} aria-hidden="true" />;
}
