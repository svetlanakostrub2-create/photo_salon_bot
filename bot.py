import asyncio
import os
from datetime import datetime
from typing import List, Tuple, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import os

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = 1606381134  # твой Telegram ID (админ)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is empty. Set BOT_TOKEN env var.")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is empty. Set BOT_TOKEN env var.")
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID is empty. Set ADMIN_ID env var.")

ORDERS_FILE = "orders.txt"
COUNTER_FILE = "order_counter.txt"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ----------------- storage utils -----------------

def next_order_number() -> int:
    if not os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "w", encoding="utf-8") as f:
            f.write("1")

    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        n = int((f.read().strip() or "1"))

    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write(str(n + 1))

    return n

def append_order(text: str) -> None:
    with open(ORDERS_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n" + "=" * 70 + "\n")

def user_ref(user: types.User) -> str:
    if user.username:
        return f"@{user.username} (id={user.id})"
    return f"{user.full_name} (id={user.id}, без username)"

# ----------------- keyboards -----------------

start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Создать заказ")]],
    resize_keyboard=True
)

services_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Печать фото")],
        [KeyboardButton(text="Печать документов")],
        [KeyboardButton(text="Фото на документы")],
        [KeyboardButton(text="Оцифровка")],
        [KeyboardButton(text="Термопечать")],
        [KeyboardButton(text="Реставрация фото")],
        [KeyboardButton(text="Визитки/буклеты/наклейки")],
        [KeyboardButton(text="Фотошоп")],
        [KeyboardButton(text="Другое")],
    ],
    resize_keyboard=True
)

confirm_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Отправить"), KeyboardButton(text="↩️ Начать заново")]],
    resize_keyboard=True
)

done_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="ГОТОВО")]],
    resize_keyboard=True
)

skip_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="ПРОПУСТИТЬ")]],
    resize_keyboard=True
)

done_or_skip_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="ГОТОВО"), KeyboardButton(text="ПРОПУСТИТЬ")]],
    resize_keyboard=True
)

done_or_skip_files_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="ГОТОВО"), KeyboardButton(text="ПРОПУСТИТЬ ФАЙЛЫ")]],
    resize_keyboard=True
)

# ----------------- validation -----------------

def normalize_phone(s: str) -> Optional[str]:
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        return digits
    return None

def is_positive_int(s: str) -> bool:
    s = (s or "").strip()
    return s.isdigit() and int(s) > 0

# ----------------- generic helpers -----------------

FileItem = Tuple[str, str]  # ("photo"|"document", file_id)

async def add_file_to_state(message: types.Message, state: FSMContext):
    data = await state.get_data()
    files: List[FileItem] = data.get("files", [])
    if message.photo:
        files.append(("photo", message.photo[-1].file_id))
    elif message.document:
        files.append(("document", message.document.file_id))
    await state.update_data(files=files)

async def send_files_to_admin(files: List[FileItem]):
    for kind, fid in files:
        if kind == "photo":
            await bot.send_photo(ADMIN_ID, fid)
        else:
            await bot.send_document(ADMIN_ID, fid)

async def ask_contact(message: types.Message, state: FSMContext, next_state: State):
    await state.set_state(next_state)
    await message.answer(
        "Контакт для связи (номер телефона на 8…). Пример: 89123456789",
        reply_markup=ReplyKeyboardRemove()
    )

async def ask_comment(message: types.Message, state: FSMContext, next_state: State):
    await state.set_state(next_state)
    await message.answer("Комментарий (или ПРОПУСТИТЬ):", reply_markup=skip_kb)

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ----------------- states -----------------

class PhotoPrint(StatesGroup):
    contact = State()
    size = State()
    paper = State()
    copies = State()
    files = State()
    comment = State()
    confirm = State()

class DocPrint(StatesGroup):
    contact = State()
    format = State()
    copies = State()
    color = State()
    duplex = State()
    pages = State()
    files = State()
    comment = State()
    confirm = State()

class IDPhoto(StatesGroup):
    contact = State()
    doc_type = State()
    qty = State()
    color = State()
    comment = State()
    confirm = State()

class Digitization(StatesGroup):
    contact = State()
    source = State()
    qty = State()
    media_confirm = State()
    comment = State()
    confirm = State()

class ThermoPrint(StatesGroup):
    contact = State()
    item = State()
    size = State()
    has_layout = State()
    files = State()
    comment = State()
    confirm = State()

class Restoration(StatesGroup):
    contact = State()
    task = State()
    files = State()
    comment = State()
    confirm = State()

class PrintProducts(StatesGroup):
    contact = State()
    product_type = State()
    tirage = State()
    format = State()
    color = State()
    has_layout = State()
    need_design = State()
    files = State()
    comment = State()
    confirm = State()

class Photoshop(StatesGroup):
    contact = State()
    task = State()
    dont_change = State()
    files = State()
    comment = State()
    confirm = State()

