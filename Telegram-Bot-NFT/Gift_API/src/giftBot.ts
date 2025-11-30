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

//================================== Работа с файлом подарков ==================================

function loadSeenSet(): Set<string> {
    try {
        const filepath = path.join("/home/dimzzz/Telegram-Bot-NFT", "data/giftID.json");
        if (!fs.existsSync(filepath)) return new Set();
        const raw = fs.readFileSync(filepath, "utf8");
        const arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return new Set();
        return new Set(arr.map(String));
    } catch (e) {
        console.warn("Ошибка при чтении seenGifts:", e);
        return new Set();
    }
}

function saveSeenSet(seen: Set<string>): void {
    try {
        const filepath = path.join("/home/dimzzz/Telegram-Bot-NFT", "data/giftID.json");
        const dir = path.dirname(filepath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

        const tmp = filepath + ".tmp";
        fs.writeFileSync(tmp, JSON.stringify(Array.from(seen), null, 2), { encoding: "utf8" });
        fs.renameSync(tmp, filepath);
    } catch (e) {
        console.error("Ошибка при сохранении seenGifts:", e);
    }
}

function idToString(idObj: any): string {
    if (idObj == null) return "";
    if (typeof idObj === "object" && "value" in idObj) {
        try { return idObj.value.toString(); } catch {}
    }
    if (typeof idObj === "bigint") return idObj.toString();
    return String(idObj);
}

//======================================================================================================
//================================= Разбор строки распределения звезд ==================================

interface PurchaseRule {
    min: number;
    max: number;
    count: number;
}

function parseDistribution(distribution: string): PurchaseRule[] {
    const rules: PurchaseRule[] = [];
    const lines = distribution.split("\n").map(line => line.trim()).filter(Boolean);

    for (const line of lines) {
        const parts = line.split(" ").filter(Boolean);
        if (parts.length === 0) continue;

        const count = parseInt(parts[parts.length - 1] ?? "0", 10);
        let min = 0;
        let max = Infinity;

        const rangePart = parts.slice(0, parts.length - 1).join(" ");

        // Разбиваем диапазон по "и", если есть
        const rangePieces = rangePart.split("и").map(p => p.trim());

        for (const piece of rangePieces) {
            let match;

            // <= или <
            if ((match = piece.match(/^<=(\d+)$/))) {
                max = parseInt(match[1] ?? "0", 10);
            } else if ((match = piece.match(/^<(\d+)$/))) {
                max = parseInt(match[1] ?? "0", 10) - 1;
            } else if ((match = piece.match(/^>=(\d+)$/))) {
                min = parseInt(match[1] ?? "0", 10);
            } else if ((match = piece.match(/^>(\d+)$/))) {
                min = parseInt(match[1] ?? "0", 10) + 1;
            }
        }

        rules.push({ min, max, count });
    }

    return rules;
}

const filepathStatus = path.join("/home/dimzzz/Telegram-Bot-NFT", "data/status.json")
const status = JSON.parse(fs.readFileSync(filepathStatus, "utf8")) as {
    is_running: boolean;
    status_text: string;
    distribution: string;
    iterations_total: number;
    iteration_current: number;
    delay: number;
};

//======================================================================================================

async function processFullCycle(): Promise<void> {
    const seen = loadSeenSet();

    const res = await getStarGifts();
    let gifts: Array<any> = res?.gifts ?? (Array.isArray(res) ? res : null); // поменять на const перед запуском на серве

    // ОБЯЗАТЕЛЬНО УБРАТЬ ПЕРЕД ЗАПУСКОМ НА СЕРВ
    if (gifts) {
        console.log("[DEBUG]: gifts пуст — используются тестовые данные");

        gifts.push(
            { id: "1234567890000" },
            { id: "9876543219999" }
        );
    }
    //============================================

    const currentIDs = gifts.map(g => idToString(g.id));

    if (seen.size === currentIDs.length) {
        console.log("[DEBUG]: Новых подарков не найдено...")
        return
    }
    else {
        // нужно создать список ID, которые являются новыми - тут же вывести их список через console.log
        const foundIDs = currentIDs.filter(id => !seen.has(id))
        console.log("[DEBUG]: Найдены новые подарки:", foundIDs);

        // тут открывается файл с настройками: data/status.json (описывает как нужно покупать подарки и по сколько штук)
        if (!fs.existsSync(filepathStatus)) {
            console.log("[DEBUG] Файл data/status.json не найден...")
            return
        }
        else {
            const purchaseRules = parseDistribution(status.distribution);
            console.log(purchaseRules);
        }

        // далее тут запускаем цикл исходя из данных, полученных из файла (+ нужно получить макс. количество подарков на юзера, + проверка на наличие у меня звезд)
        // выходим из этого цикла только когда выкупили все подарки в соответствии с файлом-настройкой (data/status.json)

        // сделав полный выкуп, добавляем ID новых подарков в файл data/giftID.json
    }
    
    return
}

async function main(): Promise<void> {
    try {
        await client.connect();
        console.log("--- Подключение выполнено ---");
        console.log("--- Сканирование подарков ---");

        while (true) {
            try {
                await processFullCycle();
            } 
            catch (err) {
                console.error("Ошибка в процессе цикла:", err);
            }
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    } catch (err) {
        console.error("Не удалось подключиться:", err);
    }
    return
}

main();

// Добавить определение подарков (можно купить или уже нет, может это базовые подарки телеграма (их кол-во null)):
//    Нужно создать список уже имеющихся подарков, отправлять запрос getStarGifts() и проверять, не появилось ли что-то новое;
//    У меня будет массив всех ID , отправляю запрос getStarGifts() и проверяю количество ID в двух наборах:
//        Если после отправки запроса появился новый ID , то размер будет больше. Далее будет проверка на soldOut и покупку в соответствии с правилами json.


//[ 'CONSTRUCTOR_ID', 'SUBCLASS_OF_ID', 'className', 'classType', 'originalArgs', 'flags', 'limited', 'soldOut', 'birthday', 'id', 'sticker', 'stars', 'availabilityRemains', 'availabilityTotal', 'convertStars', 'firstSaleDate', 'lastSaleDate', 'upgradeStars' ]

    // if (!gifts) {
    //     console.log("Не нашёл поле gifts.");
    //     return;
    // }

    // console.log("\nНайденные подарки:");

    // let count = 0;
    // for (const g of gifts) { 
    //     if (count == 1) break;

    //     console.log("-----------------------------");
    //     console.log("ID:", g.id);
    //     console.log("Stars:", g.stars);
    //     console.log("AvailabilityRemains:", g.availabilityRemains);

    //     if (g.availabilityRemains === 0) {
    //         console.log("❌ НЕЛЬЗЯ КУПИТЬ: распродано или недоступно");
    //         continue; // Переходим к следующему подарку
    //     }
    //     console.log("✅ МОЖНО КУПИТЬ!");
    //     const result = await payStarGift(
    //         g.id.value,
    //         targetPeer,
    //         undefined,
    //         true,
    //         false
    //     );
    //     //console.log("Result:\n", result);
    //     count++;
    //     // const result = await checkCanSendGift(g.id);
    //     // console.log("Can Send Gift Result:", result);
    //     // console.log("Stars:", g.stars);
    //     // console.log("SoldOut:", g.soldOut);
    //     // console.log("AvailabilityTotal:", g.availabilityTotal);
    //     // console.log("AvailabilityRemains:", g.availabilityRemains);
    // }
    // console.log(Object.keys(g));