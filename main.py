import logging
import os
import sys

from aiogram import Bot, Dispatcher, types, Router
import requests
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import yt_dlp

# TOKEN = getenv("BOT_TOKEN")
TOKEN = "CHANGEME"

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 8080

WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = "CHANGEME"
BASE_WEBHOOK_URL = "CHANGEME"

# GPT API
GPT_BASE_URL = "https://chatgpt-42.p.rapidapi.com/conversationgpt4"
GPT_KEY = "CHANGEME"
GPT_HOST = "CHANGEME"

# YOUTUBE API
YOUTUBE_BASE_URL = "https://youtube138.p.rapidapi.com/search/"
YOUTUBE_KEY = "CHANGEME"
YOUTUBE_HOST = "CHANGEME"

logging.basicConfig(level=logging.INFO)
router = Router()

bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
dp.include_router(router)
dp['bot'] = bot


def find_music(text):
    payload = {
        "system_prompt": "You must write a random popular song title and artist that matches my request and is available on YouTube. You must write only the name of the song and the artist in the format Title - Artist, without any explanation or additional sentences, this is very important!",
        "temperature": 0.9, "top_k": 5, "top_p": 0.9, "max_tokens": 64, "web_access": True, "messages": [
            {
                "role": "user",
                "content": text
            }
        ]}
    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": GPT_KEY,
        "X-RapidAPI-Host": GPT_HOST
    }
    response = requests.post(GPT_BASE_URL, json=payload, headers=headers)

    json_response = response.json()

    if response.status_code != 200:
        return None

    return json_response.get("result")


def find_youtube_link(song):
    querystring = {"q": song}
    headers = {
        "X-RapidAPI-Key": YOUTUBE_KEY,
        "X-RapidAPI-Host": YOUTUBE_HOST
    }

    response = requests.get(YOUTUBE_BASE_URL, headers=headers, params=querystring)

    if response.status_code != 200:
        return None

    content = response.json()
    videos = content.get("contents")
    if videos is None or len(videos) == 0:
        return None

    videoID = ""
    for video in videos:
        if video["video"]["lengthSeconds"] < 600:
            videoID = video["video"]["videoId"]
            break

    if videoID == "":
        return None

    url = "https://www.youtube.com/watch?v="
    return url + videoID


def download_youtube_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info_dict)
        filename = os.path.splitext(path)[0] + '.mp3'
        return filename


@router.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.reply("Привіт!\nОпиши, яку музику хочеш послухати зараз!")


@router.message()
async def echo(message: types.Message):
    await message.reply("Відбувається пошук музики...")
    text = message.text
    try:
        music = find_music(text)
        if music is None:
            await message.reply("Я не зміг нічого знайти, спробуй інший запит")
            return

        youtube_link = find_youtube_link(music)
        file_path = download_youtube_audio(youtube_link)

        await bot.send_audio(message.chat.id, audio=types.FSInputFile(path=file_path))
        os.remove(file_path)
    except Exception as e:
        print(e)
        await bot.send_message(message.chat.id, "Виникла помилка, спробуйте пізніше")


async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}", secret_token=WEBHOOK_SECRET)


def main() -> None:
    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    main()