class Other(StatesGroup):
    contact = State()
    desc = State()
    files = State()
    comment = State()
    confirm = State()

# ----------------- start/menu -----------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Фотосалон-бот. Нажмите «Создать заказ».", reply_markup=start_kb)

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Ок, отменил. Нажмите «Создать заказ».", reply_markup=start_kb)

@dp.message(F.text == "Создать заказ")
async def create_order(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=services_kb)

@dp.message(F.text == "↩️ Начать заново")
async def restart(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=services_kb)

# ----------------- 1) Печать фото -----------------

@dp.message(F.text == "Печать фото")
async def photo_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Печать фото", files=[])
    await ask_contact(message, state, PhotoPrint.contact)

@dp.message(PhotoPrint.contact)
async def photo_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(PhotoPrint.size)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="A7 (7×10)"), KeyboardButton(text="A6 (10×15)")],
            [KeyboardButton(text="A5 (15×21)"), KeyboardButton(text="A4 (21×30)")],
            [KeyboardButton(text="A3 (30×42)")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите размер:", reply_markup=kb)

@dp.message(PhotoPrint.size)
async def photo_size(message: types.Message, state: FSMContext):
    allowed = {"A7 (7×10)", "A6 (10×15)", "A5 (15×21)", "A4 (21×30)", "A3 (30×42)"}
    if (message.text or "") not in allowed:
        await message.answer("Выберите размер кнопкой.")
        return
    await state.update_data(size=message.text)
    await state.set_state(PhotoPrint.paper)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Глянцевая"), KeyboardButton(text="Матовая")]],
        resize_keyboard=True
    )
    await message.answer("Тип бумаги:", reply_markup=kb)

@dp.message(PhotoPrint.paper)
async def photo_paper(message: types.Message, state: FSMContext):
    if (message.text or "").lower() not in {"глянцевая", "матовая"}:
        await message.answer("Выберите: Глянцевая или Матовая.")
        return
    await state.update_data(paper=message.text)
    await state.set_state(PhotoPrint.copies)
    await message.answer("Количество копий (числом):", reply_markup=ReplyKeyboardRemove())

@dp.message(PhotoPrint.copies)
async def photo_copies(message: types.Message, state: FSMContext):
    if not is_positive_int(message.text or ""):
        await message.answer("Введите количество копий числом (например 2).")
        return
    await state.update_data(copies=int(message.text.strip()))
    await state.set_state(PhotoPrint.files)
    await message.answer("Пришлите фото (можно несколько). Когда закончите нажмите ГОТОВО.", reply_markup=done_kb)

@dp.message(PhotoPrint.files, F.photo | F.document)
async def photo_files_add(message: types.Message, state: FSMContext):
    await add_file_to_state(message, state)
    await message.answer("Принято. Ещё файлы или ГОТОВО.")

@dp.message(PhotoPrint.files, F.text == "ГОТОВО")
async def photo_files_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if len(data.get("files", [])) == 0:
        await message.answer("Для печати фото нужны файлы. Пришлите хотя бы одно фото.")
        return
    await ask_comment(message, state, PhotoPrint.comment)

@dp.message(PhotoPrint.comment, F.text == "ПРОПУСТИТЬ")
async def photo_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await photo_confirm(message, state)

@dp.message(PhotoPrint.comment)
async def photo_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await photo_confirm(message, state)

async def photo_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Размер: {data['size']}\n"
        f"Бумага: {data['paper']}\n"
        f"Копий: {data['copies']}\n"
        f"Файлов: {len(data.get('files', []))}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(PhotoPrint.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 2) Печать документов -----------------

@dp.message(F.text == "Печать документов")
async def docs_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Печать документов", files=[])
    await ask_contact(message, state, DocPrint.contact)

@dp.message(DocPrint.contact)
async def docs_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(DocPrint.format)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="A4"), KeyboardButton(text="A3")]],
        resize_keyboard=True
    )
    await message.answer("Формат бумаги:", reply_markup=kb)

@dp.message(DocPrint.format)
async def docs_format(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"A4", "A3"}:
        await message.answer("Выберите: A4 или A3.")
        return
    await state.update_data(format=message.text)
    await state.set_state(DocPrint.copies)
    await message.answer("Количество копий (числом):", reply_markup=ReplyKeyboardRemove())

@dp.message(DocPrint.copies)
async def docs_copies(message: types.Message, state: FSMContext):
    if not is_positive_int(message.text or ""):
        await message.answer("Введите количество копий числом (например 2).")
        return
    await state.update_data(copies=int(message.text.strip()))
    await state.set_state(DocPrint.color)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Ч/Б"), KeyboardButton(text="Цветная")]],
        resize_keyboard=True
    )
    await message.answer("Цветность:", reply_markup=kb)

