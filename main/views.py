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
from .forms import AddHostForm, AddNetForm, ConfigHostForm, ConfigNetForm, GetInfoForm, SearchDayForm, SearchMainForm, RestartForm

@main.route("/")
def index():
    return render_template('index.html')


@main.route("/search",methods=['GET','POST'])
def search():

    form = SearchDayForm()
    if form.validate_on_submit():
        days = form.day_counter.data
        return redirect(url_for('main.searchmain',days=days))
    return render_template('searchday.html',form=form,result='')

@main.route("/searchmain",methods=['GET','POST'])
def searchmain(days='0'):
    output = []
    result = []
    innerResult = []
    endFlag = 2
    fullLog = Search.logLoader(int(request.args['days']))
    form = SearchMainForm()
    if form.validate_on_submit():
        while endFlag != 0:
            if endFlag == 3:
                fullLog = Search.logLoader(int(request.args['days']))
                result = []
                endFlag = 2
            if endFlag == 2:
                output = []
                var = form.search_string.data
                result = Search.googler(fullLog,result,var)
                session['result'] = result[:]
                for r in result:
                    output.append(r)
                output.append(str(len(result) - 2) + ' совпадений найдено')
                return render_template('searchmain.html',form=form,result='\n'.join(output))
            elif endFlag == 1:
                output = []
                var = form.search_string.data
                result = session.get('result')
                innerResult = Search.googler(result,innerResult,var)
                for r in innerResult:
                    output.append(r)
                output.append(str(len(innerResult) - 2) + ' совпадений найдено')
                result = innerResult[:]
                result = session.get('result')
                innerResult = []
                return render_template('searchmain.html',form=form,result='\n'.join(output))
            endFlag = int(form.flag.data)
    session['result'] = None
    return render_template('searchmain.html', form=form, result='')


@main.route("/addnet", methods=['GET','POST'])
def addnet():
    err_list = []
    checkform = ConfigNetForm()
    form = AddNetForm()
    subnets1 = open('/etc/dhcp/subnets1').read()
    subnets2 = Common.SSHcmd('172.17.0.30',45242,'dhcpm','p@ss','cat /etc/dhcp/subnets2')[0]
    pattern_subnet = re.compile(r'subnet [\d\.\w ]+ \{.*?\n\}',re.DOTALL)

    for s in re.findall(pattern_subnet, subnets1+subnets2):
        try:
            inst = Subnet(s,1)
        except ValueError:
            pass

    if form.validate_on_submit():
        #if not any([IPv4Address(form.ip.data) in netaddr for netaddr in [item.network for item in Subnet.subnets_dict.values()]]):
        #if not any([IPv4Address(form.ip.data) in item.network for item in Subnet.subnets_dict.values()]):
        if not any([IPv4Network(form.ip.data + '/' + form.mask.data).overlaps(item.network) for item in Subnet.subnets_dict.values()]):
            netconfig = CreateConfig.create_subnets_config(form.ip.data, form.mask.data)
            checkform.text1.data = netconfig[0]
            checkform.text2.data = netconfig[1]
            return render_template('addnet.html', form=form, checkform=checkform)
        else:
            return render_template('addnet.html', form=form, result='Такая сеть уже существует!')

    '''
    if form.validate_on_submit():
        if CreateConfig.check_in_file(form.ip.data,'/etc/dhcp/subnets*'):
            netconfig = CreateConfig.create_subnets_config(form.ip.data, form.mask.data)
            checkform.text1.data = netconfig[0]
            checkform.text2.data = netconfig[1]
            return render_template('addnet.html', form=form, checkform=checkform)
        else:
            return render_template('addnet.html', form=form, result='Такая сеть уже существует!')
    '''
    if checkform.submit.data:
        err = Common.write_remote_file('172.17.0.26',checkform.text1.data,'/home/dhcpm/testfile')
        if err[0]:
            err_list.append('Ошибка записи файла на DHCP1')
            err_list.append(err[0])
        else:
            err = Common.srvrestart('172.17.0.26')
            if not err:
                err_list.append('Ошибка перезагрузки DHCP1')
                err_list.append(err[0])
            else:
                err = Common.write_remote_file('172.17.0.30',checkform.text2.data,'/home/dhcpm/testfile')
                if err[0]:
                    err_list.append('Ошибка записи файла на DHCP2')
                    err_list.append(err[0])
                else:
                    err = Common.srvrestart('172.17.0.30')
                    if not err:
                        err_list.append('Ошибка перезагрузки DHCP1')
                        err_list.append(err[0])
                    else:
                        return render_template('addnet.html', result=' Подсети добавлены ')
        return render_template('addnet.html',result=str(err_list))

    return render_template('addnet.html', form=form)


@main.route("/addhost", methods=['GET','POST'])
def addhost():
    form = AddHostForm()
    if form.mac.data and form.ip.data:
        checkform = ConfigHostForm()
        if checkform.text.data:
            return render_template('addhost.html', form=form,result=checkform.text.data)
        checkform.text.data = form.ip.data
        return render_template('addhost.html', form=form, checkform=checkform)
    return render_template('addhost.html', form=form)


@main.route("/cleandynamic")
def cleandynamic():
    return render_template('index.html')


@main.route("/cleanalarms")
def cleanalarms():
    return render_template('index.html')


@main.route("/getinfo", methods=['GET','POST'])
def getinfo():

    date = time.ctime()
    leases1 = open('/var/lib/dhcp/dhcpd.leases').read()
    subnets1 = open('/etc/dhcp/subnets1').read()
    hostspon = open('/etc/dhcp/hosts_pon').read()
    hoststech = open('/etc/dhcp/hosts_tech').read()
    subnets2,leases2 = Common.SSHcmd('172.17.0.30',45242,'dhcpm','p@ss','cat /etc/dhcp/subnets2','cat /var/lib/dhcp/dhcpd.leases')
    pattern_lease = re.compile(r'lease [\d\.]+ \{.*?\n\}',re.DOTALL)
    pattern_subnet = re.compile(r'subnet [\d\.\w ]+ \{.*?\n\}',re.DOTALL)
    pattern_host = re.compile(r'\{ .*?}',re.DOTALL)
    host_instance_list = []

    for s in re.findall(pattern_subnet, subnets1+subnets2):
        try:
            inst = Subnet(s,1)
        except ValueError:
            pass

    for le in re.findall(pattern_lease, leases1):
        inst = DynamicHost(le,'dhcp1')
    for le in re.findall(pattern_lease, leases2):
        inst = DynamicHost(le,'dhcp2')

    for file in hostspon, hoststech:
        for h in re.findall(pattern_host, file):
            if file is hostspon:
                source = 'hosts_pon'
                inst = StaticHost(h,source)
            if file is hoststech:
                source = 'hosts_tech'
                inst = StaticHost(h,source)

    form = GetInfoForm()
    if form.validate_on_submit():
        user_input = IPv4Address(form.subnet.data)
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
        server = '172.17.0.26'
    if form.flag.data == '2':
        server = '172.17.0.30'
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


