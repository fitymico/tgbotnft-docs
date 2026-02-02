import type { ReactNode } from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import CodeBlock from '@theme/CodeBlock';
import { HiGift, HiCog6Tooth, HiShieldCheck, HiBolt } from 'react-icons/hi2';
import StarField from '@site/src/components/StarField';

import styles from './index.module.css';

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <div className={styles.hero}>
      <StarField count={100} />
      <div className={styles.heroInner}>
        <div className={styles.heroContent}>
          <Heading as="h1" className={styles.heroTitle}>
            {siteConfig.title}
          </Heading>
          <p className={styles.heroSubtitle}>{siteConfig.tagline}</p>
          <div className={styles.features}>
            <div className={styles.featureItem}>
              <HiGift className={styles.featureIcon} />
              <span>Отслеживание NFT-подарков</span>
            </div>
            <div className={styles.featureItem}>
              <HiCog6Tooth className={styles.featureIcon} />
              <span>Удобная конфигурация</span>
            </div>
            <div className={styles.featureItem}>
              <HiShieldCheck className={styles.featureIcon} />
              <span>Безопасность</span>
            </div>
            <div className={styles.featureItem}>
              <HiBolt className={styles.featureIcon} />
              <span>Быстрая автопокупка</span>
            </div>
          </div>
          <div className={styles.buttons}>
            <Link
              className={styles.primaryButton}
              to="/purchase">
              Купить →
            </Link>
            <Link
              className={styles.secondaryButton}
              to="/docs/intro">
              Установка
            </Link>
          </div>
        </div>
        <div className={styles.heroVisual}>
          <div className={styles.codeBlock}>
            <div className={styles.codeHeader}>
              <span className={styles.codeDot} style={{ background: '#f7768e' }}></span>
              <span className={styles.codeDot} style={{ background: '#e0af68' }}></span>
              <span className={styles.codeDot} style={{ background: '#9ece6a' }}></span>
            </div>
            <CodeBlock language="bash">
              {`# Быстрый старт
git clone https://github.com/...
cd Telegram-Bot-NFT

# Установка и запуск
make install
make start

# Бот запущен!`}
            </CodeBlock>
          </div>
        </div>
      </div>
      <div className={styles.copyright}>
        © {new Date().getFullYear()} Telegram Bot NFT
      </div>
    </div>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Главная"
      description="Telegram Bot NFT — автоматизация работы с NFT-подарками в Telegram"
      wrapperClassName={`${styles.layoutWrapper} homepage-wrapper`}>
      <HomepageHeader />
    </Layout>
  );
}
