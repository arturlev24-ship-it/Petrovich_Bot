"""
Петрович - весёлый чат-бот для оживления беседы
Версия: 2.1
"""

import asyncio
import random
import logging
import re
import os
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

# ============================================
# НАСТРОЙКИ
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Файл .env загружен")
except ImportError:
    logger.warning("python-dotenv не установлен")

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
KARMA_FILE = os.getenv("KARMA_FILE", "user_karma.json")
AUTO_SAVE_INTERVAL = int(os.getenv("AUTO_SAVE_INTERVAL", "600"))
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "3600"))

# ============================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

last_message_time = {}
user_karma = {}
user_names = {}
message_count = 0
start_time = datetime.now()

# ============================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С КАРМОЙ
# ============================================

def save_karma():
    try:
        karma_to_save = {str(k): v for k, v in user_karma.items()}
        with open(KARMA_FILE, 'w', encoding='utf-8') as f:
            json.dump(karma_to_save, f, ensure_ascii=False, indent=2)
        logger.debug(f"Карма сохранена: {len(user_karma)} пользователей")
    except Exception as e:
        logger.error(f"Ошибка сохранения кармы: {e}")

def load_karma():
    global user_karma
    try:
        if os.path.exists(KARMA_FILE):
            with open(KARMA_FILE, 'r', encoding='utf-8') as f:
                karma_from_file = json.load(f)
                user_karma = {int(k): v for k, v in karma_from_file.items()}
            logger.info(f"Карма загружена: {len(user_karma)} пользователей")
        else:
            logger.info("Файл кармы не найден, начинаем с нуля")
    except Exception as e:
        logger.error(f"Ошибка загрузки кармы: {e}")
        user_karma = {}

async def cleanup_old_data():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        now = datetime.now()
        cleaned = 0
        for user_id in list(last_message_time.keys()):
            if (now - last_message_time[user_id]) > timedelta(hours=24):
                del last_message_time[user_id]
                cleaned += 1
        save_karma()
        if cleaned > 0:
            logger.info(f"Очистка: удалено {cleaned} старых записей")

async def auto_save_karma():
    while True:
        await asyncio.sleep(AUTO_SAVE_INTERVAL)
        save_karma()

async def safe_send_message(message: Message, text: str, reply: bool = False, reply_markup=None):
    try:
        if reply:
            await message.reply(text, reply_markup=reply_markup)
        else:
            await message.answer(text, reply_markup=reply_markup)
    except TelegramRetryAfter as e:
        logger.warning(f"Flood control: ждем {e.retry_after} секунд")
        await asyncio.sleep(e.retry_after)
        try:
            if reply:
                await message.reply(text, reply_markup=reply_markup)
            else:
                await message.answer(text, reply_markup=reply_markup)
        except TelegramAPIError as e2:
            logger.error(f"Повторная ошибка отправки: {e2}")
    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки сообщения: {e}")

# ============================================
# MIDDLEWARE ДЛЯ ОГРАНИЧЕНИЯ БОТА ГРУППАМИ
# ============================================

class ChatOnlyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            # Для личных сообщений
            if event.chat.type == ChatType.PRIVATE:
                # Пропускаем только /start
                if event.text and event.text.startswith('/start'):
                    return await handler(event, data)
                
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🚀 Добавить Петровича в чат",
                                url=f"https://t.me/{(await bot.me()).username}?startgroup=true"
                            )
                        ]
                    ]
                )
                
                await event.answer(
                    "⚠️ Я работаю только в групповых чатах!\n\n"
                    "Нажми на кнопку ниже, чтобы добавить меня в чат и начать веселье! 🎉",
                    reply_markup=keyboard
                )
                return
            
            # Для групп и супергрупп — пропускаем ВСЁ
            if event.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                return await handler(event, data)
        
        return await handler(event, data)

dp.message.middleware(ChatOnlyMiddleware())

# ============================================
# БАЗЫ ДАННЫХ
# ============================================

