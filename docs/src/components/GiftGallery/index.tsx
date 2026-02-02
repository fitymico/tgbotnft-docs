import React from 'react';
import GiftCard from '../GiftCard';
import styles from './styles.module.css';

const SAMPLE_GIFTS = [
    {
        id: 'gift_001',
        name: 'Golden Star',
        description: 'A legendary golden star NFT gift. Very rare and precious!',
        rarity: 'legendary' as const,
    },
    {
        id: 'gift_002',
        name: 'Crystal Heart',
        description: 'An epic crystal heart that shines in the dark.',
        rarity: 'epic' as const,
    },
    {
        id: 'gift_003',
        name: 'Blue Diamond',
        description: 'A rare blue diamond with mysterious powers.',
        rarity: 'rare' as const,
    },
    {
        id: 'gift_004',
        name: 'Silver Coin',
        description: 'A common silver coin for everyday gifting.',
        rarity: 'common' as const,
    },
];

export default function GiftGallery(): JSX.Element {
    return (
        <div className={styles.gallery}>
            <h2 className={styles.title}>🎁 NFT Gift Gallery</h2>
            <p className={styles.subtitle}>Click on a card to flip it!</p>
            <div className={styles.grid}>
                {SAMPLE_GIFTS.map((gift) => (
                    <GiftCard key={gift.id} {...gift} />
                ))}
            </div>
        </div>
    );
}
