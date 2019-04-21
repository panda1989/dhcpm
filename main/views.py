#! /usr/bin/python
# -*- coding: utf-8 -*-

"""View functions for Flask 
"""

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

#load constants from config.py
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

#homepage
@main.route("/")
def index():
    return render_template('index.html')

@main.route("/search",methods=['GET','POST'])
def search():

    """Input search depth and redirect to searchmain with GET with it"""

    form = SearchDayForm()
    if form.validate_on_submit():
        #days = str(form.day_counter.data)
        days = form.day_counter.data
        return redirect(url_for('main.searchmain',days=days))
    return render_template('searchday.html',form=form,result='')

@main.route("/searchmain",methods=['GET','POST'])
def searchmain():

    """Days variable sent in GET from search function
    Returns results of search
    """

    output = []
    result = []
    innerResult = []
    endFlag = 2
    #get days (search depth) from GET...
    days=int(request.args['days'])
    #...and load corresponding log files from servers
    fullLog = Search.logLoader(days)
    form = SearchMainForm()
    #form returns flag ( =1 for search in older results, =2 for new search) and search string
    if form.validate_on_submit():
        #get flag from form
        endFlag = int(form.flag.data)
        #form returns flag = 1 or 2. If flag = 0 => stop while loop
        while endFlag != 0:
            #new search
            if endFlag == 2:
                output = []
                #get search string from form
                var = form.search_string.data
                #result is [list] of strings in log files containing search string
                result = Search.googler(fullLog,result,var)
                #put_temp function creates file for temporary search data and returns it's name
                #name of temp file is saved in cookies
                session['tmp_filename'] = Search.put_temp(result)
                #copy from result variable to output variable
                for r in result:
                    output.append(r)
                output.append(str(len(result) - 2) + ' совпадений найдено')
                #return string, joined from output list
                return render_template('searchmain.html',form=form,result='\n'.join(output))
            #search in found
            elif endFlag == 1:
                output = []
                #get search string from form
                var = form.search_string.data
                #load older reult from temp file
                result = Search.get_temp(session.get('tmp_filename'))
                #innerResult is [list] of strings in older result containing new search string
                innerResult = Search.googler(result,innerResult,var)
                #copy from innerResult variable to output variable
                for r in innerResult:
                    output.append(r)
                output.append(str(len(innerResult) - 2) + ' совпадений найдено')
                #X3??? maybe just put_temp(innerResult)
                result = innerResult[:]
                session['tmp_filename'] = Search.put_temp(result)
                innerResult = []
                #return string, joined from output list
                return render_template('searchmain.html',form=form,result='\n'.join(output))
    #it is a first view
    #clean cookies and delete temp file before work
    session['tmp_filename'] = None
    Search.clear_temp()
    return render_template('searchmain.html', form=form, result='')

@main.route("/addnet", methods=['GET','POST'])
def addnet():

    """Input subnet address, mask and number of static hosts.
    Then check created config, submit and apply it to server
    """

    checkform = ConfigNetForm()
    form = AddNetForm()
    """
    # ??????????????? CHANGE TO get_subnets ???????????????????????
    """
    #get subnets files from servers
    subnets1 = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_SUBNETS1)[0]
    subnets2 = Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_SUBNETS2)[0]
    #pattern for filtering out subnet record
    pattern_subnet = re.compile(r'subnet [\d\.\w ]+ \{.*?\n\}',re.DOTALL)

    #create subnet class instances for all records in subnets files
    for s in re.findall(pattern_subnet, subnets1+subnets2):
        try:
            inst = Subnet(s,1)
        except ValueError:
            pass
    #when first form submitted (ip,mask,number of static host)
    if form.validate_on_submit():
        #check new subnet in existing subnets: true if not exist
        if not any([IPv4Network(form.ip.data + '/' + form.mask.data).overlaps(item.network) for item in Subnet.subnets_dict.values()]):
            #create subnets configs as tuple of 2 strings and send it to checkform
            netconfig = CreateConfig.create_subnets_config(form.ip.data, form.mask.data, form.static.data)
            checkform.text1.data = netconfig[0]
            checkform.text2.data = netconfig[1]
            return render_template('addnet.html', form=form, checkform=checkform)
        #show warning if subnet exists and stop processing
        else:
            return render_template('addnet.html', form=form, result='Такая сеть уже существует!')

    #if configs are created, checked and submitted
    if checkform.validate_on_submit():
        #write config, restart and check for errors
        err_list = CreateConfig.write_control([checkform.text1.data, checkform.text2.data], [PATH_SUBNETS1,PATH_SUBNETS2])
        #err_list=true if any errors occuried
        if err_list:
            return render_template('addnet.html',result=str(err_list))
        else:
            return render_template('addnet.html',result='Подсети успешно добавлены!')
    #at first time show form
    return render_template('addnet.html', form=form)

