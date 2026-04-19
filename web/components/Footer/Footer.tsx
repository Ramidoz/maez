import styles from './Footer.module.css';

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <span className={styles.brand}>maez</span>
        <nav className={styles.links} aria-label="Footer navigation">
          <a href="/privacy" className={styles.link}>Privacy</a>
          <a href="mailto:hello@maez.ai" className={styles.link}>Contact</a>
        </nav>
        <span className={styles.copy}>© {new Date().getFullYear()} Maez</span>
      </div>
    </footer>
  );
}
