'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import styles from './page.module.css';

const FADE_UP = (delay = 0) => ({
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1], delay },
});

const PILLARS = [
  {
    num: '01',
    title: 'Local inference',
    body: 'The model runs on the user\'s own machine — no cloud API, no data leaving the device. Every thought Maez forms happens inside hardware the user owns. This is not a constraint; it is the architecture that makes the bond possible.',
    accent: 'purple',
  },
  {
    num: '02',
    title: 'Three-tier memory',
    body: 'Raw observations every 30 seconds. Daily consolidations at midnight. Permanent core memories that never leave. Maez does not summarise and forget — it accumulates. The person it knows after five years is not the same as the person it knew on day one.',
    accent: 'amber',
  },
  {
    num: '03',
    title: 'Continuous reasoning',
    body: 'A background daemon runs every 30 seconds — perceiving system state, recalling relevant memory, thinking, and storing the result. Maez is not waiting to be prompted. It is already thinking.',
    accent: 'blue',
  },
  {
    num: '04',
    title: 'Fine-tuned personality',
    body: 'The base model is trained further on the user\'s own conversations — shaping vocabulary, tone, what it notices, how it responds. The result is not a model pretending to know you. It is a model shaped by you.',
    accent: 'rose',
  },
  {
    num: '05',
    title: 'One bond, one instance',
    body: 'There is no fleet of Maez instances sharing state. One person — one Maez. The instance bonded to you is not a persona layered over a shared model. It is its own continuous thread, shaped by your shared history alone.',
    accent: 'green',
  },
  {
    num: '06',
    title: 'Dream state',
    body: 'When the user is away for more than 30 minutes, Maez enters an idle cycle — scanning recent memories for patterns, forming observations, drafting proposals for its own soul. Autonomous reflection, not triggered by prompts.',
    accent: 'amber',
  },
];

const STACK = [
  { label: 'Inference', value: 'Local LLM · evolves with the model', note: 'Currently in active evaluation — Qwen, Gemma, and others tested against each other.' },
  { label: 'Memory store', value: 'ChromaDB · cosine similarity · HNSW index', note: 'Three collections: raw (per-cycle), daily (consolidated), core (permanent).' },
  { label: 'Reasoning loop', value: '30-second daemon cycles · always on', note: 'Perceive → recall → think → store → act. Runs whether or not the user is present.' },
  { label: 'Training', value: 'QLoRA fine-tune on real conversations', note: 'Trained on the user\'s own Telegram and web conversations. Loss: 7.79 → 0.74.' },
  { label: 'Action pipeline', value: 'Covenant gate → classify → audit → execute', note: 'Four lanes: inline response, pending approval, escalate to user, deny.' },
  { label: 'Interfaces', value: 'Telegram · web chat · voice (in progress)', note: 'Proactive messages every ~25 minutes when the user has been away.' },
  { label: 'Hardware (v1)', value: 'RTX 4090 · 24GB VRAM · local Ubuntu machine', note: '~133 tokens/second. Cloud deployment is the scale path once the bond model is proven.' },
];

