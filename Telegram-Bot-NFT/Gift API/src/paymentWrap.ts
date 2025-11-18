import { Api } from "telegram";
import { client } from "./mtprotoClient";

async function sleep(ms: number) {
    return new Promise((res) => setTimeout(res, ms));
}
async function retry<T>(
    fn: () => Promise<T>,
    attempts = 3,
    baseDelay = 500
): Promise<T> {
    let lastErr: any;
    for (let i = 0; i < attempts; i++) {
        try {
            return await fn();
        } catch (e) {
            lastErr = e;
            const delay = baseDelay * Math.pow(2, i);
            console.warn(`Retry ${i + 1}/${attempts} failed`);
            await sleep(delay);
        }
    }
    throw lastErr;
}

function getApiConstructor(path: string[]): any | undefined {
    let cur: any = Api;
    for (const p of path) {
        if (cur == null) return undefined;
        cur = cur[p] ?? cur[p[0]!.toLowerCase() + p.slice(1)];
    }
    return cur;
}

export async function getStarGifts(): Promise<any> {
    return retry(async () => {
        const Ctor = getApiConstructor(["payments", "GetStarGifts"]) ?? getApiConstructor(["payments", "getStarGifts"]);
        if (!Ctor) throw new Error("Api constructor payments.GetStarGifts not found in Api");
        const res = await client.invoke(new Ctor());
        return res;
    });    
}



