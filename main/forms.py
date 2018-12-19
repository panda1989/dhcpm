from flask_wtf import FlaskForm
#from flask.ext.wtf import Form
from wtforms import RadioField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import Required, IPAddress

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
    mac = StringField('MAC-адрес [01:23:45:67:89:ab]: ', validators=[Required()])
    ip = StringField('IP-адрес: ', validators=[Required(),IPAddress()])
    submit = SubmitField('Сформировать конфигурацию')

class AddNetForm(FlaskForm):
    ip = StringField('IP-адрес подсети: ', validators=[Required(),IPAddress()])
    mask = StringField('Маска подсети: ', validators=[Required(),IPAddress()])
    submit = SubmitField('Сформировать конфигурацию')

class ConfigNetForm(FlaskForm):
    text1 = TextAreaField('Проверьте конфигурацию DHCP1: ', validators=[Required()])
    text2 = TextAreaField('Проверьте конфигурацию DHCP2: ', validators=[Required()])
    submit = SubmitField('Отправить конфигурацию на сервер')

class ConfigHostForm(FlaskForm):
    text = TextAreaField('Проверьте конфигурацию: ', validators=[Required()])
    submit = SubmitField('Отправить конфигурацию на сервер')
