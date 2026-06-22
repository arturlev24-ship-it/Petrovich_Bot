"""
Палыч - весёлый чат-бот
Версия: 4.0 - Полностью переписанный
"""

import asyncio
import random
import logging
import re
import os
import json
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

# ============================================
# НАСТРОЙКИ
# ============================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в .env файле!")
    exit(1)

DATA_FILE = "palych_data.json"

# ============================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Данные
stats = {
    "messages_answered": 0,
    "users": {},
    "chats": []
}

def load():
    global stats
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
            logger.info(f"✅ Данные загружены")
    except:
        pass

def save():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

async def auto_save():
    while True:
        await asyncio.sleep(300)
        save()

async def send(msg: Message, text: str, **kwargs):
    try:
        await msg.answer(text, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# ============================================
# БАЗА ТРИГГЕРОВ
# ============================================

words = {
    "привет|здравствуй|здаров|хелло|хай|салют|ку": [
        "О, здарова! Как жизнь? Рассказывай! 😊",
        "Привет-привет! Ты сегодня прям светишься! ✨",
        "Хеллоу! Давно не виделись! Как сам? 👋",
        "Салют! Что нового? Выкладывай! 🎉",
        "Ку-ку! Я Палыч, будем знакомы! 🤝"
    ],
    "пока|прощай|бай|гудбай|чао": [
        "Куда?! Мы же только разговорились! 😢",
        "Пока-пока! Не пропадай надолго! 👋",
        "До скорого! Приходи с новостями! 🍩",
        "Эх, уходишь... А кто меня слушать будет? 🎭",
        "Спокойной ночи! Пусть приснится что-то крутое! 🦄"
    ],
    "как дела|как сам|как жизнь|как ты": [
        "Да нормально! А у тебя как? 🤔",
        "Отлично! Вот с вами общаюсь! А ты как? 😊",
        "Лучше всех! Рассказывай, как ты? 💪",
        "Нормально! Мемасы смотрю. А ты? 📱"
    ],
    "еда|кушать|голод|пицц|бургер|суши|шаурм": [
        "Ммм, еда! Что ты любишь? 🍕",
        "Ой, не напоминай! Слюнки текут! 🤤",
        "Кто сказал «еда»? Я уже тут! 🍴",
        "Обожаю вкусняшки! Ты умеешь готовить? 🧑‍🍳",
        "Шаурма — это искусство! С чесноком любишь? 🌯"
    ],
    "работа|учёба|дедлайн|начальник|офис": [
        "Работа не волк! А ты чем занимаешься? 😄",
        "Дедлайны — это адреналин! Горят сроки? 📅",
        "Понедельник? Держись! Пятница близко! 📆",
        "Начальник злой? Подари печеньку! 🍪"
    ],
    "погода|дождь|снег|холод|жара|солнце": [
        "Дождь? Самое время для пледа и какао! ☕",
        "Снег идёт! Бежим лепить снеговика! ⛄",
        "Холодно? Грейся обнимашками! 🫂",
        "Жара! Кондиционер — лучший друг! 🥵",
        "Солнце светит — жизнь прекрасна! ☀️"
    ],
    "кот|кошк|собак|пёс|хомяк|попугай": [
        "Котики правят миром! У тебя есть кот? 🐱",
        "Собака — друг человека! Какая порода? 🐕",
        "Щеночки! Милота зашкаливает! 🐶",
        "Хомячки такие пухленькие! 🐹"
    ],
    "комп|ноут|вайфай|телефон|смартфон|гаджет": [
        "Комп глючит? Перезагрузка решает 90% проблем! 💻",
        "Вайфай упал — жизнь остановилась! 📡",
        "Телефон разрядился? Паника! Какой у тебя? 😱",
        "Люблю гаджеты! Что у тебя за девайс? ⚙️"
    ],
    "игр|гейм|дота|кс|майнкрафт|гта|стрим": [
        "Геймер detected! Что проходишь? 🎮",
        "Дота? Это жизнь или боль? 🎯",
        "Майнкрафт! Строим империю! ⛏️",
        "ГТА? Не нарушай ПДД! 🚗"
    ],
    "музык|песн|трек|рок|рэп|джаз|концерт": [
        "Музыка объединяет! Что слушаешь? 🎵",
        "Что в наушниках? Делись! 🎧",
        "Рок — это навсегда! Какая группа? 🤘",
        "Концерт — это энергия! Был на живых? 🎸"
    ],
    "фильм|сериал|кино|нетфликс|аниме": [
        "Что смотришь? Нужен совет! 🎬",
        "Нетфликс и чилл? Что в топе? 🍿",
        "Анимешник? Уважаю! Какое смотришь? 🎌",
        "Сериал до 3 утра? Знакомо! 😴"
    ],
    "спорт|футбол|качалк|фитнес|йог|бег": [
        "Спорт — это жизнь! Каким занимаешься? 💪",
        "Футбол? За кого болеешь? ⚽",
        "Качалка? Мышцы не растут без труда! 🏋️",
        "Бег по утрам? Ты герой! 🏃"
    ],
    "мем|рофл|лол|кек|кринж|вайб|пранк": [
        "Мемас залетел в чат! Покажи! 😂",
        "ЛОЛ! Я тоже с этого мема ору! 🤣",
        "Рофл года! Часто мемасишь? 💾",
        "Вайб этого чата — лучший! ✌️"
    ],
    "любовь|отношен|свидан|поцелуй|обнима": [
        "Любовь витает в воздухе! 💕",
        "Отношения — это работа! Как у тебя? 💑",
        "Свидание? Надень что-то красивое! 👔",
        "Обнимашки лечат стресс! 🫂"
    ],
    "спать|сон|кровать|подушк|бессонниц": [
        "Спать? Только после дедлайна! 😴",
        "Кроватка ждёт! Мягкая подушка... 🛏️",
        "Бессонница? Считай овец! 🐑",
        "Выспаться — это искусство! 🎨"
    ],
    "чай|кофе|пиво|вино|коктейл|смузи": [
        "Чаёк? С плюшками? Я за! ☕",
        "Кофе — топливо! Что предпочитаешь? ☕",
        "Пивко после работы? Уважаю! 🍺",
        "Вино? Красное или белое? 🍷"
    ],
    "праздник|день рожден|новый год|пасх": [
        "С праздником! Ура! 🎉",
        "День рождения? Подарки, торт! 🎂",
        "Новый год! Ёлка, мандарины! 🎄",
        "Праздник — отличный повод для веселья! 🎈"
    ],
    "путешеств|отпуск|море|горы|билет|отель": [
        "Путешествия расширяют кругозор! ✈️",
        "Море зовёт! Куда хочешь? 🌊",
        "Горы — это свобода! 🏔️",
        "Отпуск? Беру чемодан и лечу! 🧳"
    ]
}

# ============================================
# КОМАНДЫ
# ============================================

@dp.message(Command("start"))
async def start(msg: Message):
    if msg.chat.type == ChatType.PRIVATE:
        me = await bot.me()
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🚀 Добавить Палыча в чат",
                url=f"https://t.me/{me.username}?startgroup=true"
            )
        ]])
        await send(msg,
            "🎉 <b>Привет! Я Палыч — душа компании!</b>\n\n"
            "Оживляю чаты, отвечаю на 100+ слов, задаю вопросы!\n"
            "Со мной никогда не скучно! 🔥\n\n"
            "👇 Жми кнопку чтобы добавить в чат:",
            reply_markup=kb
        )
    else:
        await send(msg, "🎉 <b>Палыч на связи!</b>\nПиши слова — я отвечу!\nКоманды: /help")

