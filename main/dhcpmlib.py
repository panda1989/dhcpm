#! /usr/bin/python
# -*- coding: utf-8 -*-

"""Support functions for dhcpm
"""

import os
import re
import time
import paramiko
import pickle
import random
from ipaddress import IPv4Address,IPv4Network
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

class DubbedNetworkError(ValueError):
    """A value error related to repeat of subnet record"""


class Common:

    """Functions for common purposes: get information,restart, etc.
    """

    def srvrestart(server_ip):

        """Connects to selected server IP(str) over SSH and restarts
        isc-dhcpd-server process.
        Return: True if restarted, False if not restarted, None if error
        """

        #get current dhcpd process PID
        pid_before = Common.SSHcmd(server_ip,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat /var/run/dhcp-server/dhcpd.pid')[0]
        #restart server
        Common.SSHcmd(server_ip,SRV_PORT,SRV_LOGIN,SRV_PASS,'sudo systemctl restart isc-dhcp-server.service')
        time.sleep(5)
        #get dhcpd process PID after restart
        pid_after = Common.SSHcmd(server_ip,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat /var/run/dhcp-server/dhcpd.pid')[0]
        #check status of dhcpd process
        check = Common.SSHcmd(server_ip,SRV_PORT,SRV_LOGIN,SRV_PASS,'sudo systemctl is-failed isc-dhcp-server.service')[0]
        #X3 why try/except
        #return True if restarted, False if not restarted, None if error
        try:
            #if PID had not changed or if state is bad
            if pid_before == pid_after or check == 'failed':
                return False
            else:
                return True
        #in case of error
        except:
            return None

    def SSHcmd(hostname,port,username,password,arg):

        """Execute command over SSH and get reply.
        Args: hostname(str),port(int),username(str),password(str):
        parameters for SSH connection
              arg(str): command to execute on remote server
        Return: [stdout,stderr] list with results of command
        """

        #create paramiko object and connect over SSH
        cl = paramiko.SSHClient()
        cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cl.connect(hostname=hostname,port=port,username=username,password=password)
        output = []
        #define vars to return standart streams and send result of 'arg' to it
        stdin,stdout,stderr=cl.exec_command(arg)
        output.append(stdout.read().decode('utf-8')) #.decode('utf-8') for Python3
        output.append(stderr.read().decode('utf-8')) #.decode('utf-8') for Python3
        cl.close()
        #return [stdout,stderr]
        return output

    def write_remote_file(server_ip,conf_str,remote_file):

        """Write string (conf_str) to remote file over SSH.
        Args: server_ip(str),
              conf_str(str): string to write to remote file,
              remote_file(str): absolute to path to remote file.
        Return: False if no error, True if some error, error as string if error
        """

        #send conf_str to remote file by tee command
        writecmd = 'echo "' + conf_str + '" | sudo tee -a ' + remote_file
        err = Common.SSHcmd(server_ip,SRV_PORT,SRV_LOGIN,SRV_PASS,writecmd)[1]
        #return error as string if error, True if some error, False if no error
        try:
            if err:
                return err
            else:
                return False
        except:
            return True

    def get_subnets():

        """Analyze subnets1.conf and subnets2.conf and create Subnet instances
        for every subnet in config. Paths to subnets.conf files are taken
        from config class. Then read files over SSH.
        Return subnets_dict ({self.subnet : subnet_instance})
        """

        #pattern for subnet record in config file
        pattern_subnet = re.compile(r'subnet [\d\.\w ]+ \{.*?\n\}',re.DOTALL)
        #read current config files
        subnets1 = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_SUBNETS1)[0]
        subnets2 = Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_SUBNETS2)[0]
        #try to create Subnet class instance for each subnet record
        for s in re.findall(pattern_subnet, subnets1+subnets2):
            try:
                inst = Subnet(s,1)
            #for DubbedNetworkError: if network has already processed from another file
            except ValueError:
                pass
        #return dict with {subnet : subnet_instance} form
        return Subnet.subnets_dict

    def get_dynamic_hosts():

        """Analyze dhcp.leases files and create DynamicHost instances for each
        dynamic entry. Paths to dhcpd.leases files are taken from config class.
        Then read files over SSH.
        Return dynamic_dict ({self.lease : lease_instance})
        """

        pattern_lease = re.compile(r'lease [\d\.]+ \{.*?\n\}',re.DOTALL)
        leases1 = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_LEASES)[0]
        leases2 = Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_LEASES)[0]
        for le in re.findall(pattern_lease, leases1):
            inst = DynamicHost(le,'dhcp1')
        for le in re.findall(pattern_lease, leases2):
            inst = DynamicHost(le,'dhcp2')
        return DynamicHost.dynamic_dict

    def get_static_hosts():

        """Analyze hosts_pon and hosts_tech files on both servers and create
        StaticHost instances for every dynamic entry. Paths to hosts_pon
        and hosts_tech files are taken from config class. Then read files over SSH.
        Return static_dict ({self.ip : static_instance})
        """

        pattern_host = re.compile(r'\{ .*?}',re.DOTALL)
        hostspon1 = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_PON)[0]
        hostspon2 = Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_PON)[0]
        hoststech1 = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_TECH)[0]
        hoststech2 = Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + PATH_TECH)[0]
        #check if files on both servers are equal
        if hostspon1 == hostspon2 and hoststech1 == hoststech2:
            #if files are equal, we can process only one of them
            hostspon = hostspon1
            hoststech = hoststech1
            #read data from files
            for file in hostspon, hoststech:
                for h in re.findall(pattern_host, file):
                    #mark the source of record in object
                    if file is hostspon:
                        source = 'hosts_pon'
                        inst = StaticHost(h,source)
                    if file is hoststech:
                        source = 'hosts_tech'
                        inst = StaticHost(h,source)
        #if files are not equal, show warning
        #user must manually check and fix difference
        else:
            return 'hostspon!=hostspon \n Check and fix files'
        return StaticHost.static_dict

    def string_generator(str_len,alphabet='abcdefghijklmnopqrstuvwxyz'):

        """Create pseudo-random string
        Args: str_len(int): length of output string
              alphabet(str): set of chracters from which the output string
        is composed (a-z by default if no alphabet argument has sent)
        Return: (str)
        """

        res = []
        while str_len:
            #take random char from alphabet and append it to res
            res.append(alphabet[random.randint(0,len(alphabet) - 1)])
            str_len -= 1
        #list => str
        return ''.join(res)

