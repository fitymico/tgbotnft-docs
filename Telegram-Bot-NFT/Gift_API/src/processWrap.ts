import { Api, TelegramClient } from "telegram";
import { client } from "./mtprotoClient.js";
import bigInt from "big-integer";
//import { targetPeer } from './giftBot.js';

// const BaseType = Api.payments.StarGift || Api.TypeObject || Object;

// export class CheckCanSendGiftResultOk extends BaseType {
//     static CONSTRUCTOR_ID = 0x374fa7ad;
//     static SUBCLASS_OF_ID = 0x5d20f1a2;
//     static className = "payments.CheckCanSendGiftResultOk";
    
//     constructor() {
//         super({});
//     }
// }

// export class CheckCanSendGiftResultFail extends BaseType {
//     static CONSTRUCTOR_ID = 0xd5e58274;
//     static SUBCLASS_OF_ID = 0x5d20f1a2;
//     static className = "payments.CheckCanSendGiftResultFail";
    
//     constructor(public reason: any) {
//         super({ reason });
//     }
// }

// export type CheckCanSendGiftResult = CheckCanSendGiftResultOk | CheckCanSendGiftResultFail;

// export class CheckCanSendGift extends Api.Request<{
//     gift_id: bigint;
// }, CheckCanSendGiftResult> {
//     static CONSTRUCTOR_ID = 0xc0c4edc9;
//     static SUBCLASS_OF_ID = 0x5d20f1a2;
//     className = "payments.CheckCanSendGift";
//     constructor(public gift_id: bigint) {
//         super({gift_id});
//         this.gift_id = gift_id;
//     }

//     serializeBody(writer: any) {
//         console.log("[DEBUG] serializeBody called, giftId =", String(this.gift_id));
//         writer.writeLong(this.gift_id);
//     }

//     deserializeResponse(reader: any) {
//         console.log("[DEBUG] deserializeResponse called");
//         return reader.readObject();
//     }
// }

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

// export async function checkCanSendGift(giftId: number | string | bigint): Promise<any> {
//     const id = typeof giftId === "bigint" ? giftId : BigInt(giftId);
//     const req = new CheckCanSendGift(id);
//     return await client.invoke(req as any);
// }
let cachedInputPeer: any | null = null;

export async function getStars(): Promise<any> {
    try {
        return await client.invoke(new Api.payments.GetStarsStatus({}));
    } catch (err) {
        try {
            if (!cachedInputPeer) {
                const me = await client.getMe().catch(() => null);
                if (!me) throw new Error("client not authorized (getMe returned null)");
                cachedInputPeer = await client.getInputEntity(me);
            }
            return await client.invoke(new Api.payments.GetStarsStatus({ peer: cachedInputPeer }));
        } catch (err2) {
            console.error("[getStars] both direct and fallback calls failed:", err, err2);
            return null;
        }
    }
    
}

//==================================================== ОПЛАТА ПОДАРКА ====================================================

export async function payStarGift(
    giftId: bigint,
    peer: Api.TypeInputPeer,
    message?: string,
    hideName = true,
    includeUpgrade = false
): Promise<any> {
    const invoiceParams: any = {
        giftId: bigInt(giftId.toString()),
        peer: peer,
        hideName,
        includeUpgrade,
        ...(message ? { message: new Api.TextWithEntities({ text: message, entities: [] }) } : {}),
    };

    const invoice = new Api.InputInvoiceStarGift(invoiceParams);

    const paymentForm = await client.invoke(
        new Api.payments.GetPaymentForm({ invoice })
    );

    //Отправляем PaymentForm, чтобы списать звёзды и завершить покупку
    const result = await client.invoke(
        new Api.payments.SendStarsForm({
            formId: paymentForm.formId,
            invoice: invoice,
        })
    );

    return result;
    //return paymentForm;
}