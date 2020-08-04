import random
import string

from telegraph import Telegraph
from aiogram.dispatcher.filters.state import State, StatesGroup

telegraph = Telegraph(access_token='0e1091ab7dacc5a12236177b70bbd426c822904a075efa5e22a4ffd7eff0')


def generate_key(length):
    return '_' + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def get_results(results):
    content = '<h3>Ro`yxat</h3> <hr> '
    for i in results:
        content += f'<p>Ism: {i["name"]} Username: {i["username"]}</p>'
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
    scheduler.start()


class FormTeacher(StatesGroup):
    count = State()
    time = State()
    questionsI = State()  # photo_id list of questions
    questionsQ = State()  # answers list of questions
    is_yes = State()
    get_result = State()


class FormAbt(StatesGroup):
    name = State()
    question = State()
    result = State()
    final = State()
    time = State()
    correct = State()
    list_q = State()
    key = State()