@dp.message(DocPrint.color)
async def docs_color(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Ч/Б", "Цветная"}:
        await message.answer("Выберите: Ч/Б или Цветная.")
        return
    await state.update_data(color=message.text)
    await state.set_state(DocPrint.duplex)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Односторонняя"), KeyboardButton(text="Двусторонняя")]],
        resize_keyboard=True
    )
    await message.answer("Печать:", reply_markup=kb)

@dp.message(DocPrint.duplex)
async def docs_duplex(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Односторонняя", "Двусторонняя"}:
        await message.answer("Выберите: Односторонняя или Двусторонняя.")
        return
    await state.update_data(duplex=message.text)
    await state.set_state(DocPrint.pages)
    await message.answer("Страницы: 'все' или диапазон (например 1-3,7):", reply_markup=ReplyKeyboardRemove())

@dp.message(DocPrint.pages)
async def docs_pages(message: types.Message, state: FSMContext):
    pages = (message.text or "").strip()
    if not pages:
        await message.answer("Введите 'все' или диапазон (например 1-3,7).")
        return
    await state.update_data(pages=pages)
    await state.set_state(DocPrint.files)
    await message.answer("Пришлите документы. Когда закончите нажмите ГОТОВО.", reply_markup=done_kb)

@dp.message(DocPrint.files, F.photo | F.document)
async def docs_files_add(message: types.Message, state: FSMContext):
    await add_file_to_state(message, state)
    await message.answer("Принято. Ещё файлы или ГОТОВО.")

@dp.message(DocPrint.files, F.text == "ГОТОВО")
async def docs_files_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if len(data.get("files", [])) == 0:
        await message.answer("Для печати документов нужны файлы. Пришлите хотя бы один документ.")
        return
    await ask_comment(message, state, DocPrint.comment)

@dp.message(DocPrint.comment, F.text == "ПРОПУСТИТЬ")
async def docs_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await docs_confirm(message, state)

@dp.message(DocPrint.comment)
async def docs_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await docs_confirm(message, state)

async def docs_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Формат: {data['format']}\n"
        f"Копий: {data['copies']}\n"
        f"Цвет: {data['color']}\n"
        f"Печать: {data['duplex']}\n"
        f"Страницы: {data['pages']}\n"
        f"Файлов: {len(data.get('files', []))}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(DocPrint.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 3) Фото на документы (без файлов) -----------------

@dp.message(F.text == "Фото на документы")
async def idphoto_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Фото на документы", files=[])
    await ask_contact(message, state, IDPhoto.contact)

@dp.message(IDPhoto.contact)
async def idphoto_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(IDPhoto.doc_type)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Паспорт РФ"), KeyboardButton(text="Загранпаспорт")],
            [KeyboardButton(text="Удостоверение")]
        ],
        resize_keyboard=True
    )
    await message.answer("Тип документа:", reply_markup=kb)

@dp.message(IDPhoto.doc_type)
async def idphoto_doctype(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Паспорт РФ", "Загранпаспорт", "Удостоверение"}:
        await message.answer("Выберите тип документа кнопкой.")
        return
    await state.update_data(doc_type=message.text)
    await state.set_state(IDPhoto.qty)
    await message.answer("Количество (числом):", reply_markup=ReplyKeyboardRemove())

@dp.message(IDPhoto.qty)
async def idphoto_qty(message: types.Message, state: FSMContext):
    if not is_positive_int(message.text or ""):
        await message.answer("Введите количество числом (например 2).")
        return
    await state.update_data(qty=int(message.text.strip()))
    await state.set_state(IDPhoto.color)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Цветная"), KeyboardButton(text="Ч/Б")]],
        resize_keyboard=True
    )
    await message.answer("Цвет:", reply_markup=kb)

@dp.message(IDPhoto.color)
async def idphoto_color(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Цветная", "Ч/Б"}:
        await message.answer("Выберите: Цветная или Ч/Б.")
        return
    await state.update_data(color=message.text)
    await ask_comment(message, state, IDPhoto.comment)

@dp.message(IDPhoto.comment, F.text == "ПРОПУСТИТЬ")
async def idphoto_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await idphoto_confirm(message, state)

@dp.message(IDPhoto.comment)
async def idphoto_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await idphoto_confirm(message, state)

async def idphoto_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Документ: {data['doc_type']}\n"
        f"Количество: {data['qty']}\n"
        f"Цвет: {data['color']}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(IDPhoto.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 4) Оцифровка (без файлов) -----------------

@dp.message(F.text == "Оцифровка")
async def digi_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Оцифровка", files=[])
    await ask_contact(message, state, Digitization.contact)

@dp.message(Digitization.contact)
async def digi_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(Digitization.source)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Плёнка"), KeyboardButton(text="Видеокассета")],
            [KeyboardButton(text="Аудиокассета")]
        ],
        resize_keyboard=True
    )
    await message.answer("Откуда оцифровывать?", reply_markup=kb)

