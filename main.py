from flask import Flask
from flask import request
from flask import jsonify
from flask import json
from flask import make_response
from models import Branch
from models import Mark
from models import Favorite
from flask_sslify import SSLify
import models
import requests
import json
import re
import os
from configparser import ConfigParser

app = Flask(__name__)
sslify = SSLify(app)
CONFIG = ConfigParser()
CONFIG.read("conf.ini")


class TravisCI:

    def __init__(self):
        self.token = {"Authorization": CONFIG.get("travis", "travis_token")}
        self.version = {"Travis-API-Version": "3"}
        self.base_url = CONFIG.get("travis", "travis_base_url")
        self.repository_id = CONFIG.get("travis", "travis_repository_id")

    def trigger(self, command, branch):
        body = {"request": {"branch": branch, "config": {"script": f"pytest -m {command}"}}}
        response = requests.post(url=f"{self.base_url}/repo/{self.repository_id}/requests", json=body,
                                 headers={**self.token, **self.version})
        return response


class TgHelper:

    def __init__(self):
        self.chat_id = CONFIG.get("telegram", "telegram_chat_id")
        self.URL = CONFIG.get("telegram", "telegram_bot_url")

    def send_message(self, chat_id, text, markup=None):
        url = self.URL + 'sendMessage'
        answer = {'chat_id': chat_id, 'text': text}
        if markup is not None:
            description_list = [x for x in markup[1::2]]
            name_list = [x for x in markup[::2]]
            keys_list = []
            for name, description in zip(description_list, name_list):
                keys_list.append({'text': name, 'callback_data': description})
            answer.update({'reply_markup': json.dumps({'inline_keyboard': [keys_list]})})
        response = requests.post(url, json=answer)
        return response

    @staticmethod
    def split(data):
        delimiter = re.split(r'[`\-=~!@#$%^&*()+\[\]{};\'\\:"|<,./>?]', data)
        return delimiter


class DbHelper:

    def create_tables(self):
        with models.db:
            models.db.create_tables([Mark, Branch, Favorite])

    def select_db(self, branch=None, favorite=None):
        if branch is not None:
            data_list = []
            selection = Branch.select(Branch.branch_name, Branch.branch_description)
            for x in selection:
                data_list.extend([x.branch_name, x.branch_description])
            return data_list
        elif favorite is not None:
            data_list = []
            selection = Favorite.select(Favorite.favorite_branch)
            for x in selection:
                data_list.extend([x.favorite_branch])
            return data_list
        else:
            data_list = []
            selection = Mark.select(Mark.mark_name, Mark.mark_description)
            for x in selection:
                data_list.extend([x.mark_name, x.mark_description])
            return data_list

    def insert_db(self, user_data, branch_data=None, favorite=None):
        if branch_data is not None:
            new_record = Branch.create(branch_description=user_data[0], branch_name=user_data[1])
            return new_record
        if favorite is not None:
            favorite_branch = Favorite.create(favorite_branch=user_data)
            return favorite_branch
        else:
            new_record = Mark.create(mark_description=user_data[0], mark_name=user_data[1])
            return new_record

    def detele_db(self, user_data):
        if "del_b" in user_data:
            delete_branch = Branch.get(Branch.branch_name == user_data[1])
            delete_branch.delete_instance()
        elif "del_m" in user_data:
            delete_mark = Mark.get(Mark.mark_name == user_data[1])
            delete_mark.delete_instance()

    def update_db(self, userdata):
        data_favorite = (Favorite.update({Favorite.favorite_branch: userdata}).where(Favorite.id == 1).execute())
        return data_favorite


@app.before_request
def before_request():
    if not os.path.isfile("telegram_bot.db"):
        open("telegram_bot.db", "w+")
        DbHelper().create_tables()
    models.db.connect()


@app.after_request
def after_request(response):
    models.db.close()
    return response


@app.route(f'/bot', methods=['POST', 'GET'])
def index():
    if request.method == 'GET' or "POST":
        request_json = request.get_json()
        if request_json.get("message") is not None:
            message = request_json['message'].get("text")
            if "run" in message:
                TgHelper().send_message(chat_id=TgHelper().chat_id, text="Выберите комплект для прогона автотестов",
                                        markup=DbHelper().select_db())
                return make_response(jsonify("Success"), 200)
            if "select" in message:
                TgHelper().send_message(chat_id=TgHelper().chat_id,
                                        text="Выберите ветку по умолчания для прогона автотестов",
                                        markup=DbHelper().select_db(branch=True))
                return make_response(jsonify("Success"), 200)
            if "add_b" in message or "add_m" in message:
                try:
                    user_data = message[5::]
                    data_list = [x.strip() for x in TgHelper.split(user_data)]
                    if "add_b" in message:
                        DbHelper().insert_db(branch_data=True, user_data=data_list)
                        TgHelper().send_message(chat_id=TgHelper().chat_id, text="Добавление ветки произошло успешно")
                    else:
                        DbHelper().insert_db(user_data=data_list)
                        TgHelper().send_message(chat_id=TgHelper().chat_id,
                                                text="Добавление комплекта тестов произошло успешно")
                except IndexError:
                    TgHelper().send_message(chat_id=TgHelper().chat_id, text="Не хватает разделителя")
                finally:
                    return make_response(jsonify("Success"), 200)
            if "del_b" in message or "del_m" in message:
                try:
                    data_list = [x.strip() for x in message.split(" ")]
                    DbHelper().detele_db(user_data=data_list)
                    TgHelper().send_message(chat_id=TgHelper().chat_id, text="Удаление произошло успешно")
                except Exception as error:
                    TgHelper().send_message(chat_id=TgHelper().chat_id, text=f"Произошла ошибка. Описание: {error}")
                finally:
                    return make_response(jsonify("Success"), 200)
        elif request_json["callback_query"]["from"].get("is_bot") is False:
            DbHelper().create_tables()
            branch_selected_data = DbHelper().select_db(branch=True)
            mark_selected_data = DbHelper().select_db()
            user_choice = request_json["callback_query"].get("data")
            if user_choice in branch_selected_data:
                table_data = DbHelper().select_db(favorite=True)
                if len(table_data) == 0:
                    DbHelper().insert_db(user_choice, favorite=True)
                favorite_data = DbHelper().update_db(user_choice)
                TgHelper().send_message(chat_id=TgHelper().chat_id, text="Ветка выбрана успешно")
                return str(favorite_data)
            if user_choice in mark_selected_data:
                f_branch = "".join(DbHelper().select_db(favorite=True))
                TravisCI().trigger(command=user_choice, branch=f_branch)
                TgHelper().send_message(chat_id=TgHelper().chat_id,
                                        text=f"Комплект с меткой {user_choice} и веткой {f_branch} был запущен. Ожидайте результатов")
            else:
                TgHelper().send_message(chat_id=TgHelper().chat_id,
                                        text=f"Пожалуйста, выберите ветку для запуска")
    return make_response(jsonify("Success"), 200)
