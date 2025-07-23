import asyncio
from binascii import unhexlify
from pytonlib.wallet import WalletV3R2
from pytonlib.crypto.keypair import KeyPair
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
import httpx

BOT_TOKEN = "7480001572:AAFFgR6MG_pSDcXEPn_2OxP43uM8nwsejs4"
TON_CENTER_API_KEY = "9dae242569c3e85422df7c3dcbc5f9da391b8d3c2915cc100eb451337ca4f571"
TON_CENTER_API_URL = "https://toncenter.com/api/v2"
ESCROW_PRIVATE_KEY_HEX = "49cb6e50b55a3f86417cffb7c6aa37daa178ee0ed3c829e4c01fda2a84e1cb23"
FEE_WALLET_ADDRESS = "UQAg3mG5c-QFD_KQQBzJMkd94y_r5pkAFegBijQr3LEbBWZ2"

WAIT_SELLER, WAIT_AMOUNT, WAIT_CONFIRM = range(3)

def derive_escrow_wallet():
    keypair = KeyPair(unhexlify(ESCROW_PRIVATE_KEY_HEX))
    return WalletV3R2(keypair)

async def get_balance(address: str) -> int:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{TON_CENTER_API_URL}/getAddressInformation", params={"api_key": TON_CENTER_API_KEY, "address": address})
        d = r.json()
        if d["ok"] and "balance" in d["result"]:
            return int(d["result"]["balance"])
        return 0

async def send_ton(wallet: WalletV3R2, to_address: str, amount: int, comment: bytes = b""):
    seqno = await wallet.get_seqno()
    transfer = await wallet.create_transfer(to_address, amount, seqno, 3, comment)
    tx = await wallet.send_transfer(transfer)
    return tx

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Start Escrow", callback_data="start_escrow")],
        [InlineKeyboardButton("How it Works", url="https://t.me/darkexchangeton")],
        [InlineKeyboardButton("Support", url="https://t.me/v1p3rton")]
    ]
    await update.message.reply_text("Welcome to DarkExchange TON Escrow Bot.", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if update.callback_query.data == "start_escrow":
        await update.callback_query.message.reply_text("Send SELLER TON wallet address (starts with UQ or EQ):")
        return WAIT_SELLER
    if update.callback_query.data == "cancel":
        await update.callback_query.message.reply_text("Cancelled.")
        return ConversationHandler.END

async def receive_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    if not (addr.startswith("UQ") or addr.startswith("EQ")):
        await update.message.reply_text("Invalid address. Send a TON wallet address starting with UQ or EQ.")
        return WAIT_SELLER
    context.user_data["seller"] = addr
    await update.message.reply_text("Enter amount in TON (e.g. 0.5):")
    return WAIT_AMOUNT

async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Invalid amount. Enter a positive number like 0.5")
        return WAIT_AMOUNT
    context.user_data["amount"] = amount
    seller = context.user_data["seller"]
    keyboard = [
        [InlineKeyboardButton("Confirm & Pay", callback_data="confirm_pay")],
        [InlineKeyboardButton("Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text(f"Pay {amount:.6f} TON to seller:\n{seller}\nConfirm?", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_CONFIRM

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    seller = context.user_data.get("seller")
    amount = context.user_data.get("amount")
    if not seller or not amount:
        await update.callback_query.message.reply_text("Session expired. Please start again.")
        return ConversationHandler.END

    wallet = derive_escrow_wallet()
    escrow_address = await wallet.get_address()
    prev_balance = await get_balance(escrow_address)

    await update.callback_query.message.reply_text(f"Send {amount:.6f} TON to escrow:\n{escrow_address}\nWaiting up to 1 hour...")

    for _ in range(3600 // 5):
        current_balance = await get_balance(escrow_address)
        if current_balance > prev_balance:
            break
        await asyncio.sleep(5)
    else:
        await update.callback_query.message.reply_text("Timeout. Payment not received.")
        return ConversationHandler.END

    amount_nanoton = int(amount * 1_000_000_000)
    received = current_balance - prev_balance
    if received < amount_nanoton:
        await update.callback_query.message.reply_text("Received less than expected. Cancelled.")
        return ConversationHandler.END

    fee = amount_nanoton * 5 // 100
    seller_amount = amount_nanoton - fee

    await update.callback_query.message.reply_text("Sending 95% to seller...")
    await send_ton(wallet, seller, seller_amount, b"DarkExchange seller payout")

    await update.callback_query.message.reply_text("Sending 5% fee...")
    await send_ton(wallet, FEE_WALLET_ADDRESS, fee, b"DarkExchange fee")

    await update.callback_query.message.reply_text("Escrow complete. Thank you.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^start_escrow$")],
        states={
            WAIT_SELLER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_seller)],
            WAIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            WAIT_CONFIRM: [CallbackQueryHandler(confirm_payment, pattern="^confirm_pay$"),
                           CallbackQueryHandler(cancel, pattern="^cancel$")]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
        allow_reentry=True
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
