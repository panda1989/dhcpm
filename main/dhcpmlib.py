#! /usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import time
import paramiko
from ipaddress import IPv4Address,IPv4Network


class DubbedNetworkError(ValueError):
    pass

class Common:

    def srvrestart(server_ip):
        pid_before = Common.SSHcmd(server_ip,45242,'dhcpm','p@ss','cat /var/run/dhcp-server/dhcpd.pid')
        Common.SSHcmd(server_ip,45242,'dhcpm','p@ss','sudo systemctl restart isc-dhcp-server.service')
        time.sleep(5)
        pid_after = Common.SSHcmd(server_ip,45242,'dhcpm','p@ss','cat /var/run/dhcp-server/dhcpd.pid')
        try:
            if pid_before == pid_after:
                return False
            else:
                return True
        except:
            return None


    def SSHcmd(hostname,port,username,password,*args):
        cl = paramiko.SSHClient()
        cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cl.connect(hostname=hostname,port=port,username=username,password=password)
        output = []
        for arg in args:
            stdin,stdout,stderr=cl.exec_command(arg)
            #output.append(stdout.read().decode('utf-8'))
            output.append(stdout.read().decode('utf-8')) #.decode('utf-8') for Python3
        cl.close()
        return output


    def write_remote_file(server_ip,conf_str,remote_file):
        #writecmd = 'sudo echo -e ' + conf_str + ' >> ' + remote_file
        writecmd = 'sudo echo -e ' + "'" + conf_str + "' >> " + remote_file
        err = Common.SSHcmd(server_ip,45242,'dhcpm','p@ss',writecmd)
        try:
            if err:
                return err
            else:
                return True
        except:
            return None


class StaticHost:

    static_dict = {}
    def __init__(self,hostrec,source):
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
        return self.hostrec


class Subnet:

    subnets_dict = {}  # {self.subnet : subnet_instance}
    def __init__(self,subnetrec,server):
        self.subnet=self.range1start=self.range1end=self.range2start=self.range2end=self.router=self.mask=self.broadcast=self.stroutes=self.rfc3442 = ''
        self.subnetrec = subnetrec
        self.server = server
        self.hostlist = []
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
                if self.subnet in Subnet.subnets_dict.keys():
                    Subnet.subnets_dict[self.subnet].range2start, Subnet.subnets_dict[self.subnet].range2end = [r.strip() for r in re.findall(r' [\d\.]+', line)]
                    raise DubbedNetworkError
                else:
                    Subnet.subnets_dict[self.subnet] = self
                    self.range1start, self.range1end = [r.strip() for r in re.findall(r' [\d\.]+', line)]
        self.network = IPv4Network(self.subnet + '/' + self.mask)
        self.firststatic = str(IPv4Address(self.router) + 1)
        self.laststatic = str(IPv4Address(self.range1start) - 1)

    def gethosts(self,leases):
        for lease in leases.keys():
            if IPv4Address(lease) in self.network:
                self.hostlist.append(leases[lease])


    def print_subnet_dynamic(self, leasedict):
        dynamic_page_list = []
        net = self.subnet
        subdict = Subnet.subnets_dict[net]
        Subnet.subnets_dict[net].gethosts(leasedict)
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
        logFileList1 = sorted([i for i in os.listdir('/var/log/') if 'dhcp' in i])
        logFileList2 = sorted([i for i in Common.SSHcmd('172.17.0.30',45242,'dhcp2','password','ls /var/log/ | grep dhcp')[0].split('\n') if 'dhcp' in i])
        while fCounter >= 0:
            localFile = '/var/log/' + logFileList1[fCounter]
            remoteFile = 'cat /var/log/' + logFileList2[fCounter]
            fileL = open(localFile)
            fileR = Common.SSHcmd('172.17.0.30',45242,'dhcp2','password',remoteFile)[0].split('\n')
            for sl in fileL:
                fullLog.append(sl.rstrip())
            for sr in fileR:
                fullLog.append(sr.rstrip())
            fCounter -= 1
            fileL.close()
        return fullLog


class CreateConfig:

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
                    + 'option static-routes 172.31.254.34 ' + router + ';\n}\n')
        new_net2 = ('subnet ' + subnet + ' netmask ' + netmask + ' {\n'
                    + 'range  ' + range2 + ';\n'
                    + 'option routers ' + router + ';\n'
                    + 'option subnet-mask ' + netmask + ';\n'
                    + 'option broadcast-address ' + brcast + ';\n'
                    + 'option static-routes 172.31.254.34 ' + router + ';\n}\n')
        return new_net1, new_net2


    def check_in_file(check_str,*paths):
        output = []
        for server in ('172.17.0.26','172.17.0.30'):
            for path in paths:
                file = "".join(Common.SSHcmd(server,45242,'dhcpm','p@ss','cat '+path))
                if check_str in file:
                    output.append(False)
                else:
                    output.append(True)
        if all(output) == True:
            return True
        else:
            return False
