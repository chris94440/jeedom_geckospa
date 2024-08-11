# This file is part of Jeedom.
#
# Jeedom is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Jeedom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Jeedom. If not, see <http://www.gnu.org/licenses/>.

import logging
import string
import sys
import os
import time
import datetime
import traceback
import re
import signal
from optparse import OptionParser
from os.path import join
import json
import argparse
import time
import uuid

from geckolib import GeckoLocator
from geckolib import GeckoConstants

try:
	from jeedom.jeedom import *
except ImportError:
	print("Error: importing module jeedom.jeedom")
	sys.exit(1)

def read_socket():
	global JEEDOM_SOCKET_MESSAGE
	if not JEEDOM_SOCKET_MESSAGE.empty():
		logging.debug("Message received in socket JEEDOM_SOCKET_MESSAGE")
		message = json.loads(JEEDOM_SOCKET_MESSAGE.get().decode('utf-8'))
		if message['apikey'] != _apikey:
			logging.error("Invalid apikey from socket: %s", message)
			return
		try:
			if message['action'] == 'execCmd':				
				logging.info('== action execute command ==')
				execCmd(message)
			elif message['action'] == 'synchronize':
				logging.info('== action synchronize ==')
				fetchStatesForallSpa()
			elif message['action'] == 'synchronizeBySpaId':
				spaResp={}
				spaResp['name']=""
				spaResp['id']=message['spaId']
				spa=_locator.get_spa_from_identifier(message['spaId'])                
				facade=spa.get_facade()
				spaResp['cmds']=getStateFromFacade(facade)
				jeedom_com.send_change_immediate({'updateItems' : json.dumps(spaResp)})                
				facade.complete()
				_locator.complete()
			else:
				logging.info('== other action not manage yes : ' + message['action']  + ' ==')
		except Exception as e:
			logging.error('Send command to demon error: %s' ,e)

def listen():
	logging.debug('Listen socket jeedom for client id' + _client_id)
	jeedom_socket.open()

	#_locator = GeckoLocator(_client_id)
	#spaDiscover()
	
	try:
		while 1:
			time.sleep(0.5)
			read_socket()

	except KeyboardInterrupt:
		shutdown()

def spaDiscover():
	logging.debug("Discovering spa ...")
	_locator.start_discovery()

	# We can perform other operations while this is progressing, like output a dot
	while not _locator.has_had_enough_time:
		# Could also be `await asyncio.sleep(1)`
		_locator.wait(1)		
		print(".", end="", flush=True)
	
	_locator.complete()

	if len(_locator.spas) == 0:
		logging.error("Cannot continue as there were no spas detected")
		shutdown()

	logging.debug("Number of spas discover : %i", int(len(_locator.spas)))
	#return locator

def fetchStatesForallSpa():
	logging.debug("Get all states for each spa")
	response={}
	response['spas']=[]

	for i in range(len(_locator.spas)):
		spa={}
		spa['name']=_locator.spas[i].name
		spa['id']=_locator.spas[i].identifier_as_string
		#spa['cmds']=[]
		#spa['cmds'].append(state({locator.spas[i].identifier_as_string}))
		spa['cmds']=state({_locator.spas[i].identifier_as_string})
		response['spas'].append(spa)

	logging.debug("List of spa and states : %s", json.dumps(response))
	jeedom_com.send_change_immediate({'devicesList' : json.dumps(response)})