class StaticHost:

    """Defines the structure of static hosts objects.
    Attributes: self.hw(str): MAC address of object
                self.ip(str): IP address of object
                self.type==self.source(str): "host_pon" or "host_tech": source
    file for object
                self.hostrec(str): not parsed record from hosts file as it is
    """

    static_dict = {}
    def __init__(self,hostrec,source):

        """
        Args: hostrec(str): record from hosts_pon or hosts_tech
              source(str): flag specifies source file info get from
        """

        #init: error protection if some data is out
        self.hw=self.ip = ''
        self.hostrec = hostrec
        self.source = source
        self.type = source
        for line in hostrec.split('\n'):
            if 'hardware ethernet' in line:
                self.hw = line[20:-1]
            if 'fixed-address' in line:
                self.ip = line[14:-3]
        StaticHost.static_dict[self.ip] = self

    def __repr__(self):
        """Not parsed record from hosts file as it is"""
        return self.hostrec


class Subnet:

    """Defines the structure of subnet objects.
    Attributes: self.subnetrec(str): not parsed record from subnet file
    as it is
                self.server(str): ?????????????????????????????????????
                self.hostlist(list): list of dynamic hosts from dhcpd.leases
        Parsed data from subnets file:
                self.subnet(str): subnet address
                self.router: router address
                self.mask: network mask
                self.broadcast: broadcast address
                self.stroutes: static route (option 33)
                self.rfc3442: static route (option 121)
                self.range1start: first address of first server dynamic pool
                self.range1end: last address of first server dynamic pool
                self.range2start: first address of second server dynamic pool
                self.range2end: last address of first server dynamic pool

                self.network(IPv4Address): IPv4 network object
                self.firststatic(str): first address of common static pool
                self.laststatic(str): last address of common static pool
    """


    subnets_dict = {}  # {self.subnet : subnet_instance}
    def __init__(self,subnetrec,server):

        """Args: subnetrec(str): record from subnets file
                 server():?????delete???????
        """
        #init: error protection if some data is out
        self.subnet=self.range1start=self.range1end=self.range2start=self.range2end=self.router=self.mask=self.broadcast=self.stroutes=self.rfc3442=self.network=self.firststatic=self.laststatic = ''
        self.subnetrec = subnetrec
        self.server = server
        #empty list of hosts in subnet filled by class methods
        self.hostlist = []
        #parsing subnet record from file
        for line in subnetrec.split('\n'):
            if line.startswith('subnet '):
                self.subnet = re.search(r'[\d\.]+',line).group(0)
            if 'option routers' in line:
                self.router = line[15:-1]
            if 'option subnet-mask' in line:
                self.mask = line.rstrip()[19:-1]
            if 'option broadcast-address' in line:
                self.broadcast = line[25:-1]
            if 'option static-routes' in line:
                self.stroutes = line[21:-1]
            if 'option rfc3442-classless-static-routes' in line:
                self.rfc3442 = line[39:-1]
            if 'range ' in line:
                #if subnet already in subnets_dict
                if self.subnet in Subnet.subnets_dict.keys():
                    #consider "range " in file as second pool
                    Subnet.subnets_dict[self.subnet].range2start, Subnet.subnets_dict[self.subnet].range2end = [r.strip() for r in re.findall(r' [\d\.]+', line)]
                    raise DubbedNetworkError
                else:
                    #consider "range " in file as first pool if this subnet is new
                    Subnet.subnets_dict[self.subnet] = self
                    self.range1start, self.range1end = [r.strip() for r in re.findall(r' [\d\.]+', line)]
        self.network = IPv4Network(self.subnet + '/' + self.mask)
        self.firststatic = str(IPv4Address(self.router) + 1)
        self.laststatic = str(IPv4Address(self.range1start) - 1)

    def gethosts(self,leases):

        """Append leases from leases_dict to hostlist attribute
        Args: leases(dict): dynamic_dict
        Return: None
        """

        for lease in leases.keys():
            if IPv4Address(lease) in self.network:
                self.hostlist.append(leases[lease])

    def print_subnet_dynamic(self, leasedict):

        """Forms list of dynamic leases
        Args: leasedict(dict): dynamic_dict
        Return: dynamic_page_list:
        """

        dynamic_page_list = []
        net = self.subnet
        subdict = Subnet.subnets_dict[net]
        #adds list of hosts to hostlist attribute
        Subnet.subnets_dict[net].gethosts(leasedict)
        #create user-friendly
        dynamic_page_list.append('Динамические хосты \tПодсеть\t' + str(net) + '/' + str(subdict.mask))
        dynamic_page_list.append('')
        dynamic_page_list.append('Range 1: ' + subdict.range1start + ' - ' + subdict.range1end)
        dynamic_page_list.append('Range 2: ' + subdict.range2start + ' - ' + subdict.range2end)
        dynamic_hosts_list = [(l.server, l.lease, l.hwaddress, l.bindingstate, l.starts) for l in subdict.hostlist]
        dynamic_page_list.append('')
        for i in dynamic_hosts_list:
            dynamic_page_list.append(i[0] + '\t' + i[1] + '\t' + i[2] + '\t' + i[3] + '\t' + i[4])
        dynamic_page_list.append('--------------------------------------------------------------------------------\n')
        return dynamic_page_list

    def print_subnet_static(self, hostdict):

        """
        """

        static_page_list = []
        net = self.subnet
        subdict = Subnet.subnets_dict[net]
        static_page_list.append('Статические хосты\tПодсеть\t' + str(net) + '/' + str(subdict.mask))
        static_page_list.append('')
        static_page_list.append('Статический диапазон: ' + subdict.firststatic + ' - ' + subdict.laststatic)
        static_hosts_list = [(hostdict[h].ip, hostdict[h].hw) for h in hostdict.keys() if IPv4Address(hostdict[h].ip) in subdict.network]
        static_page_list.append('')
        for i in static_hosts_list:
            static_page_list.append(i[0] + '\t' + i[1])
        static_page_list.append('--------------------------------------------------------------------------------\n')
        return static_page_list


    def __repr__(self):
        return self.subnetrec


