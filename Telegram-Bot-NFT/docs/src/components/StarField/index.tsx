import React, { type ReactNode } from 'react';
import styles from './styles.module.css';

interface StarFieldProps {
    count?: number;
}

function Star({ style }: { style: React.CSSProperties }) {
    return (
        <svg
            className={styles.star}
            style={style}
            viewBox="0 0 24 24"
            fill="currentColor"
        >
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
    );
}

export default function StarField({ count = 30 }: StarFieldProps): ReactNode {
    const stars = React.useMemo(() => {
        return Array.from({ length: count }, (_, i) => ({
            id: i,
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            size: 6 + Math.random() * 10,
            opacity: 0.1 + Math.random() * 0.2,
            animationDelay: `${Math.random() * 5}s`,
            animationDuration: `${3 + Math.random() * 4}s`,
        }));
    }, [count]);

    return (
        <div className={styles.starField}>
            {stars.map((star) => (
                <Star
                    key={star.id}
                    style={{
                        left: star.left,
                        top: star.top,
                        width: star.size,
                        height: star.size,
                        opacity: star.opacity,
                        animationDelay: star.animationDelay,
                        animationDuration: star.animationDuration,
                    }}
                />
            ))}
        </div>
    );
}
