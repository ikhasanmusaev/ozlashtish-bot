from dotenv import load_dotenv
from os import path, getenv
import logging
import random
import time
import ssl

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.utils import executor
from aiogram.utils.executor import start_webhook
from asyncio import CancelledError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from helper import generate_key, FormTeacher, FormAbt, generate_test, generate_ans, run_time, get_results, IsOn, IsOff, Auth
from db.connection import question_coll, results_coll, attempt_coll, users_coll

# logging.basicConfig(level=logging.INFO)

env_path = path.abspath(path.join(path.dirname(path.abspath(__file__)), '../.env'))
load_dotenv(dotenv_path=env_path)
scheduler = AsyncIOScheduler()

TOKEN = getenv('TOKEN')
bot = Bot(token=TOKEN)
IP = getenv('WEBHOOK_HOST')

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

WEBHOOK_HOST = f'https://{IP}:8443'
WEBHOOK_PATH = f'/{TOKEN}/'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBHOOK_SSL_CERT = path.abspath(path.join(path.dirname(path.abspath(__file__)), './webhook_cert.pem'))
WEBHOOK_SSL_PRIV = path.abspath(path.join(path.dirname(path.abspath(__file__)), './webhook_pkey.pem'))

WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = '8443'


async def kick_user(state, message):
    if scheduler.running:
        scheduler.shutdown()
    await state.finish()
    try:
        await bot.send_message(message.chat.id,
                               'Siz belgilangan vaqtda javob bera olmadingiz.\n Tayyorlanib, keyinroq harakat qiling.',
                               reply_markup=types.ReplyKeyboardRemove())
    except CancelledError:
        return
    return


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('Boshlash!')

    await bot.send_message(message.chat.id, "Salom! O'z ustingizda ishlashdan to'xtamang!")
    await bot.send_message(message.chat.id, "Savol-javobni boshlash uchun 'Boshlash!' ni bosing", reply_markup=markup)


# You can use state '*' if you need to handle all states
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    if scheduler.running:
        scheduler.shutdown()
    # And remove keyboard (just in case)
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands='addQ')
async def add_q_handler(message: types.Message):
    await FormTeacher.count.set()
    markup = types.ReplyKeyboardRemove()

    await message.reply('Nechta savol kiritasiz?', reply_markup=markup)


# Check age. Age gotta be digit
@dp.message_handler(lambda message: not message.text.isdigit(), state=FormTeacher.count or FormTeacher.time)
async def process_digit_invalid(message: types.Message):
    return await message.reply("Qiymatni sonda kiriting!\n Bad input. (faqat raqamlar)")


@dp.message_handler(lambda message: message.text.isdigit(), state=FormTeacher.count)
async def process_count(message: types.Message, state: FSMContext):
    # Update state and data
    await FormTeacher.next()
    await state.update_data(count=int(message.text))

    await message.reply("Savollar orasidagi vaqtni kiriting(sekundda)!")


@dp.message_handler(lambda message: message.text.isdigit(), state=FormTeacher.time)
async def process_time(message: types.Message, state: FSMContext):
    # Update state and data
    await FormTeacher.next()

    await state.update_data(time=int(message.text))
    await message.reply("Savollarni kiritishni boshlang. \n"
                        "1-savol rasmini kiriting.")
    await message.reply(
        "1-savol rasmi, 1-savol javoblari, hammasi(javoblarni qator tashlash bilan ajrating"
        " va to'g'ri javobni birinchi yozing)\n"
        "2-savol rasmi, 2-savol javoblari va h.k.z...")