@dp.message(Command("help"))
async def help_cmd(msg: Message):
    await send(msg,
        "🤖 <b>Палыч — оживитель чатов!</b>\n\n"
        "/start — перезапуск\n"
        "/help — справка\n"
        "/top — топ-10 болтливых\n"
        "/stats — статистика\n\n"
        "Пиши: привет, еда, погода, игры, музыка..."
    )

@dp.message(Command("top"))
async def top_cmd(msg: Message):
    u = stats.get("users", {})
    if not u:
        await send(msg, "📊 Пока никто не общался!")
        return
    
    top = sorted(u.items(), key=lambda x: x[1]["messages"], reverse=True)[:10]
    text = "🏆 <b>ТОП-10 БОЛТЛИВЫХ:</b>\n\n"
    medals = ["🥇","🥈","🥉"] + [f"{i}️⃣" for i in range(4,11)]
    
    for i, (uid, info) in enumerate(top):
        name = info.get("username", f"ID{uid}")
        text += f"{medals[i]} {name}: <b>{info['messages']}</b> сообщ.\n"
    
    await send(msg, text)

@dp.message(Command("stats"))
async def stats_cmd(msg: Message):
    await send(msg,
        "📊 <b>СТАТИСТИКА ПАЛЫЧА:</b>\n\n"
        f"👥 Пользователей: <b>{len(stats.get('users', {}))}</b>\n"
        f"💬 Ответов: <b>{stats.get('messages_answered', 0)}</b>\n"
        f"📁 Чатов: <b>{len(stats.get('chats', []))}</b>\n\n"
        "🤖 Палыч работает!"
    )

