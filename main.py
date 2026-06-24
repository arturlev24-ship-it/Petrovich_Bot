"""
Палыч - весёлый чат-бот
Версия: 15.0 - Выбор из реальных участников
"""

import asyncio
import random
import logging
import re
import os
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated, ChatPermissions
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

# НАСТРОЙКИ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_FILE = "palych_data.json"

# ИНИЦИАЛИЗАЦИЯ
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

stats = {
    "messages_answered": 0,
    "users": {},
    "chats": []
}

welcome_settings = {}
goodbye_settings = {}
muted_users = {}
last_complaint_time = {}

# ФУНКЦИИ ДАННЫХ
def load_data():
    global stats, welcome_settings, goodbye_settings, muted_users, last_complaint_time
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                stats = data.get("stats", stats)
                welcome_settings = data.get("welcome_settings", {})
                goodbye_settings = data.get("goodbye_settings", {})
                muted_users_raw = data.get("muted_users", {})
                muted_users = {int(k): datetime.fromisoformat(v) for k, v in muted_users_raw.items()}
                complaint_raw = data.get("last_complaint_time", {})
                last_complaint_time = {int(k): datetime.fromisoformat(v) for k, v in complaint_raw.items()}
            logger.info("✅ Данные загружены")
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")

def save_data():
    try:
        muted_save = {str(k): v.isoformat() for k, v in muted_users.items()}
        complaint_save = {str(k): v.isoformat() for k, v in last_complaint_time.items()}
        data = {
            "stats": stats,
            "welcome_settings": welcome_settings,
            "goodbye_settings": goodbye_settings,
            "muted_users": muted_save,
            "last_complaint_time": complaint_save
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

async def auto_save():
    while True:
        await asyncio.sleep(300)
        save_data()

async def safe_send(msg: Message, text: str, **kwargs):
    try:
        await bot.send_chat_action(chat_id=msg.chat.id, action="typing")
        await asyncio.sleep(1.5)
        await msg.answer(text, **kwargs)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        await msg.answer(text, **kwargs)
    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки: {e}")

# ФУНКЦИИ МУТА
async def mute_user(chat_id: int, user_id: int, minutes: int = 2):
    try:
        until_time = datetime.now() + timedelta(minutes=minutes)
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        await bot.restrict_chat_member(chat_id, user_id, permissions, until_date=until_time)
        muted_users[user_id] = until_time
        save_data()
        return True
    except Exception as e:
        logger.error(f"Ошибка мута: {e}")
        return False

async def check_mutes():
    while True:
        await asyncio.sleep(30)
        now = datetime.now()
        to_unmute = []
        for user_id, until_time in list(muted_users.items()):
            if now >= until_time:
                to_unmute.append(user_id)
        for user_id in to_unmute:
            muted_users.pop(user_id, None)
            logger.info(f"🔊 Пользователь {user_id} размучен")
        if to_unmute:
            save_data()

# ПРИВЕТСТВИЕ И ПРОЩАНИЕ
@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    chat_id = event.chat.id
    user = event.new_chat_member.user
    username = user.username or user.first_name
    cid = str(chat_id)
    if cid not in stats["chats"]:
        stats["chats"].append(cid)
        save_data()
    if user.id == bot.id:
        await bot.send_message(chat_id,
            "🎉 <b>Палыч в чате!</b>\n\n"
            "Теперь этот чат оживёт!\n"
            "Пишите слова — я буду отвечать!\n"
            "Команды: /help"
        )
        return
    welcome_text = welcome_settings.get(cid)
    if welcome_text:
        text = welcome_text.replace('{username}', f'@{username}' if user.username else username)
    else:
        w = [
            f"Опа, {username}! Заходи! 🎉",
            f"{username} ворвался в чат! 🍪",
            f"Смотрите-ка, {username} пришёл! ✨",
            f"{username} на радарах! 🚨",
            f"Ну привет, {username}! ☕",
            f"Бам! {username} телепортировался! 🌀",
            f"Ого, {username}! А мы тебя ждали! 🤗",
            f"Салют, {username}! 🏠"
        ]
        text = random.choice(w)
    await bot.send_message(chat_id, text)

@dp.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_user_leave(event: ChatMemberUpdated):
    chat_id = event.chat.id
    user = event.old_chat_member.user
    if user.id == bot.id:
        return
    username = user.username or user.first_name
    cid = str(chat_id)
    goodbye_text = goodbye_settings.get(cid)
    if goodbye_text:
        text = goodbye_text.replace('{username}', f'@{username}' if user.username else username)
    else:
        f_list = [
            f"Эх, {username} ушёл... 😢",
            f"{username} покинул чат... 🦜",
            f"Прощай, {username}! 👋",
            f"{username} слился... 😔",
            f"Пока, {username}! 🚪"
        ]
        text = random.choice(f_list)
    await bot.send_message(chat_id, text)

# ТРИГГЕРЫ
words = {
    r"привет|здравствуй|здаров|хелло|хай|салют|ку\b": [
        "О, здарова! Как жизнь? 😊",
        "Привет-привет! ✨",
        "Хеллоу! Как сам? 👋",
        "Салют! Что нового? 🎉",
        "Ку-ку! Я Палыч! 🤝"
    ],
    r"пока|прощай|бай|гудбай|чао": [
        "Куда?! Только разговорились! 😢",
        "Пока-пока! 👋",
        "До скорого! 🍩",
        "Эх, уходишь... 🎭"
    ],
    r"как дела|как сам|как жизнь|как ты": [
        "Да нормально! А у тебя? 🤔",
        "Отлично! А ты как? 😊",
        "Лучше всех! 💪",
        "Нормально! 📱"
    ],
    r"еда|кушать|голод|пицц|бургер|суши|шаурм": [
        "Ммм, еда! Что любишь? 🍕",
        "Не напоминай! 🤤",
        "Я уже тут! 🍴",
        "Обожаю вкусняшки! 🧑‍🍳"
    ],
    r"работа|учёба|дедлайн|начальник|офис|зарплат": [
        "Работа не волк! 😄",
        "Дедлайны горят? 📅",
        "Понедельник? Держись! 📆",
        "Начальник злой? 🍪"
    ],
    r"погода|дождь|снег|холод|жара|солнц|гроз": [
        "Дождь? Плед и какао! ☕",
        "Снег идёт! ⛄",
        "Холодно? 🫂",
        "Жара! 🥵"
    ],
    r"кот|кошк|собак|пёс|хомяк|попугай": [
        "Котики правят миром! 🐱",
        "Собака — друг! 🐕",
        "Щеночки! 🐶",
        "Хомячки! 🐹"
    ],
    r"комп|ноут|вайфай|телефон|смартфон|гаджет": [
        "Комп глючит? 💻",
        "Вайфай упал! 📡",
        "Телефон разрядился? 😱",
        "Люблю гаджеты! ⚙️"
    ],
    r"игр|гейм|дота|кс\b|майнкрафт|гта|стрим": [
        "Геймер! Что проходишь? 🎮",
        "Дота? 🎯",
        "Майнкрафт! ⛏️",
        "ГТА? 🚗"
    ],
    r"музык|песн|трек|рок|рэп|джаз|концерт": [
        "Музыка! Что слушаешь? 🎵",
        "Что в наушниках? 🎧",
        "Рок — навсегда! 🤘",
        "Концерт? 🎸"
    ],
    r"фильм|сериал|кино|нетфликс|аниме": [
        "Что смотришь? 🎬",
        "Нетфликс? 🍿",
        "Аниме? 🎌",
        "Сериал до утра? 😴"
    ],
    r"спорт|футбол|качалк|фитнес|йог|бег": [
        "Спорт — жизнь! 💪",
        "Футбол? ⚽",
        "Качалка? 🏋️",
        "Бег по утрам? 🏃"
    ],
    r"мем|рофл|лол|кек|кринж|вайб|пранк": [
        "Мемас! 😂",
        "ЛОЛ! 🤣",
        "Рофл! 💾",
        "Вайб! ✌️"
    ],
    r"любовь|отношен|свидан|поцелуй|обнима": [
        "Любовь! 💕",
        "Отношения? 💑",
        "Свидание? 👔",
        "Обнимашки! 🫂"
    ],
    r"спать|сон|кровать|подушк|бессонниц": [
        "Спать? 😴",
        "Кроватка... 🛏️",
        "Бессонница? 🐑",
        "Выспаться! 🎨"
    ],
    r"чай|кофе|пиво|вино|коктейл|смузи": [
        "Чаёк? ☕",
        "Кофе — топливо! ☕",
        "Пивко? 🍺",
        "Вино? 🍷"
    ],
    r"праздник|день рожден|новый год|пасх": [
        "С праздником! 🎉",
        "День рождения? 🎂",
        "Новый год! 🎄",
        "Праздник! 🎈"
    ],
    r"путешеств|отпуск|море|горы|билет|отель": [
        "Путешествия! ✈️",
        "Море зовёт! 🌊",
        "Горы! 🏔️",
        "Отпуск! 🧳"
    ],
    r"что делаешь|чем занят|что творишь|что случилось|что стряслось": [
        "Да так, сижу в интернете, чат оживляю! А ты? 💻",
        "Общаюсь с тобой! Это моё любимое занятие! 😊",
        "Да вот, мемасы смотрю 😂 А ты что делаешь? 📱",
        "Работаю над собой! Прокачиваю скиллы! 💪",
        "Развлекаю народ! Это моя миссия! 🎭"
    ],
    r"пошёл нахуй|иди нахуй|пошел нахуй|заткнись|завали|отъебись|отвали|съеби": [
        "Сам иди нахуй, козёл! 🖕",
        "Рот закрой, животное! 😤",
        "Ты на кого бочку катишь? 🤬",
        "Слышь, рамсы попутал? 😡",
        "Чё развыступался? 🌲",
        "Ты походу берега попутал! 💀"
    ],
    r"блять|сука|хуй|пизда|пиздец|нахуй|ебать|заебал|хуйня": [
        "Ого, эмоции! Что случилось? 🤬",
        "Выпускай пар! 😤",
        "Что разозлило? 🔥",
        "Бывает! Рассказывай! 😅"
    ],
    r"кто самый|кто тут самый|назови самого": [
        "🤔 Хмм... Мне кажется это @{username}! 😏",
        "🔮 Я вижу ауру... Это @{username}! 😂",
        "📊 По моим подсчётам — @{username}! 💀",
        "🎯 Мой рандомайзер показал на @{username}! 🤷‍♂️"
    ],
}

# КОМАНДЫ
@dp.message(Command("start"))
async def cmd_start(msg: Message):
    if msg.chat.type == ChatType.PRIVATE:
        me = await bot.me()
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🚀 Добавить Палыча в чат",
                url=f"https://t.me/{me.username}?startgroup=true"
            )
        ]])
        await safe_send(msg,
            "🎉 <b>Привет! Я Палыч!</b>\n\n"
            "Оживляю чаты, отвечаю на 100+ слов!\n"
            "Со мной не скучно! 🔥\n\n"
            "👇 Жми кнопку:",
            reply_markup=kb
        )
    else:
        await safe_send(msg, "🎉 <b>Палыч на связи!</b>\nКоманды: /help")