def state(spaIdentifier):
	logging.debug("Get states for spa identifier : %s", spaIdentifier)

	facade = GeckoLocator.find_spa(_client_id, spaIdentifier).get_facade(False)

	logging.debug("	- Connectiong to : %s", facade.name)
	#print(f"	* Connecting to {facade.name} ", end="", flush=True)
	while not facade.is_connected:
		# Could also be `await asyncio.sleep(1)`
		facade.wait(1)
		print(".", end="", flush=True)
	#spa={}
	#spa['name']=facade.name
	#spa['id']=facade.identifier
	#spa['cmds']=[]
	cmds=[]

	logging.debug("		-> Connected")
	

	#print(f"		- Watercare mode : {facade.water_care.mode} ;list: {facade.water_care.modes}")
	cmdWaterCare={}
	cmdWaterCare['name'] = 'waterCare'
	cmdWaterCare['state'] = facade.water_care.mode
	cmdWaterCare['stateString'] = facade.water_care.monitor
	cmdWaterCare['stateList'] = facade.water_care.modes
	#cmdWaterCare['on_watercar'] = facade.water_care.on_watercar
	#cmdWaterCare['stateString']=GeckoConstants.WATERCARE_MODE_STRING.index({cmdWaterCare['state']})
	cmds.append(cmdWaterCare)
    

	#print(f"		- Lights mode : {len(facade.lights)} |{facade.lights[0].is_on}")
	for i in range(len(facade.lights)):
		cmdLights = {}
		cmdLights['name'] = "lights_" + str(i)
		cmdLights['state'] = facade.lights[i].is_on
		cmdLights['stateList'] = ['ON', 'OFF']
		cmds.append(cmdLights)

	#print(f"		- Heater : {facade.water_heater.min_temp} | {facade.water_heater.max_temp} | {facade.water_heater.current_temperature} | {facade.water_heater.temperature_unit} ")
	cmdHeater={}
	cmdHeater['name'] = 'waterHeater'
	cmdHeater['min_temp'] = facade.water_heater.min_temp
	cmdHeater['max_temp'] = facade.water_heater.max_temp
	cmdHeater['current_temp'] = facade.water_heater.current_temperature
	cmdHeater['current_operation'] = facade.water_heater.current_operation
	cmdHeater['target_temperature'] = facade.water_heater.target_temperature    
	cmdHeater['unit'] = facade.water_heater.temperature_unit
	cmds.append(cmdHeater)
    
    
	#print(f"		- Pump : {len(facade.pumps)} | {facade.pumps[0].is_on} | {facade.pumps[0].mode} | {facade.pumps[0].modes} ")
	for i in range(len(facade.pumps)):
		cmdPumps={}
		cmdPumps['name'] = "pumps_" + str(i)
		cmdPumps['state'] = facade.pumps[i].is_on
		cmdPumps['mode'] = facade.pumps[i].mode
		cmdPumps['stateList'] = facade.pumps[i].modes
		cmds.append(cmdPumps)

	for i in range(len(facade.blowers)):
		cmdBlowers = {}
		cmdBlowers['name'] = "blower_" + str(i)
		cmdBlowers['state'] = facade.blowers[i].is_on
		cmds.append(cmdBlowers)

	"""
	if facade.reminders is not None:
		for i in range(len(facade.reminders)):
			print(f"aa {facade.reminders[i].type}")
	"""

	for i in range(len(facade.sensors)):
		cmdSensors = {}
		cmdSensors['name'] = "sensor_" + str(i)
		cmdSensors['label'] = facade.sensors[i].accessor.tag        
		cmdSensors['state'] = facade.sensors[i].state
		cmdSensors['unit'] = facade.sensors[i].unit_of_measurement
		cmds.append(cmdSensors)
		#print(cmdSensors)

		del cmdSensors
	for i in range(len(facade.binary_sensors)):
		cmdSensors = {}
		cmdSensors['name'] = "sensorBinary_" + str(i)
		cmdSensors['label'] = facade.binary_sensors[i].accessor.tag
		cmdSensors['state'] = facade.binary_sensors[i].state
		cmdSensors['unit'] = facade.binary_sensors[i].unit_of_measurement
		cmds.append(cmdSensors)        

		del cmdSensors

	facade.complete()
	return cmds

