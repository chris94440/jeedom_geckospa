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

import datetime
import logging
import argparse
import sys
import os
import signal
import json
import asyncio
import functools
import uuid

from config import Config
from geckolib import GeckoAsyncSpaMan, GeckoSpaEvent
#from jeedom.utils import Utils
#from jeedom.aio_connector import Listener, Publisher
from jeedom.jeedom import *

#try:
#	from jeedom.jeedom import *
#except ImportError:
#	print("Error: importing module jeedom.jeedom")
#	sys.exit(1)

SPA_ADDRESS = None

class GeckoSpaMan(GeckoAsyncSpaMan):
	async def handle_event(self, event: GeckoSpaEvent, **kwargs) -> None:
		# Uncomment this line to see events generated
		# print(f"{event}: {kwargs}")
		#_LOGGER.info("received event : " + event + " | args : " + kwargs)
		_LOGGER.info("ChD received event -> " + event.name)
		pass

class GeckoSpa:	
	def __init__(self, config: Config) -> None:
		self._config = config
		self._jeedom_publisher = None
		self._listen_task = None
		self._send_task = None
		self._auto_reconnect_task = None
		self._loop = None
		self._logger = logging.getLogger(__name__)
		self._facade = None
		self._spaman= None
		self._device_info = None

	async def main(self):
		_LOGGER.info('   main')
		self._jeedom_publisher = Publisher(self._config.callback_url, self._config.api_key, self._config.cycle)
		if not await self._jeedom_publisher.test_callback():
			return

		self._loop = asyncio.get_running_loop()
		self._send_task = self._jeedom_publisher.create_send_task()
		_LOGGER.info('ChD   before _connectingToSpas -> ')
		await self._connectingToSpas()
		_LOGGER.info('ChD    after _connectingToSpas -> ')
		self._listen_task = Listener.create_listen_task(self._config.socket_host, self._config.socket_port, self._on_socket_message)
		_LOGGER.info('ChD    _auto_reconnect_task')        
		self._auto_reconnect_task = asyncio.create_task(self._auto_reconnect())

		_LOGGER.info('ChD    add_signal_handler') 
		await self.add_signal_handler()
		_LOGGER.info('ChD    asyncio.sleep(1)')         
		await asyncio.sleep(1) # allow  all tasks to start
		_LOGGER.info("ChD Ready")
		_LOGGER.info('ChD    asyncio.gather')        
		await asyncio.gather(self._auto_reconnect_task, self._listen_task, self._send_task)
		_LOGGER.info('ChD    after asyncio.gather')

	async def _auto_reconnect(self):
		_LOGGER.info('   ChD before _auto_reconnect -> ')
		try:
			if self._spaman is not None:
				_LOGGER.info('   ChD auto reconnect wait for facade')
				await self._spaman.wait_for_facade()
			else:
				_LOGGER.info('   ChD spaman not exist -> connecting ')
				await self._connectingToSpas()
		except asyncio.CancelledError:
			_LOGGER.info('   ChD  error auto_reconnect task ')          		

	async def _connectingToSpas(self):
			async with GeckoSpaMan(self._config.clientId, spa_address=SPA_ADDRESS) as spaman:
				_LOGGER.info("ChD Looking for spas on your network ...")

				# Wait for descriptors to be available
				await spaman.wait_for_descriptors()

				if len(spaman.spa_descriptors) == 0:
					_LOGGER.info("ChD **** There were no spas found on your network.")
					return
				'''
				spa_descriptor = spaman.spa_descriptors[0]
				_LOGGER.info("ChD Connecting to " + spa_descriptor.name +" at " + spa_descriptor.ipaddress +" ...")
				await spaman.async_set_spa_info(
					spa_descriptor.ipaddress,
					spa_descriptor.identifier_as_string,
					spa_descriptor.name,
				)
				'''

				self._spaman=spaman
				await self.getDevices()

				# Wait for the facade to be ready
				#await spaman.wait_for_facade()
				_LOGGER.info("ChD spa connected")
				self._facade=spaman.facade
				_LOGGER.info("ChD after saved facade")
				#await self.getDevices()
				await asyncio.sleep(2)
				_LOGGER.info(spaman.facade.water_heater)
				#_LOGGER.info(self._spaman.facade.water_heater)
				#_LOGGER.info(self._facade.water_heater)

	async def getDevices(self):
		_LOGGER.info("ChD getDevices")
		response={}
		response['spas']=[]
		for i in range(len(self._spaman.spa_descriptors)):
			spa_descriptor = self._spaman.spa_descriptors[i]
			spa={}
			spa['name']=spa_descriptor.name
			spa['id']=spa_descriptor.identifier_as_string

			_LOGGER.info("ChD Connecting to " + spa_descriptor.name +" at " + spa_descriptor.ipaddress +" ...")
			await self._spaman.async_set_spa_info(
					spa_descriptor.ipaddress,
					spa_descriptor.identifier_as_string,
					spa_descriptor.name,
			)
			await self._spaman.wait_for_facade()
			self._facade=self._spaman.facade

			await self.state()
			if self._device_info is not None:
				spa['cmds'] = self._device_info
			response['spas'].append(spa)
		
		_LOGGER.debug("ChD get devices info : %s", json.dumps(response))
		await self.__format_and_send('devicesList', response)
	
	async def state(self):
		cmds=[]

		cmdWaterCare={}
		cmdWaterCare['name'] = 'waterCare'
		cmdWaterCare['state'] = str(self._facade.water_care.mode)
		cmdWaterCare['stateString'] = str(self._facade.water_care.monitor)
		cmdWaterCare['stateList'] = ["Away From Home", "Standard", "Energy Saving", "Super Energy Saving", "Weekender"] 
    #str(self._facade.water_care.modes)
		cmds.append(cmdWaterCare)
    

		for i in range(len(self._facade.lights)):
			#await self._auto_reconnect()
			#await self._spaman.wait_for_facade()
			cmdLights = {}
			cmdLights['name'] = "lights_" + str(i)
			cmdLights['state'] = str(self._facade.lights[i].is_on)
			cmdLights['stateList'] = ["True", "False"]
			cmds.append(cmdLights)
			_LOGGER.debug("LBE LIGHTS STATE %s", cmdLights)
		
		cmdHeater={}
		cmdHeater['name'] = 'waterHeater'
		cmdHeater['min_temp'] = str(self._facade.water_heater.min_temp)
		cmdHeater['max_temp'] = str(self._facade.water_heater.max_temp)
		cmdHeater['current_temp'] = str(self._facade.water_heater.current_temperature)
		cmdHeater['current_operation'] = str(self._facade.water_heater.current_operation)
		cmdHeater['target_temperature'] = str(self._facade.water_heater.target_temperature)
		cmdHeater['unit'] = str(self._facade.water_heater.temperature_unit)
		cmds.append(cmdHeater)
    
		for i in range(len(self._facade.pumps)):
			cmdPumps={}
			cmdPumps['name'] = "pumps_" + str(i)
			cmdPumps['state'] = str(self._facade.pumps[i].is_on)
			cmdPumps['mode'] = str(self._facade.pumps[i].mode)
			cmdPumps['stateList'] = self._facade.pumps[i].modes
			cmds.append(cmdPumps)

		for i in range(len(self._facade.blowers)):
			cmdBlowers = {}
			cmdBlowers['name'] = "blower_" + str(i)
			cmdBlowers['state'] = str(self._facade.blowers[i].is_on)
			cmds.append(cmdBlowers)

		for i in range(len(self._facade.sensors)):
			cmdSensors = {}
			cmdSensors['name'] = "sensor_" + str(i)
			cmdSensors['label'] = str(self._facade.sensors[i].accessor.tag)     
			cmdSensors['state'] = str(self._facade.sensors[i].state)
			cmdSensors['unit'] = str(self._facade.sensors[i].unit_of_measurement)
			cmds.append(cmdSensors)

		del cmdSensors

		for i in range(len(self._facade.binary_sensors)):
			cmdSensors = {}
			cmdSensors['name'] = "sensorBinary_" + str(i)
			cmdSensors['label'] = str(self._facade.binary_sensors[i].accessor.tag)
			cmdSensors['state'] = str(self._facade.binary_sensors[i].state)
			cmdSensors['unit'] = str(self._facade.binary_sensors[i].unit_of_measurement)
			cmds.append(cmdSensors)        

			del cmdSensors


		self._device_info = cmds

	async def add_signal_handler(self):
		self._loop.add_signal_handler(signal.SIGINT, functools.partial(self._ask_exit, signal.SIGINT))
		self._loop.add_signal_handler(signal.SIGTERM, functools.partial(self._ask_exit, signal.SIGTERM))

	def _ask_exit(self, sig):
		self._logger.info("ChD Signal %i caught, exiting...", sig)
		self.close()

	def close(self):
		self._auto_reconnect_task.cancel()
		self._listen_task.cancel()
		self._send_task.cancel()

	def _on_message(self, name):
		#tmpDevice = self._get_device_to_send(device)
		_LOGGER.debug("ChD _on_message")
		#self._loop.create_task(self.__format_and_send('update::' + device.uuid, tmpDevice))

	async def _on_socket_message(self, message):
		if message['apikey'] != self._config.api_key:
			_LOGGER.error('ChD Invalid apikey from socket : %s', str(message))
			return
		try:
			if message['action'] == 'stop':
				self.close()
			elif message['action'] == 'synchronizeBySpaId':
				_LOGGER.info('ChD  _on_socket_message -> synchronizeBySpaId')
				for i in range(len(self._spaman.spa_descriptors)):
					spa_descriptor = self._spaman.spa_descriptors[i]
					if (message['spaId'] == spa_descriptor.identifier_as_string):
						_LOGGER.debug(' * ChD spa found')
						response={}
						response['spas']=[]
						spa={}
						spa['name']=spa_descriptor.name
						spa['id']=spa_descriptor.identifier_as_string
						_LOGGER.debug(' * LBE SPA => %s', spa['name'])
						_LOGGER.debug(' * LBE SPA => %s', spa['id'])
						await self.state()
						_LOGGER.debug(' * LBE SPA GETDEVICES END => %s', self._device_info)
						if self._device_info is not None:
							spa['cmds'] = self._device_info
							response['spas'].append(spa)
							await self.__format_and_send('devicesList', response)
						
			elif message['action'] == 'get_activity_logs':
				#device = self._worxcloud.get_device_by_serial_number(message['serial_number'])
				#await self.__format_and_send('activity_logs::' + device.uuid, payload)
				_LOGGER.info('ChD  _on_socket_message -> _on_socket_message')
			elif message['action'] == 'execCmd':
				_LOGGER.info('ChD  execCmd -> ' + json.dumps(message))
				await self._execCmd(message)
			else:
				_LOGGER.info('ChD  else _on_socket_message')
		except Exception as e:
			_LOGGER.error('ChD Send command to daemon error: %s', e)

	async def __format_and_send(self, key, data):
		payload = json.loads(json.dumps(data, default=lambda d: self.__encoder(d)))
		await self._jeedom_publisher.add_change(key, payload)

	async def _execCmd(self,params):	
		_LOGGER.debug(' * Execute command')

		if params['spaIdentifier'] != "":
			spaResp={}
			spaResp['name']=""
			spaResp['id']=params['spaIdentifier']

		for i in range(len(self._spaman.spa_descriptors)):
			spa_descriptor = self._spaman.spa_descriptors[i]
			if (params['spaIdentifier'] == spa_descriptor.identifier_as_string):
				_LOGGER.debug(' * ChD spa found')
				spa={}
				spa['name']=spa_descriptor.name
				spa['id']=spa_descriptor.identifier_as_string

				'''
				_LOGGER.info("ChD _execCmd Connecting to " + spa_descriptor.name +" at " + spa_descriptor.ipaddress +" ...")
				await self._spaman.async_set_spa_info(
						spa_descriptor.ipaddress,
						spa_descriptor.identifier_as_string,
						spa_descriptor.name,
				)

				'''
				#await self._spaman.wait_for_facade()

				_LOGGER.info("ChD _execCmd before params check")
				if params['action'] != "":						
					if params['cmd'] != "":
						_LOGGER.debug('   - action : ' + params['action'])
						_LOGGER.debug('   - cmd : ' + params['cmd'])
						if params['cmd'] == "lights":
							_LOGGER.debug('   - value : ' + params['value'])																											
							if params['value'] == 'ON':
								await self._spaman.facade.lights[int(params['ind'])].async_turn_on()
								#await asyncio.sleep(5)
							else:
								await self._spaman.facade.lights[int(params['ind'])].async_turn_off()								
								#await asyncio.sleep(5)

						if params['cmd'] == "pumps":
							_LOGGER.debug('   - value : ' + params['value'])
							await self._spaman.facade.pumps[int(params['ind'])].async_set_mode(params['value'])  
							#await asyncio.sleep(5)
						'''
						if params['cmd'] == "waterCare":
							facade.water_care.set_mode(params['value'])
							time.sleep(15)
						if params['cmd'] == "target_temperature":
							facade.water_heater.set_target_temperature(params['value'])

						time.sleep(5)						
						spaResp['cmds']=getStateFromFacade(facade)
						logging.debug("Update items : %s", json.dumps(spaResp))
						jeedom_com.send_change_immediate({'updateItems' : json.dumps(spaResp)})
						'''
				
				_LOGGER.info("ChD _execCmd end params check")
				#await self.getDevices()

