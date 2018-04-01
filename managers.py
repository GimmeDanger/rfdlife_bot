# !/usr/bin/env python
# _*_ coding: utf-8 _*_
import json
from calendar import monthrange
from datetime import datetime, timedelta

import requests
from telebot import types

import config
import tokens
from utils import bold, cut_long_text, global_lock, is_non_zero_file, link_user, my_bot, subs_notify, user_action_log, \
    user_name


class DataJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UserSettings):
            obj.data['__type__'] = obj.__class__.__name__
            return obj.data
        return json.JSONEncoder.default(self, obj)


class DataJsonDecoder(json.JSONDecoder):
    def __init__(self, *args, **kargs):
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object, *args, **kargs)

    @staticmethod
    def dict_to_object(d):
        if '__type__' not in d:
            return d

        obj_type = d.pop('__type__')
        try:
            if obj_type == UserSettings.__name__:
                obj = UserSettings(d)
                return obj
        except:
            d['__type__'] = obj_type
        return d


class DataManager:
    def __init__(self, file_name=config.FileLocation.user_data):
        self.file_name = file_name
        self.data = dict()
        self.load()

    def load(self):
        if is_non_zero_file(self.file_name):
            global_lock.acquire()
            with open(self.file_name, 'r', encoding='utf-8') as file:
                self.data = json.load(file, cls=DataJsonDecoder)
            global_lock.release()

    def save(self):
        global_lock.acquire()
        with open(self.file_name, 'w', encoding='utf-8') as file:
            json.dump(self.data, file, cls=DataJsonEncoder, indent=True, ensure_ascii=False)
        global_lock.release()

    def dump_file(self, message):
        if is_non_zero_file(self.file_name):
            global_lock.acquire()
            with open(self.file_name, 'r', encoding='utf-8') as file:
                for text in cut_long_text(file.read()):
                    my_bot.reply_to(message, text)
            global_lock.release()

    def command_need_name(self, func):
        def wrapped(message):
            if not self.is_registered(message) or not self.is_name_set(message):
                user_action_log(message, "not registered to call: " + message.text)
                self.register_user(message)
                return
            return func(message)

        return wrapped

    def is_registered(self, message):
        if self.data.get(str(message.from_user.id)) is not None:
            if self.data.get(str(message.from_user.id)).get('authenticated', 'False') == 'True':
                return True
        return False

    def is_name_set(self, message):
        if self.data.get(str(message.from_user.id)) is not None:
            if self.data.get(str(message.from_user.id)).get('name') is not None:
                return True
        return False

    def register_user(self, message):
        if not self.is_registered(message):
            sent = my_bot.send_message(message.from_user.id,
                                       bold('❗️ Авторизация') + '\n\nВведи пароль:', parse_mode="HTML")
            my_bot.register_next_step_handler(sent, self.check_password)
            return

        sent = my_bot.send_message(message.from_user.id,
                                   '❓ Твой номер в '
                                   '<a href=\"https://corp.rfdyn.ru/index.php/acs-tabel-intermediadate/\">СКД</a>?\n'
                                   'Например: 5059, 5060 и т.д.', parse_mode="HTML")
        my_bot.register_next_step_handler(sent, self.set_user_name)

    def check_password(self, message):
        if tokens.access_pswd != "" and message.text == tokens.access_pswd:
            if self.data.get(str(message.from_user.id)) is None:
                self.data[str(message.from_user.id)] = {"authenticated": "True"}
            else:
                self.data[str(message.from_user.id)]["authenticated"] = "True"
            user_action_log(message, "successfully registered")
            my_bot.reply_to(message, "✅ Пароль верный!")
            subs_notify(config.admin_ids, '✨ Новый пользователь: {}'.format(link_user(message.from_user)))
            self.register_user(message)
        else:
            user_action_log(message, "entered wrong password")
            my_bot.reply_to(message, "⛔ Пароль не подошел!\n\nВызывай /start для новой попытки.")

    def set_user_name(self, message):
        my_data.data[str(message.from_user.id)]['who'] = user_name(message.from_user)
        # Todo: check existing
        if message.text.isdigit():
            self.data[str(message.from_user.id)]['name'] = str(message.text)
            self.register_user_finish(message)
        else:
            my_bot.send_message(message.from_user.id, '⚠️ Ошибка, нужно указать номер')

    def register_user_finish(self, message):
        my_data.data[str(message.from_user.id)]['settings'] = UserSettings()
        self.save()
        my_bot.reply_to(message, '✅ Данные сохранены', parse_mode="HTML", disable_web_page_preview=True)
        with open(config.FileLocation.cmd_help, 'r', encoding='utf-8') as file:
            my_bot.send_message(message.from_user.id, file.read(), parse_mode="HTML", disable_web_page_preview=True)

    def list_users(self, for_what=None):
        all_users = self.data.keys()
        if for_what is None:
            return all_users
        if for_what == 'morning_birthdays':
            return [user_id for user_id in all_users if self.get_user_settings(user_id)[for_what] == 'on']

    def get_user_name(self, user_id):
        return self.data.get(str(user_id), {}).get('name', '5059')

    def get_user_settings(self, user_id):
        user = self.data[str(user_id)]
        if user.get('settings') is None:
            user['settings'] = UserSettings()
        return user['settings']

    def add_alert_name(self, message):
        split = message.text.split(' ', 1)
        if len(split) > 1:
            if self.data[str(message.from_user.id)].get('alert_users') is not None:
                if self.data[str(message.from_user.id)]['alert_users'].count(split[1]) == 0:
                    self.data[str(message.from_user.id)]['alert_users'].append(split[1])
            else:
                self.data[str(message.from_user.id)]['alert_users'] = [split[1]]
            self.save()
            my_bot.reply_to(message, '⚙️ Оповещения о {} включены!'.format(split[1]))
        else:
            my_bot.reply_to(message, 'Использование: /alert_add <ФИО из /in_office>')

    def erase_alert_name(self, message):
        split = message.text.split(' ', 1)
        if len(split) > 1:
            if self.data[str(message.from_user.id)].get('alert_users') is not None:
                if self.data[str(message.from_user.id)]['alert_users'].count(split[1]) != 0:
                    self.data[str(message.from_user.id)]['alert_users'].remove(split[1])
                    self.save()
                    my_bot.reply_to(message, '⚙️ Оповещения о {} выключены!'.format(split[1]))
                    return
        my_bot.reply_to(message, 'Использование: /alert_erase <ФИО из /in_office>')

    def list_alert_name(self, message):
        users = self.data[str(message.from_user.id)].get('alert_users')
        if users is not None and len(users) > 0:
            my_bot.reply_to(message, '⚙️ Ваш список оповещений:\n— <code>{}</code>\n\n'
                                     'Используйте /alert_add и /alert_erase для управления списком.'
                                     ''.format('</code>\n— <code>'.join(users)), parse_mode='HTML')
        else:
            my_bot.reply_to(message, '⚙️ Ваш список оповещений пуст.\n\n'
                                     'Используйте /alert_add и /alert_erase для управления списком.')