@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await safe_send(msg,
        "🤖 <b>Палыч — оживитель чатов!</b>\n\n"
        "/start — перезапуск\n"
        "/help — справка\n"
        "/top — топ-10 болтливых\n"
        "/stats — статистика\n\n"
        "💢 <b>Жалоба:</b> ответь на сообщение + 'меня обидел'\n"
        "🎯 <b>Спроси:</b> 'кто самый тупой?' — я выберу!\n\n"
        "Пиши: привет, еда, погода, игры, музыка..."
    )

@dp.message(Command("top"))
async def cmd_top(msg: Message):
    u = stats.get("users", {})
    if not u:
        await safe_send(msg, "📊 Пока никого нет!")
        return
    top = sorted(u.items(), key=lambda x: x[1]["messages"], reverse=True)[:10]
    text = "🏆 <b>ТОП-10:</b>\n\n"
    medals = ["🥇","🥈","🥉"] + [f"{i}️⃣" for i in range(4,11)]
    for i, (uid, info) in enumerate(top):
        name = info.get("username", f"ID{uid}")
        text += f"{medals[i]} {name}: <b>{info['messages']}</b>\n"
    await safe_send(msg, text)

@dp.message(Command("stats"))
async def cmd_stats(msg: Message):
    await safe_send(msg,
        "📊 <b>СТАТИСТИКА:</b>\n\n"
        f"👥 Пользователей: <b>{len(stats.get('users', {}))}</b>\n"
        f"💬 Ответов: <b>{stats.get('messages_answered', 0)}</b>\n"
        f"📁 Чатов: <b>{len(stats.get('chats', []))}</b>\n"
        f"🔇 В муте: <b>{len(muted_users)}</b>"
    )

