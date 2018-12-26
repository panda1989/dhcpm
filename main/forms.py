from flask_wtf import FlaskForm
#from flask.ext.wtf import Form
from wtforms import IntegerField, RadioField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import IPAddress, NumberRange, Regexp, Required

class GetInfoForm(FlaskForm):
    subnet = StringField('Введите адрес хоста или подсети:', validators=[Required(),IPAddress()])
    submit = SubmitField('ИСКАТЬ')

class SearchDayForm(FlaskForm):
    day_counter = SelectField('Глубина поиска, дней: ',choices=[('0','0'),('1','1'),('2','2'),('3','3'),('4','4'),('5','5'),('6','6'),('7','7')])
    submit = SubmitField('ПРИМЕНИТЬ')

class SearchMainForm(FlaskForm):
    search_string = StringField('Строка поиска: ', validators=[Required()])
    flag = RadioField(' ',choices=[('1','Искать в ранее найденном'),('2','Новый поиск'),('3','Перезагрузить лог-файлы (соответственно ранее выбранной глубине поиска)')])
    submit = SubmitField('ИСКАТЬ')

class RestartForm(FlaskForm):
    flag = RadioField('Перезагрузить сервер: ',choices=[('1','DHCP 1'),('2','DHCP 2')])
    submit = SubmitField('Перезагрузить')

class AddHostForm(FlaskForm):
    mac = StringField('MAC-адрес [01:23:45:67:89:ab]: ', validators=[Regexp('^([0-9a-f]{2}:){5}([0-9a-f]{2})$',message='MAC-адрес может содержать только символы 0-9,:,a-f(маленькие!)')])
    ip = StringField('IP-адрес: ', validators=[Required(),IPAddress()])
    type = SelectField('Тип хоста: ',choices=[('pon','Обычный абонент PON'),('tech','Транк, шлюз Ростелеком, проч. технологические')])
    submit = SubmitField('Сформировать конфигурацию')

class AddNetForm(FlaskForm):
    ip = StringField('IP-адрес подсети: ', validators=[Required(),IPAddress()])
    mask = StringField('Маска подсети: ', validators=[Required(),IPAddress()])
    static = IntegerField('Количество статических хостов: ', default=8, validators=[Required(),NumberRange(min=1,max=100,message='ВНЕ ДИАПАЗОНА!(1-100)')])
    submit = SubmitField('Сформировать конфигурацию')

class ConfigNetForm(FlaskForm):
    text1 = TextAreaField('Проверьте конфигурацию DHCP1: ', validators=[Required()])
    text2 = TextAreaField('Проверьте конфигурацию DHCP2: ', validators=[Required()])
    submit = SubmitField('Отправить конфигурацию на сервер')

class ConfigHostForm(FlaskForm):
    text = TextAreaField('Проверьте конфигурацию: ', validators=[Required()])
    submit = SubmitField('Отправить конфигурацию на сервер')

class CleanAlarmForm(FlaskForm):
    alarm_type = SelectField('Очистить аварию: ',choices=[('nofree','Доступность свободных адресов'),('unknown','Запросы из неизвестной сети')])
    submit = SubmitField('ОЧИСТИТЬ')
