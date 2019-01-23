#! /usr/bin/python
# -*- coding: utf-8 -*-

import gzip
import time
import io
import os
import re

from flask import g, flash, render_template, redirect, request, session, url_for
from ipaddress import IPv4Address,IPv4Network
from .dhcpmlib import Common, CreateConfig, Search, Subnet, DynamicHost, StaticHost
from . import main
from .forms import AddHostForm, AddNetForm, CleanAlarmForm, CleanDynamicForm, ConfigHostForm, ConfigNetForm, GetInfoForm, SearchDayForm, SearchMainForm, RestartForm
from .config import config

SRV1_IP = config.SRV1_IP
SRV2_IP = config.SRV2_IP
SRV_PORT = config.SRV_PORT
SRV_LOGIN = config.SRV_LOGIN
SRV_PASS = config.SRV_PASS

PATH_SUBNETS1 = config.PATH_SUBNETS1
PATH_SUBNETS2 = config.PATH_SUBNETS2
PATH_PON = config.PATH_PON
PATH_TECH = config.PATH_TECH
PATH_LOG = config.PATH_LOG
PATH_LEASES = config.PATH_LEASES
LEASES_TEMPLATE = config.LEASES_TEMPLATE

@main.route("/")
def index():
    return render_template('index.html')


@main.route("/search",methods=['GET','POST'])
def search():

    form = SearchDayForm()
    if form.validate_on_submit():
        #days = str(form.day_counter.data)
        days = form.day_counter.data
        return redirect(url_for('main.searchmain',days=days))
    return render_template('searchday.html',form=form,result='')

@main.route("/searchmain",methods=['GET','POST'])
def searchmain():
    output = []
    result = []
    innerResult = []
    endFlag = 2
    days=int(request.args['days'])
    fullLog = Search.logLoader(days)
    form = SearchMainForm()
    if form.validate_on_submit():
        endFlag = int(form.flag.data)
        while endFlag != 0:
            if endFlag == 2:
                output = []
                var = form.search_string.data
                result = Search.googler(fullLog,result,var)
                session['tmp_filename'] = Search.put_temp(result)
                for r in result:
                    output.append(r)
                output.append(str(len(result) - 2) + ' совпадений найдено')
                return render_template('searchmain.html',form=form,result='\n'.join(output))
            elif endFlag == 1:
                output = []
                var = form.search_string.data
                result = Search.get_temp(session.get('tmp_filename'))
                innerResult = Search.googler(result,innerResult,var)
                for r in innerResult:
                    output.append(r)
                output.append(str(len(innerResult) - 2) + ' совпадений найдено')
                result = innerResult[:]
                session['tmp_filename'] = Search.put_temp(result)
                innerResult = []
                return render_template('searchmain.html',form=form,result='\n'.join(output))
    session['tmp_filename'] = None
    Search.clear_temp()
    return render_template('searchmain.html', form=form, result='')


@main.route("/addnet", methods=['GET','POST'])
def addnet():
    checkform = ConfigNetForm()
    form = AddNetForm()
    subnets1 = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_SUBNETS1)[0]
    subnets2 = Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_SUBNETS2)[0]
    pattern_subnet = re.compile(r'subnet [\d\.\w ]+ \{.*?\n\}',re.DOTALL)

    for s in re.findall(pattern_subnet, subnets1+subnets2):
        try:
            inst = Subnet(s,1)
        except ValueError:
            pass

    if form.validate_on_submit():
        if not any([IPv4Network(form.ip.data + '/' + form.mask.data).overlaps(item.network) for item in Subnet.subnets_dict.values()]):
            netconfig = CreateConfig.create_subnets_config(form.ip.data, form.mask.data, form.static.data)
            checkform.text1.data = netconfig[0]
            checkform.text2.data = netconfig[1]
            return render_template('addnet.html', form=form, checkform=checkform)
        else:
            return render_template('addnet.html', form=form, result='Такая сеть уже существует!')

    if checkform.validate_on_submit():
        err_list = CreateConfig.write_control([checkform.text1.data, checkform.text2.data], [PATH_SUBNETS1,PATH_SUBNETS2])
        if err_list:
            return render_template('addnet.html',result=str(err_list))
        else:
            return render_template('addnet.html',result='Подсети успешно добавлены!')

    return render_template('addnet.html', form=form)


