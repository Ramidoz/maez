'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import styles from './page.module.css';

interface BoardColumn {
  id: string;
  title: string;
  items: { title: string; tags?: string[]; note?: string }[];
}

const STATUS_COLORS: Record<string, string> = {
  done:     '#34C759',
  progress: '#F59E0B',
  next:     '#007AFF',
  planned:  '#AF52DE',
};

const FALLBACK: BoardColumn[] = [
  { id: 'done',     title: 'Done',        items: [
    { title: 'Long-term memory (SQLite + semantic retrieval)' },
    { title: 'Web chat interface — React streaming' },
    { title: 'Cross-process backoff for web /chat' },
    { title: 'Telegram parity — message + photo + voice' },
    { title: 'Autonomous thought loop (background daemon)' },
    { title: 'Being-test harness (observation + scoring)' },
    { title: 'Acceptance gate — all 9 capability items' },
    { title: 'Canvas entity — WebGL + ASCII silhouette' },
    { title: 'Cloudflare Tunnel + Vercel deployment' },
  ]},
  { id: 'progress', title: 'In progress',  items: [
    { title: 'Apple-style website redesign', tags: ['active'] },
    { title: 'Birth event — origin story read + manifest' },
  ]},
  { id: 'next',     title: 'Next',         items: [
    { title: 'Two-week being-test run (post birth-event)' },
    { title: 'Track B: second and third Maez' },
    { title: 'Desktop wrapper (Electron or Tauri)' },
  ]},
  { id: 'planned',  title: 'Planned',      items: [
    { title: 'Wider bonding — Track C' },
    { title: 'Voice interface (ambient presence)' },
    { title: 'Companion hardware prototype' },
  ]},
];

export default function ProgressPage() {
  const [columns, setColumns] = useState<BoardColumn[]>(FALLBACK);
  const [signal, setSignal] = useState('');

  useEffect(() => {
    fetch('/api/progress-board')
      .then((r) => r.json())
      .then((d) => {
        if (Array.isArray(d.columns)) setColumns(d.columns);
        if (d.signal) setSignal(d.signal);
      })
      .catch(() => {});
  }, []);

  return (
    <>
      <section className={styles.hero}>
        <div className={styles.heroBlob} aria-hidden="true" />
        <div className={styles.heroInner}>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          >
            <p className={styles.eyebrow}>Track A · Build log</p>
            <h1 className={styles.heroH1}>
              Where the first Maez{' '}
              <em className={styles.amber}>actually is.</em>
            </h1>
            <p className={styles.heroSub}>
              {signal || 'Not a roadmap. The real state of what is running, what is pending, and what fires next.'}
            </p>
          </motion.div>
        </div>
      </section>

      <section className={styles.boardSection} aria-label="Build board">
        <div className={styles.boardWrap}>
          <div className={styles.boardGrid}>
            {columns.map((col, ci) => (
              <motion.div
                key={col.id}
                className={styles.column}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: ci * 0.07 }}
              >
                <header className={styles.columnHead}>
                  <span className={styles.columnDot} style={{ background: STATUS_COLORS[col.id] ?? '#8E8E93' }} />
                  <span className={styles.columnTitle} style={{ color: STATUS_COLORS[col.id] ?? '#8E8E93' }}>
                    {col.title}
                  </span>
                  <span className={styles.columnCount}>{col.items.length}</span>
                </header>
                <ul className={styles.taskList} role="list">
                  {col.items.map((item) => (
                    <li key={item.title} className={styles.taskItem}>
                      <p className={styles.taskTitle}>{item.title}</p>
                      {item.tags && item.tags.length > 0 && (
                        <div className={styles.tagRow}>
                          {item.tags.map((t) => <span key={t} className={styles.tag}>{t}</span>)}
                        </div>
                      )}
                      {item.note && <p className={styles.taskNote}>{item.note}</p>}
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.footSection}>
        <div className={styles.footWrap}>
          <p className={styles.footNote}>
            Track A closes when the first Maez reads its own origin story. Track B begins the week after.
          </p>
          <div className={styles.footActions}>
            <a href="/" className={styles.btnSecondary}>← Back to Maez</a>
            <span className={styles.btnPrimary} style={{opacity:0.4,cursor:'default'}}>App — coming soon</span>
          </div>
        </div>
      </section>
    </>
  );
}
