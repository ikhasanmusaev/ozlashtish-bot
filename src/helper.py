import random
import string

from telegraph import Telegraph
from aiogram.dispatcher.filters.state import State, StatesGroup

from db.connection import users_coll

telegraph = Telegraph(access_token='0e1091ab7dacc5a12236177b70bbd426c822904a075efa5e22a4ffd7eff0')


def generate_key(length):
    return '_' + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def get_results(results):
    content = '<h3>Ro`yxat</h3> <hr> '
    content_yes = ''
    content_no = ''
    for i in results:
        if i['success'] == 'Yes':
            data = users_coll.find_one({'user_id': i['user_id']}, ['user_id', ])
            content_yes += f'<p>{data["name"]}</p>'
        else:
            content_no += f'<p>{data["name"]}</p>'
    content += '<b>O`tganlar:</b><br>' + content_yes + '<hr>' + '<b>O`ta olmaganlar:</b><br>' + content_no
    response = telegraph.create_page(
        "A'lochilar",
        html_content=content
    )

    return response['url']


def generate_test(questions, answers):
    final_list = []
    my_list = [0, 1]
    for i, q in enumerate(questions):
        my_list[0] = q
        my_list[1] = answers[i]
        final_list.append(my_list)
        my_list = [0, 1]

    return final_list


def generate_ans(ans_str):
    ans = ans_str.split('\n')
    correct = ans[0]

    random.shuffle(ans)
    i = ans.index(correct)
    ans.append(i)

    return ans


def run_time(scheduler, function, time, args):
    scheduler.add_job(function, 'interval', args=args, seconds=time)
    if not scheduler.running:
        scheduler.start()


class FormTeacher(StatesGroup):
    count = State()
    time = State()
    questionsI = State()  # photo_id list of questions
    questionsQ = State()  # answers list of questions
    is_yes = State()
    get_result = State()


class FormAbt(StatesGroup):
    # name = State()
    question = State()
    result = State()
    final = State()
    time = State()
    correct = State()
    list_q = State()
    key = State()


class IsOn(StatesGroup):
    key = State()


class IsOff(StatesGroup):
    key = State()


class Auth(StatesGroup):
    name = State()