welcome_phrases = [
    "Опа, {name}! Заходи, не стесняйся, тут все свои! 🎉",
    "{name} ворвался в чат! Прячьте печеньки! 🍪",
    "Смотрите-ка, {name} пришел! Чат оживает! ✨",
    "Внимание! {name} теперь с нами. Аплодисменты! 👏",
    "Ну привет, {name}! Рассказывай, как жизнь? ☕",
    "{name} появился на радарах! Всем построиться! 🚨",
    "Бам! {name} телепортировался в чат! 🌀",
    "Двери открываются... {name} заходит! 🚪",
    "Ого, {name}! А мы тебя ждали! Где пропадал? 🤗",
    "Салют, {name}! Чувствуй себя как дома, но не забывай, что в гостях! 🏠",
    "Народ, встречайте! {name} решил к нам присоединиться! 🥳",
    "Тук-тук! Кто там? {name}! Заходи! 🚪",
    "{name} присоединился к вечеринке! Музыку громче! 🎵",
    "В чате пополнение! {name}, дай пять! 🖐️",
    "Легенда гласит, что {name} наконец-то здесь! 📜"
]

triggers = {
    r"привет": [
        "Привет-привет! Как жизнь молодая? 😊",
        "О, здарова! Давно не виделись! 👋",
        "Приветствую тебя, странник интернета! 🧙‍♂️",
        "Хеллоу! Слышал, ты сегодня в ударе! 💪",
        "Приветики-пистолетики! Как сам? 🔫",
        "Здравствуй, друг! Чай, кофе, потанцуем? ☕💃",
        "О! Какие люди! Привет! 🎭",
        "Салют! Ты прям как солнышко сегодня! ☀️",
        "Привет, бро! Чего нового расскажешь? 🤜🤛",
        "Хай! Ты пропустил всё самое интересное! 🎪"
    ],
    r"пока|до\s+свидания|прощай|бай|гудбай|увидимся|спокойной": [
        "Куда?! Мы же только начали тусить! 😢",
        "Пока-пока! Не пропадай надолго! 👋",
        "До скорого! Приходи с плюшками! 🍩",
        "Эх, уходишь... А кто меня веселить будет? 🎭",
        "Спокойной ночи! Пусть приснится единорог! 🦄",
        "Увидимся! Береги себя, бро! 🤗",
        "Не прощаюсь! До новых встреч в эфире! 📡",
        "Чао-какао! Жду с нетерпением! ☕",
        "Ладно, иди. Но я буду скучать! 🥺",
        "Гудбай, май лав, гудбай! 🎵",
        "Возвращайся скорее! Я тут без тебя заскучаю! 😿",
        "Покасики! Ты лучший! 🌟"
    ],
    r"спасибо|спс|благодарю|сяб|сяп|спасиб|мерси|thanks|thx": [
        "Всегда пожалуйста! Обращайся в любое время! 😎",
        "Не за что! Я ж Петрович — душа компании! 🫶",
        "Рад помочь! Заходи ещё! 🤝",
        "На здоровье! Пользуйся! 💪",
        "Мерси за мерси! Ты супер! ⭐",
        "Да пустяки! Для хорошего человека ничего не жалко! 💝",
        "Обращайся! Я здесь именно для этого! 🎯",
        "Пожалуйста! Ты тоже можешь меня чему-нибудь научить! 📚",
        "Не стоит благодарности! Просто будь счастлив! 😊",
        "Всегда рад! Ты крутой, не забывай! 🏆"
    ],
    r"еда|кушать|жрать|голод|вкусн|пицца|бургер|суши|шаурма|рецепт|готовить": [
        "Ммм, еда! Я бы сейчас съел пиццу! 🍕",
        "Не напоминай! У меня слюнки текут! 🤤",
        "Кто сказал «еда»? Я уже тут с вилкой! 🍴",
        "Обожаю вкусняшки! Что готовим? 🧑‍🍳",
        "Шаурма — это искусство! С чесноком! 🌯",
        "Пицца с ананасами? Ухожу из чата! 🍍❌",
        "Суши? Только если с лососем! 🍣",
        "Бургеры! Двойной чиз, пожалуйста! 🍔",
        "Я на диете... Но один кусочек можно! 🎂",
        "Готовить — это магия! Что ты умеешь? 🪄",
        "Пельмени! Русская классика! 🥟",
        "Еда объединяет людей! Давайте устроим пир! 🍽️"
    ],
    r"работа|учёба|учеба|экзамен|дедлайн|начальник|коллега|офис|зарплата|уволился|совещание": [
        "Работа не волк! В лес не убежит! 😄",
        "Дедлайны — это адреналин для взрослых! 📅",
        "Понедельник? Держись! Пятница уже близко! 📆",
        "Начальник злой? Подари ему печеньку! 🍪",
        "Зарплата — лучший мотиватор! 💰",
        "Учёба — свет! А неучёных — тьма! 💡",
        "Экзамены? Главное — не паниковать! 📝",
        "Коллеги бесят? Считай до десяти! 🧘",
        "Офисная жизнь: чай, сплетни, работа. В таком порядке! ☕",
        "Уволился? Поздравляю с новой главой! 📖",
        "Совещание? Главное — не уснуть! 😴",
        "Работай в кайф, а не на износ! 💆‍♂️"
    ],
    r"кот|кошк|собак|пёс|щенок|хомяк|попуг|рыбк|черепах|ёж|лис|заяц|медвед|питомец": [
        "Котики правят миром! И интернетом! 🐱",
        "Собака — друг человека! Петрович — тоже друг! 🐕",
        "Щеночки! Милота зашкаливает! 🐶💕",
        "Хомячки такие пухленькие! 🐹",
        "Попугаи — те ещё болтуны! Как я! 🦜",
        "Рыбки успокаивают нервы! 🐠",
        "Черепахи — символ мудрости и спокойствия! 🐢",
        "Ёжики! Колючие, но милые! 🦔",
        "Лиса — хитрый зверь! Как некоторые тут! 🦊",
        "Зайка моя! Я твой зайчик! 🐰",
        "Медведь? Не буди во мне зверя! 🐻",
        "Питомцы — это семья! Кто у тебя есть? 🐾"
    ],
    r"игр|гейм|ps\b|playstation|xbox|steam|дота|кс\b|cs\b|контр[.]?страйк|майнкрафт|гта|gta|киберспорт|стрим": [
        "Геймер detected! Что проходишь? 🎮",
        "Дота? Это жизнь или боль? 🎯",
        "Контр-страйк? Раш Б не забудь! 🔫",
        "Майнкрафт! Строим империю! ⛏️",
        "ГТА? Не нарушай ПДД хотя бы в игре! 🚗",
        "Стим-распродажа? Прощай, зарплата! 💸",
        "PlayStation или Xbox? Вечный спор! 🎮",
        "Киберспортсмен? Респект! 🏆",
        "Стримишь? Где ссылка? Будем смотреть! 📺",
        "Игры — это искусство! Не дайте себя убедить в обратном! 🎨",
        "Пятница — время для гейминга! 🕹️",
        "Задротить или не задротить? Вот в чем вопрос! ⚔️"
    ],
    r"музык|песн|трек|альбом|концерт|пою|рок|рэп|джаз|классик|метал|попса": [
        "Музыка объединяет! Что слушаешь? 🎵",
        "У меня в наушниках играет... Что-то классное! 🎧",
        "Рок — это навсегда! 🤘",
        "Рэп — поэзия улиц! 🎤",
        "Джаз для души! Расслабляет! 🎷",
        "Классика? Ты эстет! 🎻",
        "Металлисты, отзовитесь! 🤘🔥",
        "Попса? Почему бы и нет! Главное — качает! 💃",
        "Концерт — это энергия! Был на живых выступлениях? 🎸",
        "Спой что-нибудь! Я подпою! 🎶",
        "Музыка лечит душу! Это факт! 💊",
        "Какой трек у тебя на репите? 🔁"
    ],
    r"спорт|футбол|баскетбол|хоккей|теннис|тренир|качалк|фитнес|йог|бег|плаван": [
        "Спорт — это жизнь! 💪",
        "Футбол? За кого болеешь? ⚽",
        "Качалка? Мышцы не растут без труда! 🏋️",
        "Йога для души и тела! 🧘",
        "Бег по утрам? Ты герой! 🏃",
        "Плавание — лучший спорт! 🏊",
        "Баскетбол! Данк — это искусство! 🏀",
        "Хоккей! Шайбу, шайбу! 🏒",
        "Теннис? Уимблдон смотрю! 🎾",
        "Фитнес — это не наказание, а награда! 💪",
        "Спортсмен? Дай пять! 🖐️",
        "Главное — движение! Вперед! 🚴"
    ],
    r"грустно|печаль|тоска|депресс|плохо|хреново|устал|тяжело|плачу|одиноко": [
        "Эй, не грусти! Лови виртуальную обнимашку! 🫂",
        "Грусть — это временно! Счастье — навсегда! 🌈",
        "Выше нос! Ты справишься со всем! 💪",
        "Обнимаю тебя через экран! Всё будет хорошо! 🤗",
        "Помни: после дождя всегда выходит солнце! ☀️",
        "Хочешь, расскажу анекдот? Может, улыбнешься? 😊",
        "Ты не один! У тебя есть мы и Петрович! ❤️",
        "Плохой день? Давай сделаем его лучше вместе! 🎈",
        "Отдохни, выпей чаю, посмотри котиков! 🐱☕",
        "Всё пройдет! И это тоже пройдет! Держись! 🕊️",
        "Лови лучи добра! Ты заслуживаешь счастья! ✨",
        "Сегодня грустно, но завтра будет новый день! 🌅"
    ],
}

