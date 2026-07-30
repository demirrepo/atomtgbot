import asyncio
import io
import csv
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    BufferedInputFile
)
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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
ADMIN_ID = 6201090116

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

# --------------------------------------------------
# USER HANDLERS
# --------------------------------------------------

@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject, bot: Bot):
    # 1. Extract referrer ID
    args = command.args
    referred_by = None
    if args and args.isdigit():
        referred_by = int(args)
        if referred_by == message.from_user.id:
            referred_by = None

    # 2. Check if the contest is active and if user has already joined
    is_active = await get_contest_status()
    has_joined = await get_user_status(message.from_user.id)
    
    # 3. Contest is stopped logic
    if not is_active:
        if has_joined:
            await message.answer(
                "🛑 <b>Tanlov o'z nihoyasiga yetgan!</b>\n\n"
                "Siz o'z yakuniy natijalaringiz va reyting bilan tanishishingiz mumkin:", 
                reply_markup=main_menu, 
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Kechirasiz, tanlov o'z nihoyasiga yetgan. Tez orada g'oliblarni e'lon qilamiz!", 
                parse_mode="HTML"
            )
        return

    # 4. Add user to database (if active)
    await add_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referred_by=referred_by
    )

    # 5. If they already verified subscription previously
    if has_joined:
        await message.answer(
            f"Siz allaqachon tanlovda ishtirok etyapsiz, <b>{message.from_user.first_name}</b>! 🎉\n\n"
            "Quyidagi menyudan foydalanishingiz mumkin:",
            reply_markup=main_menu,
            parse_mode="HTML"
        )
        return

    # 6. New users must subscribe
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
    # Don't allow verifying if the contest was stopped while they were joining
    is_active = await get_contest_status()
    if not is_active:
        await callback.answer("❌ Tanlov yakunlangan, endi ro'yxatdan o'tish imkoni yo'q.", show_alert=True)
        return

    channels_to_check = ["@atommasterklass", "@atom_urganch"]
    
    for channel in channels_to_check:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=callback.from_user.id)
            if member.status in ["left", "kicked"]:
                await callback.answer("❌ Siz hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)
                return
        except Exception:
            await callback.answer("Xatolik yuz berdi. Bot kanallarda admin ekanligini tekshiring!", show_alert=True)
            return

    await process_subscription(callback.from_user.id)
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    
    await callback.message.edit_text("🎉 <b>Obuna tasdiqlandi!</b>", parse_mode="HTML")
    
    await callback.message.answer(
        "Do'stlaringizga yuborish uchun shaxsiy havolangiz:\n\n"
        f"<code>{referral_link}</code>\n\n"
        "Ushbu havola orqali qo'shilgan har bir do'stingiz uchun 1 ballga ega bo'lasiz!\n\n"
        "👇 <i>Asosiy menyudan kerakli bo'limni tanlang:</i>",
        reply_markup=main_menu,
        parse_mode="HTML"
    )

@router.message(Command("reyting"))
@router.message(F.text == "🏆 Reyting")
async def leaderboard_handler(message: Message):
    top_users = await get_top_users()
    user_score = await get_user_score(message.from_user.id)
    
    if not top_users:
        await message.answer(
            "🏆 <b>Hozircha reytingda hech kim yo'q.</b>\n\n"
            "Do'stlaringizni taklif qilib, birinchi bo'lishga shoshiling!", 
            parse_mode="HTML"
        )
        return
        
    text = "🏆 <b>Eng faol ishtirokchilar reytingi:</b>\n\n"
    for i, (name, score) in enumerate(top_users, start=1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name} — {score} ball\n"
        
    text += f"\n🎯 <b>Sizning balingiz:</b> {user_score} ball"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("statistika"))
@router.message(F.text == "📊 Statistika")
async def my_stats_handler(message: Message):
    user_score = await get_user_score(message.from_user.id)
    text = (
        f"👤 <b>Shaxsiy statistikangiz:</b>\n\n"
        f"👥 Taklif qilgan do'stlaringiz soni: <b>{user_score} ta</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔗 Shaxsiy havola")
async def referral_link_handler(message: Message):
    bot_info = await message.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    
    text = (
        f"🔗 <b>Sizning shaxsiy havolangiz:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"<i>Ushbu havolani do'stlaringizga yuboring va ko'proq ball yig'ing!</i>"
    )
    await message.answer(text, parse_mode="HTML")

# --------------------------------------------------
# ADMIN HANDLERS
# --------------------------------------------------

# Helper function to generate admin keyboard
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

# --- BROADCASTING LOGIC ---
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

# --- RESULTS & RESET LOGIC ---
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
        
    csv_bytes = file.getvalue().encode('utf-8-sig') # utf-8-sig helps Excel read special characters properly
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
    
    # Take them safely back to the admin menu
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