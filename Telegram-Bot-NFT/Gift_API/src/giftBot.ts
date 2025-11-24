// Ты пишешь код в /src/giftBot.ts (человекочитаемый)
// Команда npx tsc читает настройки из tsconfig.json
// TypeScript из node_modules превращает TS в JS
// Готовый JS появляется в /dist/giftBot.js

// ======================== ЗАПУСК ОСУЩЕСТВЛЯЕТСЯ КОМАНДОЙ npm run dev ========================

import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';
import { loginFlow, saveSession, client } from './mtprotoClient.js';
import { getStarGifts, checkCanSendGift, payStarGift, } from './processWrap.js';
dotenv.config();

interface aiogramBotStatus {
    is_running: boolean,
    status_text: string,
    distribution: string,
    iterations_total: number,
    iteration_current: number,
    delay: number
}

function loadStatus(): aiogramBotStatus {
    try {
        const filepath = path.join("/home/dimzzz/Telegram-Bot-NFT", "data/status.json");
        const data = fs.readFileSync(filepath, 'utf8');
        const status: aiogramBotStatus = JSON.parse(data);
        return status;
    }
    catch (error) {
        console.log("No found file");
        return {
            "is_running": false,
            "status_text": "stopped",
            "distribution": "",
            "iterations_total": 0,
            "iteration_current": 0,
            "delay": 0.1
        }
    }
}

function saveStatus(status: aiogramBotStatus): void {
    try {
        const filepath = path.join("/home/dimzzz/Telegram-Bot-NFT", "data/status.json");
        fs.writeFileSync(filepath, JSON.stringify(status, null, 4));
        return;
    }
    catch (error) {
        console.log("No found file");
        return;
    }
}

async function processFullCycle(): Promise<void> {
    console.log("Запуск процесса...");
    await client.connect();
    console.log("client.connect() выполнен");
    console.log("Выполнение цикла закупки подарков...");

    const seen = new Set<string>();
    const OK_CONSTR = 0x374fa7ad;   // checkCanSendGiftResultOk
    const FAIL_CONSTR = 0xd5e58274; // checkCanSendGiftResultFail

    const res = await getStarGifts();
    const gifts = res?.gifts ?? (Array.isArray(res) ? res : null);

    if (!gifts) {
        console.log("Не нашёл поле gifts. Посмотри структуру выше ↑");
        return;
    }

    console.log("\nНайденные подарки:");
    for (const g of gifts) {
        console.log("-----------------------------");
        console.log("ID:", g.id);

    }

}

processFullCycle();

// Добавить alt - эмодзи, который показывает подарок ( мб придется использовать getGiftReadableName() )
// Добавить определение подарков (можно купить или уже нет, может это базовые подарки телеграма)
// Сделать сортировку по ID (можно сделать список: 'эмодзи': {а тут все id для этого эмодзи} )