compliments = [
    "Ты сегодня отлично выглядишь! Даже через интернет видно! 😎",
    "С тобой чат становится интереснее! 💫",
    "Ты просто космос! Нет, правда! 🌟",
    "У тебя отличное чувство юмора! 👍",
    "Ты делаешь этот мир лучше! Не забывай об этом! ❤️",
    "Твой позитив заражает! Вирус счастья! 🦠😊",
    "Ты как Wi-Fi — без тебя всё не то! 📶",
    "У тебя аура крутости! Серьёзно! ✨",
    "Твои сообщения — лучшее, что случалось с этим чатом! 💬",
    "С тобой даже понедельник не страшен! 📅",
    "Ты источник вдохновения! Не останавливайся! 🎨",
    "Твоя энергетика зашкаливает! Заряжаешь всех! ⚡",
    "Ты как пицца — всем нравишься! 🍕",
    "У тебя талант поднимать настроение! 🎭",
    "Ты просто находка для этого чата! 💎",
    "С тобой легко и весело! Не меняйся! 🤗",
    "Ты светишься изнутри! Секрет фирмы? 💡",
    "Твой юмор — на высшем уровне! 🎯",
    "Ты делаешь обычный день праздником! 🎉",
    "Ты как солнце — без тебя пасмурно! ☀️"
]

