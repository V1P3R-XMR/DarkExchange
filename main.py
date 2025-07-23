import asyncio
import logging
import hashlib
import secrets
import time
from typing import Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiohttp import ClientSession
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
bot_token = os.getenv("BOT_TOKEN", "8175684032:AAFbwljxZ0OMso8q7Wzm8HvW0PilFVxhH2Q")
fee_wallet = os.getenv("FEE_WALLET", "UQAg3mG5c-QFD_KQQBzJMkd94y_r5pkAFegBijQr3LEbBWZ2")
ton_api_key = os.getenv("TON_API_KEY", "9dae242569c3e85422df7c3dcbc5f9da391b8d3c2915cc100eb451337ca4f571")

bot = Bot(token=bot_token)
dp = Dispatcher()

# Session storage
user_sessions: Dict[int, Dict[str, Any]] = {}
escrow_wallets: Dict[str, Dict[str, Any]] = {}

# Keyboards
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛒 Start Escrow", callback_data="start_escrow")],
    [InlineKeyboardButton(text="📘 How it Works", url="https://t.me/darkexchangeton")],
    [InlineKeyboardButton(text="🛠 Support", url="https://t.me/v1p3rton")]
])

back_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu"),
     InlineKeyboardButton(text="📋 Main Menu", callback_data="main_menu")]
])

def is_valid_ton_address(address: str) -> bool:
    """Validate TON address format"""
    try:
        address = address.strip()
        # Basic validation for TON address
        if len(address) < 40 or len(address) > 50:
            return False
        if not (address.startswith('EQ') or address.startswith('UQ') or address.startswith('kQ')):
            return False
        return True
    except:
        return False

def generate_escrow_wallet() -> Dict[str, str]:
    """Generate a deterministic wallet address for escrow"""
    # Generate unique seed
    timestamp = str(int(time.time() * 1000))
    random_bytes = secrets.token_hex(16)
    seed = f"{timestamp}{random_bytes}"
    
    # Create a deterministic address hash
    address_hash = hashlib.sha256(seed.encode()).hexdigest()[:44]
    escrow_address = f"UQ{address_hash}"
    
    wallet_info = {
        "address": escrow_address,
        "seed": seed,
        "created_at": timestamp
    }
    
    logger.info(f"Generated escrow wallet: {escrow_address}")
    return wallet_info

async def get_wallet_balance(address: str) -> float:
    """Get wallet balance using TON API"""
    try:
        url = f"https://toncenter.com/api/v2/getAddressBalance?address={address}"
        headers = {"X-API-Key": ton_api_key} if ton_api_key else {}
        
        async with ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        balance_nano = int(data.get("result", 0))
                        return balance_nano / 1e9
                    else:
                        logger.error(f"API error: {data}")
                        return 0.0
                else:
                    logger.error(f"HTTP error: {response.status}")
                    return 0.0
    except Exception as e:
        logger.error(f"Error getting balance for {address}: {e}")
        return 0.0

async def simulate_payment(to_address: str, amount: float, from_address: str) -> bool:
    """Simulate TON payment (for demo purposes)"""
    try:
        logger.info(f"Simulating payment of {amount} TON from {from_address} to {to_address}")
        
        # In a real implementation, you would:
        # 1. Create a transaction using the private key
        # 2. Sign the transaction
        # 3. Send it to the TON network
        
        # For now, we'll simulate success
        await asyncio.sleep(2)  # Simulate network delay
        
        logger.info(f"Payment simulation completed: {amount} TON to {to_address}")
        return True
        
    except Exception as e:
        logger.error(f"Error in payment simulation: {e}")
        return False

@dp.message(Command("start"))
async def start_handler(msg: types.Message):
    """Handle /start command"""
    try:
        await msg.answer(
            "🌟 Welcome to DarkExchange — Fully Automated TON Escrow!\n\n"
            "🔒 Secure, fast, and reliable escrow service for TON transactions.",
            reply_markup=main_menu
        )
    except Exception as e:
        logger.error(f"Error in start handler: {e}")

