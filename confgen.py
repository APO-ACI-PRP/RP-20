#!/usr/bin/env python

#################################################################################
# This Script takes a customer-facing Excel spreadsheet with device information #
# and pushes a config via NXAPI                                                 #
#                                                                               #
# Much of the data is pulled using relative cell values, so if the column/row   #
# formatting changes, might need to change column/row values in this script     #
#                                  YAY                                          #
#################################################################################

import xlrd #For reading Excel files natively
import sys
import json
from pycsco.nxos.device import Device
import getpass #For hiding password input
import xmltodict
import re #For performing regular expression searches in strings

args = sys.argv

#VALIDATE ARGUMENT AND VERIFY THE EXCEL WORKBOOK CAN BE OPENED
if len(args) == 1:
    print 'Please include the excel filename as a parameter to confgen.py:'
    print 'confgen.py <filename.xlsm>'
    sys.exit()
else:
    mainfile_location = args[1]
    try:
        workbook = xlrd.open_workbook(mainfile_location)
    except:
        print 'Could not open Excel Workbook. Filename correct?'
        sys.exit()

#I don't want to see these characters in the hostname
illegalchars = [' ', '!', '#', '$', '%', '^', '&', '*', '(', ')', '=', '+', \
                '[', ']', '{', '}', '|']
#Function for getting the hostname from the user
def inputHostname():
    hostname = raw_input('Enter hostname of device you wish to configure: ')
    for each in illegalchars:
        if each in hostname:
            print 'Illegal character found: [' + each + ']\n'
            return 1
    return hostname
#Getting hostname from the user and validating it    
hostname=inputHostname()       
while hostname == 1:
    hostname=inputHostname()

#Now we've got the Workbook opened and a valid hostname for the device, 
#time to load some Excel worksheets
#Load the Inventory & Global Settings sheets
sheet_inventory = workbook.sheet_by_name('Inventory')
sheet_settings = workbook.sheet_by_name('Global Network Settings')

#Prepare for searching the Excel worksheets
def getColumn(x,thesheet): #Finds the column number for a given text in a given sheet
    col = ''
    for each in range(thesheet.nrows):
        row = thesheet.row(each)
        for coli, cell in enumerate(row):
            if cell.value == x:
                col = coli
                return col
        if col != '':
            break
facts = {} #This is the dictionary that will store ALL device variables
hcol = getColumn('HOSTNAME',sheet_inventory)
lcol = getColumn('LOCATION',sheet_inventory)
ctcol = getColumn('CONFIG TYPE',sheet_inventory)
mipcol = getColumn('MANAGEMENT IP',sheet_inventory)
#We have the columns for the data we're looking for
#Now we loop through the rows to find our device/hostname  
facts['type'] = '' #So that we know in a bit whether or not the device was found
for each in range(sheet_inventory.nrows):
    if sheet_inventory.cell_value(each, hcol).lower() == hostname.lower():
        #Found the device/hostname, load identifying data into facts dictionary
        facts['hostname'] = sheet_inventory.cell_value(each, hcol)
        facts['location'] = sheet_inventory.cell_value(each, lcol)
        facts['type'] = sheet_inventory.cell_value(each, ctcol)
        facts['mgt_ip'] = sheet_inventory.cell_value(each, mipcol)
        print '\n' + hostname + ' found in inventory, is located at ' + facts['location'] + ' and is a ' + facts['type'] + ' device.'
        break
if facts['type'] == '':
    print 'Hostname not found!!'
    sys.exit()