random_facts = [
    "Знаете ли вы, что утята считают первое, что видят, своей мамой? 🦆",
    "Интересный факт: бананы — это ягоды, а клубника — нет! 🍌",
    "А вы в курсе, что котики могут издавать до 100 разных звуков? 🐱",
    "В Японии есть кафе, где можно поиграть с ежами! 🦔",
    "Чихнуть с открытыми глазами невозможно! Попробуйте! 🤧",
    "Осьминоги имеют три сердца! ❤️❤️❤️",
    "Слоны — единственные животные, которые не могут прыгать! 🐘",
    "Мёд никогда не портится! Находили мёд в гробницах фараонов! 🍯",
    "В космосе нельзя плакать — слёзы не текут! 🚀",
    "Крокодилы не могут высовывать язык! 🐊",
    "У улитки около 25 000 зубов! 🐌",
    "Дельфины спят с одним открытым глазом! 🐬",
    "Пчёлы могут узнавать человеческие лица! 🐝",
    "В среднем человек проводит 6 месяцев жизни в ожидании зелёного света! 🚦",
    "Кофе — второй самый продаваемый товар в мире после нефти! ☕",
    "Язык — самая сильная мышца в теле относительно размера! 👅",
    "Глаз страуса больше, чем его мозг! 🦢",
    "В сутках на Венере больше, чем в году! 🌍",
    "Арахис — это не орех, а боб! 🥜",
    "Лимон содержит больше сахара, чем клубника! 🍋"
]