# ОСНОВНОЙ ОБРАБОТЧИК
@dp.message(F.text)
async def handle_all_text(msg: Message):
    if msg.from_user.is_bot or not msg.text:
        return
    if msg.text.startswith('/'):
        return

    text = msg.text.lower().strip()

    # ЖАЛОБА ЧЕРЕЗ REPLY
    if msg.reply_to_message and re.search(r"(меня\s+обидел|обидел\s+меня|жалоба|накажи)", text):
        offender = msg.reply_to_message.from_user
        complainant_id = msg.from_user.id
        complainant_name = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name
        offender_name = f"@{offender.username}" if offender.username else offender.first_name

        if offender.id == complainant_id:
            await msg.reply("🤔 Нельзя жаловаться на себя!")
            return
        if offender.is_bot:
            await msg.reply("🤖 Нельзя жаловаться на ботов!")
            return

        now = datetime.now()
        if complainant_id in last_complaint_time:
            diff = now - last_complaint_time[complainant_id]
            if diff < timedelta(minutes=10):
                remaining = timedelta(minutes=10) - diff
                mins = remaining.seconds // 60
                secs = remaining.seconds % 60
                await msg.reply(f"⏳ Жалоба через: <b>{mins} мин {secs} сек</b>")
                return

        success = await mute_user(msg.chat.id, offender.id, 2)
        if success:
            last_complaint_time[complainant_id] = now
            save_data()
            await msg.reply(
                f"📢 <b>ЖАЛОБА!</b>\n\n"
                f"👊 Обидчик: {offender_name}\n"
                f"💀 Я уебал {offender_name}!\n"
                f"🔇 Мут на <b>2 минуты</b>!\n\n"
                f"⏰ Следующая жалоба через <b>10 мин</b>"
            )
        else:
            await msg.reply("❌ Не удалось! Проверь права бота!")
        return

    # СТАТИСТИКА
    cid = str(msg.chat.id)
    uid = str(msg.from_user.id)
    uname = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name

    if cid not in stats["chats"]:
        stats["chats"].append(cid)
    if uid not in stats["users"]:
        stats["users"][uid] = {"username": uname, "messages": 0}
    else:
        stats["users"][uid]["username"] = uname
    stats["users"][uid]["messages"] += 1

    # ТРИГГЕРЫ
    for pattern, responses in words.items():
        if re.search(pattern, text):
            response = random.choice(responses)

            # Замена {username} на СЛУЧАЙНОГО из ВСЕХ участников
            if "{username}" in response:
                try:
                    all_members = []

                    # Получаем администраторов
                    try:
                        admins = await bot.get_chat_administrators(msg.chat.id)
                        for admin in admins:
                            if not admin.user.is_bot:
                                name = f"@{admin.user.username}" if admin.user.username else admin.user.first_name
                                all_members.append(name)
                    except:
                        pass

                    # Добавляем участников из статистики
                    for uid_str, info in stats.get("users", {}).items():
                        name = info.get("username", f"ID{uid_str}")
                        if name not in all_members and not name.startswith("ID"):
                            all_members.append(name)

                    # Пытаемся получить количество участников
                    try:
                        member_count = await bot.get_chat_member_count(msg.chat.id)
                        # Если участников больше чем у нас в списке
                        if member_count > len(all_members):
                            # Добавляем ещё раз всех админов для разнообразия
                            for admin in admins:
                                if not admin.user.is_bot:
                                    name = f"@{admin.user.username}" if admin.user.username else admin.user.first_name
                                    if name not in all_members:
                                        all_members.append(name)
                    except:
                        pass

                    if all_members:
                        response = response.replace("{username}", random.choice(all_members))
                    else:
                        response = response.replace("{username}", "кто-то из чата")
                except:
                    response = response.replace("{username}", "кто-то из чата")

            await safe_send(msg, response)
            stats["messages_answered"] += 1
            save_data()
            return

    # РАНДОМ
    if random.random() < 0.15:
        reactions = [
            "🤔 Интересно! Расскажи подробнее!",
            "Ого! И что дальше?",
            "Хмм, любопытно!",
            "Серьёзно? Вот это поворот!",
            "Да ладно! Объясни!",
            "🔥 Вот это тема!"
        ]
        await safe_send(msg, random.choice(reactions))
        stats["messages_answered"] += 1

    save_data()

# ЗАГЛУШКА
@dp.message()
async def catch_all(msg: Message):
    pass

# ЗАПУСК
async def main():
    load_data()
    asyncio.create_task(auto_save())
    asyncio.create_task(check_mutes())
    logger.info("🤖 Палыч запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "chat_member"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")