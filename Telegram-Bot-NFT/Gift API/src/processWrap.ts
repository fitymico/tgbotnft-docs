import { Api } from "telegram";
import { client } from "./mtprotoClient";
import bigInt from "big-integer";

export class CheckCanSendGift {
    CONSTRUCTOR_ID = 0xc0c4edc9;
    constructor(public gift_id: bigint) {}

    serializeBody(writer: any) {
        console.log("[DEBUG] serializeBody called, gift_id =", String(this.gift_id));
        writer.writeLong(this.gift_id);
    }

    deserializeResponse(reader: any) {
        console.log("[DEBUG] deserializeResponse called");
        return reader.readObject();
    }
}

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

export async function checkCanSendGift(giftId: number | string | bigint): Promise<any> {
    const id = typeof giftId === "bigint" ? giftId : BigInt(giftId);
    const req = new CheckCanSendGift(id);
    return await client.invoke(req as any);
}

//==================================================== ОПЛАТА ПОДАРКА ====================================================

export async function payStarGift(
    giftId: bigint,
    peer: Api.TypeInputPeer,
    message?: string,
    hideName = false,
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
        new Api.payments.SendPaymentForm({
            formId: paymentForm.formId,
            invoice: invoice,
            credentials: new Api.InputPaymentCredentialsSaved({
                id: "", // пусто, потому что мы используем Telegram Stars
                tmpPassword: Buffer.alloc(0),
            }),
        })
    );

    return result;
}