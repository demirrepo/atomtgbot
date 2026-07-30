import asyncio
import io
import csv
from urllib.parse import quote
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    BufferedInputFile,
    FSInputFile
)
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Import all our database functions
from database import (
    add_user, process_subscription, get_top_users, 
    get_user_score, get_user_status, get_total_users_count, 
    get_all_user_ids, get_contest_status, toggle_contest_status,
    get_all_results, reset_database
)

# A router groups your handlers together
router = Router()

# Admin's Telegram ID
ADMIN_ID = 1448159070

# FSM State for admin broadcasting
class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()

# Persistent main menu
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="🔗 Shaxsiy havola")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Quyidagilardan birini tanlang..."
)

CHANNELS_TO_CHECK = ["@atommasterklass", "@atom_urganch"]

# --------------------------------------------------
# HELPER: STRICT SUBSCRIPTION CHECK
# --------------------------------------------------
async def force_subscription(bot: Bot, user_id: int) -> bool:
    """Returns True if user is in all channels, False otherwise."""
    for channel in CHANNELS_TO_CHECK:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False # Treat errors (bot not admin) as unsubscribed to be safe
    return True

async def send_subscription_warning(message_or_callback):
    """Sends the warning message with inline buttons to subscribe."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 1 - Kanal", url="https://t.me/atommasterklass")],
        [InlineKeyboardButton(text="📢 2 - Kanal", url="https://t.me/atom_urganch")],
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]
    ])
    text = (
        "🛑 <b>Kechirasiz, botdan foydalanish uchun kanallarimizdan chiqib ketmasligingiz kerak!</b>\n\n"
        "Iltimos, quyidagi kanallarga qayta obuna bo'ling va 'Tasdiqlash' tugmasini bosing:"
    )
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# --------------------------------------------------
# HELPER: SEND PROMO POST
# --------------------------------------------------
async def send_promo_post(bot: Bot, user_id: int, send_method):
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    promo_text = (
        "Assalomu aleykum!\n\n"
        "ATOM o'quv markazi 3-avgust kuni kuzgi milliy sertifikat imtihoniga intensiv online kurslariga start beradi!\n"
        "Eng qizig'i siz bu kursda tekinga o'qishingiz mumkin.\n"
        "Shartlar judayam oson!\n\n"
        "Bot sizga referal ssilka beradi, ana shu ssilkani siz kimyoga qiziquvchi do'stlaringizga yuborasiz.\n"
        "Ular botdan ro'yxatdan o'tib kanallarga obuna bo'lsa, sizga har bir taklif qilgan do'stingiz uchun +5 ball beriladi!\n\n"
        "Eng ko'p ball to'plagan 5 nafar qatnashuvchini tanlab olib ONLINE kurslarimizda bepul o'qitamiz!\n"
        "Biz bilan A+ sari harakatni boshlang!\n"
        "Batafsil malumot uchun:\n"
        "@ONLINE_ATOM\n"
        "TEL: +998938968909\n\n"
        f"👇 Shaxsiy havolangiz:\n<code>{referral_link}</code>"
    )

    share_text = quote("ATOM o'quv markazining bepul intensiv kursiga qo'shiling! 🚀")
    share_url = f"https://t.me/share/url?url={referral_link}&text={share_text}"

    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Ishtirok etish 🔥", url=share_url)

    # Ensure "promo.jpg" is uploaded to your Render project folder!
    photo = FSInputFile("promo.jpg")

    await send_method(
        photo=photo, 
        caption=promo_text,
        reply_markup=builder.as_markup()
    )


# --------------------------------------------------
# USER HANDLERS
# --------------------------------------------------

@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject, bot: Bot):
    args = command.args
    referred_by = None
    if args and args.isdigit():
        referred_by = int(args)
        if referred_by == message.from_user.id:
            referred_by = None

    is_active = await get_contest_status()
    has_joined = await get_user_status(message.from_user.id)
    
    if not is_active:
        if has_joined:
            await message.answer(
                "🛑 <b>Tanlov o'z nihoyasiga yetgan!</b>\n\n"
                "Siz o'z yakuniy natijalaringiz va reyting bilan tanishishingiz mumkin:", 
                reply_markup=main_menu, 
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Kechirasiz, tanlov o'z nihoyasiga yetgan. Tez orada g'oliblarni e'lon qilamiz!", parse_mode="HTML")
        return

    await add_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referred_by=referred_by
    )

    if has_joined:
        # Before letting them use the bot, verify they haven't left the channels
        if not await force_subscription(bot, message.from_user.id):
            await send_subscription_warning(message)
            return
            
        await message.answer(
            f"Siz allaqachon tanlovda ishtirok etyapsiz, <b>{message.from_user.first_name}</b>! 🎉\n\n"
            "Quyidagi menyudan foydalanishingiz mumkin:",
            reply_markup=main_menu,
            parse_mode="HTML"
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 1 - Kanal", url="https://t.me/atommasterklass")],
        [InlineKeyboardButton(text="📢 2 - Kanal", url="https://t.me/atom_urganch")],
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]
    ])

    await message.answer(
        f"Salom, <b>{message.from_user.first_name}</b>! 👋\n\n"
        "Tanlovda ishtirok etish va o'z havolangizni olish uchun, avval quyidagi rasmiy kanallarimizga obuna bo'lishingiz kerak.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "check_sub")
async def check_subscription_handler(callback: CallbackQuery, bot: Bot):
    is_active = await get_contest_status()
    if not is_active:
        await callback.answer("❌ Tanlov yakunlangan, endi ro'yxatdan o'tish imkoni yo'q.", show_alert=True)
        return
    
    if not await force_subscription(bot, callback.from_user.id):
        await callback.answer("❌ Siz hali hamma kanalga obuna bo'lmadingiz yoxud chiqib ketgansiz!", show_alert=True)
        return

    await process_subscription(callback.from_user.id)
    
    await callback.message.edit_text("🎉 <b>Obuna tasdiqlandi!</b>", parse_mode="HTML")
    
    # Send them the full image promo post directly!
    await send_promo_post(bot, callback.from_user.id, callback.message.answer_photo)
    
    await callback.message.answer(
        "👇 <i>Asosiy menyudan kerakli bo'limni tanlang:</i>",
        reply_markup=main_menu,
        parse_mode="HTML"
    )

@router.message(Command("reyting"))
@router.message(F.text == "🏆 Reyting")
async def leaderboard_handler(message: Message, bot: Bot):
    # Strict check before showing leaderboard
    if not await force_subscription(bot, message.from_user.id):
        await send_subscription_warning(message)
        return

    top_users = await get_top_users()
    user_score = await get_user_score(message.from_user.id)
    
    if not top_users:
        await message.answer("🏆 <b>Hozircha reytingda hech kim yo'q.</b>\n\nDo'stlaringizni taklif qilib, birinchi bo'lishga shoshiling!", parse_mode="HTML")
        return
        
    text = "🏆 <b>Eng faol ishtirokchilar reytingi:</b>\n\n"
    for i, (name, score) in enumerate(top_users, start=1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name} — {score} ball\n"
        
    text += f"\n🎯 <b>Sizning balingiz:</b> {user_score} ball"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("statistika"))
@router.message(F.text == "📊 Statistika")
async def my_stats_handler(message: Message, bot: Bot):
    # Strict check before showing stats
    if not await force_subscription(bot, message.from_user.id):
        await send_subscription_warning(message)
        return

    user_score = await get_user_score(message.from_user.id)
    text = (
        f"👤 <b>Shaxsiy statistikangiz:</b>\n\n"
        f"👥 To'plagan balingiz: <b>{user_score} ball</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔗 Shaxsiy havola")
async def referral_link_handler(message: Message, bot: Bot):
    # Strict check before generating link
    if not await force_subscription(bot, message.from_user.id):
        await send_subscription_warning(message)
        return

    # Use the helper function to send the full image post
    await send_promo_post(bot, message.from_user.id, message.answer_photo)

# --------------------------------------------------
# ADMIN HANDLERS (Unchanged, left exactly as you had them)
# --------------------------------------------------

def get_admin_keyboard(is_active: bool):
    toggle_text = "🛑 Tanlovni to'xtatish" if is_active else "✅ Tanlovni boshlash"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Hammaga xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text=toggle_text, callback_data="toggle_contest")],
        [InlineKeyboardButton(text="💾 Natijalarni yuklab olish", callback_data="download_results")],
        [InlineKeyboardButton(text="♻️ Bazani tozalash (Yangi tanlov)", callback_data="reset_db_warning")]
    ])

@router.message(Command("admin"))
async def admin_panel_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda bu buyruqdan foydalanish huquqi yo'q.")
        return
        
    total_users = await get_total_users_count()
    is_active = await get_contest_status()
    status_text = "🟢 Faol" if is_active else "🔴 To'xtatilgan"
    
    await message.answer(
        "👑 <b>Admin paneliga xush kelibsiz!</b>\n\n"
        f"👥 Botdagi jami ishtirokchilar: <b>{total_users} ta</b>\n"
        f"📊 Tanlov holati: <b>{status_text}</b>",
        reply_markup=get_admin_keyboard(is_active),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "toggle_contest")
async def toggle_contest_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
        
    new_status = await toggle_contest_status()
    total_users = await get_total_users_count()
    status_text = "🟢 Faol" if new_status else "🔴 To'xtatilgan"
    
    await callback.message.edit_text(
        "👑 <b>Admin paneliga xush kelibsiz!</b>\n\n"
        f"👥 Botdagi jami ishtirokchilar: <b>{total_users} ta</b>\n"
        f"📊 Tanlov holati: <b>{status_text}</b>",
        reply_markup=get_admin_keyboard(new_status),
        parse_mode="HTML"
    )
    
    popup_msg = "✅ Tanlov boshlandi!" if new_status else "🛑 Tanlov to'xtatildi! Endi hech kim ball yig'a olmaydi."
    await callback.answer(popup_msg, show_alert=True)

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
        
    await callback.message.answer(
        "✍️ Ishtirokchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "(Matn, rasm yoki videolardan ham foydalanishingiz mumkin. Eslatma: xabar darhol barchaga ketadi!)"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_message)
async def execute_broadcast(message: Message, state: FSMContext, bot: Bot):
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

@router.callback_query(F.data == "download_results")
async def download_results_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
        
    results = await get_all_results()
    
    if not results:
        await callback.answer("❌ Bazada foydalanuvchilar yo'q!", show_alert=True)
        return
        
    file = io.StringIO()
    writer = csv.writer(file)
    writer.writerow(["ID", "Ism", "Familiya", "Ball"])
    
    for row in results:
        writer.writerow([row[0], row[1], row[2], row[3]])
        
    csv_bytes = file.getvalue().encode('utf-8-sig')
    document = BufferedInputFile(csv_bytes, filename="Tanlov_Natijalari.csv")
    
    await callback.message.answer_document(
        document=document,
        caption="📊 <b>Barcha ishtirokchilarning yakuniy natijalari.</b>\n\nBu faylni Excel dasturida ochishingiz mumkin.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "reset_db_warning")
async def reset_db_warning_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ HA, BARCHASINI O'CHIRISH", callback_data="confirm_reset")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_reset")]
    ])
    
    await callback.message.edit_text(
        "⚠️ <b>DIQQAT! BAZANI TOZALASH</b> ⚠️\n\n"
        "Siz chindan ham barcha ishtirokchilarni va ularning ballarini o'chirib yubormoqchimisiz?\n\n"
        "<i>(Agar natijalarni saqlab olmagan bo'lsangiz, avval 'Natijalarni yuklab olish' tugmasini bosing!)</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "cancel_reset")
async def cancel_reset_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    
    total_users = await get_total_users_count()
    is_active = await get_contest_status()
    status_text = "🟢 Faol" if is_active else "🔴 To'xtatilgan"
    
    await callback.message.edit_text(
        "👑 <b>Admin paneliga xush kelibsiz!</b>\n\n"
        f"👥 Botdagi jami ishtirokchilar: <b>{total_users} ta</b>\n"
        f"📊 Tanlov holati: <b>{status_text}</b>",
        reply_markup=get_admin_keyboard(is_active),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "confirm_reset")
async def confirm_reset_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
        
    await reset_database()
    
    await callback.message.edit_text(
        "✅ <b>Baza muvaffaqiyatli tozalandi!</b>\n\n"
        "Tanlov to'xtatilgan holatda turibdi. Yangi tanlovni boshlash uchun /admin menyusidan 'Tanlovni boshlash' tugmasini bosing.",
        parse_mode="HTML"
    )