@main.route("/addhost", methods=['GET','POST'])
def addhost():

    """Input MAC and IP addresses of static hosts.
    Then check created config, submit and apply it to server
    """

    form = AddHostForm()
    checkform = ConfigHostForm()
    #get static hosts files as strings
    hostspon = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_PON)[0]
    hoststech = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_TECH)[0]
    #pattern for filtering out static host record
    pattern_host = re.compile(r'\{ .*?}',re.DOTALL)
    #get current info about subnets and static hosts
    Common.get_subnets()
    Common.get_static_hosts()

    #when first form submitted (ip and MAC)
    if form.validate_on_submit():
        #address of subnetwork containing ip from form
        net = [subnet for subnet in Subnet.subnets_dict.values() if IPv4Address(form.ip.data) in subnet.network][0]
        #check if mac already in static hosts (false if in)
        if not any([form.mac.data in item.hw for item in StaticHost.static_dict.values()]):
            #list of current static hosts in net
            static_list = [IPv4Address(h.ip) for h in StaticHost.static_dict.values() if IPv4Address(h.ip) in net.network]
            #use address of last static host +1 if any static hosts in that network
            if static_list:
                ip = max(static_list) + 1
            #use address of router +1 if not any static hosts in that network
            else:
                ip = IPv4Address(net.router) + 1
            #warning if new address out of static pool
            if ip >= IPv4Address(net.range1start):
                return render_template('addhost.html', form=form, result='!! Необходимо увеличить статический пул !!'+str(ip))
            #create config if all OK
            else:
                checkform.text.data = CreateConfig.create_hosts_config(form.type.data, str(ip), form.mac.data)
                return render_template('addhost.html', form=form, checkform=checkform)
        #if mac already in static hosts
        else:
            return render_template('addhost.html', form=form, result='Устройство с таким MAC-адресом уже привязано!')

    #if config is created, checked and submitted
    if checkform.validate_on_submit():
        #choose different paths depending on the type
        if 'pon' in checkform.text.data:
            path = PATH_PON
        elif 'tech' in checkform.text.data:
            path = PATH_TECH
        #write config, restart and check for errors
        err_list = CreateConfig.write_control([checkform.text.data, checkform.text.data], [path, path])
        #err_list=true if any errors
        if err_list:
            return render_template('addnet.html',result=str(err_list))
        else:
            return render_template('addnet.html',result='Статическая привязка успешно добавлена!')
    #at first time show form
    return render_template('addhost.html', form=form)

@main.route("/cleandynamic", methods=['GET','POST'])
def cleandynamic():

    """Clean all current dynamic leases (clean dhcp.leases)
    """

    #just submit form
    form = CleanDynamicForm()
    result = []
    if form.validate_on_submit():
        for srv in (SRV1_IP, SRV2_IP):
            #in last versions of isc-dhcp some config strings are needed (LEASES_TEMPLATE)
            result.append(Common.SSHcmd(srv,SRV_PORT,SRV_LOGIN,SRV_PASS,'echo "' + LEASES_TEMPLATE + '" | sudo tee ' + PATH_LEASES))
            result.append(Common.srvrestart(srv))
        return render_template('cleandynamic.html', form=form, result=result)
    #at first time show form
    return render_template('cleandynamic.html', form=form)

