"""
Палыч - весёлый чат-бот
Версия: 5.0 - Финальная
"""

import asyncio
import random
import logging
import re
import os
import json
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

# Настройки
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден!")
    exit(1)

DATA_FILE = "palych_data.json"

# Инициализация
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

stats = {
    "messages_answered": 0,
    "users": {},
    "chats": []
}

welcome_settings = {}  # {chat_id: welcome_message}
goodbye_settings = {}  # {chat_id: goodbye_message}

def load_data():
    global stats, welcome_settings, goodbye_settings
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                stats = data.get("stats", stats)
                welcome_settings = data.get("welcome_settings", {})
                goodbye_settings = data.get("goodbye_settings", {})
            logger.info("✅ Данные загружены")
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")

def save_data():
    try:
        data = {
            "stats": stats,
            "welcome_settings": welcome_settings,
            "goodbye_settings": goodbye_settings
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
        await msg.answer(text, **kwargs)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        await msg.answer(text, **kwargs)
    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки: {e}")

async def is_admin(chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# ============================================
# ПРИВЕТСТВИЕ И ПРОЩАНИЕ (как в первом боте)
# ============================================

@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    """Приветствие нового участника"""
    chat_id = event.chat.id
    user = event.new_chat_member.user
    username = user.username or user.first_name
    
    logger.info(f"🔔 НОВЫЙ УЧАСТНИК в чате {chat_id}: {username}")
    
    # Сохраняем чат
    cid = str(chat_id)
    if cid not in stats["chats"]:
        stats["chats"].append(cid)
        save_data()
    
    # Если зашёл сам бот
    if user.id == bot.id:
        await bot.send_message(chat_id,
            "🎉 <b>Палыч в чате!</b>\n\n"
            "Теперь этот чат оживёт!\n"
            "Пишите слова — я буду отвечать!\n"
            "Команды: /help"
        )
        return
    
    # Проверяем кастомное приветствие
    welcome_text = welcome_settings.get(cid)
    if welcome_text:
        text = welcome_text.replace('{username}', f'@{username}' if user.username else username)
    else:
        w = [
            f"Опа, {username}! Заходи, не стесняйся! 🎉",
            f"{username} ворвался в чат! Прячьте печеньки! 🍪",
            f"Смотрите-ка, {username} пришёл! Чат оживает! ✨",
            f"{username} на радарах! Всем построиться! 🚨",
            f"Ну привет, {username}! Рассказывай, как жизнь? ☕",
            f"Бам! {username} телепортировался в чат! 🌀",
            f"Ого, {username}! А мы тебя ждали! 🤗",
            f"Салют, {username}! Чувствуй себя как дома! 🏠"
        ]
        text = random.choice(w)
    
    await bot.send_message(chat_id, text)

@dp.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_user_leave(event: ChatMemberUpdated):
    """Прощание с ушедшим участником"""
    chat_id = event.chat.id
    user = event.old_chat_member.user
    
    logger.info(f"🚪 УШЁЛ УЧАСТНИК из чата {chat_id}: {user.username or user.first_name}")
    
    if user.id == bot.id:
        return
    
    username = user.username or user.first_name
    cid = str(chat_id)
    
    goodbye_text = goodbye_settings.get(cid)
    if goodbye_text:
        text = goodbye_text.replace('{username}', f'@{username}' if user.username else username)
    else:
        f = [
            f"Эх, {username} ушёл... Вернись, я всё прощу! 😢",
            f"{username} покинул чат... Свободу попугаям! 🦜",
            f"Прощай, {username}! Без тебя будет скучно... 👋",
            f"{username} слился... Чат понёс невосполнимую потерю! 😔",
            f"Пока, {username}! Заходи если что! Двери открыты! 🚪"
        ]
        text = random.choice(f)
    
    await bot.send_message(chat_id, text)

# ============================================
# ТРИГГЕРЫ
# ============================================

words = {
    r"привет|здравствуй|здаров|хелло|хай|салют|ку\b": [
        "О, здарова! Как жизнь? Рассказывай! 😊",
        "Привет-привет! Ты сегодня прям светишься! ✨",
        "Хеллоу! Давно не виделись! Как сам? 👋",
        "Салют! Что нового? Выкладывай! 🎉",
        "Ку-ку! Я Палыч, будем знакомы! 🤝"
    ],
    r"пока|прощай|бай|гудбай|чао": [
        "Куда?! Мы же только разговорились! 😢",
        "Пока-пока! Не пропадай надолго! 👋",
        "До скорого! Приходи с новостями! 🍩",
        "Эх, уходишь... А кто меня слушать будет? 🎭"
    ],
    r"как дела|как сам|как жизнь|как ты": [
        "Да нормально! А у тебя как? 🤔",
        "Отлично! Вот с вами общаюсь! А ты как? 😊",
        "Лучше всех! Рассказывай, как ты? 💪",
        "Нормально! Мемасы смотрю. А ты? 📱"
    ],
    r"еда|кушать|голод|пицц|бургер|суши|шаурм": [
        "Ммм, еда! Что ты любишь? 🍕",
        "Ой, не напоминай! Слюнки текут! 🤤",
        "Кто сказал «еда»? Я уже тут! 🍴",
        "Обожаю вкусняшки! Ты умеешь готовить? 🧑‍🍳"
    ],
    r"работа|учёба|дедлайн|начальник|офис|зарплат": [
        "Работа не волк! А ты чем занимаешься? 😄",
        "Дедлайны — это адреналин! Горят сроки? 📅",
        "Понедельник? Держись! Пятница близко! 📆",
        "Начальник злой? Подари печеньку! 🍪"
    ],
    r"погода|дождь|снег|холод|жара|солнц|гроз": [
        "Дождь? Самое время для пледа и какао! ☕",
        "Снег идёт! Бежим лепить снеговика! ⛄",
        "Холодно? Грейся обнимашками! 🫂",
        "Жара! Кондиционер — лучший друг! 🥵"
    ],
    r"кот|кошк|собак|пёс|хомяк|попугай": [
        "Котики правят миром! У тебя есть кот? 🐱",
        "Собака — друг человека! Какая порода? 🐕",
        "Щеночки! Милота зашкаливает! 🐶",
        "Хомячки такие пухленькие! 🐹"
    ],
    r"комп|ноут|вайфай|телефон|смартфон|гаджет": [
        "Комп глючит? Перезагрузка решает 90% проблем! 💻",
        "Вайфай упал — жизнь остановилась! 📡",
        "Телефон разрядился? Паника! 😱",
        "Люблю гаджеты! Что у тебя за девайс? ⚙️"
    ],
    r"игр|гейм|дота|кс\b|майнкрафт|гта|стрим": [
        "Геймер detected! Что проходишь? 🎮",
        "Дота? Это жизнь или боль? 🎯",
        "Майнкрафт! Строим империю! ⛏️",
        "ГТА? Не нарушай ПДД! 🚗"
    ],
    r"музык|песн|трек|рок|рэп|джаз|концерт": [
        "Музыка объединяет! Что слушаешь? 🎵",
        "Что в наушниках? Делись! 🎧",
        "Рок — это навсегда! Какая группа? 🤘",
        "Концерт — это энергия! Был на живых? 🎸"
    ],
    r"фильм|сериал|кино|нетфликс|аниме": [
        "Что смотришь? Нужен совет! 🎬",
        "Нетфликс и чилл? Что в топе? 🍿",
        "Анимешник? Уважаю! Какое смотришь? 🎌",
        "Сериал до 3 утра? Знакомо! 😴"
    ],
    r"спорт|футбол|качалк|фитнес|йог|бег": [
        "Спорт — это жизнь! Каким занимаешься? 💪",
        "Футбол? За кого болеешь? ⚽",
        "Качалка? Мышцы не растут без труда! 🏋️",
        "Бег по утрам? Ты герой! 🏃"
    ],
    r"мем|рофл|лол|кек|кринж|вайб|пранк": [
        "Мемас залетел в чат! Покажи! 😂",
        "ЛОЛ! Я тоже с этого мема ору! 🤣",
        "Рофл года! Часто мемасишь? 💾",
        "Вайб этого чата — лучший! ✌️"
    ],
    r"любовь|отношен|свидан|поцелуй|обнима": [
        "Любовь витает в воздухе! 💕",
        "Отношения — это работа! Как у тебя? 💑",
        "Свидание? Надень что-то красивое! 👔",
        "Обнимашки лечат стресс! 🫂"
    ],
    r"спать|сон|кровать|подушк|бессонниц": [
        "Спать? Только после дедлайна! 😴",
        "Кроватка ждёт! Мягкая подушка... 🛏️",
        "Бессонница? Считай овец! 🐑",
        "Выспаться — это искусство! 🎨"
    ],
    r"чай|кофе|пиво|вино|коктейл|смузи": [
        "Чаёк? С плюшками? Я за! ☕",
        "Кофе — топливо! Что предпочитаешь? ☕",
        "Пивко после работы? Уважаю! 🍺",
        "Вино? Красное или белое? 🍷"
    ],
    r"праздник|день рожден|новый год|пасх": [
        "С праздником! Ура! 🎉",
        "День рождения? Подарки, торт! 🎂",
        "Новый год! Ёлка, мандарины! 🎄",
        "Праздник — отличный повод! 🎈"
    ],
    r"путешеств|отпуск|море|горы|билет|отель": [
        "Путешествия расширяют кругозор! ✈️",
        "Море зовёт! Куда хочешь? 🌊",
        "Горы — это свобода! 🏔️",
        "Отпуск? Беру чемодан и лечу! 🧳"
    ],
r"\bблять\b|\bсука\b|\bхуй\b|\bпизда\b|\bпиздец\b|\bпошел нахуй\b|\bнахуй\b|\bебать\b|\bзаебал\b|\bхуйня\b": [
    "Ого, эмоции зашкаливают! Рассказывай, что случилось? 🤬",
    "Вижу, всё серьёзно! Выпускай пар, я слушаю! 😤",
    "Ох, чувствую накал! Давай обсудим, что тебя так разозлило? 🔥",
    "Ситуация — пиздец, согласен! Но мы справимся! 💪",
    "Братан, держи себя в руках! Хотя... бывает! Рассказывай! 😅",
    "Да уж, жизнь иногда подкидывает сюрпризы... Что стряслось? 🤔",
    "Слышу боль в твоих словах! Поделишься? Я тут для тебя! 🫂",
    "Эмоции — это нормально! Главное — не держи в себе! 🗣️"
]
}

# ============================================
# КОМАНДЫ
# ============================================

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
            "🎉 <b>Привет! Я Палыч — душа компании!</b>\n\n"
            "Оживляю чаты, отвечаю на 100+ слов, задаю вопросы!\n"
            "Со мной никогда не скучно! 🔥\n\n"
            "👇 Жми кнопку чтобы добавить в чат:",
            reply_markup=kb
        )
    else:
        await safe_send(msg, "🎉 <b>Палыч на связи!</b>\nПиши слова — я отвечу!\nКоманды: /help")

@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await safe_send(msg,
        "🤖 <b>Палыч — оживитель чатов!</b>\n\n"
        "/start — перезапуск\n"
        "/help — справка\n"
        "/top — топ-10 болтливых\n"
        "/stats — статистика\n"
        "/set_welcome [текст] — настроить приветствие (админ)\n"
        "/set_goodbye [текст] — настроить прощание (админ)\n"
        "/reset_welcome — сбросить приветствие (админ)\n"
        "/reset_goodbye — сбросить прощание (админ)\n\n"
        "Пиши: привет, еда, погода, игры, музыка..."
    )

@dp.message(Command("top"))
async def cmd_top(msg: Message):
    u = stats.get("users", {})
    if not u:
        await safe_send(msg, "📊 Пока никто не общался!")
        return
    
    top = sorted(u.items(), key=lambda x: x[1]["messages"], reverse=True)[:10]
    text = "🏆 <b>ТОП-10 БОЛТЛИВЫХ:</b>\n\n"
    medals = ["🥇","🥈","🥉"] + [f"{i}️⃣" for i in range(4,11)]
    
    for i, (uid, info) in enumerate(top):
        name = info.get("username", f"ID{uid}")
        text += f"{medals[i]} {name}: <b>{info['messages']}</b> сообщ.\n"
    
    await safe_send(msg, text)

@dp.message(Command("stats"))
async def cmd_stats(msg: Message):
    await safe_send(msg,
        "📊 <b>СТАТИСТИКА ПАЛЫЧА:</b>\n\n"
        f"👥 Пользователей: <b>{len(stats.get('users', {}))}</b>\n"
        f"💬 Ответов: <b>{stats.get('messages_answered', 0)}</b>\n"
        f"📁 Чатов: <b>{len(stats.get('chats', []))}</b>\n\n"
        "🤖 Палыч работает!"
    )

# Команды настройки приветствий
@dp.message(Command("set_welcome"))
async def cmd_set_welcome(msg: Message):
    if msg.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_admin(msg.chat.id, msg.from_user.id):
        await safe_send(msg, "❌ Только администраторы могут настраивать приветствия!")
        return
    
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await safe_send(msg, "📝 Использование: /set_welcome [текст]\nИспользуй {username} для имени")
        return
    
    cid = str(msg.chat.id)
    welcome_settings[cid] = parts[1]
    save_data()
    await safe_send(msg, f"✅ Приветствие установлено!\nПревью: {parts[1].replace('{username}', f'@{msg.from_user.username or msg.from_user.first_name}')}")

@dp.message(Command("set_goodbye"))
async def cmd_set_goodbye(msg: Message):
    if msg.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_admin(msg.chat.id, msg.from_user.id):
        await safe_send(msg, "❌ Только администраторы могут настраивать прощания!")
        return
    
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await safe_send(msg, "📝 Использование: /set_goodbye [текст]\nИспользуй {username} для имени")
        return
    
    cid = str(msg.chat.id)
    goodbye_settings[cid] = parts[1]
    save_data()
    await safe_send(msg, f"✅ Прощание установлено!\nПревью: {parts[1].replace('{username}', f'@{msg.from_user.username or msg.from_user.first_name}')}")

@dp.message(Command("reset_welcome"))
async def cmd_reset_welcome(msg: Message):
    if msg.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return
    
    cid = str(msg.chat.id)
    welcome_settings.pop(cid, None)
    save_data()
    await safe_send(msg, "✅ Приветствие сброшено до стандартного!")

@dp.message(Command("reset_goodbye"))
async def cmd_reset_goodbye(msg: Message):
    if msg.chat.type not in ['group', 'supergroup']:
        return
    
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return
    
    cid = str(msg.chat.id)
    goodbye_settings.pop(cid, None)
    save_data()
    await safe_send(msg, "✅ Прощание сброшено до стандартного!")

# ============================================
# ОСНОВНОЙ ОБРАБОТЧИК
# ============================================

@dp.message(F.text)
async def handle_text(msg: Message):
    """Обработка текстовых сообщений"""
    if msg.from_user.is_bot or msg.text.startswith('/'):
        return
    
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
    
    text = msg.text.lower()
    for pattern, responses in words.items():
        if re.search(pattern, text):
            await safe_send(msg, random.choice(responses))
            stats["messages_answered"] += 1
            save_data()
            return
    
    if random.random() < 0.15:
        reactions = [
            "🤔 Интересно! А расскажи поподробнее?",
            "Ого, неожиданно! И что дальше?",
            "Хмм, любопытно! А почему ты так думаешь?",
            "Серьёзно? Вот это поворот!",
            "Да ладно! А можешь объяснить?",
            "🔥 Вот это тема! Продолжай!"
        ]
        await safe_send(msg, random.choice(reactions))
        stats["messages_answered"] += 1
    
    save_data()

@dp.message()
async def catch_all(msg: Message):
    pass

# ============================================
# ЗАПУСК
# ============================================

async def main():
    load_data()
    asyncio.create_task(auto_save())
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