jokes = [
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 OCT = 25 DEC! 😂",
    "Колобок повесился... Теперь он просто блин 🥞",
    "Идёт медведь по лесу, видит — машина горит. Сел в неё и сгорел. Вот такой он невезучий 🐻",
    "Оптимист видит стакан наполовину полным. Пессимист — наполовину пустым. Программист видит стакан, размер которого вдвое больше необходимого 💻",
    "Почему скелеты не ходят на вечеринки? Потому что у них нет тела! 💀",
    "Купил мужик шляпу, а она ему как раз! 🎩",
    "Встречаются два глиста в животе. Один грустный. Второй спрашивает: 'Ты чего?' А первый: 'Эх, опять на диету посадили...' 🪱",
    "Почему курица перешла дорогу? Чтобы доказать, что она не только для супа! 🐔",
    "Звонок в дверь. Мужик открывает — никого. Только улитка. Он её выкидывает. Через год звонок. Открывает — улитка: 'Ты чего?' 🐌",
    "Доктор, я ничего не слышу! — А как вы меня поняли? — По губам читаю. — А так? (закрывает лицо руками) 🤦‍♂️",
    "Сидят два наркомана. Один говорит: 'Смотри, белка!' Второй: 'Где?'. Первый: 'Улетела' 🐿️",
    "Штирлиц шел по улице и упал в люк. 'Вот так и проваливаются явки', — подумал он 🕵️",
    "Почему вода в море солёная? Потому что там селёдки плавают! 🐟",
    "Как называется боязнь Санта-Клауса? Клаустрофобия! 🎅",
    "Чем отличается фея от ведьмы? Возрастом! 🧚‍♀️🧙‍♀️",
    "Почему призраки плохо врут? Потому что их насквозь видно! 👻",
    "Что сказал ноль восьмёрке? 'Классный ремень!' 8️⃣",
    "Парадокс: утром не можешь встать, вечером не можешь уснуть 😴",
    "Если выкинуть клавиатуру в окно, можно выйти в окна! 💻🪟",
    "Хакеры взломали Пентагон играя в бинго! Б-52! 💣"
]

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.type == ChatType.PRIVATE:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚀 Добавить Петровича в чат",
                        url=f"https://t.me/{(await bot.me()).username}?startgroup=true"
                    )
                ]
            ]
        )
        
        await safe_send_message(
            message,
            f"🎉 <b>Привет! Я Петрович — душа компании!</b>\n\n"
            f"Нажми на кнопку ниже, чтобы добавить меня в групповой чат и начать веселье!",
            reply_markup=keyboard
        )
    else:
        await safe_send_message(
            message,
            f"🎉 Всем привет! Я Петрович, душа этого чата!\n\n"
            f"Пишите слова, а я буду реагировать! У меня 300+ ответов!\n"
            f"Команды: /help"
        )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await safe_send_message(message,
        "🤖 <b>Петрович к вашим услугам!</b>\n\n"
        "📋 <b>Команды:</b>\n"
        "/compliment - получить дозу позитива\n"
        "/fact - узнать что-то новое\n"
        "/joke - посмеяться\n"
        "/karma - узнать свою карму\n"
        "/top - топ участников\n"
        "/stats - статистика чата\n\n"
        "💬 Просто общайтесь в чате, а я буду реагировать на слова!"
    )

@dp.message(Command("compliment"))
async def cmd_compliment(message: Message):
    compliment = random.choice(compliments)
    await safe_send_message(message, f"💝 {compliment}")

@dp.message(Command("fact"))
async def cmd_fact(message: Message):
    fact = random.choice(random_facts)
    await safe_send_message(message, f"🤓 {fact}")