@main.route("/cleanalarms", methods=['GET','POST'])
def cleanalarms():

    """Clean alarm messages from logs
    """

    #form contains alarm_type to clean
    form = CleanAlarmForm()
    result = []
    if form.validate_on_submit():
        if form.alarm_type.data == 'nofree':
            #spoil dhcp.log string with alarms
            #result contains any errors in sed work
            result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/no free leases/n o f r e e l e a s e s/' " + PATH_LOG)[1])
            result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/no free leases/n o f r e e l e a s e s/' " + PATH_LOG)[1])
            #show errors
            if ''.join(result):
                return render_template('cleanalarm.html', form=form, result=result)
            #if no errors
            else:
                result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                return render_template('cleanalarm.html', form=form, result='No free leases alarm cleared')

        if form.alarm_type.data == 'unknown':
            #spoil dhcp.log string with alarms
            #result contains any errors in sed work
            result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/unknown network segment/u n k n o w n n e t w o r k/' " + PATH_LOG)[1])
            result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo sed -i 's/unknown network segment/u n k n o w n n e t w o r k/' " + PATH_LOG)[1])
            #show errors
            if ''.join(result):
                return render_template('cleanalarm.html', form=form, result=result)
            #if no errors
            else:
                result.append(Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                result.append(Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,"sudo service rsyslog restart")[1])
                return render_template('cleanalarm.html', form=form, result='Unknown network alarm cleared')
    #at first time show form
    return render_template('cleanalarm.html', form=form)


@main.route("/getinfo", methods=['GET','POST'])
def getinfo():

    """Input network address.
    Return info about subnet config, static and dynamic hosts.
    """

    form = GetInfoForm()
    #user_input = IP (subnet or address)
    if form.validate_on_submit():
        #create IP address object
        user_input = IPv4Address(form.subnet.data)
        #create objects for subnets in subnets.conf
        Common.get_subnets()
        #create objects for dynamic hosts in dhcpd.leases
        Common.get_dynamic_hosts()
        #create objects for static hosts in hosts_tech and hosts_pon
        Common.get_static_hosts()
        #iterate over all subnet objects
        for n in Subnet.subnets_dict:
            #check if user input is in current subnet
            if user_input in Subnet.subnets_dict[n].network:
                #Subnet.subnets_dict[n].subnet defines subnet address for user_input
                #then save static and dynamic hosts info in result_stat and result_dyn
                result_stat = '\n'.join(Subnet.subnets_dict[Subnet.subnets_dict[n].subnet].print_subnet_static(StaticHost.static_dict))
                result_dyn = '\n'.join(Subnet.subnets_dict[Subnet.subnets_dict[n].subnet].print_subnet_dynamic(DynamicHost.dynamic_dict))
                return render_template('getinfo.html',form=form,result=result_stat+result_dyn)
        #if all subnets iterated and no entry found
        return render_template('getinfo.html',form=form,result='Нет такой сети :(')
    #at first time show form
    return render_template('getinfo.html',form=form,result='')


@main.route("/getinfostat")
def getinfostat():
    """Redirect to old page (get stat by cron every 5 minutes)
    """
    return redirect('http://172.17.0.26/')

#edited 15.04.19
#controlled restart
@main.route("/restart", methods=['GET','POST'])
def restart():

    """Restart isc-dhcp-service.
    Return result of restart.
    """

    #choose server 1 or 2
    form = RestartForm()
    server = ''
    #send form
    if form.validate_on_submit():
        #choose server from form (form.flag.data)
        if form.flag.data == '1':
            server = SRV1_IP
        if form.flag.data == '2':
            server = SRV2_IP
        #restart selected server
        restart_result = Common.srvrestart(server)
        #in case of explicit server restart
        if restart_result == True:
            result = 'Сервер успешно перезагружен!'
        #in case of explicit fail
        if restart_result == False:
            result = '!!!Сервер не перезагружен!!!'
        #in case of implicit fail
        if restart_result == None:
            result = '!!! АШЫПКА !!!'
        return render_template('restart.html',form=form,result=result)
    #at first time show form
    return render_template('restart.html',form=form,result='')
