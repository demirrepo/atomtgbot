import asyncio
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    add_user, process_subscription, get_total_users_count, 
    get_all_user_ids
)

router = Router()

ADMIN_ID = 1448159070
PRIVATE_GROUP_ID = -1004430339073 # <-- GURUH ID SINI SHU YERGA YOZING
PRIVATE_GROUP_LINK = "https://t.me/+PQGtzPqUxmNjZjYy" # <-- HAVOLANI SHU YERGA YOZING
CHANNELS_TO_CHECK = ["@atommasterklass", "@atom_urganch"]

class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔗 Yopiq guruhga kirish")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Quyidagilardan birini tanlang..."
)

# --------------------------------------------------
# HELPER: STRICT SUBSCRIPTION CHECK
# --------------------------------------------------
async def force_subscription(bot: Bot, user_id: int) -> bool:
    for channel in CHANNELS_TO_CHECK:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False 
    return True

async def send_subscription_warning(message_or_callback):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 1 - Kanal", url="https://t.me/atommasterklass")],
        [InlineKeyboardButton(text="📢 2 - Kanal", url="https://t.me/atom_urganch")],
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]
    ])
    text = (
        "🛑 <b>Kechirasiz, guruhga qo'shilish va unda qolish uchun kanallarimizdan chiqib ketmasligingiz kerak!</b>\n\n"
        "Iltimos, quyidagi kanallarga obuna bo'ling va 'Tasdiqlash' tugmasini bosing:"
    )
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# --------------------------------------------------
# GROUP INTERCEPTOR: BAN USERS WHO LEFT CHANNELS
# --------------------------------------------------
@router.message(F.chat.id == PRIVATE_GROUP_ID)
async def enforce_group_rules(message: Message, bot: Bot):
    if message.from_user.is_bot:
        return

    try:
        # Skip admins so the bot doesn't try to ban you
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in ['creator', 'administrator']:
            return

        is_subbed = await force_subscription(bot, message.from_user.id)
        if not is_subbed:
            # Delete their message and ban them
            await message.delete()
            await bot.ban_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
    except Exception as e:
        print(f"Banning error: {e}")

# --------------------------------------------------
# PRIVATE DM HANDLERS
# --------------------------------------------------
@router.message(CommandStart(), F.chat.type == "private")
async def start_handler(message: Message, bot: Bot):
    await add_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    if not await force_subscription(bot, message.from_user.id):
        await send_subscription_warning(message)
        return
        
    await message.answer(
        f"Salom, <b>{message.from_user.first_name}</b>! 🎉\n\n"
        "Siz kanallarimizga a'zosiz. Yopiq guruhga kirish uchun pastdagi tugmani bosing:",
        reply_markup=main_menu,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "check_sub")
async def check_subscription_handler(callback: CallbackQuery, bot: Bot):
    if not await force_subscription(bot, callback.from_user.id):
        await callback.answer("❌ Siz hali hamma kanalga obuna bo'lmadingiz yoxud chiqib ketgansiz!", show_alert=True)
        return

    await process_subscription(callback.from_user.id)
    await callback.message.edit_text("🎉 <b>Obuna tasdiqlandi!</b>", parse_mode="HTML")
    
    await callback.message.answer(
        "👇 <i>Yopiq guruhga kirish uchun quyidagi havoladan foydalaning:</i>\n\n"
        f"🔗 {PRIVATE_GROUP_LINK}\n\n"
        "⚠️ <b>Diqqat:</b> Agar kanallardan chiqib ketsangiz, bot sizni guruhdan avtomatik ravishda o'chiradi!",
        reply_markup=main_menu,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(F.text == "🔗 Yopiq guruhga kirish", F.chat.type == "private")
async def group_link_handler(message: Message, bot: Bot):
    if not await force_subscription(bot, message.from_user.id):
        await send_subscription_warning(message)
        return

    await message.answer(
        "👇 <i>Yopiq guruhimiz havolasi:</i>\n\n"
        f"🔗 {PRIVATE_GROUP_LINK}\n\n"
        "⚠️ <b>Diqqat:</b> Agar kanallardan chiqib ketsangiz, bot sizni guruhdan avtomatik ravishda o'chiradi!",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# --------------------------------------------------
# ADMIN BROADCAST HANDLERS
# --------------------------------------------------
@router.message(Command("admin"), F.chat.type == "private")
async def admin_panel_handler(message: Message):
    if message.from_user.id != ADMIN_ID: return
        
    total_users = await get_total_users_count()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Hammaga xabar yuborish", callback_data="admin_broadcast")]
    ])
    
    await message.answer(
        "👑 <b>Admin paneliga xush kelibsiz!</b>\n\n"
        f"👥 Botdagi jami foydalanuvchilar: <b>{total_users} ta</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("✍️ Ishtirokchilarga yubormoqchi bo'lgan xabaringizni yuboring.")
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_message, F.chat.type == "private")
async def execute_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
        
    user_ids = await get_all_user_ids()
    success_count = 0
    await message.answer("⏳ Barchaga xabar yuborish boshlandi... Kuting.")
    
    for user_id in user_ids:
        try:
            await message.copy_to(chat_id=user_id)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass 
            
    await message.answer(f"✅ Xabar tarqatish yakunlandi!\n\n👥 Qabul qildi: <b>{success_count} ta</b> foydalanuvchi.", parse_mode="HTML")
    await state.clear()