# ============================================
# ОБРАБОТЧИК СООБЩЕНИЙ (САМЫЙ ГЛАВНЫЙ)
# ============================================

@dp.message()
async def handle_all(msg: Message):
    """Единый обработчик ВСЕХ сообщений"""
    
    # === ПРОВЕРКА НА НОВЫХ УЧАСТНИКОВ ===
    if msg.new_chat_members:
        logger.info(f"🔔 НОВЫЙ УЧАСТНИК!")
        
        # Добавляем чат в статистику
        cid = str(msg.chat.id)
        if cid not in stats["chats"]:
            stats["chats"].append(cid)
            save()
        
        for member in msg.new_chat_members:
            if member.id == bot.id:
                await send(msg,
                    "🎉 <b>Палыч в чате!</b>\n\n"
                    "Теперь этот чат оживёт!\n"
                    "Пишите слова — я буду отвечать!\n"
                    "Команды: /help"
                )
                return
            
            name = member.first_name or member.full_name
            welcomes = [
                f"Опа, {name}! Заходи, не стесняйся! 🎉",
                f"{name} ворвался в чат! 🍪",
                f"Смотрите-ка, {name} пришёл! ✨",
                f"{name} на радарах! 🚨",
                f"Ну привет, {name}! ☕",
                f"Бам! {name} телепортировался! 🌀",
                f"Ого, {name}! А мы тебя ждали! 🤗",
                f"Салют, {name}! 🏠"
            ]
            await send(msg, random.choice(welcomes))
        return
    
    # === ПРОВЕРКА НА УШЕДШИХ ===
    if msg.left_chat_member:
        logger.info(f"🚪 УШЁЛ УЧАСТНИК!")
        
        if msg.left_chat_member.id == bot.id:
            return
        
        name = msg.left_chat_member.first_name or msg.left_chat_member.full_name
        farewells = [
            f"Эх, {name} ушёл... 😢",
            f"{name} покинул чат... 🦜",
            f"Прощай, {name}! 👋",
            f"{name} слился... 😔",
            f"Пока, {name}! 🚪"
        ]
        await send(msg, random.choice(farewells))
        return
    
    # === ПРОПУСКАЕМ БОТОВ И КОМАНДЫ ===
    if msg.from_user.is_bot:
        return
    
    if not msg.text:
        return
    
    if msg.text.startswith('/'):
        return
    
    # === ОБРАБОТКА ТЕКСТА ===
    logger.info(f"💬 Сообщение: {msg.text[:50]}")
    
    # Статистика
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
    
    # Проверяем триггеры
    text = msg.text.lower()
    
    for pattern, responses in words.items():
        if re.search(pattern, text):
            await send(msg, random.choice(responses))
            stats["messages_answered"] += 1
            save()
            return
    
    # Рандомная реакция (15% шанс)
    if random.random() < 0.15:
        reactions = [
            "🤔 Интересно! А расскажи поподробнее?",
            "Ого, неожиданно! И что дальше?",
            "Хмм, любопытно! А почему ты так думаешь?",
            "Серьёзно? Вот это поворот!",
            "Да ладно! А можешь объяснить?",
            "Ничего себе! И часто такое бывает?",
            "🔥 Вот это тема! Продолжай!",
            "Ммм, занимательно!"
        ]
        await send(msg, random.choice(reactions))
        stats["messages_answered"] += 1
    
    save()

# ============================================
# ЗАПУСК
# ============================================

async def main():
    load()
    asyncio.create_task(auto_save())
    
    logger.info("🤖 Палыч запускается...")
    logger.info(f"📊 Чатов: {len(stats['chats'])}, Пользователей: {len(stats['users'])}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())