// Ты пишешь код в /src/giftBot.ts (человекочитаемый)
// Команда npx tsc читает настройки из tsconfig.json
// TypeScript из node_modules превращает TS в JS
// Готовый JS появляется в /dist/giftBot.js

// ======================== ЗАПУСК ОСУЩЕСТВЛЯЕТСЯ КОМАНДОЙ npm run dev ========================

import * as fs from 'fs';
import * as path from 'path';
import axios from "axios";
import * as dotenv from 'dotenv';
import { loginFlow, saveSession } from './mtprotoClient.js';
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

