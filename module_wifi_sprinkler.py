import threading

import time

import RPi.GPIO as GPIO

arrPorts= [17,27,10,11,5,6,19,26]

# wu = module_wunderground.WunderGround()

"""Internet 'thing' that can control GPIO on a Raspberry Pi."""
class WifiSprinkler(object):

	def __init__(self):
		"""Initialize the 'thing'."""
		# Setup GPIO library.
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		# Setup Ports as an output.
		for port in arrPorts:
			GPIO.setup(port, GPIO.OUT)
			GPIO.output(port, GPIO.LOW)

		# Create a lock to syncronize access to hardware from multiple threads.
		self._lock = threading.Lock()

		# self._wu_thread = threading.Thread(target=self._update_wu)
		# self._wu_thread.daemon = True  # Don't let this thread block exiting.
		# self._wu_thread.start()

		# Initialize callback
		self._zone_callback = None
		# Interrupt flag
		self._zone_interrupt = False

		# def _update_wu(self):
		#     print("Main thread starting!")
		#     while True:
		#         wu.getNewData()
		#         time.sleep(20.0)

		# def get_temp_c(self):
		#     """Get temp and return its current value."""
		#     with self._lock:
		#         return wu.get_temp_c()

		# def get_timestamp(self):
		#     """Get timestamp and return its current value."""
		#     with self._lock:
		#         return wu.get_observation_epoch()

		# def get_humidity(self):
		#     """Get humidity and return its current value."""
		#     with self._lock:
		#         return wu.get_relative_humidity()

	def set_interrupt(self, value):
		self._zone_interrupt = value

	def set_zone(self, zone, value, duration):
		"""Set the Zone to the provided value (True = on, False = off)."""
		#print ("set_zone called, value: ", value)
		with self._lock:
			""" First turn off any possible zones first and wait 10 seconds - time for valves to close """
			for port in arrPorts:
				GPIO.setup(port, GPIO.OUT)
				GPIO.output(port, GPIO.LOW)
			time.sleep(1.0); # make it 10 sec - TBD 
			# Keep it on for the duration
			# TBD step needs to be 1 sec
			# TBD step needs to be calculated based on lenght of duration
			# 
			if value == 1:
				# Turn ON the sprinkler           
				GPIO.output(arrPorts[zone-1], GPIO.HIGH)
				# TBD: Calculate step based on duration
				step = 1.0
				# minutes = duration * 60
				minutes = duration
				for x in range(0, minutes+1, 1):
					time.sleep(step);
					progress_zone = int( (float(x) / float(minutes)) * 100)
					# Send update event via callback
					if self._zone_callback is not None:
						# Last callback parameter 0 = progress
						self._zone_callback(zone, progress_zone, 0)
						# Check for interrupt flag and if true goto end of cycle
					if self._zone_interrupt:
						# self._zone_interrupt = False
						break
				# Turn OFF the sprinkler  
				GPIO.output(arrPorts[zone-1], GPIO.LOW)
					# Send update event via callback
				if self._zone_callback is not None:
					if self._zone_interrupt:
						self._zone_interrupt = False
						self._zone_callback(zone, 0, 1)
					else:
						# Last callback parameter 100 = done
						self._zone_callback(zone, 100, 0)

	def set_zone_callback(self, callback):
		""" Register a callback function to call when we have a zone update """
		self._zone_callback = callback