import requests

BOT_TOKEN = "7480001572:AAFFgR6MG_pSDcXEPn_2OxP43uM8nwsejs4"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
params = {"drop_pending_updates": True}

resp = requests.get(url, params=params)
print(resp.json())
