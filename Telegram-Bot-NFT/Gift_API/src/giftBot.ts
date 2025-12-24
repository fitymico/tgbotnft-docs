// Ты пишешь код в /src/giftBot.ts (человекочитаемый)
// Команда npx tsc читает настройки из tsconfig.json
// TypeScript из node_modules превращает TS в JS
// Готовый JS появляется в /dist/giftBot.js

// ======================== ЗАПУСК ОСУЩЕСТВЛЯЕТСЯ КОМАНДОЙ npm run dev ========================

import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';
import { loginFlow, saveSession, client } from './mtprotoClient.js';
import { getStarGifts, payStarGift, getStars } from './processWrap.js';
import { availableMemory } from 'process';
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

function starsToNumber(starsObj: any): number {
    if (starsObj == null) return 0;
    if (typeof starsObj === "number") return starsObj;
    if (typeof starsObj === "string") return parseInt(starsObj, 10) || 0;
    if (typeof starsObj === "object" && "value" in starsObj) {
        try { return Number(starsObj.value); } catch {}
    }
    if (typeof starsObj === "bigint") return Number(starsObj);
    return 0;
}

//================================== Логирование ==================================

const LOG_DIR = path.join("/home/dimzzz/Telegram-Bot-NFT", "data");
const LOG_FILE = path.join(LOG_DIR, "bot.log");

function debugLog(message: string): void {
    // Выводим только в консоль (не записываем в файл)
    console.log(message);
}

