from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, CommandObject
from database import add_user, process_subscription

# A router groups your handlers together
router = Router()

@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject):
    # 1. Extract the referrer's ID if it exists (the '12345' part of the link)
    args = command.args
    referred_by = None
    
    if args and args.isdigit():
        referred_by = int(args)
        # Prevent users from referring themselves to cheat
        if referred_by == message.from_user.id:
            referred_by = None

    # 2. Add the new user to the database 
    await add_user(
        user_id=message.from_user.id,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referred_by=referred_by
    )

    # 3. Build the Channel Guard keyboard
    # ⚠️ Replace the URLs with your friend's actual channel links
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 1 - Kanal", url="https://t.me/atommasterklass")],
        [InlineKeyboardButton(text="📢 2- Kanal", url="https://t.me/atom_urganch")],
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]
    ])

    # 4. Send the welcome message
    await message.answer(
        f"Salom, <b>{message.from_user.first_name}</b>! 👋\n\n"
        "Tanlovda qatnashish va referral link olish uchun 2 ta kanalga a'zo bo'lishingiz kerak!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "check_sub")
async def check_subscription_handler(callback: CallbackQuery, bot: Bot):
    # ⚠️ IMPORTANT: Replace these with your friend's ACTUAL channel usernames
    channels_to_check = ["@YourFriendChannel1", "@YourFriendChannel2"]
    
    for channel in channels_to_check:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=callback.from_user.id)
            # If they left or were kicked, stop the process
            if member.status in ["left", "kicked"]:
                await callback.answer("❌ You haven't subscribed to all channels yet!", show_alert=True)
                return
        except Exception:
            # This triggers if the bot doesn't have permission to see the channel
            await callback.answer("Error checking channels. Make sure the bot is an admin in the channels!", show_alert=True)
            return

    # If the loop finishes without returning, they are in both channels!
    # Let's process the reward in the database
    await process_subscription(callback.from_user.id)
    
    # Generate their unique referral link
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"
    
    # Replace the original button message with the success message and their link
    await callback.message.edit_text(
        "🎉 <b>Thank you for subscribing!</b>\n\n"
        "Here is your unique referral link to send to your friends:\n"
        f"<code>{referral_link}</code>\n\n"
        "You will get 1 point for every friend who joins using this link!",
        parse_mode="HTML"
    )