@dp.message(Digitization.source)
async def digi_source(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Плёнка", "Видеокассета", "Аудиокассета"}:
        await message.answer("Выберите вариант кнопкой.")
        return
    await state.update_data(source=message.text)
    await state.set_state(Digitization.qty)
    await message.answer("Количество (штук) (числом):", reply_markup=ReplyKeyboardRemove())

@dp.message(Digitization.qty)
async def digi_qty(message: types.Message, state: FSMContext):
    if not is_positive_int(message.text or ""):
        await message.answer("Введите количество числом (например 1).")
        return
    await state.update_data(qty=int(message.text.strip()))
    await state.set_state(Digitization.media_confirm)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Да, принесу носитель"), KeyboardButton(text="Нет")]],
        resize_keyboard=True
    )
    await message.answer("Результат отдаём только на съёмный носитель клиента. Принесёте?", reply_markup=kb)

@dp.message(Digitization.media_confirm)
async def digi_media(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Да, принесу носитель", "Нет"}:
        await message.answer("Выберите кнопку: Да или Нет.")
        return
    await state.update_data(media=message.text)
    await ask_comment(message, state, Digitization.comment)

@dp.message(Digitization.comment, F.text == "ПРОПУСТИТЬ")
async def digi_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await digi_confirm(message, state)

@dp.message(Digitization.comment)
async def digi_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await digi_confirm(message, state)

async def digi_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Источник: {data['source']}\n"
        f"Количество: {data['qty']}\n"
        f"Носитель: {data.get('media','-')}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(Digitization.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 5) Термопечать -----------------

@dp.message(F.text == "Термопечать")
async def thermo_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Термопечать", files=[])
    await ask_contact(message, state, ThermoPrint.contact)

@dp.message(ThermoPrint.contact)
async def thermo_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(ThermoPrint.item)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Футболка"), KeyboardButton(text="Кофта/Худи")],
            [KeyboardButton(text="Кружка"), KeyboardButton(text="Свой вариант")]
        ],
        resize_keyboard=True
    )
    await message.answer("На чём печать?", reply_markup=kb)

@dp.message(ThermoPrint.item)
async def thermo_item(message: types.Message, state: FSMContext):
    txt = (message.text or "").strip()
    if txt == "Свой вариант":
        await message.answer("Введите свой вариант (например: кепка):", reply_markup=ReplyKeyboardRemove())
        return
    if txt not in {"Футболка", "Кофта/Худи", "Кружка"}:
        # если пользователь вводом написал своё
        await state.update_data(item=txt)
    else:
        await state.update_data(item=txt)

    await state.set_state(ThermoPrint.size)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Маленький"), KeyboardButton(text="Средний")],
            [KeyboardButton(text="Большой"), KeyboardButton(text="Свой размер")]
        ],
        resize_keyboard=True
    )
    await message.answer("Размер принта:", reply_markup=kb)

@dp.message(ThermoPrint.size)
async def thermo_size(message: types.Message, state: FSMContext):
    txt = (message.text or "").strip()
    if txt == "Свой размер":
        await message.answer("Введите свой размер/описание (например: 20×25 см):", reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data(size=txt)
    await state.set_state(ThermoPrint.has_layout)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Есть макет"), KeyboardButton(text="Нет макета")]],
        resize_keyboard=True
    )
    await message.answer("Макет есть?", reply_markup=kb)

@dp.message(ThermoPrint.has_layout)
async def thermo_has_layout(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Есть макет", "Нет макета"}:
        await message.answer("Выберите: Есть макет / Нет макета.")
        return
    await state.update_data(has_layout=message.text)
    if message.text == "Есть макет":
        await state.set_state(ThermoPrint.files)
        await message.answer("Пришлите макет(ы). Когда закончите нажмите ГОТОВО.", reply_markup=done_kb)
    else:
        await ask_comment(message, state, ThermoPrint.comment)

@dp.message(ThermoPrint.files, F.photo | F.document)
async def thermo_files_add(message: types.Message, state: FSMContext):
    await add_file_to_state(message, state)
    await message.answer("Принято. Ещё файлы или ГОТОВО.")

@dp.message(ThermoPrint.files, F.text == "ГОТОВО")
async def thermo_files_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # макет логичнее требовать хотя бы один файл, но оставим мягко:
    if len(data.get("files", [])) == 0:
        await message.answer("Если макет есть, лучше приложить файл. Пришлите или нажмите /cancel и начните заново.")
        return
    await ask_comment(message, state, ThermoPrint.comment)

@dp.message(ThermoPrint.comment, F.text == "ПРОПУСТИТЬ")
async def thermo_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await thermo_confirm(message, state)

@dp.message(ThermoPrint.comment)
async def thermo_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await thermo_confirm(message, state)

async def thermo_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"На чём: {data.get('item','-')}\n"
        f"Размер: {data.get('size','-')}\n"
        f"Макет: {data.get('has_layout','-')}\n"
        f"Файлов: {len(data.get('files', []))}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(ThermoPrint.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 6) Реставрация фото (файлы опционально) -----------------

@dp.message(F.text == "Реставрация фото")
async def rest_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Реставрация фото", files=[])
    await ask_contact(message, state, Restoration.contact)

@dp.message(Restoration.contact)
async def rest_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(Restoration.task)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Убрать царапины/трещины"), KeyboardButton(text="Восстановить порванное")],
            [KeyboardButton(text="Улучшить качество/резкость"), KeyboardButton(text="Раскрасить Ч/Б")],
            [KeyboardButton(text="Убрать лишние объекты"), KeyboardButton(text="Свой вариант")],
        ],
        resize_keyboard=True
    )
    await message.answer("Что нужно сделать?", reply_markup=kb)

