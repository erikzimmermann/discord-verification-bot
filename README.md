# discord-verification-bot
A Discord bot that verifies [SpigotMC](https://www.spigotmc.org/) resource purchases of Discord accounts by using the PayPal API
to access transactions and an e-mail service to send verification keys to authorized users.  

# Requirements
* python
* pip
* a mysql database
* a general premium role
* one functional role per plugin resource

# Setup
1. Download code and unpack it into a folder
2. Run `pip install -r requirements.txt`
3. Run `py bot.py`