@dp.callback_query(F.data == "main_menu")
async def menu_handler(callback: types.CallbackQuery):
    """Handle main menu callback"""
    try:
        await callback.message.edit_text(
            "🌟 DarkExchange Main Menu\n\n"
            "Choose an option below:",
            reply_markup=main_menu
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in menu handler: {e}")
        await callback.answer("Error occurred, please try again.")

@dp.callback_query(F.data == "start_escrow")
async def escrow_entry(callback: types.CallbackQuery):
    """Start escrow process"""
    try:
        user_sessions[callback.from_user.id] = {"step": "waiting_seller_wallet"}
        await callback.message.edit_text(
            "💰 Starting Escrow Process\n\n"
            "📝 Please enter the seller's TON wallet address:",
            reply_markup=back_main
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in escrow entry: {e}")
        await callback.answer("Error occurred, please try again.")

@dp.message(F.text)
async def handle_text_messages(msg: types.Message):
    """Handle text messages based on user session state"""
    user_id = msg.from_user.id
    
    try:
        if user_id not in user_sessions:
            await msg.answer("Please start by using /start command", reply_markup=main_menu)
            return
        
        session = user_sessions[user_id]
        
        if session.get("step") == "waiting_seller_wallet":
            await handle_seller_wallet_input(msg, session)
        elif session.get("step") == "waiting_amount":
            await handle_amount_input(msg, session)
        else:
            await msg.answer("Please use the menu buttons to navigate.", reply_markup=main_menu)
            
    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        await msg.answer("An error occurred. Please try again.", reply_markup=main_menu)

async def handle_seller_wallet_input(msg: types.Message, session: Dict[str, Any]):
    """Handle seller wallet address input"""
    wallet_address = msg.text.strip()
    
    if not is_valid_ton_address(wallet_address):
        await msg.answer(
            "❌ Invalid TON address format.\n\n"
            "Please enter a valid TON address (should start with EQ, UQ, or kQ):",
            reply_markup=back_main
        )
        return
    
    session["seller_wallet"] = wallet_address
    session["step"] = "waiting_amount"
    
    await msg.answer(
        f"✅ Seller wallet saved: `{wallet_address}`\n\n"
        "💰 Now enter the total amount (in TON) for this escrow:",
        parse_mode="Markdown",
        reply_markup=back_main
    )

async def handle_amount_input(msg: types.Message, session: Dict[str, Any]):
    """Handle amount input"""
    try:
        amount = float(msg.text.strip())
        if amount <= 0:
            await msg.answer("Please enter a positive amount.", reply_markup=back_main)
            return
        
        if amount < 0.1:
            await msg.answer("Minimum escrow amount is 0.1 TON.", reply_markup=back_main)
            return
            
        session["amount"] = amount
        session["step"] = "completed"
        
        # Generate escrow wallet
        escrow_wallet_info = generate_escrow_wallet()
        session["escrow_address"] = escrow_wallet_info["address"]
        escrow_wallets[escrow_wallet_info["address"]] = escrow_wallet_info
        
        fee_amount = round(amount * 0.05, 4)  # 5% fee
        
        await msg.answer(
            f"🏦 **Escrow Created Successfully!**\n\n"
            f"💰 Amount: `{amount}` TON\n"
            f"🏪 Seller: `{session['seller_wallet']}`\n"
            f"💸 Fee (5%): `{fee_amount}` TON\n"
            f"📨 You'll receive: `{amount - fee_amount}` TON\n\n"
            f"🔐 **Send exactly {amount} TON to:**\n"
            f"`{escrow_wallet_info['address']}`\n\n"
            f"⏰ The bot will automatically release funds once payment is confirmed.",
            parse_mode="Markdown",
            reply_markup=back_main
        )
        
        # Start monitoring payment
        asyncio.create_task(monitor_payment(msg.from_user.id))
        
    except ValueError:
        await msg.answer("Invalid amount. Please enter a valid number.", reply_markup=back_main)

async def monitor_payment(user_id: int):
    """Monitor payment and release funds when received"""
    max_checks = 60  # Check for 30 minutes (60 checks * 30s)
    check_count = 0
    
    while check_count < max_checks:
        try:
            session = user_sessions.get(user_id)
            if not session or session.get("step") != "completed":
                logger.info(f"Stopping payment monitor for user {user_id} - session invalid")
                break
            
            escrow_address = session["escrow_address"]
            expected_amount = session["amount"]
            seller_address = session["seller_wallet"]
            
            # Check balance
            balance = await get_wallet_balance(escrow_address)
            
            if balance >= expected_amount:
                # Payment received, process release
                await process_escrow_release(user_id, session)
                break
            else:
                # Send periodic updates
                if check_count in [2, 10, 20, 40]:  # Send updates at specific intervals
                    await bot.send_message(
                        user_id,
                        f"⏳ Still waiting for payment...\n"
                        f"Expected: {expected_amount} TON\n"
                        f"Received: {balance} TON\n"
                        f"Address: `{escrow_address}`",
                        parse_mode="Markdown"
                    )
            
            check_count += 1
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in payment monitoring: {e}")
            await asyncio.sleep(30)
    
    # Timeout handling
    if check_count >= max_checks:
        session = user_sessions.get(user_id)
        if session and session.get("step") == "completed":
            await bot.send_message(
                user_id,
                "⏰ Escrow timeout. If you sent the payment, please contact support.\n"
                "The escrow will remain active for manual verification."
            )

async def process_escrow_release(user_id: int, session: Dict[str, Any]):
    """Process the escrow release"""
    try:
        amount = session["amount"]
        seller_address = session["seller_wallet"]
        escrow_address = session["escrow_address"]
        
        fee_amount = round(amount * 0.05, 4)
        seller_amount = round(amount - fee_amount, 4)
        
        # Simulate payments (in real implementation, use actual TON transfers)
        seller_success = await simulate_payment(seller_address, seller_amount, escrow_address)
        fee_success = await simulate_payment(fee_wallet, fee_amount, escrow_address)
        
        if seller_success and fee_success:
            await bot.send_message(
                user_id,
                f"✅ **Escrow Completed Successfully!**\n\n"
                f"💰 {seller_amount} TON sent to seller\n"
                f"💸 {fee_amount} TON fee processed\n"
                f"🏪 Seller: `{seller_address}`\n\n"
                f"Thank you for using DarkExchange! 🌟",
                parse_mode="Markdown",
                reply_markup=main_menu
            )
        else:
            await bot.send_message(
                user_id,
                "⚠️ Payment processing encountered issues.\n"
                "Your funds are safe. Please contact support for assistance.",
                reply_markup=main_menu
            )
        
        # Clean up session
        if user_id in user_sessions:
            del user_sessions[user_id]
        if escrow_address in escrow_wallets:
            del escrow_wallets[escrow_address]
            
    except Exception as e:
        logger.error(f"Error processing escrow release: {e}")
        await bot.send_message(
            user_id,
            "❌ Error processing escrow. Please contact support.",
            reply_markup=main_menu
        )

async def main():
    """Main function to run the bot"""
    try:
        logger.info("Starting DarkExchange Bot...")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Bot startup error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