class Setting:
    def __init__(self, show_name, statuses, statuses_emoji, help_text):
        self.show_name = show_name
        self.help_text = help_text

        if len(statuses) != len(statuses_emoji):
            raise IndexError
        self.statuses = statuses
        self.statuses_emoji = statuses_emoji
        self.len = len(statuses)
        self.curr = 0

    def get(self):
        return self.statuses[self.curr]

    def set(self, status):
        self.curr = self.statuses.index(status)

    def get_emoji(self):
        return self.statuses_emoji[self.curr]

    def defaultify(self):
        self.curr = 0

    def next(self):
        self.curr = (self.curr + 1) % self.len


class UserSettings:
    def __init__(self, data=None):
        self.settings_info = {
            'morning_birthdays':
                Setting('Дни рождения:', ['on', 'off'], ['🔔', '🔕'],
                        'Оповещение о днях рождения с утра.\n'
                        '🔔 — оповещать\n'
                        '🔕 — отключить оповещения'),
            'alert_about_users':
                Setting('Появление сотрудников:', ['on', 'when_in_office', 'off'], ['🔔', '🔔+🖥', '🔕'],
                        'Оповещение о появлении сотрудников в офисе (команда /alert).\n'
                        '🔔 — оповещать всегда\n'
                        '🔔+🖥 — оповещать только, когда я в офисе\n'
                        '🔕 — отключить оповещения')}

        if data is None:
            self.data = {}
            self.defaultify_all()
        else:
            self.data = data
            for name, setting in self.settings_info.items():
                if self.data.get(name) is not None:
                    setting.set(self.data[name])

    def __getitem__(self, item):
        return self.data[item]

    def defaultify_all(self):
        for name, setting in self.settings_info.items():
            setting.defaultify()
            self.data[name] = setting.get()

    def show_settings_message(self, message):
        my_bot.reply_to(message, 'Ваши настройки\n\nПримечание: при нажатии на кнопки слева '
                                 'появляется описание настройки', reply_markup=self.generate_settings_buttons())

    def generate_settings_buttons(self):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(types.InlineKeyboardButton(text="Оповещения:", callback_data="settings_dummy"))
        for name, setting in self.settings_info.items():
            keyboard.row(types.InlineKeyboardButton(text=setting.show_name, callback_data="settings_help_" + name),
                         types.InlineKeyboardButton(text=setting.get_emoji(), callback_data="settings_" + name))
        keyboard.row(types.InlineKeyboardButton(text="❎ Сброс настроек", callback_data="settings_default"))
        return keyboard

    def settings_update(self, call):
        message = call.message

        cmd_name = call.data.split('_', 1)[1]
        if cmd_name == 'dummy':
            my_bot.answer_callback_query(callback_query_id=call.id)
            return
        elif cmd_name.startswith('help'):
            setting_name = cmd_name.split('_', 1)[1]
            my_bot.answer_callback_query(callback_query_id=call.id, show_alert=True,
                                         text=self.settings_info[setting_name].help_text)
            return
        elif cmd_name == 'default':
            self.defaultify_all()
        else:
            self.settings_info[cmd_name].next()
            self.data[cmd_name] = self.settings_info[cmd_name].get()

        my_bot.answer_callback_query(callback_query_id=call.id, show_alert=False, text="✅  Настройки обновлены")
        my_bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=message.message_id,
                                         reply_markup=self.generate_settings_buttons())


