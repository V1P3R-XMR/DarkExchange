import asyncio
from binascii import unhexlify
from pytonlib.wallet import WalletV3R2
from pytonlib.crypto.keypair import KeyPair
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import httpx
import logging

BOT_TOKEN = "8175684032:AAFbwljxZ0OMso8q7Wzm8HvW0PilFVxhH2Q"
TON_CENTER_API_KEY = "9dae242569c3e85422df7c3dcbc5f9da391b8d3c2915cc100eb451337ca4f571"
TON_CENTER_API_URL = "https://toncenter.com/api/v2"
ESCROW_PRIVATE_KEY_HEX = "49cb6e50b55a3f86417cffb7c6aa37daa178ee0ed3c829e4c01fda2a84e1cb23"
FEE_WALLET_ADDRESS = "UQAg3mG5c-QFD_KQQBzJMkd94y_r5pkAFegBijQr3LEbBWZ2"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class EscrowStates(StatesGroup):
    waiting_for_seller = State()
    waiting_for_amount = State()
    waiting_for_confirm = State()

class CallbackActions(CallbackData, prefix="action"):
    action: str

def derive_escrow_wallet():
    keypair = KeyPair(unhexlify(ESCROW_PRIVATE_KEY_HEX))
    return WalletV3R2(keypair)

async def get_balance(address: str) -> int:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TON_CENTER_API_URL}/getAddressInformation",
            params={"api_key": TON_CENTER_API_KEY, "address": address},
            timeout=15
        )
        data = resp.json()
        if data["ok"] and "balance" in data["result"]:
            return int(data["result"]["balance"])
        return 0

async def send_ton(wallet: WalletV3R2, to_address: str, amount: int, comment: bytes = b""):
    seqno = await wallet.get_seqno()
    transfer = await wallet.create_transfer(to_address, amount, seqno, 3, comment)
    tx = await wallet.send_transfer(transfer)
    return tx

@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Start Escrow", callback_data=CallbackActions(action="start_escrow").pack())],
        [InlineKeyboardButton(text="How it Works", url="https://t.me/darkexchangeton")],
        [InlineKeyboardButton(text="Support", url="https://t.me/v1p3rton")]
    ])
    await message.answer("Welcome to DarkExchange TON Escrow Bot.", reply_markup=keyboard)

@dp.callback_query(CallbackActions.filter())
async def process_callback(callback: types.CallbackQuery, callback_data: CallbackActions, state: FSMContext):
    await callback.answer()
    if callback_data.action == "start_escrow":
        await callback.message.answer("Send SELLER TON wallet address (starts with UQ or EQ):")
        await state.set_state(EscrowStates.waiting_for_seller)
    elif callback_data.action == "cancel":
        await callback.message.answer("Operation cancelled.")
        await state.clear()

@dp.message(state=EscrowStates.waiting_for_seller)
async def seller_received(message: types.Message, state: FSMContext):
    addr = message.text.strip()
    if not (addr.startswith("UQ") or addr.startswith("EQ")):
        await message.answer("Invalid TON wallet address. Must start with UQ or EQ. Try again:")
        return
    await state.update_data(seller_address=addr)
    await message.answer("Enter amount in TON (e.g. 0.5):")
    await state.set_state(EscrowStates.waiting_for_amount)

@dp.message(state=EscrowStates.waiting_for_amount)
async def amount_received(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError
    except:
        await message.answer("Invalid amount. Enter a positive number like 0.5")
        return
    await state.update_data(amount=amount)
    data = await state.get_data()
    seller = data["seller_address"]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Confirm & Pay", callback_data=CallbackActions(action="confirm_pay").pack())],
        [InlineKeyboardButton(text="Cancel", callback_data=CallbackActions(action="cancel").pack())]
    ])
    await message.answer(f"Pay {amount:.6f} TON to seller:\n{seller}\nConfirm?", reply_markup=keyboard)
    await state.set_state(EscrowStates.waiting_for_confirm)

@dp.callback_query(CallbackActions.filter())
async def confirm_payment(callback: types.CallbackQuery, callback_data: CallbackActions, state: FSMContext):
    await callback.answer()
    if callback_data.action != "confirm_pay":
        return
    data = await state.get_data()
    seller = data.get("seller_address")
    amount = data.get("amount")
    if not seller or not amount:
        await callback.message.answer("Session expired. Please start again.")
        await state.clear()
        return

    wallet = derive_escrow_wallet()
    escrow_address = await wallet.get_address()
    prev_balance = await get_balance(escrow_address)
    await callback.message.answer(f"Send {amount:.6f} TON to escrow wallet:\n{escrow_address}\nWaiting up to 1 hour...")

    for _ in range(3600 // 5):
        current_balance = await get_balance(escrow_address)
        if current_balance > prev_balance:
            break
        await asyncio.sleep(5)
    else:
        await callback.message.answer("Timeout. Payment not received.")
        await state.clear()
        return

    amount_nanoton = int(amount * 1_000_000_000)
    received = current_balance - prev_balance
    if received < amount_nanoton:
        await callback.message.answer("Received less than expected. Cancelled.")
        await state.clear()
        return

    fee = amount_nanoton * 5 // 100
    seller_amount = amount_nanoton - fee

    await callback.message.answer("Sending 95% to seller...")
    await send_ton(wallet, seller, seller_amount, b"DarkExchange seller payout")
    await callback.message.answer("Sending 5% fee...")
    await send_ton(wallet, FEE_WALLET_ADDRESS, fee, b"DarkExchange fee")
    await callback.message.answer("Escrow complete. Thank you.")
    await state.clear()

@dp.message()
async def default_handler(message: types.Message):
    await message.answer("Use /start to begin.")

if __name__ == "__main__":
    import asyncio
    from aiogram.fsm.storage.memory import MemoryStorage
    storage = MemoryStorage()
    dp.storage = storage
    asyncio.run(dp.start_polling(bot))
