import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';
dotenv.config();

import { TelegramClient, Api } from "telegram";
import { StringSession } from "telegram/sessions";

const SESSIONFILE = path.join("/home/dimzzz/Telegram-Bot-NFT", "data/session.session");

let sessionString = '';
if (fs.existsSync(SESSIONFILE)) {
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
    fs.writeFileSync(SESSIONFILE, NEWSESSION, 'utf8');
    console.log("Текущая сессия сохранена в ", SESSIONFILE);
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