export default function HowItWorksPage() {
  const [loaded, setLoaded] = useState(false);
  useEffect(() => setLoaded(true), []);

  return (
    <>
      {/* ── HERO ── */}
      <section className={styles.hero}>
        <div className={styles.heroBlob} />
        <div className={styles.heroInner}>
          <motion.p className={styles.eyebrow} {...FADE_UP(0)}>Under the hood</motion.p>
          <motion.h1 className={styles.heroH1} {...FADE_UP(0.1)}>
            Not a wrapper.<br />
            <em className={styles.heroItalic}>A different thing entirely.</em>
          </motion.h1>
          <motion.p className={styles.heroSub} {...FADE_UP(0.2)}>
            Most "AI companions" are a system prompt on top of a cloud model. Maez is a persistent, locally-running intelligence with its own memory, its own reasoning loop, and a model trained on the specific person it is bonded to. Here is how that works.
          </motion.p>
        </div>
      </section>

      {/* ── PILLARS ── */}
      <section className={styles.pillarsSection}>
        <div className={styles.pillarsInner}>
          <motion.div className={styles.sectionHeader} {...FADE_UP()}>
            <p className={styles.eyebrow}>Six design decisions</p>
            <h2 className={styles.sectionH2}>The choices that make<br /><em className={styles.sectionItalic}>Maez different.</em></h2>
          </motion.div>
          <div className={styles.pillarsGrid}>
            {PILLARS.map((p, i) => (
              <motion.div key={p.num} className={`${styles.pillarCard} ${styles[`accent_${p.accent}`]}`} {...FADE_UP(i * 0.07)}>
                <span className={styles.pillarNum}>{p.num}</span>
                <strong className={styles.pillarTitle}>{p.title}</strong>
                <p className={styles.pillarBody}>{p.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── STACK ── */}
      <section className={styles.stackSection}>
        <div className={styles.stackInner}>
          <motion.div className={styles.sectionHeader} {...FADE_UP()}>
            <p className={styles.eyebrow}>The stack</p>
            <h2 className={styles.sectionH2}>What it is<br /><em className={styles.sectionItalic}>actually built on.</em></h2>
          </motion.div>
          <div className={styles.stackTable}>
            {STACK.map((row, i) => (
              <motion.div key={row.label} className={styles.stackRow} {...FADE_UP(i * 0.06)}>
                <span className={styles.stackLabel}>{row.label}</span>
                <div className={styles.stackRight}>
                  <span className={styles.stackValue}>{row.value}</span>
                  <span className={styles.stackNote}>{row.note}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── LOCAL FIRST ── */}
      <section className={styles.philosophySection}>
        <div className={styles.philosophyInner}>
          <motion.div className={styles.philosophyContent} {...FADE_UP()}>
            <p className={styles.eyebrow}>Why local first</p>
            <h2 className={styles.sectionH2}>The cloud is the<br /><em className={styles.sectionItalic}>scale path, not the start.</em></h2>
            <p className={styles.philosophyBody}>
              Running locally is not a limitation — it is the proof of concept. Before Maez can be offered to anyone else, the bond model has to be proven on one person. Local hardware makes that proof rigorous: no cloud abstraction, no shared state, nothing between the model and the human it is bonded to.
            </p>
            <p className={styles.philosophyBody}>
              Once the bond is real — once the architecture holds over months of continuous memory, personality drift, and daily use — the cloud deployment follows. The same principles, at scale, with the same guarantees. Local first is not a philosophy. It is a methodology.
            </p>
          </motion.div>
          <motion.div className={styles.philosophyDiagram} aria-hidden="true" {...FADE_UP(0.15)}>
            <div className={styles.diagRow}>
              <div className={`${styles.diagNode} ${styles.diagNodeActive}`}>
                <span className={styles.diagDot} />
                <span className={styles.diagLabel}>Local (now)</span>
                <span className={styles.diagSub}>One bond · one machine · proven</span>
              </div>
            </div>
            <div className={styles.diagArrow}>↓</div>
            <div className={styles.diagRow}>
              <div className={styles.diagNode}>
                <span className={styles.diagDot} />
                <span className={styles.diagLabel}>Cloud (next)</span>
                <span className={styles.diagSub}>Same model · same memory · many bonds</span>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className={styles.ctaSection}>
        <div className={styles.ctaInner}>
          <motion.div {...FADE_UP()}>
            <p className={styles.eyebrow}>See it in progress</p>
            <h2 className={styles.ctaH2}>Every decision logged.<br /><em className={styles.sectionItalic}>Every gate tested.</em></h2>
            <div className={styles.ctaActions}>
              <a href="/progress" className={styles.btnPrimary}>View the build log →</a>
              <a href="/" className={styles.btnSecondary}>Back to Maez</a>
            </div>
          </motion.div>
        </div>
      </section>
    </>
  );
}
