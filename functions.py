def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! Salom! O'z ustingizda ishlashni davom eting!")


def caps(update, context):
    text_caps = ' '.join(context.args).upper()
    context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Kechirasiz, bunday buyruq mavjud emas!")


def echo(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)