@dp.message_handler(Text(equals='Back', ignore_case=True), state=FormTeacher.questionsI)
async def process_edit_prev(message: types.Message, state: FSMContext):
    await FormTeacher.next()
    data = await state.get_data()
    questions_q = data.get('questionsQ')
    del questions_q[-1]
    await state.update_data(questionsQ=questions_q)
    await bot.send_message(message.chat.id, 'Oldingi savolning javoblarini qayta kiriting',
                           reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(lambda message: not len(message.photo) > 0, state=FormTeacher.questionsI)
async def process_is_photo(message: types.Message):
    await message.reply('Rasm kiriting! \n Bad input.')


@dp.message_handler(state=FormTeacher.questionsI, content_types=['photo'])
async def process_question(message: types.Message, state: FSMContext):
    await FormTeacher.next()
    data = await state.get_data()
    questions_i = data.get('questionsI') or []
    questions_i.append(message.photo[-1].file_id)
    await state.update_data(questionsI=questions_i)
    await message.reply(f'{len(questions_i)}-savolning javoblarini kiriting!')
    await bot.send_message(message.chat.id, 'Misol: To`g`ri javob\nNoto`g`ri javob\nNoto`g`ri javob\n...',
                           reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state=FormTeacher.questionsQ)
async def process_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    questions_q = data.get('questionsQ') or []
    questions_q.append(message.text)
    await state.update_data(questionsQ=questions_q)
    if len(questions_q) == data['count']:
        await FormTeacher.next()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add('Tasdiqlayman')
        await message.reply('Siz savollarni kiritib bo`ldingiz! \n'
                            'Tasdiqlash uchun `Tasdiqlayman`ni kiriting', reply_markup=markup)
    else:
        await FormTeacher.previous()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add('Back')
        await message.reply(f'{len(questions_q) + 1}-savolning rasmini kiriting!', reply_markup=markup)


@dp.message_handler(lambda message: message.text != "Tasdiqlayman", state=FormTeacher.is_yes)
async def process_is_yes(message: types.Message):
    return await message.reply('Bad Input. Tasdiqlash uchun `Tasdiqlayman` tugmasini bosing!')


@dp.message_handler(state=FormTeacher.is_yes)
async def process_save(message: types.Message, state: FSMContext):
    secret_key = generate_key(6)
    async with state.proxy() as data:
        # data['is_yes'] = message.text
        test = generate_test(data['questionsI'], data['questionsQ'])
        # Remove keyboard

        markup = types.ReplyKeyboardRemove()

        # And send message
        await bot.send_message(message.chat.id, 'Bu siz uchun kod 👇', reply_markup=markup)
        await bot.send_message(message.chat.id, f'{secret_key}')

        to_db = {
            'questions': test,
            'count': data['count'],
            'time': data['time'],
            'key': secret_key,
            'is_on': True
        }

        question_coll.insert_one(to_db)

    # Finish conversation
    await state.finish()


@dp.message_handler(Text(equals='Boshlash!', ignore_case=True) | Text(equals='Boshlash', ignore_case=True))
async def process_starting(message: types.Message):
    await FormAbt.question.set()
    markup = types.ReplyKeyboardRemove()

    await bot.send_message(message.chat.id, 'Savollar uchun maxsus kodni kiriting!', reply_markup=markup)


# @dp.message_handler(state=FormAbt.name)
# async def process_name(message: types.Message, state: FSMContext):
#     await FormAbt.next()
#     await state.update_data(name=message.text)
#
#     await bot.send_message(message.chat.id, 'Savollar uchun maxsus kodni kiriting!')


@dp.message_handler(lambda message: message.text[0] != "_", state=FormAbt.question)
async def process_key_invalid(message: types.Message):
    await bot.send_message(message.chat.id, 'Kodni xato kiritdingiz, Iltimos qayta urinib ko`ring')


@dp.message_handler(lambda message: message.text[0] == "_", state=FormAbt.question)
async def process_get_questions(message: types.Message, state: FSMContext):
    data = question_coll.find_one({"key": message.text}, ['questions', 'time', 'is_on', '-_id'])
    if data:
        is_on = data['is_on']
        if not is_on:
            await bot.send_message(message.chat.id, 'Bu savol avtori tomonidan vaqtincha to`xtatilgan')
            await state.finish()
            return

        attempt = attempt_coll.find_one({'user_id': message.from_user.id, 'key': message.text})
        if not attempt:
            attempt_coll.insert_one({"user_id": message.from_user.id, 'key': message.text, 'count': 1})
        elif int(attempt['count']) < 10:
            count = attempt['count']
            attempt_coll.update_one({'user_id': message.from_user.id},
                                    {"$set": {"user_id": message.from_user.id, 'count': count + 1,
                                              'key': message.text}},
                                    upsert=False)
        else:
            await bot.send_message(message.chat.id, 'Siz 10ta imkoniyatdan foydalanib bo`ldingiz!')
            await state.finish()
            return

        question = data['questions']
        random.shuffle(question)
        await state.update_data(question=question)
        time_interval = int(data['time'])
        await state.update_data(time=time_interval)
        await state.update_data(key=message.text)
        answers = generate_ans(question[0][1])
        await state.update_data(correct=answers[int(answers[-1])])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        for i in answers[:-1]:
            markup.add(i)
        await FormAbt.next()
        await bot.send_message(message.chat.id,
                               f'Sizga har bir savolga javob berish uchun {str(time_interval)} sekund vaqt beriladi.')
        time.sleep(2)
        await bot.send_photo(message.chat.id, question[0][0],
                             'Savolga javobni tugmalar orqali bering.\n E`tiborli bo`ling', reply_markup=markup)
        run_time(scheduler, kick_user, time_interval, [state, message])
    else:
        await bot.send_message(message.chat.id, 'Kodni xato kiritdingiz, Iltimos qayta urinib ko`ring')
        return


@dp.message_handler(state=FormAbt.result)
async def process_get_questions(message: types.Message, state: FSMContext):
    data = await state.get_data()
    result = data.get('result') or 0
    if data['correct'] != message.text:
        if scheduler.running:
            scheduler.shutdown()
        await state.finish()
        await bot.send_message(message.chat.id, 'Siz noto`g`ri javob berdingiz, Tayyorlanib qayta urinib ko`ring',
                               reply_markup=types.ReplyKeyboardRemove())

        attempt = attempt_coll.find_one({'user_id': message.from_user.id, 'key': data['key']})

        if int(attempt['count']) >= 10:
            users_data = users_coll.find_one({'user_id': message.from_user.id}, ['user_id', 'name'])
            if not users_data['name']:
                await bot.send_message(message.from_user.id,
                                       'Sizning ismingiz bazaga kiritlmagan. /name orqali ismingizni bazaga yozib qo`ying')

            username = message.from_user.username or None
            user_result = {
                'username': username,
                'key': data['key'],
                'user_id': message.from_user.id,
                'success': 'No'
            }
            results_coll.update_one({'user_id': message.from_user.id, 'key': data['key']}, {"$set": user_result},
                                    upsert=True)
    else:
        result += 1
        if result < 20:
            if scheduler.running:
                scheduler.shutdown()
            question = data['question']
            time_interval = data['time']
            answers = generate_ans(question[result][1])
            await state.update_data(correct=answers[int(answers[-1])])
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
            for i in answers[:-1]:
                markup.add(i)

            await bot.send_photo(message.chat.id, question[result][0],
                                 'Savolga javobni tugmalar orqali bering.\n E`tiborli bo`ling', reply_markup=markup)

            run_time(scheduler, kick_user, time_interval, [state, message])
            await state.update_data(result=result)
        else:
            if scheduler.running:
                scheduler.shutdown()
            await FormAbt.next()
            await bot.send_message(message.chat.id,
                                   'Siz hamma savolga to`g`ri javob berdingiz! Shunday o`qishda davom eting!',
                                   reply_markup=types.ReplyKeyboardRemove())

            users_data = users_coll.find_one({'user_id': message.from_user.id}, ['user_id', 'name'])

            if not users_data:
                await bot.send_message(message.from_user.id,
                                       'Sizning ismingiz bazaga kiritlmagan. /name orqali ismingizni bazaga yozib qo`ying')

            username = message.from_user.username or None
            user_result = {
                'username': username,
                'key': data['key'],
                'user_id': message.from_user.id,
                'success': 'Yes'
            }
            results_coll.update_one({'user_id': message.from_user.id, 'key': data['key']}, {'$set': user_result},
                                    upsert=True)
            await state.finish()



@dp.message_handler(commands='getR')
async def process_get_results(message: types.Message):
    await FormTeacher.get_result.set()

    await bot.send_message(message.chat.id, 'Natijalarni olish uchun maxsus kodni kiriting!')


@dp.message_handler(state=FormTeacher.get_result)
async def process_set_results(message: types.Message, state: FSMContext):
    link = 'Hamma ismini kirtmagan'
    data = [i for i in results_coll.find({"key": message.text}, ['user_id', '-_id', 'success'])]
    if not data:
        await bot.send_message(message.chat.id, "Kod xato!")
    else:
        link = get_results(data)
    await state.finish()
    await bot.send_message(message.chat.id, link)


async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL, certificate=open(WEBHOOK_SSL_CERT, 'rb'))


