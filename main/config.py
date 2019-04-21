#! /usr/bin/python
# -*- coding: utf-8 -*-

class Config:
    """
    Contains constants, used in dhcpm system (servers ip addresses,
    paths to working directories/files)
    config variable is used for choosing proper  file (test/prod)
    """
    SRV1_IP = '172.17.0.26'
    SRV2_IP = '172.17.0.30'
    SRV_PORT = 45242
    SRV_LOGIN = 'dhcpm'
    SRV_PASS = 'p@ss'

    PATH_SUBNETS1 = '/etc/dhcp/subnets1'
    PATH_SUBNETS2 = '/etc/dhcp/subnets2'
    PATH_PON = '/etc/dhcp/hosts_pon'
    PATH_TECH = '/etc/dhcp/hosts_tech'
    PATH_LOG = '/var/log/dhcp.log'
    PATH_TMP = '/var/www/dhcpm/dhcpm/tmp/'
    PATH_LEASES = ''


    LEASES_TEMPLATE = """# The format of this file is documented in the dhcpd.leases(5) manual page.
# This lease file was written by isc-dhcp-4.3.5

# authoring-byte-order is generated, DO NOT DELETE
authoring-byte-order little-endian;\n\n"""

class TestConfig(Config):
    PATH_LEASES = '/home/dhcpm/leasestest'

class ProductionConfig(Config):
    PATH_LEASES = '/var/lib/dhcp/dhcpd.leases'


# !!!!!!!!!!!!
config = ProductionConfig()
# !!!!!!!!!!!!
