from telethon import TelegramClient

api_id = 37178559
api_hash = 'ac248466661ba17e936335d08f6eb26d'

with TelegramClient('nft_session', api_id, api_hash) as client:
    print("Logged in as:", client.get_me().username)