def getStateFromFacade(facade):
	logging.debug("Get states from facade")
	cmds=[]

	#print(f"		- Watercare mode : {facade.water_care.mode} ;list: {facade.water_care.modes}")
	cmdWaterCare={}
	cmdWaterCare['name'] = 'waterCare'
	cmdWaterCare['state'] = facade.water_care.mode
	cmdWaterCare['stateString'] = facade.water_care.monitor
	cmdWaterCare['stateList'] = facade.water_care.modes
	#cmdWaterCare['on_watercar'] = facade.water_care.on_watercar
	#cmdWaterCare['stateString']=GeckoConstants.WATERCARE_MODE_STRING.index({cmdWaterCare['state']})
	cmds.append(cmdWaterCare)
    

	#print(f"		- Lights mode : {len(facade.lights)} |{facade.lights[0].is_on}")
	logging.debug("	- get lights info")
	for i in range(len(facade.lights)):
		cmdLights = {}
		cmdLights['name'] = "lights_" + str(i)
		cmdLights['state'] = facade.lights[i].is_on
		cmdLights['stateList'] = ['ON', 'OFF']
		cmds.append(cmdLights)

	#print(f"		- Heater : {facade.water_heater.min_temp} | {facade.water_heater.max_temp} | {facade.water_heater.current_temperature} | {facade.water_heater.temperature_unit} ")
	logging.debug("	- get waterHeater info")
	cmdHeater={}
	cmdHeater['name'] = 'waterHeater'
	cmdHeater['min_temp'] = facade.water_heater.min_temp
	cmdHeater['max_temp'] = facade.water_heater.max_temp
	cmdHeater['current_temp'] = facade.water_heater.current_temperature
	cmdHeater['current_operation'] = facade.water_heater.current_operation
	cmdHeater['target_temperature'] = facade.water_heater.target_temperature    
	cmdHeater['unit'] = facade.water_heater.temperature_unit
	cmds.append(cmdHeater)
    
    
	#print(f"		- Pump : {len(facade.pumps)} | {facade.pumps[0].is_on} | {facade.pumps[0].mode} | {facade.pumps[0].modes} ")
	logging.debug("	- get pumps info")
	for i in range(len(facade.pumps)):
		cmdPumps={}
		cmdPumps['name'] = "pumps_" + str(i)
		cmdPumps['state'] = facade.pumps[i].is_on
		cmdPumps['mode'] = facade.pumps[i].mode
		cmdPumps['stateList'] = facade.pumps[i].modes
		cmds.append(cmdPumps)

	logging.debug("	- get blowers info")
	for i in range(len(facade.blowers)):
		cmdBlowers = {}
		cmdBlowers['name'] = "blower_" + str(i)
		cmdBlowers['state'] = facade.blowers[i].is_on
		cmds.append(cmdBlowers)

	#logging.debug("	- get reminders info")
	#for i in range(len(facade.reminders)):
	#	print(f"aa {facade.reminders[i].type}")

	logging.debug("	- get sensors info")
	for i in range(len(facade.sensors)):
		cmdSensors = {}
		cmdSensors['name'] = "sensor_" + str(i)
		cmdSensors['label'] = facade.sensors[i].accessor.tag        
		cmdSensors['state'] = facade.sensors[i].state
		cmdSensors['unit'] = facade.sensors[i].unit_of_measurement
		cmds.append(cmdSensors)
		#print(cmdSensors)

		del cmdSensors
        
	logging.debug("	- get binary sensors info")
	for i in range(len(facade.binary_sensors)):
		cmdSensors = {}
		cmdSensors['name'] = "sensorBinary_" + str(i)
		cmdSensors['label'] = facade.binary_sensors[i].accessor.tag
		cmdSensors['state'] = facade.binary_sensors[i].state
		cmdSensors['unit'] = facade.binary_sensors[i].unit_of_measurement
		cmds.append(cmdSensors)        

		del cmdSensors

	facade.complete()
	return cmds	

def handler(signum=None, frame=None):
	logging.debug("Signal %i caught, exiting...", int(signum))
	shutdown()

def shutdown():
	logging.debug("Shutdown")
	logging.debug("Removing PID file %s", _pidfile)
	try:
		if _listenerId:
			unregisterListener()
	except:
		pass
	try:
		os.remove(_pidfile)
	except:
		pass
	try:
		jeedom_socket.close()
	except:
		pass
	# try:
	# 	jeedom_serial.close()
	# except:
	# 	pass
	logging.debug("Exit 0")
	sys.stdout.flush()
	os._exit(0)

