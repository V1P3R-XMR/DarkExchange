import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import ClientSession

bot_token = "7480001572:AAFFgR6MG_pSDcXEPn_2OxP43uM8nwsejs4"
fee_wallet = "UQAg3mG5c-QFD_KQQBzJMkd94y_r5pkAFegBijQr3LEbBWZ2"
ton_api_key = "9dae242569c3e85422df7c3dcbc5f9da391b8d3c2915cc100eb451337ca4f571"
private_key = "49cb6e50b55a3f86417cffb7c6aa37daa178ee0ed3c829e4c01fda2a84e1cb23"
api_url = "https://toncenter.com/api/v2"

bot = Bot(token=bot_token)
dp = Dispatcher()

user_sessions = {}

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛒 Start Escrow", callback_data="start_escrow")],
    [InlineKeyboardButton(text="📘 How it Works", url="https://t.me/darkexchangeton")],
    [InlineKeyboardButton(text="🛠 Support", url="https://t.me/v1p3rton")]
])

back_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu"),
     InlineKeyboardButton(text="📋 Main Menu", callback_data="main_menu")]
])

@dp.message()
async def start_handler(msg: types.Message):
    await msg.answer("Welcome to DarkExchange — Fully Automated TON Escrow.", reply_markup=main_menu)

@dp.callback_query(lambda c: c.data == "main_menu")
async def menu_handler(callback: types.CallbackQuery):
    await callback.message.edit_text("Main Menu", reply_markup=main_menu)

@dp.callback_query(lambda c: c.data == "start_escrow")
async def escrow_entry(callback: types.CallbackQuery):
    user_sessions[callback.from_user.id] = {}
    await callback.message.edit_text("Enter the seller’s TON wallet address:", reply_markup=back_main)

@dp.message()
async def collect_wallet(msg: types.Message):
    user_id = msg.from_user.id
    if user_id in user_sessions and "seller_wallet" not in user_sessions[user_id]:
        user_sessions[user_id]["seller_wallet"] = msg.text.strip()
        await msg.answer("Now enter the total price (in TON) you will send to escrow:", reply_markup=back_main)
    elif user_id in user_sessions and "amount" not in user_sessions[user_id]:
        try:
            amount = float(msg.text.strip())
            user_sessions[user_id]["amount"] = amount
            escrow_address = await create_wallet()
            user_sessions[user_id]["escrow_address"] = escrow_address
            await msg.answer(f"Send exactly {amount} TON to the escrow address:\n\n`{escrow_address}`\n\nOnce received, the bot will release funds automatically.",
                             parse_mode="Markdown", reply_markup=back_main)
            asyncio.create_task(check_and_release(user_id))
        except:
            await msg.answer("Invalid amount. Please enter a number.", reply_markup=back_main)

async def create_wallet():
    async with ClientSession() as session:
        payload = {
            "id": 1,
            "method": "wallet.getAccount",
            "params": [],
            "api_key": ton_api_key
        }
        async with session.post(api_url, json=payload) as resp:
            data = await resp.json()
            return data.get("result", {}).get("address", "UNKNOWN_WALLET")

async def check_and_release(user_id):
    await asyncio.sleep(15)
    data = user_sessions.get(user_id)
    if not data:
        return

    address = data["escrow_address"]
    expected = data["amount"]
    seller = data["seller_wallet"]
    fee = round(expected * 0.05, 5)
    payout = round(expected - fee, 5)

    async with ClientSession() as session:
        async with session.get(f"{api_url}/getAddressBalance?address={address}&api_key={ton_api_key}") as resp:
            res = await resp.json()
            balance = int(res["result"]) / 1e9
            if balance >= expected:
                await send_payment(seller, payout)
                await send_payment(fee_wallet, fee)
                await bot.send_message(user_id, f"✅ Escrow complete. {payout} TON sent to seller.\n5% fee sent to operator.")
            else:
                await bot.send_message(user_id, "⏳ Still waiting for payment to escrow wallet.")

async def send_payment(to_address, amount):
    async with ClientSession() as session:
        payload = {
            "id": 1,
            "method": "wallet.sendTransaction",
            "params": {
                "destination": to_address,
                "amount": int(amount * 1e9),
                "private_key": private_key
            },
            "api_key": ton_api_key
        }
        await session.post(api_url, json=payload)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(dp.start_polling(bot))