class DynamicHost:

    dynamic_dict = {}  # {self.lease : lease_instance}
    def __init__(self,leaserec,server):
        self.leaserec = leaserec
        self.server = server
        self.lease=self.starts=self.ends=self.cltt=self.bindingstate=self.nextbindingstate=self.rewindbindingstate=self.hwaddress=self.vendorclassid=self.circuitid=self.remoteid = ''
        for line in self.leaserec.split('\n'):
            if line.startswith('lease '):
                self.lease = line[6:-2]
            if '  starts' in line:
                self.starts = line[9:-1]
            if '  ends' in line:
                self.ends = line[7:-1]
            if '  cltt' in line:
                self.cltt = line[7:-1]
            if '  binding state' in line:
                self.bindingstate = line[16:-1]
            if '  next binding state' in line:
                self.nextbindingstate = line[21:-1]
            if '  rewind binding state' in line:
                self.rewindbindingstate = line[23:-1]
            if '  hardware ethernet' in line:
                self.hwaddress = line[20:-1]
            if '  set vendor-class-identifier' in line:
                self.vendorclassid = line[32:-1]
            if '  option agent.circuit-id' in line:
                self.circuitid = line[26:-1]
            if '  option agent.remote-id' in line:
                self.remoteid = line[25:-1]
        DynamicHost.dynamic_dict[self.lease] = self

    def __repr__(self):
        return self.leaserec


