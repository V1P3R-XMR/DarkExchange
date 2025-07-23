import requests

BOT_TOKEN = "7480001572:AAFFgR6MG_pSDcXEPn_2OxP43uM8nwsejs4"

resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
print(resp.json())