@main.route("/addhost", methods=['GET','POST'])
def addhost():
    form = AddHostForm()
    checkform = ConfigHostForm()
    hostspon = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_PON)[0]
    hoststech = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_TECH)[0]
    pattern_host = re.compile(r'\{ .*?}',re.DOTALL)
    Common.get_subnets()
    Common.get_static_hosts()

    if form.validate_on_submit():
        net = [subnet for subnet in Subnet.subnets_dict.values() if IPv4Address(form.ip.data) in subnet.network][0]
        if not any([form.mac.data in item.hw for item in StaticHost.static_dict.values()]):
            static_list = [IPv4Address(h.ip) for h in StaticHost.static_dict.values() if IPv4Address(h.ip) in net.network]
            if static_list:
                ip = max(static_list) + 1
            else:
                ip = IPv4Address(net.router) + 1
            if ip >= IPv4Address(net.range1start):
                return render_template('addhost.html', form=form, result='!! Необходимо увеличить статический пул !!'+str(ip))
            else:
                checkform.text.data = CreateConfig.create_hosts_config(form.type.data, str(ip), form.mac.data)
                return render_template('addhost.html', form=form, checkform=checkform)
        else:
            return render_template('addhost.html', form=form, result='Устройство с таким MAC-адресом уже привязано!')

    if checkform.validate_on_submit():
        if 'pon' in checkform.text.data:
            path = PATH_PON
        elif 'tech' in checkform.text.data:
            path = PATH_TECH
        err_list = CreateConfig.write_control([checkform.text.data, checkform.text.data], [path, path])
        if err_list:
            return render_template('addnet.html',result=str(err_list))
        else:
            return render_template('addnet.html',result='Статическая привязка успешно добавлена!')

    return render_template('addhost.html', form=form)


@main.route("/cleandynamic", methods=['GET','POST'])
def cleandynamic():
    form = CleanDynamicForm()
    result = []
    if form.validate_on_submit():
        for srv in (SRV1_IP, SRV2_IP):
            #result.append(Common.SSHcmd(srv,SRV_PORT,SRV_LOGIN,SRV_PASS,'sudo echo "' + LEASES_TEMPLATE + '" > ' + PATH_LEASES))
            result.append(Common.SSHcmd(srv,SRV_PORT,SRV_LOGIN,SRV_PASS,'echo "' + LEASES_TEMPLATE + '" | sudo tee ' + PATH_LEASES))
            result.append(Common.srvrestart(srv))
        return render_template('cleandynamic.html', form=form, result=result)
    return render_template('cleandynamic.html', form=form)

@main.route("/cleanalarms", methods=['GET','POST'])
def cleanalarms():
    form = CleanAlarmForm()
    result = []
    if form.validate_on_submit():
        if form.alarm_type.data == 'nofree':
            result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/no free leases/n o f r e e l e a s e s/' " + PATH_LOG)[1])
            result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/no free leases/n o f r e e l e a s e s/' " + PATH_LOG)[1])
            if ''.join(result):
                return render_template('cleanalarm.html', form=form, result=result)
            else:
                result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                return render_template('cleanalarm.html', form=form, result='No free leases alarm cleared')
        if form.alarm_type.data == 'unknown':
            result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/unknown network segment/u n k n o w n n e t w o r k/' " + PATH_LOG)[1])
            result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/unknown network segment/u n k n o w n n e t w o r k/' " + PATH_LOG)[1])
            if ''.join(result):
                return render_template('cleanalarm.html', form=form, result=result)
            else:
                result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                return render_template('cleanalarm.html', form=form, result='Unknown network alarm cleared')
    return render_template('cleanalarm.html', form=form)


@main.route("/getinfo", methods=['GET','POST'])
def getinfo():

    #date = time.ctime()
    form = GetInfoForm()
    if form.validate_on_submit():
        user_input = IPv4Address(form.subnet.data)
        Common.get_subnets()
        Common.get_dynamic_hosts()
        Common.get_static_hosts()
        for n in Subnet.subnets_dict:
            if user_input in Subnet.subnets_dict[n].network:
                result_stat = '\n'.join(Subnet.subnets_dict[Subnet.subnets_dict[n].subnet].print_subnet_static(StaticHost.static_dict))
                result_dyn = '\n'.join(Subnet.subnets_dict[Subnet.subnets_dict[n].subnet].print_subnet_dynamic(DynamicHost.dynamic_dict))
                return render_template('getinfo.html',form=form,result=result_stat+result_dyn)
        return render_template('getinfo.html',form=form,result='Нет такой сети :(')
    return render_template('getinfo.html',form=form,result='')


@main.route("/getinfostat")
def getinfostat():

    def common_stat(statdict, dyndict):
        common_page_list = []
        com_stat = str(len(statdict))
        com_dyn_act = [a for a in dyndict.keys() if dyndict[a].bindingstate == 'active']
        common_page_list.append('Количество статических привязок ' + com_stat)
        common_page_list.append('Количество активных динамических аренд ' + str(len(com_dyn_act)))
        common_page_list.append('Количество уникальных динамических аренд ' + str(len(set(com_dyn_act))))
        return '\n'.join(common_page_list)

    #return render_template('index.html')
    return redirect('http://172.17.0.26/')


@main.route("/restart", methods=['GET','POST'])
def restart():
    form = RestartForm()
    server = ''
    if form.flag.data == '1':
        server = SRV1_IP
    if form.flag.data == '2':
        server = SRV2_IP
    if server:
        restart_result = Common.srvrestart(server)
        if restart_result == True:
            result = 'Сервер успешно перезагружен!'
        if restart_result == False:
            result = '!!!Сервер не перезагружен!!!'
        if restart_result == None:
            result = '!!! АШЫПКА !!!'
        return render_template('restart.html',form=form,result=result)
    return render_template('restart.html',form=form,result='')