@dp.message_handler(commands=['offBot'])
async def process_off(message: types.Message):
    await bot.send_message(message.chat.id, 'Savollarning maxsus kodini kiriting!')
    await IsOff.key.set()


@dp.message_handler(state=IsOff.key)
async def off_bot_by_key(message: types.Message, state: FSMContext):
    key = message.text
    question_coll.update_one({'key': key}, {'$set': {'is_on': False}}, upsert=False)
    await bot.send_message(message.chat.id, f'{key} kodli savol imkoniyatlari to`xtatildi')
    await state.finish()


@dp.message_handler(commands=['onBot'])
async def process_on(message: types.Message):
    await bot.send_message(message.chat.id, 'Savollarning maxsus kodini kiriting!')
    await IsOn.key.set()


@dp.message_handler(state=IsOn.key)
async def on_bot_by_key(message: types.Message, state: FSMContext):
    key = message.text
    question_coll.update_one({'key': key}, {'$set': {'is_on': True}}, upsert=False)
    await bot.send_message(message.chat.id, f'{key} kodli savol imkoniyatlari faollashtirildi')
    await state.finish()


@dp.message_handler(commands=['name'])
async def process_auth(message: types.Message):
    await Auth.name.set()

    await bot.send_message(message.chat.id, 'Ism-sharifingizni kiriting!')


@dp.message_handler(state=Auth.name)
async def process_name(message: types.Message, state: FSMContext):
    users_coll.update_one({'user_id': message.from_user.id},
                          {'$set': {'name': message.text, 'user_id': message.from_user.id}}, upsert=True)
    await state.finish()
    await bot.send_message(message.chat.id, 'Sizning ism sharifingiz yozib olindi')


async def on_shutdown(dispatcher: Dispatcher):
    logging.warning('Shutting down..')
    await bot.delete_webhook()
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


if __name__ == '__main__':
    # executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)
    start_webhook(
         dispatcher=dp,
         webhook_path=WEBHOOK_PATH,
         on_startup=on_startup,
         on_shutdown=on_shutdown,
         skip_updates=True,
         host=WEBAPP_HOST,
         port=WEBAPP_PORT,
         ssl_context=context
     )