@dp.message(Command("joke"))
async def cmd_joke(message: Message):
    joke = random.choice(jokes)
    await safe_send_message(message, f"😄 {joke}")

@dp.message(Command("karma"))
async def cmd_karma(message: Message):
    user_id = message.from_user.id
    karma = user_karma.get(user_id, 0)
    name = message.from_user.first_name
    
    if karma > 50:
        status = "👑 Король чата"
    elif karma > 30:
        status = "🏆 Легенда чата"
    elif karma > 20:
        status = "⭐ Звезда тусовки"
    elif karma > 10:
        status = "👍 Свой человек"
    elif karma > 5:
        status = "👋 Новый друг"
    else:
        status = "🌱 Только знакомимся"
    
    await safe_send_message(message, f"{name}, твоя карма: <b>{karma}</b> очков\nСтатус: {status}")

@dp.message(Command("top"))
async def cmd_top(message: Message):
    if not user_karma:
        await safe_send_message(message, "Пока никто не заработал карму! Будьте активнее! 🏃‍♂️")
        return
    
    sorted_users = sorted(user_karma.items(), key=lambda x: x[1], reverse=True)[:10]
    top_text = "🏆 <b>ТОП-10 участников:</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"] + [f"{i}️⃣" for i in range(4, 11)]
    
    for i, (user_id, karma) in enumerate(sorted_users):
        if user_id in user_names:
            name = user_names[user_id]
        else:
            try:
                user = await bot.get_chat(user_id)
                if user.username:
                    name = f"@{user.username}"
                    user_names[user_id] = name
                else:
                    name = user.first_name
                    user_names[user_id] = name
            except:
                name = f"ID{user_id}"
        
        top_text += f"{medals[i]} {name}: <b>{karma}</b> кармы\n"
    
    await safe_send_message(message, top_text)

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    uptime = datetime.now() - start_time
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    stats_text = (
        "📊 <b>Статистика Петровича:</b>\n\n"
        f"⏱ Время работы: {uptime.days}д {hours}ч {minutes}м\n"
        f"💬 Обработано сообщений: <b>{message_count}</b>\n"
        f"👥 Пользователей с кармой: <b>{len(user_karma)}</b>\n"
        f"📝 Всего реакций: <b>100+</b>\n\n"
        "🤖 Петрович работает стабильно!"
    )
    
    await safe_send_message(message, stats_text)

# ============================================
# ОБРАБОТЧИКИ СОБЫТИЙ ЧАТА
# ============================================

@dp.message(F.new_chat_members)
async def new_member(message: Message):
    """Приветствие новых участников"""
    logger.info(f"🎉 Событие: новые участники в чате {message.chat.id}")
    
    for new_member in message.new_chat_members:
        logger.info(f"👤 Новый участник: {new_member.full_name} (ID: {new_member.id})")
        
        # Сохраняем имя в кеш
        if new_member.username:
            user_names[new_member.id] = f"@{new_member.username}"
        else:
            user_names[new_member.id] = new_member.first_name or new_member.full_name
        
        # Если это сам бот
        if new_member.id == bot.id:
            logger.info("🤖 Это я! Приветствую чат")
            await message.answer(
                "🎉 Всем привет! Я Петрович, ваш новый любимчик!\n"
                "Пишите слова, а я буду реагировать! У меня 100+ ответов!\n"
                "Команды: /help"
            )
            continue
        
        # Приветствуем нового участника
        name = new_member.first_name or new_member.full_name
        welcome = random.choice(welcome_phrases).format(name=name)
        
        try:
            await message.answer(welcome)
            logger.info(f"✅ Приветствие отправлено: {name}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки приветствия для {name}: {e}")
        
        # Начисляем бонусную карму
        user_karma[new_member.id] = user_karma.get(new_member.id, 0) + 5
        logger.info(f"💰 Бонусная карма для {name}: +5")

