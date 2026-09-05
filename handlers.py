import asyncio
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ChatMemberUpdated
)
from aiogram.filters import CommandStart, Command
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, IS_NOT_MEMBER
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    add_user, get_total_users_count, get_all_user_ids,
    set_user_joined_status, get_user_status
)

router = Router()

ADMIN_ID = 1448159070  # confirm this is YOUR real Telegram ID (check via @userinfobot)

MANDATORY_GROUP_IDS = [-1003611114564, -1001386900457]

PRIVATE_GROUP_LINK = "https://t.me/+PQGtzPqUxmNjZjYy"
PRIVATE_GROUP_ID = -1004430339073

class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()

async def force_subscription(bot: Bot, user_id: int) -> bool:
    for chat_id in MANDATORY_GROUP_IDS:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

def get_sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 1 - Kanal", url="https://t.me/atommasterklass")],
        [InlineKeyboardButton(text="📢 2 - Kanal", url="https://t.me/atom_urganch")],
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]
    ])

def get_link_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Yopiq guruh linkini olish", callback_data="get_group_link")]
    ])

# --------------------------------------------------
# TEMPORARY: get a chat's numeric ID
# Delete once you no longer need it
# --------------------------------------------------
@router.message(Command("groupid"))
async def show_group_id(message: Message):
    await message.answer(f"This chat's ID is: {message.chat.id}")

# --------------------------------------------------
# USER JOURNEY
# --------------------------------------------------
@router.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    await add_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or "",
        referred_by=None
    )

    if await force_subscription(bot, message.from_user.id):
        await set_user_joined_status(message.from_user.id, True)
        await message.answer(
            f"Salom, <b>{message.from_user.first_name}</b>! 👋\n\n"
            "Barcha kanallarga a'zosiz! Yopiq guruhga kirish uchun quyidagi tugmani bosing:",
            reply_markup=get_link_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"Salom, <b>{message.from_user.first_name}</b>! 👋\n\n"
            "Maxsus darslar va materiallarga kirish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=get_sub_keyboard(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "check_sub")
async def check_subscription_handler(callback: CallbackQuery, bot: Bot):
    if await force_subscription(bot, callback.from_user.id):
        await set_user_joined_status(callback.from_user.id, True)
        await callback.message.edit_text(
            "🎉 <b>Rahmat!</b> Obuna tasdiqlandi.\n\nYopiq guruhga kirish uchun quyidagi tugmani bosing:",
            reply_markup=get_link_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Siz hali hamma kanalga a'zo bo'lmadingiz!", show_alert=True)

@router.callback_query(F.data == "get_group_link")
async def get_group_link_handler(callback: CallbackQuery, bot: Bot):
    if await force_subscription(bot, callback.from_user.id):
        await callback.message.answer(
            f"🔗 Yopiq guruhga kirish havolasi:\n\n{PRIVATE_GROUP_LINK}",
            disable_web_page_preview=True
        )
        await callback.answer()
    else:
        await callback.answer(
            "❌ Siz kanallardan birini tark etgansiz. Qaytadan a'zo bo'ling.",
            show_alert=True
        )

# --------------------------------------------------
# WATCH FOR PEOPLE LEAVING A MANDATORY CHANNEL
# --------------------------------------------------
@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER >> IS_NOT_MEMBER))
async def user_left_mandatory_channel(event: ChatMemberUpdated, bot: Bot):
    if event.chat.id not in MANDATORY_GROUP_IDS:
        return

    user_id = event.new_chat_member.user.id

    had_access = await get_user_status(user_id)
    if not had_access:
        return

    try:
        await bot.ban_chat_member(PRIVATE_GROUP_ID, user_id)
        await bot.unban_chat_member(PRIVATE_GROUP_ID, user_id)
    except Exception:
        pass

    await set_user_joined_status(user_id, False)

    try:
        await bot.send_message(
            user_id,
            "⚠️ Siz majburiy kanallardan birini tark etdingiz.\n\n"
            "Yopiq guruhdagi kirish huquqingiz bekor qilindi. "
            "Qayta kirish uchun ikkala kanalga qaytadan a'zo bo'ling va /start bosing."
        )
    except Exception:
        pass

# --------------------------------------------------
# ADMIN
# --------------------------------------------------
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Hammaga xabar yuborish", callback_data="admin_broadcast")]
    ])

@router.message(F.text == "/admin")
async def admin_panel_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    total_users = await get_total_users_count()
    await message.answer(
        "👑 <b>Admin paneliga xush kelibsiz!</b>\n\n"
        f"👥 Botdan ro'yxatdan o'tganlar: <b>{total_users} ta</b>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("✍️ Ishtirokchilarga yubormoqchi bo'lgan xabaringizni yuboring.")
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_message)
async def execute_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
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