def shutdown():
	_LOGGER.info("ChD Shuting down")
	try:
		_LOGGER.debug("ChD Removing PID file %s", config.pid_filename)
		os.remove(config.pid_filename)
	except:
		pass

	_LOGGER.debug("Exit 0")
	sys.stdout.flush()
	os._exit(0)
# ----------------------------------------------------------------------------
parser = argparse.ArgumentParser(
description='Desmond Daemon for Jeedom plugin')
parser.add_argument("--device", help="Device", type=str)
parser.add_argument("--loglevel", help="Log Level for the daemon", type=str)
parser.add_argument("--callback", help="Callback", type=str)
parser.add_argument("--apikey", help="Apikey", type=str)
parser.add_argument("--pid", help="Pid file", type=str)
parser.add_argument("--socketport", help="Daemon port", type=str)
parser.add_argument("--clientId", help="Client Id", type=str)

args = parser.parse_args()
config = Config(**vars(args))
Utils.init_logger(config.log_level)
_LOGGER = logging.getLogger(__name__)
logging.getLogger('asyncio').setLevel(logging.WARNING)
#logging.getLogger('pyworxcloud').setLevel(Utils.convert_log_level(config.log_level))

try:
	_LOGGER.info('Starting daemon')
	_LOGGER.info('Log level: %s', config.log_level)
	Utils.write_pid(str(config.pid_filename))

	geckospa = GeckoSpa(config)
	asyncio.run(geckospa.main())
	_LOGGER.info('-------------LBE END OF START------------')
except Exception as e:
	exception_type, exception_object, exception_traceback = sys.exc_info()
	filename = exception_traceback.tb_frame.f_code.co_filename
	line_number = exception_traceback.tb_lineno
	_LOGGER.error('ChD Fatal error: %s(%s) in %s on line %s', e, exception_type, filename, line_number)
	shutdown()