@dp.message(Restoration.task)
async def rest_task(message: types.Message, state: FSMContext):
    txt = (message.text or "").strip()
    if txt == "Свой вариант":
        await message.answer("Опишите, что нужно сделать:", reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data(task=txt)
    await state.set_state(Restoration.files)
    await message.answer("Прикрепите фото (если есть). Или нажмите ПРОПУСТИТЬ ФАЙЛЫ.", reply_markup=done_or_skip_files_kb)

@dp.message(Restoration.files, F.photo | F.document)
async def rest_files_add(message: types.Message, state: FSMContext):
    await add_file_to_state(message, state)
    await message.answer("Принято. Ещё файлы или ГОТОВО / ПРОПУСТИТЬ ФАЙЛЫ.")

@dp.message(Restoration.files, F.text == "ПРОПУСТИТЬ ФАЙЛЫ")
async def rest_files_skip(message: types.Message, state: FSMContext):
    await ask_comment(message, state, Restoration.comment)

@dp.message(Restoration.files, F.text == "ГОТОВО")
async def rest_files_done(message: types.Message, state: FSMContext):
    await ask_comment(message, state, Restoration.comment)

@dp.message(Restoration.comment, F.text == "ПРОПУСТИТЬ")
async def rest_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await rest_confirm(message, state)

@dp.message(Restoration.comment)
async def rest_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await rest_confirm(message, state)

async def rest_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Задача: {data.get('task','-')}\n"
        f"Файлов: {len(data.get('files', []))}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(Restoration.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 7) Визитки/буклеты/наклейки -----------------

@dp.message(F.text == "Визитки/буклеты/наклейки")
async def prod_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Визитки/буклеты/наклейки", files=[])
    await ask_contact(message, state, PrintProducts.contact)

@dp.message(PrintProducts.contact)
async def prod_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(PrintProducts.product_type)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Визитки"), KeyboardButton(text="Буклеты"), KeyboardButton(text="Наклейки")]],
        resize_keyboard=True
    )
    await message.answer("Что печатаем?", reply_markup=kb)

@dp.message(PrintProducts.product_type)
async def prod_type(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Визитки", "Буклеты", "Наклейки"}:
        await message.answer("Выберите кнопку: Визитки / Буклеты / Наклейки.")
        return
    await state.update_data(product_type=message.text)
    await state.set_state(PrintProducts.tirage)
    await message.answer("Тираж (количество) (числом):", reply_markup=ReplyKeyboardRemove())

@dp.message(PrintProducts.tirage)
async def prod_tirage(message: types.Message, state: FSMContext):
    if not is_positive_int(message.text or ""):
        await message.answer("Введите тираж числом (например 100).")
        return
    await state.update_data(tirage=int(message.text.strip()))
    await state.set_state(PrintProducts.format)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Стандартный"), KeyboardButton(text="Свой формат")]],
        resize_keyboard=True
    )
    await message.answer("Размер/формат:", reply_markup=kb)

@dp.message(PrintProducts.format)
async def prod_format(message: types.Message, state: FSMContext):
    txt = (message.text or "").strip()
    if txt == "Свой формат":
        await message.answer("Введите свой формат (например 90×50 мм):", reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data(format=txt)
    await state.set_state(PrintProducts.color)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Ч/Б"), KeyboardButton(text="Цветная")]],
        resize_keyboard=True
    )
    await message.answer("Цветность:", reply_markup=kb)

@dp.message(PrintProducts.color)
async def prod_color(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Ч/Б", "Цветная"}:
        await message.answer("Выберите: Ч/Б или Цветная.")
        return
    await state.update_data(color=message.text)
    await state.set_state(PrintProducts.has_layout)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Есть макет"), KeyboardButton(text="Нет макета")]],
        resize_keyboard=True
    )
    await message.answer("Макет есть?", reply_markup=kb)

