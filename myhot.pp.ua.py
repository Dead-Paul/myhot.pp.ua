from configparser import ConfigParser
from telebot import TeleBot, types
from typing import TypedDict
from flask import Flask, request
import threading
import json
import io

config = ConfigParser()
config.read("settings.ini")

TOKEN: str = config["Bot"]["token"]
ADMIN_ID: int = int(config["Bot"]["admin_id"])
bot = TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start_handler(message: types.Message):
    strt_msg = bot.send_message(message.chat.id, "Hi, send me JSON file and I will create request to add it to the anime library! (*^_^*)")
    with open("anime_example.json", "rb") as example_file:
        bot.send_document(message.chat.id, example_file, caption="Example of an anime JSON file", reply_to_message_id=strt_msg.message_id)


class AnimeDict(TypedDict):
    title: str
    note: str | None

def insert_anime(anime: AnimeDict) -> tuple[bool, str]:
    try:
        # here must be code to add to database
        """
            INSERT INTO anime VALUES(?, ?, ?)
        """
        return True, f"Successfully added {anime['title']}! 💮"
    except Exception as e:
        return False, f"An error occurred on adding {anime['title']}: \"{e.args[0]}\"... 🔁"

@bot.callback_query_handler(lambda callback: isinstance(callback.data, str))
def parse_callback(callback: types.CallbackQuery):
    assert isinstance(callback.data, str)
    file_path, user_id, is_approved = callback.data.split(':', 2)
    anime: AnimeDict = json.loads(bot.download_file(file_path))
    inline_keyboard = types.InlineKeyboardMarkup()

    if is_approved == "True":
        is_inserted, message = insert_anime(anime)
        inline_keyboard.add(types.InlineKeyboardButton(message, url="https://www.myhot.pp.ua/anime") if is_inserted 
                            else types.InlineKeyboardButton(message, callback_data=callback.data))
        if str.isdigit(user_id):
            bot.send_message(user_id, f"Approved request to add \"{anime['title']}\"!")
    else:
        inline_keyboard.add(types.InlineKeyboardButton("Disapproved 🈲", url="https://www.myhot.pp.ua/hentai"))
        if str.isdigit(user_id):
            bot.send_message(user_id, f"Disapproved request to add \"{anime['title']}\"...")
    try:
        bot.edit_message_reply_markup(ADMIN_ID, callback.message.message_id, reply_markup=inline_keyboard)
    except Exception as e:
        print("Looks like we have multiple errors in DB and retrying doesn't help...")


def send_to_aprove(anime_json: str|list[AnimeDict], user_name: str|None, user_id: int|None = None) -> None:
    if isinstance(anime_json, str):
        anime_json = json.loads(bot.download_file(anime_json))["AnimeInfo"]
    assert isinstance(anime_json, list)
    for anime in anime_json:
        archive_message: types.Message = bot.send_document(ADMIN_ID, types.InputFile(io.BytesIO(json.dumps(anime).encode()),
                                                           f"{anime['title']}.json"), disable_notification=True)
        assert isinstance(archive_message.document, types.Document)
        pending_file_path: str|None = bot.get_file(archive_message.document.file_id).file_path
        inline_keyboard = types.InlineKeyboardMarkup()
        inline_keyboard.add(
            types.InlineKeyboardButton("Approve ⭕️", callback_data=f"{pending_file_path}:{user_id}:True"),
            types.InlineKeyboardButton("Disapprove ❌", callback_data=f"{pending_file_path}:{user_id}:False")
        )
        bot.send_message(ADMIN_ID, f"{user_name if user_name is not None else 'Someone'} requests to add \"{anime['title']}\" to the DB!", 
                         reply_markup=inline_keyboard, reply_to_message_id=archive_message.message_id)

@bot.message_handler(content_types=["document"])
def document_handler(message: types.Message) -> None:
    assert isinstance(message.document, types.Document)
    file: types.Document = message.document

    if file.mime_type == "application/json" and (file_path := bot.get_file(file.file_id).file_path) is not None:
        assert isinstance(message.from_user, types.User)
        send_to_aprove(file_path, message.from_user.username, message.chat.id)
    else:
        bot.send_message(message.chat.id, "I can handle JSON files ONLY!")

app = Flask(__name__)

@app.route("/add-anime", methods=["POST"])
def add_anime_handler():
    assert request.json is not None
    anime_json: list[AnimeDict] = request.get_json()["AnimeInfo"]
    send_to_aprove(anime_json, request.get_json().get("user-name"))
    return "Waiting for approval...", 200

threading.Thread(target=lambda: bot.polling(none_stop = True)).start()
app.run()