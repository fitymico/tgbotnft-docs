import React, { useState } from 'react';
import styles from './styles.module.css';

interface GiftCardProps {
    id: string;
    name: string;
    description: string;
    imageUrl?: string;
    rarity?: 'common' | 'rare' | 'epic' | 'legendary';
}

export default function GiftCard({
    id,
    name,
    description,
    imageUrl = 'https://via.placeholder.com/200x200/6366f1/ffffff?text=NFT',
    rarity = 'common',
}: GiftCardProps): JSX.Element {
    const [isFlipped, setIsFlipped] = useState(false);

    return (
        <div
            className={`${styles.card} ${styles[rarity]}`}
            onClick={() => setIsFlipped(!isFlipped)}
        >
            <div className={`${styles.cardInner} ${isFlipped ? styles.flipped : ''}`}>
                <div className={styles.cardFront}>
                    <img src={imageUrl} alt={name} className={styles.image} />
                    <h3 className={styles.name}>{name}</h3>
                    <span className={styles.rarity}>{rarity.toUpperCase()}</span>
                </div>
                <div className={styles.cardBack}>
                    <p className={styles.description}>{description}</p>
                    <code className={styles.id}>ID: {id}</code>
                </div>
            </div>
        </div>
    );
}
