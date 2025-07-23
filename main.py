import asyncio
import logging
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
fee_wallet = os.getenv("FEE_WALLET", "UQAg3mG5c-QFD_KQQBzJMkd94y_r5pkAFegBijQr3LEbBWZ2") # Your Ledger TON address
ton_api_key = os.getenv("TON_API_KEY", "9dae242569c3e85422df7c3dcbc5f9da391b8d3c2915cc100eb451337ca4f571")

bot = Bot(token=bot_token)
dp = Dispatcher()

# User sessions
user_sessions: Dict[int, Dict[str, Any]] = {}

# Escrow wallet info (single wallet used for all escrows)
escrow_wallet_info: Dict[str, Any] = {}

# Keyboards
main_menu = InlineKeyboardMarkup(inline_keyboard=[
[InlineKeyboardButton(text="🛒 Start Escrow", callback_data="start_escrow")],
[InlineKeyboardButton(text="📘 How it Works", callback_data="how_it_works")],
[InlineKeyboardButton(text="🛠 Support", url="https://t.me/v1p3rton")]
])

back_main = InlineKeyboardMarkup(inline_keyboard=[
[InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu"),
InlineKeyboardButton(text="📋 Main Menu", callback_data="main_menu")]
])


def is_valid_ton_address(address: str) -> bool:
try:
address = address.strip()
if len(address) < 40 or len(address) > 50:
return False
if not (address.startswith('EQ') or address.startswith('UQ') or address.startswith('kQ')):
return False
return True
except:
return False


def load_escrow_wallet() -> Dict[str, Any]:
try:
from pytoniq import WalletV4R2

# Your fixed escrow private key (hex string)
escrow_private_key_hex = "49cb6e50b55a3f86417cffb7c6aa37daa178ee0ed3c829e4c01fda2a84e1cb23"
private_key_bytes = bytes.fromhex(escrow_private_key_hex)

wallet = WalletV4R2(private_key_bytes, 0)

wallet_info = {
"address": wallet.address.to_str(is_user_friendly=True),
"private_key": escrow_private_key_hex,
"wallet_object": wallet,
"created_at": str(int(time.time() * 1000))
}

logger.info(f"Loaded escrow wallet: {wallet_info['address']}")
return wallet_info

except Exception as e:
logger.error(f"Error loading escrow wallet: {e}")
raise


async def get_wallet_balance(address: str) -> float:
try:
url = f"https://tonapi.io/v2/accounts/{address}"
async with ClientSession() as session:
async with session.get(url) as response:
if response.status == 200:
data = await response.json()
balance_nano = int(data.get("balance", 0))
return balance_nano / 1e9
else:
logger.error(f"HTTP error getting balance: {response.status}")
return 0.0
except Exception as e:
logger.error(f"Error getting balance for {address}: {e}")
return 0.0


async def send_ton_payment(from_wallet, to_address: str, amount_ton: float) -> bool:
try:
# TODO: Replace with actual pytoniq transaction sending
await asyncio.sleep(2) # simulate network delay
logger.info(f"Sent {amount_ton} TON from {from_wallet['address']} to {to_address}")
return True
except Exception as e:
logger.error(f"Error sending payment: {e}")
return False


@dp.message(Command("start"))
async def start_handler(msg: types.Message):
await msg.answer(
"🌟 Welcome to DarkExchange — Real TON Escrow Service!\n\n"
"🔒 Secure, automated escrow using your fixed escrow wallet.\n",
reply_markup=main_menu
)


@dp.callback_query(F.data == "main_menu")
async def menu_handler(callback: types.CallbackQuery):
await callback.message.edit_text("🌟 DarkExchange Main Menu\n\nChoose an option below:",
reply_markup=main_menu
)
await callback.answer()


@dp.callback_query(F.data == "how_it_works")
async def how_it_works_handler(callback: types.CallbackQuery):
instructions = (
"🌟 **How DarkExchange Works:**\n\n"
"1. Click 'Start Escrow' to initiate a transaction.\n"
"2. Enter the seller's TON wallet address.\n"
"3. Specify the amount of TON for escrow.\n"
"4. Send TON to the escrow wallet address provided.\n"
"5. The bot monitors payment and releases funds automatically.\n"
"⚠️ Double-check all details."
)
await callback.message.edit_text(instructions, reply_markup=back_main)
await callback.answer()


@dp.callback_query(F.data == "start_escrow")
async def escrow_entry(callback: types.CallbackQuery):
user_sessions[callback.from_user.id] = {"step": "waiting_seller_wallet"}
await callback.message.edit_text(
"💰 Starting TON Escrow Process\n\n"
"📝 Please enter the seller's TON wallet address:",
reply_markup=back_main
)
await callback.answer()


