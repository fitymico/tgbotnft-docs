from telethon import TelegramClient

api_id = 37178559
api_hash = 'ac248466661ba17e936335d08f6eb26d'

client = TelegramClient('nft_session', api_id, api_hash)

async def main():

    # You can send messages to yourself...
    await client.send_message('me', 'Hello, myself!')

    # Or send files, songs, documents, albums...
    #await client.send_file('me', '/home/me/Pictures/holidays.jpg')


with client:
    client.loop.run_until_complete(main())