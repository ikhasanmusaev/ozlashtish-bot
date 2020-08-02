from dotenv import load_dotenv
from os import path, getenv
import logging
import random
import time

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.utils import executor

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from helper import generate_key, FormTeacher, FormAbt, generate_test, generate_ans, run_time, get_results
from db.connection import question_coll, results_coll

logging.basicConfig(level=logging.INFO)

env_path = path.abspath(path.join(path.dirname(path.abspath(__file__)), '../.env'))
load_dotenv(dotenv_path=env_path)
scheduler = AsyncIOScheduler()

TOKEN = getenv('TOKEN')
bot = Bot(token=TOKEN)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


async def kick_user(state, message):
    scheduler.shutdown()
    await state.finish()
    await bot.send_message(message.chat.id,
                           'Siz belgilangan vaqtda javob bera olmadingiz yoki sizning javobingiz noto`g`ri.\n Tayyorlanib, keyinroq harakat qiling.',
                           reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add('Boshlash!')

    await message.reply("Salom! O'z ustingizda ishlashdan to'xtamang!")
    await message.reply("Savol-javobni boshlash uchun 'Boshlash!' ni bosing", reply_markup=markup)


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
    try:
        scheduler.shutdown()
    except:
        pass
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
    await bot.send_message(message.chat.id, 'Misol: To`g`ri javob\nNoto`g`ri javob\nNoto`g`ri javob\n...')


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
        await message.reply(f'{len(questions_q) + 1}-savolning rasmini kiriting!')


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
            'key': secret_key
        }

        question_coll.insert_one(to_db)

    # Finish conversation
    await state.finish()


@dp.message_handler(Text(equals='Boshlash!', ignore_case=True) | Text(equals='Boshlash', ignore_case=True))
async def process_starting(message: types.Message):
    await FormAbt.name.set()
    markup = types.ReplyKeyboardRemove()

    await bot.send_message(message.chat.id, 'Ism sharifingizni kiriting!', reply_markup=markup)


@dp.message_handler(state=FormAbt.name)
async def process_name(message: types.Message, state: FSMContext):
    await FormAbt.next()
    await state.update_data(name=message.text)

    await bot.send_message(message.chat.id, 'Savollar uchun maxsus kodni kiriting!')


@dp.message_handler(lambda message: message.text[0] != "_", state=FormAbt.question)
async def process_key_invalid(message: types.Message):
    await bot.send_message(message.chat.id, 'Kodni xato kiritdingiz, Iltimos qayta urinib ko`ring')


@dp.message_handler(lambda message: message.text[0] == "_", state=FormAbt.question)
async def process_get_questions(message: types.Message, state: FSMContext):
    data = question_coll.find_one({"key": message.text}, ['questions', 'time', '-_id'])
    if data:
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
        time.sleep(3)
        await bot.send_photo(message.chat.id, question[0][0],
                             'Savolga javobni tugmalar orqali bering.\n E`tiborli bo`ling', reply_markup=markup)
        run_time(scheduler, kick_user, time_interval, [state, message])
    else:
        await bot.send_message(message.chat.id, 'Kodni xato kiritdingiz, Iltimos qayta urinib ko`ring')


@dp.message_handler(state=FormAbt.result)
async def process_get_questions(message: types.Message, state: FSMContext):
    data = await state.get_data()
    result = data.get('result') or 0
    if data['correct'] != message.text:
        await kick_user(state, message)
    else:
        result += 1
        if result < 5:

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
            await FormAbt.next()
            await bot.send_message(message.chat.id,
                                   'Siz hamma savolga to`g`ri javob berdingiz! Shunday o`qishda davom eting!',
                                   reply_markup=types.ReplyKeyboardRemove())
            username = message.from_user.username or None
            user_result = {
                'name': data['name'],
                'username': username,
                'key': data['key'],
            }
            results_coll.insert_one(user_result)
            await state.finish()
            scheduler.shutdown()


@dp.message_handler(commands='getR')
async def process_get_results(message: types.Message):
    await FormTeacher.get_result.set()

    await bot.send_message(message.chat.id, 'Natijalarni olish uchun maxsus kodni kiriting!')


@dp.message_handler(state=FormTeacher.get_result)
async def process_set_results(message: types.Message, state: FSMContext):
    data = [i for i in results_coll.find({"key": message.text}, ['name', 'username', '-_id'])]
    link = get_results(data)

    await bot.send_message(message.chat.id, link)


async def shutdown(dispatcher: Dispatcher):
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


# async def on_startup(dispatcher: Dispatcher):
#     scheduler.start()
#
#
# async def on_shutdown(dispatcher: Dispatcher):
#     scheduler.shutdown()
#
#
# def setup(executor: Executor):
#     executor.on_startup(on_startup)
#     executor.on_shutdown(on_shutdown)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)
