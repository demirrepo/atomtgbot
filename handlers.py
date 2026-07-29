from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, CommandObject, Command
from database import add_user, process_subscription, get_top_users, get_user_score, get_user_status, get_total_users_count, get_all_user_ids


ADMIN_ID = 6201090116


# Router - barcha handlerlarni bitta joyga jamlaydi
router = Router()



# Pastki doimiy menyu tugmalari
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="🔗 Shaxsiy havola")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Quyidagilardan birini tanlang..."
)


@router.message(Command("admin"))
async def admin_panel_handler(message: Message):
    # Faqat do'stingizgina kira olishi uchun tekshiruv
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda bu buyruqdan foydalanish huquqi yo'q.")
        return
        
    total_users = await get_total_users_count()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Hammaga xabar yuborish", callback_data="admin_broadcast")]
    ])
    
    await message.answer(
        "👑 <b>Admin paneliga xush kelibsiz!</b>\n\n"
        f"👥 Botdagi jami ishtirokchilar: <b>{total_users} ta</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_broadcast")
async def broadcast_prompt(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
        
    await callback.message.answer(
        "✍️ Ishtirokchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "(Matn, rasm yoki havolalardan foydalanishingiz mumkin. Eslatma: xabar darhol barchaga ketadi!)"
    )
    await callback.answer()

@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject, bot: Bot):
    # 1. Havola orqali kelgan ID ni ajratib olamiz (referral mantiq)
    args = command.args
    referred_by = None
    
    if args and args.isdigit():
        referred_by = int(args)
        # O'zini o'zi taklif qilishni oldini olamiz
        if referred_by == message.from_user.id:
            referred_by = None

    # 2. Yangi foydalanuvchini bazaga qo'shamiz 
    await add_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referred_by=referred_by
    )

    # 3. Foydalanuvchi avval ro'yxatdan o'tib, obuna bo'lganligini tekshiramiz
    has_joined = await get_user_status(message.from_user.id)
    
    if has_joined:
        # Agar a'zo bo'lgan bo'lsa, pastki menyuni chiqarib beramiz
        await message.answer(
            f"Siz allaqachon tanlovda ishtirok etyapsiz, <b>{message.from_user.first_name}</b>! 🎉\n\n"
            "Quyidagi menyudan foydalanishingiz mumkin:",
            reply_markup=main_menu,
            parse_mode="HTML"
        )
        return

    # 4. Agar a'zo bo'lmagan bo'lsa (yangi user), majburiy obuna tugmalarini ko'rsatamiz
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 1 - Kanal", url="https://t.me/cinephilessclub")],
        [InlineKeyboardButton(text="📢 2 - Kanal", url="https://t.me/examplechannel111")],
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
    
    channels_to_check = ["@cinephilessclub", "@examplechannel111"]
    
    for channel in channels_to_check:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=callback.from_user.id)
            if member.status in ["left", "kicked"]:
                await callback.answer("❌ Siz hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)
                return
        except Exception:
            await callback.answer("Xatolik yuz berdi. Bot kanallarda admin ekanligini tekshiring!", show_alert=True)
            return

    # Foydalanuvchini bazada "obuna bo'ldi" qilib belgilaymiz va ballni beramiz
    await process_subscription(callback.from_user.id)
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    
    # Eski xabarni o'zgartirib qoyamiz (tugmalarni yo'qotish uchun)
    await callback.message.edit_text("🎉 <b>Obuna tasdiqlandi!</b>", parse_mode="HTML")
    
    # Yangi xabar bilan pastki menyuni yuboramiz
    await callback.message.answer(
        "Do'stlaringizga yuborish uchun shaxsiy havolangiz:\n\n"
        f"<code>{referral_link}</code>\n\n"
        "Ushbu havola orqali qo'shilgan har bir do'stingiz uchun 1 ballga ega bo'lasiz!\n\n"
        "👇 <i>Asosiy menyudan kerakli bo'limni tanlang:</i>",
        reply_markup=main_menu,
        parse_mode="HTML"
    )

# Buyruq orqali va menyu tugmasi orqali ishlashi uchun ikkita filter qo'yamiz
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

# Faqat havola kerak bo'lganda bosiladigan tugma uchun
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