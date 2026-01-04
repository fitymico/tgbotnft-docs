import React, { useState, type ReactNode } from 'react';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import { HiCheck, HiStar } from 'react-icons/hi2';
import { SiBoosty } from 'react-icons/si';
import StarField from '@site/src/components/StarField';

import styles from './styles.module.css';

// Telegram Stars icon (official TG Stars design)
function TgStarsIcon({ className }: { className?: string }) {
    return (
        <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            className={className}
            style={{ width: '1em', height: '1em' }}
        >
            <path d="M12 2L14.4 8.4L21 9.6L16.2 14.4L17.4 21L12 17.6L6.6 21L7.8 14.4L3 9.6L9.6 8.4L12 2Z" />
        </svg>
    );
}

interface PlanPricing {
    price: string;
    period: string;
    boostyLink: string;
    tgStarsLink: string;
}

interface Plan {
    title: string;
    monthly: PlanPricing;
    yearly: PlanPricing;
    features: string[];
    popular?: boolean;
}

interface PricingCardProps {
    title: string;
    price: string;
    period: string;
    features: string[];
    popular?: boolean;
    boostyLink: string;
    tgStarsLink: string;
}

function PricingCard({ title, price, period, features, popular, boostyLink, tgStarsLink }: PricingCardProps) {
    return (
        <div className={`${styles.card} ${popular ? styles.popular : ''}`}>
            {popular && (
                <div className={styles.popularBadge}>
                    <HiStar /> Популярный
                </div>
            )}
            <h3 className={styles.cardTitle}>{title}</h3>
            <div className={styles.price}>
                <span className={styles.priceValue}>{price}</span>
                <span className={styles.pricePeriod}>/ {period}</span>
            </div>
            <ul className={styles.features}>
                {features.map((feature, index) => (
                    <li key={index} className={styles.feature}>
                        <HiCheck className={styles.checkIcon} />
                        {feature}
                    </li>
                ))}
            </ul>
            <div className={styles.buyButtons}>
                <a href={boostyLink} className={styles.buyButton}>
                    <SiBoosty /> Boosty
                </a>
                <a href={tgStarsLink} className={styles.buyButton}>
                    <TgStarsIcon /> TG Stars
                </a>
            </div>
        </div>
    );
}

interface ToggleSwitchProps {
    checked: boolean;
    onChange: (checked: boolean) => void;
    leftLabel: string;
    rightLabel: string;
}

function ToggleSwitch({ checked, onChange, leftLabel, rightLabel }: ToggleSwitchProps) {
    return (
        <div className={styles.toggleSection}>
            <span className={`${styles.toggleLabel} ${!checked ? styles.activeLabel : ''}`}>
                {leftLabel}
            </span>
            <button
                type="button"
                className={`${styles.toggle} ${checked ? styles.toggleOn : ''}`}
                onClick={() => onChange(!checked)}
                role="switch"
                aria-checked={checked}
            >
                <span className={styles.toggleThumb} />
            </button>
            <span className={`${styles.toggleLabel} ${checked ? styles.activeLabel : ''}`}>
                {rightLabel}
            </span>
        </div>
    );
}

const PLANS: Plan[] = [
    {
        title: 'SELF-HOST',
        monthly: {
            price: '199₽',
            period: 'месяц',
            boostyLink: 'https://boosty.to/dimopster/purchase/1',
            tgStarsLink: 'https://t.me/dimopster?start=selfhost_monthly',
        },
        yearly: {
            price: '1990₽',
            period: 'год',
            boostyLink: 'https://boosty.to/dimopster/purchase/2',
            tgStarsLink: 'https://t.me/dimopster?start=selfhost_yearly',
        },
        features: [
            'Полный доступ к боту',
            'Автоматическая покупка NFT',
            'Отслеживание подарков',
            'Telegram поддержка',
        ],
    },
    {
        title: 'HOSTING',
        monthly: {
            price: '299₽',
            period: 'месяц',
            boostyLink: 'https://boosty.to/dimopster/purchase/3',
            tgStarsLink: 'https://t.me/dimopster?start=hosting_monthly',
        },
        yearly: {
            price: '2990₽',
            period: 'год',
            boostyLink: 'https://boosty.to/dimopster/purchase/4',
            tgStarsLink: 'https://t.me/dimopster?start=hosting_yearly',
        },
        features: [
            'Полный доступ к боту',
            'Автоматическая покупка NFT',
            'Отслеживание подарков',
            'Telegram поддержка',
            'Развёртывание "под ключ"',
            'Защищенный сервер',
        ],
        popular: true,
    },
    {
        title: 'HOSTING PRO',
        monthly: {
            price: '449₽',
            period: 'месяц',
            boostyLink: 'https://boosty.to/dimopster/purchase/5',
            tgStarsLink: 'https://t.me/dimopster?start=hostingpro_monthly',
        },
        yearly: {
            price: '4490₽',
            period: 'год',
            boostyLink: 'https://boosty.to/dimopster/purchase/6',
            tgStarsLink: 'https://t.me/dimopster?start=hostingpro_yearly',
        },
        features: [
            'Полный доступ к боту',
            'Автоматическая покупка NFT',
            'Отслеживание подарков',
            'Приоритетная поддержка',
            'Развёртывание "под ключ"',
            'Отдельный защищенный сервер',
        ],
    },
];

export default function Purchase(): ReactNode {
    const [isYearly, setIsYearly] = useState(false);

    return (
        <Layout
            title="Купить"
            description="Тарифы и цены на Telegram Bot NFT">
            <div className={styles.pageWrapper}>
                <StarField count={50} />
                <div className={styles.container}>
                    <Heading as="h1" className={styles.title}>Тарифы</Heading>
                    <p className={styles.subtitle}>Выберите подходящий план</p>

                    <ToggleSwitch
                        checked={isYearly}
                        onChange={setIsYearly}
                        leftLabel="Помесячно"
                        rightLabel="Годовой"
                    />

                    <div className={styles.cards}>
                        {PLANS.map((plan, index) => {
                            const pricing = isYearly ? plan.yearly : plan.monthly;
                            return (
                                <PricingCard
                                    key={index}
                                    title={plan.title}
                                    price={pricing.price}
                                    period={pricing.period}
                                    features={plan.features}
                                    popular={plan.popular}
                                    boostyLink={pricing.boostyLink}
                                    tgStarsLink={pricing.tgStarsLink}
                                />
                            );
                        })}
                    </div>

                </div>
                <div className={styles.copyright}>
                    © {new Date().getFullYear()} Telegram Bot NFT
                </div>
            </div>
        </Layout>
    );
}