class Search:

    def googler(in_list,out_list,var):
        out_list.append('----------------------------------------')
        for i in sorted(in_list):
            if var in i:
                out_list.append(i)
        out_list.append('----------------------------------------')
        return out_list

    def logLoader(fCounter):
        fullLog = []
        #logFileList1 = sorted([i for i in Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'ls /var/log/ | grep dhcp')[0].split('\n')])
        #logFileList2 = sorted([i for i in Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'ls /var/log/ | grep dhcp')[0].split('\n')])
        logFileList1 = [i for i in Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'ls /var/log/ | grep dhcp')[0].split('\n')]
        logFileList2 = [i for i in Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'ls /var/log/ | grep dhcp')[0].split('\n')]
        while fCounter >= 0:
            file1 = Common.SSHcmd(SRV1_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat /var/log/' + logFileList1[fCounter])[0].split('\n')
            file2 = Common.SSHcmd(SRV2_IP,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat /var/log/' + logFileList2[fCounter])[0].split('\n')
            for sl in file1:
                fullLog.append(sl.rstrip())
            for sr in file2:
                fullLog.append(sr.rstrip())
            fCounter -= 1
        return fullLog

    def put_temp(data):
        tmp_filename = os.path.join('/var/www/dhcpm/dhcpm/tmp/' + Common.string_generator(4))
        with open(tmp_filename,'wb') as f:
            pickle.dump(data,f)
        return tmp_filename

    def get_temp(tmp_filename):
        with open(tmp_filename,'rb') as f:
            res = pickle.load(f)
        return res

    def clear_temp():
        filelist = [f for f in os.listdir('/var/www/dhcpm/dhcpm/tmp/')]
        for f in filelist:
            os.remove(os.path.join('/var/www/dhcpm/dhcpm/tmp/',f))


class CreateConfig:

    def create_hosts_config(type, add_ip, add_mac): 
        new_host = ('host ' + type + '.' + add_ip + '\n'
                    + '{ hardware ethernet ' + add_mac + ';\n'
                    + 'fixed-address ' + add_ip + '; }')  # -\n
        return new_host

    def create_subnets_config(add_net, add_mask, static):
        net = IPv4Network(add_net + '/' + add_mask)
        allhosts = [str(i) for i in net.hosts()]
        subnet = str(net.network_address)
        netmask = str(net.netmask)
        router = allhosts[0]
        brcast = str(net.broadcast_address)
        rule80_20 = int((net.num_addresses - 4 - static)*0.78)
        range1 = allhosts[static + 1] + ' ' + allhosts[static + rule80_20]
        range2 = allhosts[static + rule80_20 + 1] + ' ' + allhosts[-1]
        new_net1 = ('subnet ' + subnet + ' netmask ' + netmask + ' {\n'
                    + 'range  ' + range1 + ';\n'
                    + 'option routers ' + router + ';\n'
                    + 'option subnet-mask ' + netmask + ';\n'
                    + 'option broadcast-address ' + brcast + ';\n'
                    + 'option static-routes 172.31.254.34 ' + router + ';\n}')  # -\n
        new_net2 = ('subnet ' + subnet + ' netmask ' + netmask + ' {\n'
                    + 'range  ' + range2 + ';\n'
                    + 'option routers ' + router + ';\n'
                    + 'option subnet-mask ' + netmask + ';\n'
                    + 'option broadcast-address ' + brcast + ';\n'
                    + 'option static-routes 172.31.254.34 ' + router + ';\n}')  # -\n
        return new_net1, new_net2

    def check_in_file(check_str,*paths):
        output = []
        for server in (SRV1_IP,SRV2_IP):
            for path in paths:
                file = "".join(Common.SSHcmd(server,SRV_PORT,SRV_LOGIN,SRV_PASS,'cat ' + path))
                if check_str in file:
                    output.append(False)
                else:
                    output.append(True)
        if all(output) == True:
            return True
        else:
            return False

    def write_control(data, filepaths):
        err_list = []
        err = Common.write_remote_file(SRV1_IP,data[0],filepaths[0])
        if err:
            err_list.append('Ошибка записи файла на DHCP1')
            err_list.append(err)
        else:
            err = Common.srvrestart(SRV1_IP)
            if not err:
                err_list.append('Ошибка перезагрузки DHCP1')
                err_list.append(err)
            else:
                err = Common.write_remote_file(SRV2_IP,data[1],filepaths[1])
                if err:
                    err_list.append('Ошибка записи файла на DHCP2')
                    err_list.append(err)
                else:
                    err = Common.srvrestart(SRV2_IP)
                    if not err:
                        err_list.append('Ошибка перезагрузки DHCP1')
                        err_list.append(err)
                    else:
                        return False
        return err_list

## !!!!!!!!!!!!!!!!!!!!!!
    def write_control_old(data, filepaths):
        err_list = []
        err = Common.write_remote_file(SRV1_IP,data[0],filepaths[0])
        if err[0]:
            err_list.append('Ошибка записи файла на DHCP1')
            err_list.append(err[0])
        else:
            err = Common.srvrestart(SRV1_IP)
            if not err:
                err_list.append('Ошибка перезагрузки DHCP1')
                err_list.append(err[0])
            else:
                err = Common.write_remote_file(SRV2_IP,data[1],filepaths[0])
                if err[0]:
                    err_list.append('Ошибка записи файла на DHCP2')
                    err_list.append(err[0])
                else:
                    err = Common.srvrestart(SRV2_IP)
                    if not err:
                        err_list.append('Ошибка перезагрузки DHCP1')
                        err_list.append(err[0])
                    else:
                        return False
        return err_list
## !!!!!!!!!!!!!!!!!!!!!!!!
