from telegram.ext import Updater, CommandHandler
from dotenv import load_dotenv
from os import path, getenv
import logging

import handlers

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

env_path = path.abspath(path.join(path.dirname(path.abspath(__file__)), '../.env'))
load_dotenv(dotenv_path=env_path)

TOKEN = getenv('TOKEN')

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

# HANDLERS ================================
dispatcher.add_handler(handlers.start_handler)
dispatcher.add_handler(handlers.caps_handler)
dispatcher.add_handler(handlers.unknown_handler)

dispatcher.add_handler(handlers.echo_handler)
# END_HANDLERS ================================

updater.start_polling()
