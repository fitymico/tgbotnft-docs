// Ты пишешь код в /src/giftBot.ts (человекочитаемый)
// Команда npx tsc читает настройки из tsconfig.json
// TypeScript из node_modules превращает TS в JS
// Готовый JS появляется в /dist/giftBot.js

// ======================== ЗАПУСК ОСУЩЕСТВЛЯЕТСЯ КОМАНДОЙ npm run dev ========================

import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';
import { loginFlow, saveSession, client } from './mtprotoClient.js';
import { getStarGifts, payStarGift, } from './processWrap.js';
dotenv.config();

const targetPeer = await client.getInputEntity('me');
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

    let count = 0;
    for (const g of gifts) { 
        if (count == 1) break;

        console.log("-----------------------------");
        console.log("ID:", g.id);
        console.log("Stars:", g.stars);
        console.log("AvailabilityRemains:", g.availabilityRemains);

        if (g.availabilityRemains === 0) {
            console.log("❌ НЕЛЬЗЯ КУПИТЬ: распродано или недоступно");
            continue; // Переходим к следующему подарку
        }
        console.log("✅ МОЖНО КУПИТЬ!");
        const result = await payStarGift(
            g.id.value,
            targetPeer,
            undefined,
            true,
            false
        );
        //console.log("Result:\n", result);
        count++;
        // const result = await checkCanSendGift(g.id);
        // console.log("Can Send Gift Result:", result);
        // console.log("Stars:", g.stars);
        // console.log("SoldOut:", g.soldOut);
        // console.log("AvailabilityTotal:", g.availabilityTotal);
        // console.log("AvailabilityRemains:", g.availabilityRemains);
    }
    // console.log(Object.keys(g));

    return;
}

processFullCycle();

// Добавить определение подарков (можно купить или уже нет, может это базовые подарки телеграма (из кол-во null)):
//    Нужно создать список уже имеющихся подарков, отправлять запрос getStarGifts() и проверять, не появилось ли что-то новое;
//    У меня будет массив всех ID , отправляю запрос getStarGifts() и проверяю количество ID в двух наборах:
//        Если после отправки запроса появился новый ID , то размер будет больше. Далее будет проверка на soldOut и покупку в соответствии с правилами json.

// НУЖНО ПОДСУНУТЬ ФУНКЦИЮ CheckCanSendGift В api.d.ts файл (вручную)


//[ 'CONSTRUCTOR_ID', 'SUBCLASS_OF_ID', 'className', 'classType', 'originalArgs', 'flags', 'limited', 'soldOut', 'birthday', 'id', 'sticker', 'stars', 'availabilityRemains', 'availabilityTotal', 'convertStars', 'firstSaleDate', 'lastSaleDate', 'upgradeStars' ]