@dp.message(F.left_chat_member)
async def left_member(message: Message):
    """Прощание с ушедшими участниками"""
    left_user = message.left_chat_member
    
    # Игнорируем если бот сам вышел
    if left_user.id == bot.id:
        logger.info("Бот был удалён из чата")
        return
    
    logger.info(f"👋 Участник покинул чат: {left_user.full_name}")
    
    name = left_user.first_name or left_user.full_name
    farewells = [
        f"Эх, {name} ушёл... Вернись, я всё прощу! 😢",
        f"{name} покинул чат. Свободу попугаям! 🦜",
        f"Прощай, {name}! Без тебя будет скучно... 👋",
        f"{name} слился... Чат понёс невосполнимую потерю! 😔",
        f"Пока, {name}! Заходи если что! Двери открыты! 🚪",
        f"Куда же ты, {name}? А как же наша дружба? 💔",
        f"{name} ушёл в закат... 🌅",
        f"Грустно... {name} покинул нас. Но мы не плачем! 🥲"
    ]
    
    try:
        await message.answer(random.choice(farewells))
        logger.info(f"✅ Прощание отправлено для {name}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки прощания для {name}: {e}")

# ============================================
# ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ
# ============================================

@dp.message(F.text)
async def handle_messages(message: Message):
    global message_count
    
    # Игнорируем сообщения от ботов
    if message.from_user.is_bot:
        return
    
    # Пропускаем команды
    if message.text and message.text.startswith('/'):
        return
    
    if not message.text:
        return
    
    message_count += 1
    
    user_id = message.from_user.id
    current_time = datetime.now()
    
    # Сохраняем имя пользователя в кеш
    if message.from_user.username:
        user_names[user_id] = f"@{message.from_user.username}"
    else:
        user_names[user_id] = message.from_user.first_name
    
    # Начисляем карму (не чаще раза в минуту)
    if user_id not in last_message_time or \
       (current_time - last_message_time[user_id]) > timedelta(minutes=1):
        user_karma[user_id] = user_karma.get(user_id, 0) + 1
        last_message_time[user_id] = current_time
    
    text_lower = message.text.lower()
    
    # Проверяем триггеры
    trigger_found = False
    for trigger, responses in triggers.items():
        if re.search(trigger, text_lower):
            response = random.choice(responses)
            await safe_send_message(message, response)
            trigger_found = True
            break
    
    # Дополнительные реакции
    if not trigger_found:
        # Реакция на длинные сообщения
        if len(message.text) > 200 and random.random() < 0.3:
            reactions = [
                "Ого, целый роман написал! 📖",
                "Вот это я понимаю, развернутый ответ! 👏",
                "Ты случайно не писатель? Такое длинное сообщение! ✍️",
                "Читаю запоем! Интересно! 📚",
                "Вот это лонгрид! Респект за труд! 📝"
            ]
            await safe_send_message(message, random.choice(reactions))
        
        # Реакция на много смайликов
        emoji_count = sum(1 for char in message.text if ord(char) > 1000)
        if emoji_count >= 5:
            emoji_reactions = [
                "Да ты эмоциональный! Столько смайликов! 🎭",
                "Смайл-атака! Я тоже так могу! 😀😃😄😁😆",
                "Эмодзи-пати! Продолжай! 🎉🎊🎈",
                "Вот это экспрессия! Люблю! 🎪",
                "Столько эмоций! Ты меня заражаешь! 😄"
            ]
            await safe_send_message(message, random.choice(emoji_reactions))

# Заглушка для необработанных сообщений
@dp.message()
async def catch_all(message: Message):
    pass

# ============================================
# ЗАПУСК БОТА
# ============================================

async def on_startup():
    load_karma()
    logger.info("Карма загружена")
    
    asyncio.create_task(cleanup_old_data())
    asyncio.create_task(auto_save_karma())
    logger.info("Фоновые задачи запущены")

async def main():
    await on_startup()
    
    logger.info("🤖 Петрович запускается...")
    
    try:
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "edited_message",
                "chat_member",
                "my_chat_member"
            ]
        )
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        save_karma()
    finally:
        save_karma()
        logger.info("Бот остановлен, карма сохранена")