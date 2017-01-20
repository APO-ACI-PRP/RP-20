#!/usr/bin/env python
'''
TENANT RENAMER
Takes two parameters:
	1.	Existing Tenant name
	2.	New Tenant name
Copies all attributes from the existing tenant,
creates a new tenant with the same attributes
and deletes the old tenant
'''

import sys
import getpass
import acitoolkit.acitoolkit as ACI

def apic_login(hostname):
	user = raw_input('Username for ' + hostname + ' : ')
	password = getpass.getpass('Please enter password: ')
	hostname = 'https://' + hostname
	session = ACI.Session(hostname, user, password)
	try:
		result = session.login()
	except:
		print 'Could not connect to ' + hostname
		sys.exit(0)
	if not result.ok:
		print ('Could not log in to APIC')
		sys.exit(0)
	return session

def main():
	#Create the APIC session/login
	hostname, ctenant, ntenant = sys.argv[1:]
	session = apic_login(hostname)
	#Pull the details from old tenant
	tnames=[ctenant]
	tenants = ACI.Tenant.get_deep(session, names=tnames)
	if not tenants:
		print '\nTenant "' + ctenant + '" not found, exiting...'
		sys.exit(0)
	#Create an object for the new tenant and change the name
	newtenant = tenants[0]
	newtenant.name = ntenant
	#Push the new tenant to APIC
	resp = session.push_to_apic(newtenant.get_url(), newtenant.get_json())
	print resp.text
	#Delete the old tenant from APIC
	oldtenant = ACI.Tenant(ctenant)
	oldtenant.mark_as_deleted()
	resp = session.push_to_apic(oldtenant.get_url(), oldtenant.get_json())
	print resp.text

if __name__ == '__main__':
	if len(sys.argv) != 4:
		print "Usage: rt.py <hostname> <current_tenant_name> <new_tenant_name>"
		sys.exit()
	else:
		main()