#Hostname has been found and it's location & device type have been loaded
#Now we loop through and load Global settings into facts dictionary
print '\nLoading Globl network settings into facts dictionary...'
aaa_col = getColumn('AAA Server(s) / type',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'AAA Server(s) / type':
        facts['aaa_srv'] = sheet_settings.cell_value(each, hcol+1) #SEE!! "hcol+1" is a relative cell value
        aaasrv = facts['aaa_srv'].split(',')
        for i in aaasrv:
            i.strip()
        facts['aaa_srv'] = aaasrv
        facts['aaa_srv_type'] = sheet_settings.cell_value(each, hcol+2)
        facts['aaa_srv_grp'] = sheet_settings.cell_value(each+1, hcol+1)
        facts['aaa_srv_key'] = sheet_settings.cell_value(each+2, hcol+1)
        break
syslog_col = getColumn('Syslog Server & VRF',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'Syslog Server & VRF':
        facts['log_srv'] = sheet_settings.cell_value(each, hcol+1)
        facts['log_srv_vrf'] = sheet_settings.cell_value(each, hcol+2)
        break
SNMPVer_col = getColumn('SNMP Version',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'SNMP Version':
        facts['snmp_ver'] = sheet_settings.cell_value(each, hcol+1)
        break
SNMPRO_col = getColumn('SNMP RO String / permitted hosts',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'SNMP RO String / permitted hosts':
        facts['ro_string'] = sheet_settings.cell_value(each, hcol+1)
        break
SNMPRW_col = getColumn('SNMP RW String / permitted hosts',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'SNMP RW String / permitted hosts':
        facts['rw_string'] = sheet_settings.cell_value(each, hcol+1)
        break
flow_col = getColumn('NetFlow Server(s)',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'NetFlow Server(s)':
        facts['flow_srv'] = sheet_settings.cell_value(each, hcol+1)
        facts['flow_ver'] = sheet_settings.cell_value(each+1, hcol+1)
        facts['flow_port'] = sheet_settings.cell_value(each+2, hcol+1)
        break
time_col = getColumn('Time Zone',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'Time Zone':
        facts['time_zone'] = sheet_settings.cell_value(each, hcol+1)
        facts['ntp_srv_1'] = sheet_settings.cell_value(each+1, hcol+1)
        facts['ntp_srv_1_key'] = sheet_settings.cell_value(each+1, hcol+2)
        facts['ntp_srv_2'] = sheet_settings.cell_value(each+2, hcol+1)
        facts['ntp_srv_2_key'] = sheet_settings.cell_value(each+2, hcol+2)
        facts['ntp_srv_3'] = sheet_settings.cell_value(each+3, hcol+1)
        facts['ntp_srv_3_key'] = sheet_settings.cell_value(each+3, hcol+2)
        break
dom_col = getColumn('Domain name',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'Domain name':
        facts['domain'] = sheet_settings.cell_value(each, hcol+1)
        break
dns_col = getColumn('DNS Server 1',sheet_settings)
for each in range(sheet_settings.nrows):
    if sheet_settings.cell_value(each, hcol) == 'DNS Server 1':
        facts['dns_srv_1'] = sheet_settings.cell_value(each, hcol+1)
        facts['dns_srv_2'] = sheet_settings.cell_value(each+1, hcol+1)
        break
        
#ALL GLOBAL SETTINGS HAVE BEEN LOADED
#Now we try to find a vlan tab for this location and if found,
#Load up the vlan database dictionary
print '\nGlobal settings gathered, getting vlan information...'
def fourthoctetReplacer(x): #Replaces 4th octet in an ip address with ".1"
    ip_dict = {}
    for each in x.iteritems():
        tmpvlan = each[0]
        tmpip = each[1]
        tmplist = tmpip.split('.')
        mask = tmplist[3].split('/')
        ip_addr = tmplist[0] + '.' + tmplist[1] + '.' + tmplist[2] + '.1/' + mask[1]
        ip_dict[tmpvlan] = ip_addr
    return ip_dict
try:
    sheet_vlans = workbook.sheet_by_name('VLANs - ' + facts['location'])
except:
    print '\nNO VLAN TAB FOUND FOR "' + facts['location'] + '," SKIPPING...'
    sheet_vlans = None
if sheet_vlans:
    rvlans = []
    vlans = {}
    vips = {}
    hsrpvlans = []
    vcol = getColumn('VLAN ID',sheet_vlans)
    for each in range(sheet_vlans.nrows):
        if sheet_vlans.cell_value(each, vcol) == 'VLAN ID':
            for i in range(each+1,sheet_vlans.nrows):
                tmpval = sheet_vlans.cell_value(i, vcol)
                if tmpval:
                    vid = sheet_vlans.cell_value(i, vcol)
                    vname = sheet_vlans.cell_value(i, vcol+1)
                    vsub = sheet_vlans.cell_value(i, vcol+3)
                    gateway = sheet_vlans.cell_value(i, vcol+5)
                    vlans[vid] = vname
                    vips[vid] = vsub
                    if gateway.lower() == hostname.lower():
                        rvlans.append(vid)
                        hsrp = sheet_vlans.cell_value(i, vcol+6)
                        if hsrp == 'y':
                            hsrpvlans.append(vid)
    facts['routed_vlans'] = rvlans
    facts['vlans'] = vlans
    facts['vlan_ip_addr'] = fourthoctetReplacer(vips)
    facts['hsrp_vlans'] = hsrpvlans

#ALL VLAN SETTINGS HAVE BEEN LOADED
#Now we try to find a port tab for this location and if found,
#Stuff all the port configuration into the facts dictionary
print '\nVLAN configuration gathered, getting port configuration...'
try:
    sheet_ports = workbook.sheet_by_name('Port Map - ' + facts['location'])
except:
    print '\nNO PORTS TAB FOUND FOR "' + facts['location'] + '", SKIPPING...'
    sheet_ports = None
if sheet_ports:
    phcol = getColumn('HOSTNAME (chassis id)',sheet_ports)
    port_config = {}
    for each in range(sheet_ports.nrows):
        if sheet_ports.cell_value(each, phcol) == facts['hostname']:
            port = sheet_ports.cell_value(each, phcol+1)
            mode = sheet_ports.cell_value(each, phcol+2)
            desc = sheet_ports.cell_value(each, phcol+5)
            portchan = sheet_ports.cell_value(each, phcol+6)
            port_config[port] = {'mode': mode, 'desc': desc, 'pochan': portchan}
    facts['port_config'] = port_config

#ALL FACTS GATHERED, TIME TO FORMAT DATA FOR DEVICE TYPE (Could be
#NXOS/IOS/UCS)
print '\nAll facts gathered, formatting data for type ' + facts['type']
tzdict = {'CST (GMT -6)': 'CST -6 0'}
if facts['type'] == 'NXOS CLI' or 'NXOS API':
    for each in tzdict.iteritems():
        if facts['time_zone'] in each[0]:
            facts['time_zone'] = each[1]
            break
#print json.dumps(facts, indent=4)        #For Debugging

#ALL DATA FORMATTED
#START CONFIGURING DEVICE
print '\nAll data formatted. Beginning device configuration...'
def cmdRunner(x): #Runs a config command and checks whether or not it was successful
    try:
        print 'RUNNING COMMAND: ' + x
        results = sw1.config(x)
        print "SUCCESS\n"
    except Exception as e:
        print "ERROR:"
        print str(e) + '\n'
def shRunner(x): #Runs a show command and checks whether or not it was successful
    try:
        results = sw1.show(x)
        return results
    except Exception as e:
        print str(e)
def inputSWNUM(): #If HSRP present and can't determine switch #, get it from user
    innum = raw_input('Which switch is this? [1|2]: ')
    if innum == '1':
        return innum
    elif innum == '2':
        return innum
    else:
        print 'Invalid input!!'
        return 0
if facts['type'] == 'NXOS API':
    #Log in to device
    uname = raw_input('Please enter username for ' + facts['mgt_ip'] + ': ')
    pword = getpass.getpass('Please enter password: ')
    sw1 = Device(ip=facts['mgt_ip'], username=uname, password=pword)
    sw1.open()
    #Set Hostname, Domain Name, & Time Zone
    cmd = 'hostname ' + facts['hostname'] + ' ; clock timezone ' + facts['time_zone']
    if facts['domain']:
        cmd =  cmd + ' ; ip domain-name ' + facts['domain'] + ' ; cli alias name wr copy run start'
    cmdRunner(cmd)
    #Configure NTP Servers
    if facts['ntp_srv_1']:
        cmd = 'ntp server ' + facts['ntp_srv_1']
        if facts['ntp_srv_1_key']:
            cmd = 'ntp authentication-key 1 md5 ' + facts['ntp_srv_1_key'] + ' ; ' + cmd + ' key 1'
    if facts['ntp_srv_2']:
        cmd = cmd + ' ; ntp server ' + facts['ntp_srv_2']
        if facts['ntp_srv_2_key']:
            if facts['ntp_srv_1_key'] == facts['ntp_srv_2_key']:
                cmd = cmd + ' key 1'
            else:
                cmd = 'ntp authentication-key 2 md5 ' + facts['ntp_srv_2_key'] + ' ; ' + cmd + ' key 2'
    cmdRunner(cmd)
    #Configure Syslog Server
    if facts['log_srv']:
        cmd = 'logging server ' + facts['log_srv']
        if facts['log_srv_vrf']:
            cmd = cmd + ' use-vrf ' + facts['log_srv_vrf']
        cmdRunner(cmd)
    #Configure SNMP
    if (facts['ro_string'] and facts['snmp_ver'] == '2c'):
        cmd = 'snmp-server community ' + facts['ro_string'] + ' ro'
        cmdRunner(cmd)
    if (facts['rw_string'] and facts['snmp_ver'] == '2c'):
        cmd = 'snmp-server community ' + facts['rw_string'] + ' rw'
        cmdRunner(cmd)
    if facts['snmp_ver'] == '3':
        print 'Script currently does not support SNMPv3, skipping SNMP...\n'
    #Configure Netflow, first get NXOS version to make sure it is supported
    if facts['flow_srv']:
        cmd = 'sh ver'
        devver = shRunner(cmd)
        devver = xmltodict.parse(devver[1])
        devver = devver['ins_api'] ['outputs'] ['output'] ['body'] ['chassis_id']
        if '9000' in devver:
            print '9K does not support Netflow, skipping Netflow...\n'
        else:
            print 'Netflow config not supported in this script yet...\n'
    #Configure AAA
    if facts['aaa_srv']:
        if facts['aaa_srv_type'] == 'TACACS':
            cmd = 'feature tacacs ; aaa group server tacacs+ ' + facts['aaa_srv_grp']
            cmdRunner(cmd)
            aaasrvs = facts['aaa_srv']
            for each in aaasrvs:
                cmd = 'tacacs-server host ' + each + ' key ' + facts['aaa_srv_key'] + ' ; aaa group server tacacs+ ' + facts['aaa_srv_grp'] + ' ; server ' + each
                cmdRunner(cmd)
    #Configure VLANs
    if 'vlans' in facts:
        cmd = ''
        for key, value in facts['vlans'].iteritems():
            cmd = cmd + 'vlan ' + key + ' ; name ' + value + ' ; '
        cmdRunner(cmd)
    #Configure VLAN Routing
    if 'routed_vlans' in facts:
        cmd = 'feature interface-vlan'
        cmdRunner(cmd)
        for each in facts['routed_vlans']:
            for key, value in facts['vlan_ip_addr'].iteritems():
                if each == key:
                    cmd = 'interface vlan' + key + ' ; ip address ' + value + ' ; no ip redirects ; no ip unreachables ; no ip proxy ; no shutdown ; description ' + facts['vlans'][key]
                    cmdRunner(cmd)
    #Configure HSRP
    #Going to assume if the hostname ends with '-1' it is router/switch 1, otherwise
    #prompt the user which switch this is
    #Also, going to assume .1 is the vip, .2 & .3 are physicals for SW1 & SW2
    if 'hsrp_vlans' in facts:
        swnum = 0
        if facts['hostname'].endswith('-1'):
            swnum = '1'
        elif facts['hostname'].endswith('-2'):
            swnum = '2'
        else:
            print "Preparing HSRP config but couldn't tell if this is switch 1 or 2"
            while swnum == 0:
                swnum = inputSWNUM()               
        cmd = 'feature hsrp'
        cmdRunner(cmd)
        for each in facts['hsrp_vlans']:
            for key, value in facts['vlan_ip_addr'].iteritems():
                if each == key:
                    subnet = facts['vlan_ip_addr'][key].split('/')
                    mask = subnet[1]
                    workingip = subnet[0]
                    workingip = workingip.split('.')
                    prefix = ''
                    for i in range (0,3):
                       prefix = prefix + workingip[i] + '.'
                    physip = prefix
                    vip = prefix
                    if swnum == '1':
                        physip = physip + '2'
                    elif swnum == '2':
                        physip = physip + '3'
                    vip = vip + '1'
                    cmd = 'interface vlan' + key + ' ; ip address ' + physip + '/' + mask + ' ; hsrp v 2 ; hsrp ' + key + ' ; ip ' + vip + ' ; preempt'
                    if swnum == '1':
                      cmd = cmd + ' ; prio 200'
                    cmdRunner(cmd)
    #CONFIGURE INTERFACES
    if 'port_config' in facts:
        realints = shRunner('sh int br')
        realints = xmltodict.parse(realints[1])
        realints = realints['ins_api']['outputs']['output']['body']['TABLE_interface']['ROW_interface']
        realintlist = []
        for each in realints:
            if 'type' in each:
                if each['type'] == 'eth' and 'port-channel' not in each['interface']:
                    realintlist.append(each['interface'].strip('Ethernet'))
        for key, value in facts['port_config'].iteritems():
            pdesc = None
            pvlan = None
            pkey = key.strip('e')
            if pkey in realintlist:
                cmd = 'interface ' + key + ' ; swi mod ' + value['mode']
                if value['mode'] == 'Access':
                    cmd = cmd + ' ; spann port type edge'
                pdesc = value['desc']
                if 'vpc' in pdesc.lower():
                    pdesc = pdesc
                elif 'esx' in pdesc.lower():
                    pdesc = pdesc
                    cmd = cmd + ' ; spann port type edge trunk'
                elif 'vlan' in pdesc.lower():
                    pvlan = re.findall('\d+', pdesc)
                    pvlan = pvlan[0]
                    pdesc = None
                else:
                    pdesc = pdesc
                if pdesc != None and pdesc != '':
                    cmd = cmd + ' ; description ' + pdesc
                if value['pochan']:
                    tcmd = 'feature lacp'
                    cmdRunner(tcmd)
                    cmd2 = ' interface ' + key + ' ; channel-group ' + value['pochan'] + ' mode active'
                if pvlan:
                    cmd = cmd + ' ; switchport access vlan ' + pvlan
                cmdRunner(cmd)
                if value['pochan']:
                    cmdRunner(cmd2)

print '!!!!!!!!!!!ALL DONE!!!!!!!!!!!'
print "Here's the dictionary for your record:\n\n\n"
print json.dumps(facts, indent=4)