@dp.message(PrintProducts.has_layout)
async def prod_has_layout(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Есть макет", "Нет макета"}:
        await message.answer("Выберите: Есть макет / Нет макета.")
        return
    await state.update_data(has_layout=message.text)
    if message.text == "Есть макет":
        await state.set_state(PrintProducts.files)
        await message.answer("Пришлите макет(ы). Когда закончите нажмите ГОТОВО.", reply_markup=done_kb)
    else:
        await state.set_state(PrintProducts.need_design)
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Нужен дизайн"), KeyboardButton(text="Дизайн не нужен")]],
            resize_keyboard=True
        )
        await message.answer("Нужно разработать дизайн?", reply_markup=kb)

@dp.message(PrintProducts.need_design)
async def prod_need_design(message: types.Message, state: FSMContext):
    if (message.text or "") not in {"Нужен дизайн", "Дизайн не нужен"}:
        await message.answer("Выберите кнопку: Нужен дизайн / Дизайн не нужен.")
        return
    await state.update_data(need_design=message.text)
    # если дизайн нужен, файлов нет; если не нужен, всё равно можно приложить
    await state.set_state(PrintProducts.files)
    await message.answer("Если есть материалы/логотипы, прикрепите файлы. Иначе нажмите ПРОПУСТИТЬ ФАЙЛЫ.", reply_markup=done_or_skip_files_kb)

@dp.message(PrintProducts.files, F.photo | F.document)
async def prod_files_add(message: types.Message, state: FSMContext):
    await add_file_to_state(message, state)
    await message.answer("Принято. Ещё файлы или ГОТОВО / ПРОПУСТИТЬ ФАЙЛЫ.")

@dp.message(PrintProducts.files, F.text == "ПРОПУСТИТЬ ФАЙЛЫ")
async def prod_files_skip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get("has_layout") == "Есть макет":
        await message.answer("Если макет есть, пришлите файл. Иначе выберите «Нет макета» и идём дальше.")
        return
    await ask_comment(message, state, PrintProducts.comment)

@dp.message(PrintProducts.files, F.text == "ГОТОВО")
async def prod_files_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get("has_layout") == "Есть макет" and len(data.get("files", [])) == 0:
        await message.answer("Для печати по макету нужен файл. Пришлите макет.")
        return
    await ask_comment(message, state, PrintProducts.comment)

@dp.message(PrintProducts.comment, F.text == "ПРОПУСТИТЬ")
async def prod_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await prod_confirm(message, state)

@dp.message(PrintProducts.comment)
async def prod_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await prod_confirm(message, state)

async def prod_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Тип: {data.get('product_type','-')}\n"
        f"Тираж: {data.get('tirage','-')}\n"
        f"Формат: {data.get('format','-')}\n"
        f"Цвет: {data.get('color','-')}\n"
        f"Макет: {data.get('has_layout','-')}\n"
        f"Дизайн: {data.get('need_design','-')}\n"
        f"Файлов: {len(data.get('files', []))}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(PrintProducts.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 8) Фотошоп (файлы обязательны) -----------------

@dp.message(F.text == "Фотошоп")
async def ps_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Фотошоп", files=[])
    await ask_contact(message, state, Photoshop.contact)

@dp.message(Photoshop.contact)
async def ps_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(Photoshop.task)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ретушь"), KeyboardButton(text="Замена фона")],
            [KeyboardButton(text="Удаление объектов"), KeyboardButton(text="Коллаж")],
            [KeyboardButton(text="Восстановление"), KeyboardButton(text="Подготовка к печати")],
            [KeyboardButton(text="Другое")]
        ],
        resize_keyboard=True
    )
    await message.answer("Задача:", reply_markup=kb)

