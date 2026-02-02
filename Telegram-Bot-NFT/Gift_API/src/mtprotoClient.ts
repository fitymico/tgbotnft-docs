import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';
import { fileURLToPath } from "url";

// Определяем корневую директорию проекта
function getProjectRoot(): string {
    if (process.env.DATA_DIR) return process.env.DATA_DIR;
    
    try {
        const __filename = fileURLToPath(import.meta.url);
        const __dirname = path.dirname(__filename);
        // Если путь виртуальный (Bun бинарник) - используем cwd
        if (__dirname.startsWith('/$bunfs') || __dirname === '/') {
            return process.cwd();
        }
        return path.resolve(__dirname, "../..");
    } catch {
        return process.cwd();
    }
}

const PROJECT_ROOT = getProjectRoot();
dotenv.config({ path: path.join(PROJECT_ROOT, ".env") });

import { TelegramClient, Api } from "telegram";
import { StringSession } from "telegram/sessions/index.js";

// Сессия может быть из .env (SESSION_STRING) или из файла
let sessionString = process.env.SESSION_STRING || '';

// Если SESSION_STRING не задан, пробуем загрузить из файла
const SESSIONFILE = path.join(PROJECT_ROOT, "data/session.session");
if (!sessionString && fs.existsSync(SESSIONFILE)) {
    sessionString = fs.readFileSync(SESSIONFILE, 'utf8');
}

const STRINGSESSION = new StringSession(sessionString);

const API_ID = Number(process.env.API_ID);
const API_HASH = process.env.API_HASH!;

if (!API_ID || !API_HASH) {
    console.log("Нет API_ID или API_HASH");
    throw new Error("API_ID или API_HASH не заданы в .env");
}

export const client = new TelegramClient(STRINGSESSION, API_ID, API_HASH, {
    connectionRetries: 5,
});

export async function saveSession(): Promise<void> {
    const NEWSESSION = STRINGSESSION.save();
    
    // Сохраняем в файл если есть директория data
    const dataDir = path.join(PROJECT_ROOT, "data");
    if (fs.existsSync(dataDir)) {
        fs.writeFileSync(SESSIONFILE, NEWSESSION, 'utf8');
        console.log("Сессия сохранена в файл:", SESSIONFILE);
    }
    
    // Выводим сессию для .env если запущен без файла
    console.log("\n=== SESSION_STRING для .env ===");
    console.log(NEWSESSION);
    console.log("================================\n");
    return;
}

export async function loginFlow() {
    await client.start({
        phoneNumber: async () => {
            process.stdout.write("Введите номер телефона (+7...): ");
            return new Promise<string>(resolve => process.stdin.once("data", d => resolve(d.toString().trim())));
        },
        phoneCode: async () => {
            process.stdout.write("Введите код из Telegram: ");
            return new Promise<string>(resolve => process.stdin.once("data", d => resolve(d.toString().trim())));
        },
        password: async () => {
            process.stdout.write("Если включен 2FA, введите пароль (или Enter): ");
            return new Promise<string>(resolve => process.stdin.once("data", d => resolve(d.toString().trim())));
        },
        onError: (err) => console.error("Ошибка в loginFlow:", err)
    });

    console.log("Логин выполнен");
    await saveSession();
}