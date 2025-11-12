import asyncio
from telethon import TelegramClient

api_id = 37178559
api_hash = 'ac248466661ba17e936335d08f6eb26d'

client = TelegramClient('nft_session', api_id, api_hash)

async def main():

    # You can send messages to yourself...
    await client.send_message('me', '✅ Telethon бот запущен и работает!')

    while True:
        try:
            await client.send_message('me', '⏰ Бот всё ещё активен...')
        except Exception as e:
            print(f"Ошибка при отправке: {e}")

        await asyncio.sleep(20)


with client:
    client.loop.run_until_complete(main())