@dp.message(Photoshop.task)
async def ps_task(message: types.Message, state: FSMContext):
    txt = (message.text or "").strip()
    if txt == "Другое":
        await message.answer("Опишите задачу своими словами:", reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data(task=txt)
    await state.set_state(Photoshop.dont_change)
    await message.answer("Что точно нельзя менять? (или ПРОПУСТИТЬ)", reply_markup=skip_kb)

@dp.message(Photoshop.dont_change, F.text == "ПРОПУСТИТЬ")
async def ps_dont_change_skip(message: types.Message, state: FSMContext):
    await state.update_data(dont_change="")
    await state.set_state(Photoshop.files)
    await message.answer("Пришлите исходники (файлы обязательны). Когда закончите нажмите ГОТОВО.", reply_markup=done_kb)

@dp.message(Photoshop.dont_change)
async def ps_dont_change(message: types.Message, state: FSMContext):
    await state.update_data(dont_change=(message.text or "").strip())
    await state.set_state(Photoshop.files)
    await message.answer("Пришлите исходники (файлы обязательны). Когда закончите нажмите ГОТОВО.", reply_markup=done_kb)

@dp.message(Photoshop.files, F.photo | F.document)
async def ps_files_add(message: types.Message, state: FSMContext):
    await add_file_to_state(message, state)
    await message.answer("Принято. Ещё файлы или ГОТОВО.")

@dp.message(Photoshop.files, F.text == "ГОТОВО")
async def ps_files_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if len(data.get("files", [])) == 0:
        await message.answer("Для фотошопа нужны исходники. Пришлите хотя бы один файл.")
        return
    await ask_comment(message, state, Photoshop.comment)

@dp.message(Photoshop.comment, F.text == "ПРОПУСТИТЬ")
async def ps_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await ps_confirm(message, state)

@dp.message(Photoshop.comment)
async def ps_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await ps_confirm(message, state)

async def ps_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Задача: {data.get('task','-')}\n"
        f"Нельзя менять: {data.get('dont_change') or '-'}\n"
        f"Файлов: {len(data.get('files', []))}\n"
        f"Комментарий: {data.get('comment') or '-'}\n\n"
        "Примечание: подделку документов не делаем."
    )
    await state.set_state(Photoshop.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- 9) Другое (описание + файлы опционально) -----------------

@dp.message(F.text == "Другое")
async def other_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(service="Другое", files=[])
    await ask_contact(message, state, Other.contact)

@dp.message(Other.contact)
async def other_contact(message: types.Message, state: FSMContext):
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer("Нужен номер на 8… (11 цифр). Пример: 89123456789")
        return
    await state.update_data(contact=phone)
    await state.set_state(Other.desc)
    await message.answer("Опишите, что нужно сделать:", reply_markup=ReplyKeyboardRemove())

@dp.message(Other.desc)
async def other_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=(message.text or "").strip())
    await state.set_state(Other.files)
    await message.answer("Если нужно, прикрепите файлы. Или нажмите ПРОПУСТИТЬ ФАЙЛЫ.", reply_markup=done_or_skip_files_kb)

@dp.message(Other.files, F.photo | F.document)
async def other_files_add(message: types.Message, state: FSMContext):
    await add_file_to_state(message, state)
    await message.answer("Принято. Ещё файлы или ГОТОВО / ПРОПУСТИТЬ ФАЙЛЫ.")

@dp.message(Other.files, F.text == "ПРОПУСТИТЬ ФАЙЛЫ")
async def other_files_skip(message: types.Message, state: FSMContext):
    await ask_comment(message, state, Other.comment)

@dp.message(Other.files, F.text == "ГОТОВО")
async def other_files_done(message: types.Message, state: FSMContext):
    await ask_comment(message, state, Other.comment)

@dp.message(Other.comment, F.text == "ПРОПУСТИТЬ")
async def other_comment_skip(message: types.Message, state: FSMContext):
    await state.update_data(comment="")
    await other_confirm(message, state)

@dp.message(Other.comment)
async def other_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=(message.text or "").strip())
    await other_confirm(message, state)