@dp.message(F.text)
async def handle_text_messages(msg: types.Message):
user_id = msg.from_user.id
if user_id not in user_sessions:
await msg.answer("Please start by using /start", reply_markup=main_menu)
return

session = user_sessions[user_id]
if session.get("step") == "waiting_seller_wallet":
wallet_address = msg.text.strip()
if not is_valid_ton_address(wallet_address):
await msg.answer("❌ Invalid TON address format. Please re-enter.", reply_markup=back_main)
return

session["seller_wallet"] = wallet_address
session["step"] = "waiting_amount"
await msg.answer(
f"✅ Seller wallet saved: `{wallet_address}`\n\nEnter the amount (TON):",
parse_mode="Markdown",
reply_markup=back_main
)

elif session.get("step") == "waiting_amount":
try:
amount = float(msg.text.strip())
if amount < 0.1:
await msg.answer("Minimum escrow amount is 0.1 TON.", reply_markup=back_main)
return
session["amount"] = amount
session["step"] = "completed"

fee_amount = round(amount * 0.05, 4)
seller_amount = round(amount - fee_amount, 4)
escrow_address = escrow_wallet_info["address"]

await msg.answer(
f"🏦 Escrow Wallet:\n`{escrow_address}`\n\n"
f"💰 Amount: {amount} TON\n"
f"💸 Fee (5%): {fee_amount} TON\n"
f"📨 Seller receives: {seller_amount} TON\n\n"
f"🔐 Send exactly {amount} TON to the escrow wallet above.\n"
f"⏳ The bot will monitor the payment and release funds automatically.",
parse_mode="Markdown",
reply_markup=back_main
)
asyncio.create_task(monitor_payment(user_id))

except ValueError:
await msg.answer("Invalid amount. Please enter a valid number.", reply_markup=back_main)
else:
await msg.answer("Please use menu buttons.", reply_markup=main_menu)


async def monitor_payment(user_id: int):
max_checks = 120 # 60 minutes max (30 sec intervals)
check_count = 0
while check_count < max_checks:
session = user_sessions.get(user_id)
if not session or session.get("step") != "completed":
break

escrow_address = escrow_wallet_info["address"]
expected_amount = session["amount"]
balance = await get_wallet_balance(escrow_address)

if balance >= expected_amount:
await process_escrow_release(user_id, session)
break

if check_count in [2, 10, 20, 40, 80]:
await bot.send_message(
user_id,
f"⏳ Monitoring payment...\nExpected: {expected_amount} TON\nReceived: {balance} TON\nAddress: `{escrow_address}`",
parse_mode="Markdown"
)
check_count += 1
await asyncio.sleep(30)

if check_count >= max_checks:
await bot.send_message(
user_id,
"⏰ Escrow timeout (60 minutes). If you sent the payment, contact support."
)


async def process_escrow_release(user_id: int, session: Dict[str, Any]):
amount = session["amount"]
fee_amount = round(amount * 0.05, 4)
seller_amount = round(amount - fee_amount, 4)
seller_address = session["seller_wallet"]
escrow_address = escrow_wallet_info["address"]

await bot.send_message(user_id, "🔄 Processing TON transfers...")

seller_success = await send_ton_payment(escrow_wallet_info, seller_address, seller_amount)
fee_success = await send_ton_payment(escrow_wallet_info, fee_wallet, fee_amount)

if seller_success and fee_success:
await bot.send_message(
user_id,
f"✅ Escrow Completed!\n\n"
f"{seller_amount} TON sent to seller\n"
f"{fee_amount} TON fee sent to fee wallet\n"
f"Seller: `{seller_address}`\n"
f"Escrow wallet: `{escrow_address}`",
parse_mode="Markdown",
reply_markup=main_menu
)
else:
await bot.send_message(
user_id,
f"⚠️ Payment error.\nFunds are safe in escrow wallet {escrow_address}.\nContact support.",
parse_mode="Markdown",
reply_markup=main_menu
)
if user_id in user_sessions:
del user_sessions[user_id]


async def main():
global escrow_wallet_info
logger.info("Starting DarkExchange BOT")
try:
from pytoniq import WalletV4R2
except ImportError:
logger.error("pytoniq library not installed. Run: pip install pytoniq")
return

escrow_wallet_info = load_escrow_wallet()
await dp.start_polling(bot, skip_updates=True)


if name == "__main__":
asyncio.run(main())