function logPurchase(message: string): void {
    // Выводим в консоль
    console.log(message);
    
    // Записываем в файл лога
    try {
        // Создаем директорию, если её нет
        if (!fs.existsSync(LOG_DIR)) {
            fs.mkdirSync(LOG_DIR, { recursive: true });
        }
        
        // Форматируем сообщение с временной меткой
        const timestamp = new Date().toISOString();
        const logMessage = `[${timestamp}] ${message}\n`;
        
        // Добавляем в файл (append mode)
        fs.appendFileSync(LOG_FILE, logMessage, { encoding: "utf8" });
    } catch (e) {
        // Если не удалось записать в лог, выводим ошибку в консоль, но не прерываем выполнение
        console.error("Ошибка при записи в лог-файл:", e);
    }
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
    // Узнаем кол-во звезд на балансе
    let starsInfo = await getStars();
    let stars = Number(starsInfo.balance.amount.value);

    // Подгружаем множество подарков из файла
    const seen = loadSeenSet();

    const res = await getStarGifts();
    const gifts: Array<any> = res?.gifts ?? (Array.isArray(res) ? res : null);

    if (!gifts) {
        console.log("Не нашёл поле gifts.");
        return;
    }

    const currentGifts = gifts.map(g => ({
        id: idToString(g.id),
        stars: starsToNumber(g.stars),
        availabilityRemains: g.availabilityRemains
    }));

    if (seen.size === currentGifts.length) {
        debugLog("[DEBUG]: Новых подарков не найдено...")
        return
    }
    else {
        // Cписок с новыми ID
        const foundIDs = currentGifts.filter(id => !seen.has(id.id))

        // Если новых подарков не найдено, выходим (для подстраховки)
        if (foundIDs.length === 0) {
            debugLog("[DEBUG]: Новых подарков не найдено...")
            return
        }

        // Открытие файла с настройками: data/status.json
        if (!fs.existsSync(filepathStatus)) {
            debugLog("[DEBUG] Файл data/status.json не найден...")
            return
        }
        else {
            // Парсинг правил для закупки подарков
            const purchaseRules = parseDistribution(status.distribution);
            
            // Создаем счетчики для каждого диапазона (сколько уже куплено в каждом диапазоне)
            const rangeCounters = new Map<string, {rule: PurchaseRule, bought: number}>();
            for (const rule of purchaseRules) {
                const rangeKey = `${rule.min}-${rule.max}`;
                rangeCounters.set(rangeKey, { rule, bought: 0 });
            }

            // Сортируем все подарки по убыванию стоимости (глобально)
            const allGifts = foundIDs.filter(gift => {
                // Проверка что ID реально есть
                if (!gift?.id) return false;
                // Проверка наличия подарка
                if (gift?.availabilityRemains === null || gift?.availabilityRemains === 0) return false;
                return true;
            });
            
            allGifts.sort((a, b) => b.stars - a.stars);
            
            logPurchase(`[DEBUG] Всего найдено ${allGifts.length} доступных подарков для покупки`);

            // Множество для хранения ID подарков, которые были куплены в этом цикле
            const boughtInThisCycle = new Set<string>();
            // Множество для хранения ID подарков, которые были обработаны в этом цикле
            const processedInThisCycle = new Set<string>();

            // Проходим по всем подаркам в порядке убывания стоимости
            for (const gift of allGifts) {
                if (processedInThisCycle.has(gift.id)) continue;
                processedInThisCycle.add(gift.id);

                // Определяем, к каким диапазонам относится этот подарок
                const applicableRules: Array<{rule: PurchaseRule, rangeKey: string}> = [];
                for (const rule of purchaseRules) {
                    const rangeKey = `${rule.min}-${rule.max}`;
                    const counter = rangeCounters.get(rangeKey);
                    if (!counter) continue;
                    
                    const giftStars = gift.stars;
                    if (giftStars >= rule.min && giftStars <= rule.max && counter.bought < rule.count) {
                        applicableRules.push({ rule, rangeKey });
                    }
                }

                // Если подарок не относится ни к одному диапазону, который еще нужно заполнить, пропускаем
                if (applicableRules.length === 0) {
                    continue;
                }

                // Преобразование из string в bigint
                const giftIdBigInt = BigInt(gift.id);
                
                // Определяем доступность подарка
                let giftAvailability = gift.availabilityRemains;
                if (typeof giftAvailability === "string") {
                    giftAvailability = parseInt(giftAvailability, 10) || 0;
                } else if (typeof giftAvailability === "object" && "value" in giftAvailability) {
                    giftAvailability = Number(giftAvailability.value) || 0;
                } else {
                    giftAvailability = Number(giftAvailability) || 0;
                }

                // Покупаем подарок, пока есть доступность, звезды, и есть диапазоны, которые нужно заполнить
                while (giftAvailability > 0 && stars >= gift.stars) {
                    // Проверяем, есть ли еще диапазоны, которые нужно заполнить
                    const activeRules = applicableRules.filter(({rule, rangeKey}) => {
                        const counter = rangeCounters.get(rangeKey);
                        return counter && counter.bought < rule.count;
                    });

                    if (activeRules.length === 0) {
                        // Все диапазоны, к которым относится этот подарок, уже заполнены
                        break;
                    }

                    // Покупаем подарок
                    const result = await payStarGift(
                        giftIdBigInt,
                        targetPeer,
                        undefined,
                        true,
                        false
                    );

                    if (!result) {
                        throw new Error("Покупка вернула пустой результат");
                    }

                    stars -= gift.stars;
                    giftAvailability--;
                    boughtInThisCycle.add(gift.id);

                    // Обновляем счетчики для всех диапазонов, к которым относится подарок
                    for (const {rangeKey} of activeRules) {
                        const counter = rangeCounters.get(rangeKey);
                        if (counter) {
                            counter.bought++;
                        }
                    }

                    // Формируем сообщение о покупке
                    const rangeInfo = activeRules.map(({rule, rangeKey}) => {
                        const counter = rangeCounters.get(rangeKey);
                        return `${rangeKey} (${counter?.bought || 0}/${rule.count})`;
                    }).join(', ');

                    logPurchase(`[DEBUG] Куплен подарок ${giftIdBigInt}, стоимость ${gift.stars} звезд, остаток: ${stars} звезд на балансе. Диапазоны: ${rangeInfo}`);
                    await new Promise(resolve => setTimeout(resolve, 200));
                }

                if (giftAvailability <= 0) {
                    logPurchase(`[DEBUG] Подарка с ${gift.id} больше не осталось`);
                }
                if (stars < gift.stars) {
                    logPurchase(`[DEBUG] Недостаточно звёзд для дальнейшей покупки подарка ${gift.id} (нужно ${gift.stars}, есть ${stars})`);
                }
            }

            // Выводим итоговую статистику по диапазонам
            for (const [rangeKey, counter] of rangeCounters.entries()) {
                if (counter.bought < counter.rule.count) {
                    logPurchase(`[DEBUG] Не удалось купить все подарки в диапазоне ${rangeKey}: куплено ${counter.bought} из ${counter.rule.count}`);
                } else {
                    logPurchase(`[DEBUG] Достигнуто нужное количество подарков в диапазоне ${rangeKey}: куплено ${counter.bought} из ${counter.rule.count}`);
                }
            }

            // После завершения всех покупок добавляем все обработанные подарки в seen set
            for (const giftId of processedInThisCycle) {
                seen.add(giftId);
            }

            // Сохраняем обновленный seen set после всех покупок
            saveSeenSet(seen);
        }
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