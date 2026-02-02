/**
 * License Client для Telegram Gift Bot
 * Активация, heartbeat и проверка лицензии
 */
import * as os from 'os';
import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';

// Конфигурация
// ВАЖНО: IP сервера лицензий захардкожен для безопасности
const LICENSE_SERVER_URL = 'http://82.148.18.168:8080';
const HEARTBEAT_INTERVAL = 60 * 60 * 1000; // 1 час в миллисекундах

// Типы для API ответов
interface ActivateResponse {
    success: boolean;
    session_token?: string;
    expires_at?: string;
    message: string;
}

interface HeartbeatResponse {
    success: boolean;
    expires_at?: string;
    message: string;
}

interface ErrorResponse {
    detail?: string;
}

// Хранение сессии
let sessionToken: string | null = null;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let licenseExpiresAt: Date | null = null;

/**
 * Генерация уникального instance_id на основе железа
 */
function generateInstanceId(): string {
    const networkInterfaces = os.networkInterfaces();
    let macAddress = '';
    
    // Ищем первый MAC-адрес
    for (const [name, interfaces] of Object.entries(networkInterfaces)) {
        if (!interfaces) continue;
        for (const iface of interfaces) {
            if (!iface.internal && iface.mac && iface.mac !== '00:00:00:00:00:00') {
                macAddress = iface.mac;
                break;
            }
        }
        if (macAddress) break;
    }
    
    // Создаём хеш из MAC + hostname
    const data = `${macAddress}-${os.hostname()}-${os.platform()}-${os.arch()}`;
    return crypto.createHash('sha256').update(data).digest('hex').substring(0, 32);
}

/**
 * Активация лицензии
 */
export async function activateLicense(licenseKey: string): Promise<boolean> {
    const instanceId = generateInstanceId();
    
    console.log(`[LICENSE] Активация лицензии...`);
    console.log(`[LICENSE] Instance ID: ${instanceId}`);
    
    try {
        const response = await fetch(`${LICENSE_SERVER_URL}/api/activate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                license_key: licenseKey,
                instance_id: instanceId
            })
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText })) as ErrorResponse;
            console.error(`[LICENSE] Ошибка активации: ${error.detail || 'Неизвестная ошибка'}`);
            return false;
        }
        
        const data = await response.json() as ActivateResponse;
        
        if (data.success && data.session_token) {
            sessionToken = data.session_token;
            licenseExpiresAt = new Date(data.expires_at || Date.now());
            
            console.log(`[LICENSE] ✅ Лицензия активирована`);
            console.log(`[LICENSE] Истекает: ${licenseExpiresAt.toLocaleString()}`);
            
            // Запускаем heartbeat
            startHeartbeat();
            
            return true;
        }
        
        return false;
    } catch (error) {
        console.error(`[LICENSE] Ошибка подключения к серверу лицензий:`, error);
        return false;
    }
}

/**
 * Heartbeat — проверка лицензии каждый час
 */
async function sendHeartbeat(): Promise<boolean> {
    if (!sessionToken) {
        console.error(`[LICENSE] Нет активной сессии`);
        return false;
    }
    
    try {
        const response = await fetch(`${LICENSE_SERVER_URL}/api/heartbeat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_token: sessionToken })
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText })) as ErrorResponse;
            console.error(`[LICENSE] ❌ Heartbeat failed: ${error.detail}`);
            
            // Лицензия недействительна
            stopHeartbeat();
            sessionToken = null;
            
            return false;
        }
        
        const data = await response.json() as HeartbeatResponse;
        licenseExpiresAt = new Date(data.expires_at || Date.now());
        
        console.log(`[LICENSE] ✓ Heartbeat OK. Лицензия до: ${licenseExpiresAt.toLocaleString()}`);
        return true;
    } catch (error) {
        console.error(`[LICENSE] Ошибка heartbeat:`, error);
        return false;
    }
}

/**
 * Запуск периодической проверки
 */
function startHeartbeat(): void {
    if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
    }
    
    heartbeatTimer = setInterval(async () => {
        const success = await sendHeartbeat();
        if (!success) {
            console.error(`[LICENSE] ❌ Лицензия недействительна! Остановка бота...`);
            process.exit(1);
        }
    }, HEARTBEAT_INTERVAL);
    
    console.log(`[LICENSE] Heartbeat запущен (каждые ${HEARTBEAT_INTERVAL / 1000 / 60} мин)`);
}

/**
 * Остановка heartbeat
 */
function stopHeartbeat(): void {
    if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
    }
}

/**
 * Деактивация при выходе
 */
export async function deactivateLicense(): Promise<void> {
    if (!sessionToken) return;
    
    stopHeartbeat();
    
    try {
        await fetch(`${LICENSE_SERVER_URL}/api/deactivate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_token: sessionToken })
        });
        console.log(`[LICENSE] Лицензия деактивирована`);
    } catch (error) {
        // Игнорируем ошибки при выходе
    }
    
    sessionToken = null;
}

/**
 * Проверка активности лицензии
 */
export function isLicenseActive(): boolean {
    return sessionToken !== null;
}

/**
 * Получить дату истечения
 */
export function getLicenseExpiry(): Date | null {
    return licenseExpiresAt;
}

// Деактивация при завершении процесса
process.on('SIGINT', async () => {
    console.log('\n[LICENSE] Завершение работы...');
    await deactivateLicense();
    process.exit(0);
});

process.on('SIGTERM', async () => {
    await deactivateLicense();
    process.exit(0);
});