class AcsManager:
    def __init__(self):
        self.acs_url = 'https://corp.rfdyn.ru/index.php/acs-tabel-intermediadate/index-text'
        self.in_url = 'https://corp.rfdyn.ru/index.php/site/now-in-office-text'
        self.in_office = set()
        self.in_office_old = set()

        self.asc_unaccessible_error = 'Сервер СКД сейчас недоступен :('

        self.keyboard = types.InlineKeyboardMarkup()
        self.keyboard.add(types.InlineKeyboardButton(text="🔄", callback_data="in_office_update"))

    @staticmethod
    def time_format(time):
        return time.strftime('%Y-%m-%d')

    @staticmethod
    def reply_format(text, start_date, end_date):
        if is_non_zero_file(config.FileLocation.acs_answer):
            with open(config.FileLocation.acs_answer, 'r', encoding='utf-8') as file:
                split = text.split()
                nice = file.read()
                return nice.format(split[-5], split[-4], start_date, end_date, split[-2], split[-1])
        return text

    @staticmethod
    def state_format(text):
        if is_non_zero_file(config.FileLocation.acs_state_answer):
            with open(config.FileLocation.acs_state_answer, 'r', encoding='utf-8') as file:
                split = text.split()
                nice = file.read()
                if len(split) > 17:
                    return nice.format(split[-6], split[-5], 'В офисе' if split[18] == 'Вход' else 'Не в офисе',
                                       split[-2])
                return '🌴 Не в офисе сегодня 🌴'
        return text

    def year_time(self, message):
        today = datetime.today()
        year_start = today.replace(day=1, month=1)
        year_end = today.replace(day=31, month=12)
        self._make_time_request(message, year_start, year_end)

    def month_time(self, message):
        today = datetime.today()
        month_start = today.replace(day=1)
        month_end = today.replace(day=monthrange(today.year, today.month)[1])
        self._make_time_request(message, month_start, month_end)

    def week_time(self, message):
        today = datetime.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        self._make_time_request(message, week_start, week_end)

    def day_time(self, message):
        today = datetime.today()
        self._make_time_request(message, today, today)

    def _make_time_request(self, message, start_date, end_date):
        payload = (('AcsTabelIntermediadateSearch[staff_id]', my_data.get_user_name(message.from_user.id)),
                   ('AcsTabelIntermediadateSearch[date_pass_first]', self.time_format(start_date)),
                   ('AcsTabelIntermediadateSearch[date_pass_last]', self.time_format(end_date)),
                   ('AcsTabelIntermediadateSearch[summary_table]', '1'))

        response = requests.get(self.acs_url, auth=(tokens.auth_login, tokens.auth_pswd), params=payload)
        answer = self.reply_format(response.text,
                                   self.time_format(start_date),
                                   self.time_format(end_date)) if response.ok else self.asc_unaccessible_error
        my_bot.reply_to(message, answer, parse_mode="HTML")

    def in_office_now_text(self, user_id=0):
        in_office_txt = self._make_in_office_request()
        for alert_user in my_data.data.get(str(user_id), {}).get('alert_users', []):
            in_office_txt = in_office_txt.replace(alert_user, bold(alert_user))
        return '👥 ' + in_office_txt

    def in_office_now(self, message):
        text = self.in_office_now_text(message.from_user.id)
        my_bot.reply_to(message, text, reply_markup=self.keyboard, parse_mode="HTML")

    def in_office_update(self, call):
        message = call.message
        text = self.in_office_now_text(message.chat.id)
        my_bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=text, parse_mode="HTML")
        my_bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=message.message_id,
                                         reply_markup=self.keyboard)
        my_bot.answer_callback_query(callback_query_id=call.id, show_alert=False, text="✅  Данные обновлены")

    def in_office_alert(self):
        def need_alert():
            if my_data.get_user_settings(user_id)['alert_about_users'] == 'on':
                return True
            if my_data.get_user_settings(user_id)['alert_about_users'] == 'when_in_office':
                return self.is_user_in_office(user_id)

        self.in_office = set(self._make_in_office_request().split('\n'))
        if len(self.in_office) == 1:
            return
        if len(self.in_office_old) == 0:
            self.in_office_old = self.in_office
            return
        come = self.in_office - self.in_office_old
        gone = self.in_office_old - self.in_office

        for user_id, user in my_data.data.items():
            if need_alert():
                for alert_user in user.get('alert_users', []):
                    if alert_user in come:
                        my_bot.send_message(user_id, '👨🏻‍💻️ {} сейчас в офисе!'.format(alert_user))
                    if alert_user in gone:
                        my_bot.send_message(user_id, '🙇🏻 {} теперь не в офисе!'.format(alert_user))
        self.in_office_old = self.in_office

    def _make_in_office_request(self):
        response = requests.get(self.in_url, auth=(tokens.auth_login, tokens.auth_pswd))
        return response.text if response.ok else ''

    def user_state(self, message):
        today = datetime.today()

        payload = (('AcsTabelIntermediadateSearch[staff_id]', my_data.get_user_name(message.from_user.id)),
                   ('AcsTabelIntermediadateSearch[date_pass_first]', self.time_format(today)),
                   ('AcsTabelIntermediadateSearch[date_pass_last]', self.time_format(today)))

        response = requests.get(self.acs_url, auth=(tokens.auth_login, tokens.auth_pswd), params=payload)
        answer = self.state_format(response.text) if response.ok else self.asc_unaccessible_error
        my_bot.reply_to(message, answer, parse_mode="HTML")

    def is_user_in_office(self, user_id):
        today = datetime.today()

        payload = (('AcsTabelIntermediadateSearch[staff_id]', my_data.get_user_name(user_id)),
                   ('AcsTabelIntermediadateSearch[date_pass_first]', self.time_format(today)),
                   ('AcsTabelIntermediadateSearch[date_pass_last]', self.time_format(today)))

        response = requests.get(self.acs_url, auth=(tokens.auth_login, tokens.auth_pswd), params=payload)
        if response.ok:
            split = response.text.split()
            if len(split) > 17:
                return split[18] == 'Вход'
        return True


my_data = DataManager()
my_acs = AcsManager()
