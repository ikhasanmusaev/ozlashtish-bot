from telegram.ext import CommandHandler, MessageHandler, Filters

import functions

start_handler = CommandHandler('start', functions.start)

echo_handler = MessageHandler(Filters.text & (~Filters.command), functions.echo)

unknown_handler = MessageHandler(Filters.command, functions.unknown)

caps_handler = CommandHandler('caps', functions.caps)