def execCmd(params):	
	logging.debug(' * Execute command')

	try:
		if params['spaIdentifier'] != "":
			spaResp={}
			spaResp['name']=""
			spaResp['id']=params['spaIdentifier']

			spa=_locator.get_spa_from_identifier(params['spaIdentifier'])

			if(spa is not None):
				facade=spa.get_facade()
				if(facade is not None):	
					if params['action'] != "":						
						if params['cmd'] != "":
							logging.debug('   - action : ' + params['action'])
							logging.debug('   - cmd : ' + params['cmd'])

							if params['cmd'] == "lights":
								logging.debug('   - value : ' + params['value'])																											
								if params['value'] == 'ON':
									facade.lights[int(params['ind'])].turn_on()
								else:
									facade.lights[int(params['ind'])].turn_off()
							if params['cmd'] == "pumps":
								logging.debug('   - value : ' + params['value'])
								facade.pumps[int(params['ind'])].set_mode(params['value'])  
							if params['cmd'] == "waterCare":
								facade.water_care.set_mode(params['value'])
								time.sleep(15)
							if params['cmd'] == "target_temperature":
								facade.water_heater.set_target_temperature(params['value'])

							time.sleep(5)						
							spaResp['cmds']=getStateFromFacade(facade)
							logging.debug("Update items : %s", json.dumps(spaResp))
							jeedom_com.send_change_immediate({'updateItems' : json.dumps(spaResp)})

			_locator.complete()						
	except requests.exceptions.HTTPError as err:
		logging.error("Error when executing cmd to tahoma -> %s",err)
		shutdown()


# ----------------------------------------------------------------------------

_log_level = "error"
_socket_port = 55009
_socket_host = 'localhost'
_device = 'auto'
_pidfile = '/tmp/geckospapid.pid'
_apikey = ''
_callback = ''
_cycle = 0.3

_client_id=''

parser = argparse.ArgumentParser(
description='Daemon for Jeedom plugin')
parser.add_argument("--device", help="Device", type=str)
parser.add_argument("--loglevel", help="Log Level for the daemon", type=str)
parser.add_argument("--callback", help="Callback", type=str)
parser.add_argument("--apikey", help="Apikey", type=str)
parser.add_argument("--cycle", help="Cycle to send event", type=str)
parser.add_argument("--pid", help="Pid file", type=str)
parser.add_argument("--socketport", help="Daemon port", type=str)
parser.add_argument("--clientId", help="Client Id", type=str)
args = parser.parse_args()

if args.device:
	_device = args.device
if args.loglevel:
    _log_level = args.loglevel
if args.callback:
    _callback = args.callback
if args.apikey:
    _apikey = args.apikey
if args.pid:
    _pidfile = args.pid
if args.cycle:
    _cycle = float(args.cycle)
if args.socketport:
	_socket_port = args.socketport
if args.clientId:
	_client_id = args.clientId

_socket_port = int(_socket_port)

jeedom_utils.set_log_level(_log_level)

logging.info('*-------------------------------------------------------------------------*')
logging.info('Start demond')
logging.info('Log level: %s', _log_level)
logging.info('Socket port: %s', _socket_port)
logging.info('Socket host: %s', _socket_host)
logging.info('PID file: %s', _pidfile)
logging.info('Apikey: %s', _apikey)
logging.info('Device: %s', _device)
logging.info('Client Id : %s', _client_id)
logging.info('*-------------------------------------------------------------------------*')

signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

try:
	jeedom_utils.write_pid(str(_pidfile))
	jeedom_com = jeedom_com(apikey = _apikey,url = _callback,cycle=_cycle) # création de l'objet jeedom_com
	if not jeedom_com.test(): #premier test pour vérifier que l'url de callback est correcte
		logging.error('Network communication issues. Please fixe your Jeedom network configuration.')
		shutdown()

	jeedom_socket = jeedom_socket(port=_socket_port,address=_socket_host)

	_locator = GeckoLocator(_client_id)
	spaDiscover()
	fetchStatesForallSpa()
	_locator.complete()
	listen()
except Exception as e:
	logging.error('Fatal error: %s', e)
	logging.info(traceback.format_exc())
	shutdown()