'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import styles from './Nav.module.css';

export function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <motion.header
      className={`${styles.nav} ${scrolled ? styles.scrolled : ''}`}
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <Link href="/" className={styles.wordmark}>
        <span className={styles.dot} aria-hidden="true" />
        maez
      </Link>
      <nav className={styles.links} aria-label="Primary navigation">
        <Link href="/progress" className={styles.link}>Build log</Link>
        <Link href="/how-it-works" className={styles.link}>How it works</Link>
        <span className={`${styles.link} ${styles.linkMuted}`}>Sign in — soon</span>
      </nav>
    </motion.header>
  );
}