async def other_confirm(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary = (
        "Проверьте заказ:\n"
        f"Услуга: {data['service']}\n"
        f"Контакт: {data['contact']}\n"
        f"Описание: {data.get('desc','-')}\n"
        f"Файлов: {len(data.get('files', []))}\n"
        f"Комментарий: {data.get('comment') or '-'}"
    )
    await state.set_state(Other.confirm)
    await message.answer(summary + "\n\nВсё верно?", reply_markup=confirm_kb)

# ----------------- Finalize common -----------------

async def finalize_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_no = next_order_number()

    text = (
        f"Заказ №{order_no}\n"
        f"Дата: {now_str()}\n"
        f"Клиент: {user_ref(message.from_user)}\n"
        f"Контакт: {data.get('contact','-')}\n"
        f"Услуга: {data.get('service','-')}\n"
    )

    service = data.get("service")

    if service == "Печать фото":
        text += (
            f"Размер: {data.get('size','-')}\n"
            f"Бумага: {data.get('paper','-')}\n"
            f"Копий: {data.get('copies','-')}\n"
        )
    elif service == "Печать документов":
        text += (
            f"Формат: {data.get('format','-')}\n"
            f"Копий: {data.get('copies','-')}\n"
            f"Цвет: {data.get('color','-')}\n"
            f"Печать: {data.get('duplex','-')}\n"
            f"Страницы: {data.get('pages','-')}\n"
        )
    elif service == "Фото на документы":
        text += (
            f"Документ: {data.get('doc_type','-')}\n"
            f"Количество: {data.get('qty','-')}\n"
            f"Цвет: {data.get('color','-')}\n"
        )
    elif service == "Оцифровка":
        text += (
            f"Источник: {data.get('source','-')}\n"
            f"Количество: {data.get('qty','-')}\n"
            f"Носитель: {data.get('media','-')}\n"
        )
    elif service == "Термопечать":
        text += (
            f"На чём: {data.get('item','-')}\n"
            f"Размер принта: {data.get('size','-')}\n"
            f"Макет: {data.get('has_layout','-')}\n"
        )
    elif service == "Реставрация фото":
        text += f"Задача: {data.get('task','-')}\n"
    elif service == "Визитки/буклеты/наклейки":
        text += (
            f"Тип: {data.get('product_type','-')}\n"
            f"Тираж: {data.get('tirage','-')}\n"
            f"Формат: {data.get('format','-')}\n"
            f"Цвет: {data.get('color','-')}\n"
            f"Макет: {data.get('has_layout','-')}\n"
            f"Дизайн: {data.get('need_design','-')}\n"
        )
    elif service == "Фотошоп":
        text += (
            f"Задача: {data.get('task','-')}\n"
            f"Нельзя менять: {data.get('dont_change') or '-'}\n"
        )
    elif service == "Другое":
        text += f"Описание: {data.get('desc','-')}\n"

    comment = data.get("comment") or ""
    text += f"Комментарий: {comment if comment else '-'}\n"

    files: List[FileItem] = data.get("files", [])
    text += f"Файлов: {len(files)}\n"

    append_order(text)

    await bot.send_message(ADMIN_ID, "📥 НОВАЯ ЗАЯВКА\n\n" + text)
    if files:
        await send_files_to_admin(files)

    await message.answer(
        f"✅ Заявка принята. Номер заказа: {order_no}\nОжидайте, мы свяжемся с вами.",
        reply_markup=start_kb
    )
    await state.clear()

@dp.message(F.text == "✅ Отправить")
async def confirm_send(message: types.Message, state: FSMContext):
    cur = await state.get_state()
    ok_states = {
        PhotoPrint.confirm.state,
        DocPrint.confirm.state,
        IDPhoto.confirm.state,
        Digitization.confirm.state,
        ThermoPrint.confirm.state,
        Restoration.confirm.state,
        PrintProducts.confirm.state,
        Photoshop.confirm.state,
        Other.confirm.state,
    }
    if cur in ok_states:
        await finalize_order(message, state)
    else:
        await message.answer("Сначала оформим заказ. Нажмите «Создать заказ».", reply_markup=start_kb)

# ----------------- Missing branch fixups (inputs for 'Свой вариант' / 'Свой размер' / custom formats) -----------------
# Эти три хендлера ловят свободный ввод там, где мы предложили "Свой ..." и попросили текст.

@dp.message(F.text, ThermoPrint.item)
async def thermo_item_custom(message: types.Message, state: FSMContext):
    # сюда попадём, если пользователь после "Свой вариант" написал текст
    await state.update_data(item=(message.text or "").strip())
    await state.set_state(ThermoPrint.size)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Маленький"), KeyboardButton(text="Средний")],
            [KeyboardButton(text="Большой"), KeyboardButton(text="Свой размер")]
        ],
        resize_keyboard=True
    )
    await message.answer("Размер принта:", reply_markup=kb)

@dp.message(F.text, ThermoPrint.size)
async def thermo_size_custom(message: types.Message, state: FSMContext):
    # сюда попадём, если пользователь после "Свой размер" написал текст
    await state.update_data(size=(message.text or "").strip())
    await state.set_state(ThermoPrint.has_layout)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Есть макет"), KeyboardButton(text="Нет макета")]],
        resize_keyboard=True
    )
    await message.answer("Макет есть?", reply_markup=kb)

@dp.message(F.text, PrintProducts.format)
async def prod_format_custom(message: types.Message, state: FSMContext):
    # сюда попадём после "Свой формат" (ввёл вручную)
    await state.update_data(format=(message.text or "").strip())
    await state.set_state(PrintProducts.color)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Ч/Б"), KeyboardButton(text="Цветная")]],
        resize_keyboard=True
    )
    await message.answer("Цветность:", reply_markup=kb)

@dp.message(F.text, Restoration.task)
async def rest_task_custom(message: types.Message, state: FSMContext):
    # после "Свой вариант" описали задачу
    await state.update_data(task=(message.text or "").strip())
    await state.set_state(Restoration.files)
    await message.answer("Прикрепите фото (если есть). Или нажмите ПРОПУСТИТЬ ФАЙЛЫ.", reply_markup=done_or_skip_files_kb)

@dp.message(F.text, Photoshop.task)
async def ps_task_custom(message: types.Message, state: FSMContext):
    # после "Другое" описали задачу
    await state.update_data(task=(message.text or "").strip())
    await state.set_state(Photoshop.dont_change)
    await message.answer("Что точно нельзя менять? (или ПРОПУСТИТЬ)", reply_markup=skip_kb)

# ----------------- Run -----------------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())