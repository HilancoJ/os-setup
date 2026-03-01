#!/usr/bin/env python3
"""
===================================================================================================
cooldx | Cooling Daemon eXtended
===================================================================================================

A lightweight, configuration-driven fan and pump controller.

Design Pattern: Configuration-Driven Controller
	- The daemon follows a declarative approach where behaviour is defined in a JSON config file. 
	- The code is generic, the config specifies the hardware.

Key Concepts:
	- Sensor: Reads temperature from hardware (`hwmon`, `nvml`).
	- Controller: Maps temperature to duty cycle via piecewise-linear interpolation.
	- Hysteresis: Prevents oscillation by requiring minimum temperature change.
	- Actuator: Writes PWM duty cycle to hardware (`hwmon`, `nvml`).

Features:
	- Duplicate Device Name Handling: Supports multiple sensors with identical names 
	  (e.g., RAM modules all named "spd5118") via sequential discovery with exclusion.
	- Sensor Initialisation Logging: Displays sensor-to-hardware mapping at startup 
	  for visibility and troubleshooting.
"""



# ===================================================================================================
# IMPORTS
# ===================================================================================================
# Only Python standard library modules are used to avoid external dependencies.
# This is critical for Fedora Silverblue where layering packages is discouraged.

from __future__ import annotations		# Enables forward references in type hints (PEP 563)
import ctypes							# Foreign function interface (NVML)
import json								# JSON config parsing
import logging							# Structured logging (integrates with journald)
import signal							# Unix signal handling for graceful shutdown
import sys								# System exit codes
import time								# Sleep between control cycles
from abc import ABC, abstractmethod		# Abstract Base Classes for interfaces
from dataclasses import dataclass		# Reduces boilerplate for data containers
from pathlib import Path				# Object-oriented filesystem paths
from typing import Optional				# Type hints for optional values



# ===================================================================================================
# CONSTANTS
# ===================================================================================================
# Module-level constants follow UPPER_SNAKE_CASE convention (PEP 8).

CONFIG_PATH_SYSTEM = Path("/etc/cooldx/cooldx_config.json")
"""System-wide config path (preferred for systemd deployment)."""

SYSTEM_INSTALL_DIR = Path("/usr/local/lib/cooldx")
"""Expected installation directory for system-wide deployment."""

HWMON_BASE_PATH = Path("/sys/class/hwmon")
"""
Linux hwmon subsystem base path. Each sensor driver registers under hwmonN/.
Device numbers change between boots, so discovery is performed by name.
"""

# PWM enable modes (hwmon sysfs interface)
PWM_MODE_OFF = 0
"""PWM mode: Fan/pump disabled."""

PWM_MODE_MANUAL = 1
"""PWM mode: Manual/software control (daemon controls duty cycle)."""

PWM_MODE_AUTO = 2
"""PWM mode: Automatic/hardware control (motherboard/device controls duty cycle)."""

PWM_MAX = 255
"""Maximum PWM value (0-255). Conversion: pwm = duty_pct x 255 / 100."""

# NVML constants
NVML_DEVICE_NAME_BUFFER_SIZE = 64
"""Buffer size for NVML device name queries (NVML API specification)."""

NVML_TEMPERATURE_GPU = 0
"""NVML temperature sensor type: GPU core temperature."""

# Determine config path
def get_config_path() -> Path:
	"""
	Returns the configuration file path.
	
	Strategy:
		1. If script is in '/usr/local/lib/cooldx/', use the SYSTEM config
		2. If cooldx_config.json exists in same directory as script, use the LOCAL config
		
	Returns:
		Path to the configuration file.
		
	Raises:
		ConfigError: If no configuration file is found.
	"""

	# Determine the directory of the currently running script
	# Use resolve() to handle symlinks and get absolute path
	script_dir = Path(__file__).resolve().parent
	
	# Normalize the system install directory for comparison
	system_dir = SYSTEM_INSTALL_DIR.resolve()
	
	# Check if running from system installation directory
	# Use Path comparison instead of string comparison for robustness
	if script_dir == system_dir:
		# Use SYSTEM config
		if CONFIG_PATH_SYSTEM.exists():
			return CONFIG_PATH_SYSTEM
		else:
			raise ConfigError(
				f"System installation detected at {script_dir}\n"
				f"Expected config at {CONFIG_PATH_SYSTEM}, but file not found."
			)
	
	# Not in system directory. Use LOCAL config (development mode)
	config_local = script_dir / "cooldx_config.json"
	if config_local.exists():
		return config_local
	else:
		raise ConfigError(
			f"Configuration file not found. Searched:\n"
			f"  - {config_local} (local)\n"
			f"Script directory: {script_dir}"
		)



# ===================================================================================================
# LOGGING CONFIGURATION
# ===================================================================================================
# The logging module integrates with systemd journald when running as a service.

log = logging.getLogger("cooldx")
"""Module-level logger instance with fixed name for consistent filtering."""


def configure_logging(verbose: bool) -> None:
	"""
	Configures the logging subsystem based on verbosity setting.
	
	Args:
		verbose: If True, logs DEBUG messages. Otherwise, INFO only.
	"""
	level = logging.DEBUG if verbose else logging.INFO
	
	# StreamHandler sends to stderr, which systemd captures to journald
	handler = logging.StreamHandler()
	handler.setFormatter(logging.Formatter(
		fmt="%(asctime)s [%(levelname)s] %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S"
	))
	
	log.setLevel(level)
	log.addHandler(handler)



# ===================================================================================================
# DATA CLASSES
# ===================================================================================================
# Dataclasses (PEP 557) auto-generate __init__, __repr__, and __eq__ methods.
# They provide type safety and IDE support compared to plain dictionaries.

@dataclass
class RuntimeConfig:
	"""Runtime configuration parameters loaded from the JSON config file."""
	test_mode: bool
	verbose_logging: bool
	poll_interval_s: float
	hysteresis_c: float
	failsafe_duty_pct: int



# ===================================================================================================
# ABSTRACT BASE CLASSES (Interfaces)
# ===================================================================================================
# ABCs define contracts that concrete classes must fulfill (Strategy Pattern).
# This enables polymorphism: the main loop works with any Sensor/Actuator without knowing the specific implementation.

class Sensor(ABC):
	"""
	Abstract base class for temperature sensors.
	
	Subclasses must implement read() to return temperature in degrees Celsius.
	"""
	
	@abstractmethod
	def read(self) -> float:
		"""
		Reads the current temperature.
		
		Returns:
			Temperature in degrees Celsius.
			
		Raises:
			SensorReadError: If the sensor cannot be read.
		"""
		pass



class Actuator(ABC):
	"""
	Abstract base class for fan/pump actuators.
	
	Subclasses must implement write() and enable_manual_control().
	"""
	
	@abstractmethod
	def enable_manual_control(self) -> None:
		"""
		Enables manual/software control of the actuator.
		
		Switches from automatic mode to manual PWM control.
		"""
		pass
	
	@abstractmethod
	def write(self, duty_pct: float) -> None:
		"""
		Sets the actuator to the specified duty cycle.
		
		Args:
			duty_pct: Duty cycle as percentage (0.0 to 100.0).
		"""
		pass



# ===================================================================================================
# CUSTOM EXCEPTIONS
# ===================================================================================================
# Custom exceptions enable precise error handling and informative messages.

class CooldxError(Exception):
	"""Base exception for all cooldx errors."""
	pass

class SensorReadError(CooldxError):
	"""Raised when a sensor read operation fails."""
	pass

class ActuatorWriteError(CooldxError):
	"""Raised when an actuator write operation fails."""
	pass

class ConfigError(CooldxError):
	"""Raised when configuration is invalid or missing."""
	pass



# ===================================================================================================
# HWMON UTILITIES
# ===================================================================================================
# Functions for interacting with the Linux `hwmon` subsystem via `sysfs`.

def discover_hwmon_device(device_name: str, excluded_paths: Optional[list[Path]] = None) -> Path:
	"""
	Finds the hwmon directory for a device by its name.
	
	Device numbers (hwmon0, hwmon1) are assigned at boot and may change.
	Device names (e.g., "coretemp", "kraken2023") are stable identifiers.
	
	Multiple devices with the same name (e.g., RAM modules with "spd5118") are 
	supported via the excluded_paths parameter. This allows sequential discovery 
	where each match is excluded from subsequent searches.
	
	Args:
		device_name: The hwmon device name from /sys/class/hwmon/hwmonN/name.
		excluded_paths: List of hwmon paths to skip during discovery (for handling duplicates).
		
	Returns:
		Path to the hwmon directory (e.g., /sys/class/hwmon/hwmon3).
		
	Raises:
		ConfigError: If no device with the given name is found (excluding already-matched paths).
	"""
	# Initialize excluded paths list if not provided
	if excluded_paths is None:
		excluded_paths = []
	
	for hwmon_dir in HWMON_BASE_PATH.iterdir():
		# Skip if this path is in the exclusion list
		if hwmon_dir in excluded_paths:
			continue
			
		name_file = hwmon_dir / "name"
		if name_file.exists():
			# .read_text() returns string with trailing newline; strip() removes it
			if name_file.read_text().strip() == device_name:
				return hwmon_dir
	
	raise ConfigError(f"hwmon device '{device_name}' not found (or all instances already assigned)")



# ===================================================================================================
# NVML Handler
# ===================================================================================================
# Singleton class that manages the NVIDIA Management Library (NVML) via ctypes.

class NvmlHandle:
	"""
	Singleton wrapper for the NVIDIA Management Library (NVML) via ctypes.
	
	NVML is the C library that nvidia-smi is built on. It ships with the NVIDIA	driver 
	as "libnvidia-ml.so.1" and provides direct GPU access without requiring	X11, Wayland 
	or any display server.
	
	This class manages:
		- Library loading and initialisation (once).
		- GPU device handle caching (per gpu_index).
		- Clean shutdown to restore automatic fan control.
	
	Singleton Pattern:
		Only one NVML instance should exist per process. Multiple sensors/actuators
		share the same instance via the class-level get() method.
	"""
	
	_instance: Optional[NvmlHandle] = None
	
	def __init__(self):
		"""
		Loads libnvidia-ml.so.1 and initialises NVML.
		
		Raises:
			ConfigError: If the NVIDIA driver or NVML library is not available.
		"""
		try:
			self._nvml = ctypes.CDLL("libnvidia-ml.so.1")
		except OSError:
			raise ConfigError(
				"libnvidia-ml.so.1 not found. "
				"NVIDIA driver is required for NVML GPU control."
			)
		
		# Initialize NVML
		ret = self._nvml.nvmlInit_v2()
		if ret != 0:
			raise ConfigError(f"NVML initialisation failed (error code {ret})")
		
		# Cache for GPU handles: gpu_index -> nvmlDevice_t (void pointer).
		self._handles: dict[int, ctypes.c_void_p] = {}
		
		# Cache for GPU device names: gpu_index -> device name string.
		self._gpu_names: dict[int, str] = {}

		# Track which fans have been manually controlled for proper cleanup on shutdown.
		# Stores tuples of (gpu_index, fan_index) for each fan that has been set via NVML.
		self._fan_controlled: list[tuple[int, int]] = [] 
	
	
	@classmethod
	def get(cls) -> NvmlHandle:
		"""
		Returns the singleton NvmlHandle instance, creating it on first call.
		
		Returns:
			The shared NvmlHandle instance.
		"""
		if cls._instance is None:
			cls._instance = NvmlHandle()
		return cls._instance
	
	
	def _get_handle(self, gpu_index: int) -> ctypes.c_void_p:
		"""
		Returns the cached device handle for a GPU index.
		
		Args:
			gpu_index: GPU index (0 for single-GPU systems).
			
		Returns:
			NVML device handle.
			
		Raises:
			ConfigError: If the GPU index is invalid.
		"""
		if gpu_index not in self._handles:

			# nvmlDeviceGetHandleByIndex_v2 takes a pointer to a c_void_p and fills it with the handle.
			handle = ctypes.c_void_p()
			ret = self._nvml.nvmlDeviceGetHandleByIndex_v2(
				gpu_index, ctypes.byref(handle)
			)

			# NVML returns 0 on success. Non-zero indicates an error.
			if ret != 0:
				raise ConfigError(f"Failed to get GPU {gpu_index} handle (error code {ret})")
			
			# Cache the handle for future use
			self._handles[gpu_index] = handle
			
		return self._handles[gpu_index]
	
	
	def get_device_name(self, gpu_index: int) -> str:
		"""
		Reads GPU device name via NVML.
		
		Caches the device name to avoid repeated NVML calls and for use during shutdown.
		
		Args:
			gpu_index: GPU index.
			
		Returns:
			GPU device name (e.g., "NVIDIA GeForce RTX 4090").
			
		Raises:
			ConfigError: If the device name cannot be read.
		"""
		# Return cached name if available
		if gpu_index in self._gpu_names:
			return self._gpu_names[gpu_index]
		
		# Extract the GPU handle for the specified index. 
		handle = self._get_handle(gpu_index)
		
		# Allocate buffer for device name
		name_buffer = ctypes.create_string_buffer(NVML_DEVICE_NAME_BUFFER_SIZE)
		ret = self._nvml.nvmlDeviceGetName(handle, name_buffer, NVML_DEVICE_NAME_BUFFER_SIZE)
		
		# NVML returns 0 on success. Non-zero indicates an error.
		if ret != 0:
			raise ConfigError(f"NVML get device name failed (error code {ret})")
		
		# Decode bytes to string and cache it
		device_name = name_buffer.value.decode('utf-8')
		self._gpu_names[gpu_index] = device_name
		
		return device_name
	
	
	def get_temperature(self, gpu_index: int) -> float:
		"""
		Reads GPU temperature via NVML.
		
		Args:
			gpu_index: GPU index.
			
		Returns:
			Temperature in degrees Celsius.
			
		Raises:
			SensorReadError: If the temperature cannot be read.
		"""

		# Extract the GPU handle for the specified index. 
		handle = self._get_handle(gpu_index)
		
		# Read the temperature from GPU core sensor.
		temp = ctypes.c_uint()
		ret = self._nvml.nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU, ctypes.byref(temp))

		# NVML returns 0 on success. Non-zero indicates an error.
		if ret != 0:
			raise SensorReadError(f"NVML temperature read failed (error code {ret})")
		
		return float(temp.value)
	
	
	def set_fan_speed(self, gpu_index: int, fan_index: int, duty_pct: int) -> None:
		"""
		Sets GPU fan speed via NVML.
		
		Args:
			gpu_index: GPU index.
			fan_index: Fan index (0 for single-fan GPUs).
			duty_pct: Fan speed as integer percentage (0-100).
			
		Raises:
			ActuatorWriteError: If the fan speed cannot be set.
		"""
		# Extract the GPU handle for the specified index. 
		handle = self._get_handle(gpu_index)
		
		# Ensure duty_pct is an integer percentage (NVML expects int, not float).
		duty_pct = int(duty_pct)

		# Update the fan speed. 
		ret = self._nvml.nvmlDeviceSetFanSpeed_v2(handle, fan_index, duty_pct)

		# NVML returns 0 on success. Non-zero indicates an error.
		if ret != 0:
			raise ActuatorWriteError(f"NVML set fan speed failed (error code {ret})")
		
		# Track this fan for automatic restore on shutdown.
		pair = (gpu_index, fan_index)
		if pair not in self._fan_controlled:
			self._fan_controlled.append(pair)
	
	
	def get_fan_speed(self, gpu_index: int, fan_index: int) -> int:
		"""
		Reads the current fan speed via NVML.
		
		Args:
			gpu_index: GPU index.
			fan_index: Fan index.
			
		Returns:
			Current fan speed as integer percentage (0-100).
			
		Raises:
			SensorReadError: If the fan speed cannot be read.
		"""
		# Extract the GPU handle for the specified index. 
		handle = self._get_handle(gpu_index)
		
		# Read the current fan speed.
		fan_speed = ctypes.c_uint()
		ret = self._nvml.nvmlDeviceGetFanSpeed_v2(handle, fan_index, ctypes.byref(fan_speed))

		# NVML returns 0 on success. Non-zero indicates an error.
		if ret != 0:
			raise SensorReadError(f"NVML fan speed read failed for GPU {gpu_index} fan {fan_index} (error code {ret})")
		
		return fan_speed.value
	
	
	def shutdown(self) -> None:
		"""
		Restores automatic fan control and shuts down NVML.
		
		Calls nvmlDeviceSetDefaultFanSpeed_v2 for each fan that was manually
		controlled, then calls nvmlShutdown.
		"""

		# Restore automatic fan control for all manually controlled fans.
		for gpu_index, fan_index in self._fan_controlled:
			try:
				handle = self._get_handle(gpu_index)
				ret = self._nvml.nvmlDeviceSetDefaultFanSpeed_v2(handle, fan_index)
				
				# Get GPU name for logging (use cached name if available)
				gpu_name = self._gpu_names.get(gpu_index, f"GPU {gpu_index}")
				
				if ret == 0:
					log.info(f"Restored automatic fan control for {gpu_name} (GPU {gpu_index}, Fan {fan_index})")
				else:
					log.warning(f"Failed to restore fan control for {gpu_name} (GPU {gpu_index}, Fan {fan_index}) (error code {ret})")
			except Exception as e:
				gpu_name = self._gpu_names.get(gpu_index, f"GPU {gpu_index}")
				log.warning(f"Error restoring fan control for {gpu_name} (GPU {gpu_index}, Fan {fan_index}): {e}")
		
		# Shutdown NVML
		self._nvml.nvmlShutdown()

		# Clear the singleton instance.
		NvmlHandle._instance = None




# ===================================================================================================
# SENSOR IMPLEMENTATIONS
# ===================================================================================================
# Concrete Sensor subclasses for different hardware interfaces. 
# Extends the Sensor ABC (Abstract Base Class).

class HwmonSensor(Sensor):
	"""
	Reads temperature from the Linux hwmon sysfs interface.
	
	Temperature files contain millidegrees Celsius (e.g., "45000" = 45.0 degrees celsius).
	Multiple sensors matching a glob pattern are aggregated (max, min, or avg).
	
	Supports multiple devices with the same name (e.g., RAM modules) via explicit 
	discovery with exclusion lists. Call discover_device() during initialisation 
	to ensure correct hwmon assignment before entering the control loop.
	
	Attributes:
		device_name: hwmon device name (e.g., "coretemp").
		match_pattern: Glob pattern for temp files (e.g., "temp*_input").
		aggregate: Aggregation method ("max", "min", "avg").
	"""
	
	def __init__(
		self,
		device_name: str,
		match_pattern: str,
		aggregate: str
	):
		"""
		Initialises the hwmon sensor.
		
		Note: Discovery is deferred until discover_device() is called or read() 
		is first invoked. For sensors with duplicate names, call discover_device() 
		explicitly during initialisation with appropriate exclusions.
		
		Args:
			device_name: hwmon device name for discovery.
			match_pattern: Glob pattern to match temperature files.
			aggregate: Method to combine multiple readings.
		"""
		self.device_name = device_name
		self.match_pattern = match_pattern
		self.aggregate = aggregate
		self._cached_path: Optional[Path] = None
	

	def discover_device(self, excluded_paths: Optional[list[Path]] = None) -> Path:
		"""
		Explicitly discovers and caches the hwmon device path.
		
		Should be called during daemon initialisation for sensors that may have 
		duplicate device names. Allows passing an exclusion list to handle multiple 
		devices with the same name (e.g., RAM modules all named "spd5118").
		
		Args:
			excluded_paths: List of hwmon paths to skip (for duplicate device names).
			
		Returns:
			The discovered hwmon directory path.
			
		Raises:
			ConfigError: If device cannot be found.
		"""
		self._cached_path = discover_hwmon_device(self.device_name, excluded_paths)
		return self._cached_path
	

	def _get_hwmon_path(self) -> Path:
		"""
		Returns the cached hwmon directory path, discovering it on first call.
		
		Note: For sensors with duplicate names, discover_device() should be called 
		explicitly during initialisation to ensure correct assignment.
		"""
		if self._cached_path is None:
			self._cached_path = discover_hwmon_device(self.device_name)
		return self._cached_path
	

	def get_device_info(self) -> str:
		"""
		Returns a display string identifying the hwmon sensor device.
		
		Returns:
			String in format "{device_name} is located at 'hwmonN'".
		"""
		hwmon_path = self._get_hwmon_path()
		return f"{self.device_name} is located at '{hwmon_path.name}'"
	

	def read(self) -> float:
		"""
		Reads temperature(s) from hwmon and returns the aggregated value.
		
		Returns:
			Temperature in degrees Celsius.
			
		Raises:
			SensorReadError: If no sensors found or all reads fail.
		"""
		hwmon_path = self._get_hwmon_path()
		temps: list[float] = []
		
		# glob() returns an iterator of matching paths
		for sensor_file in hwmon_path.glob(self.match_pattern):
			try:
				# Read millidegrees, convert to degrees
				millidegrees = int(sensor_file.read_text().strip())
				temps.append(millidegrees / 1000.0)
			except (ValueError, OSError) as e:
				log.warning(f"Failed to read {sensor_file}: {e}")
		
		if not temps:
			raise SensorReadError(
				f"No valid readings from {self.device_name}/{self.match_pattern}"
			)
		
		# Aggregate using the specified method
		# Python's built-in functions handle the list operations efficiently
		if self.aggregate == "max":
			return max(temps)
		elif self.aggregate == "min":
			return min(temps)
		elif self.aggregate == "avg":
			return sum(temps) / len(temps)
		else:
			raise ConfigError(f"Unknown aggregation method: {self.aggregate}")



class NvmlSensor(Sensor):
	"""
	Reads GPU temperature via NVML (NVIDIA Management Library).
	Uses ctypes to call libnvidia-ml.so.1 directly. 
	"""
	
	def __init__(self, gpu_index):
		"""
		Initialises the NVML sensor.
		
		Args:
			gpu_index: GPU index for multi-GPU systems.
		"""
		self.gpu_index = gpu_index
		self._cached_device_name: Optional[str] = None
	
	
	def get_device_info(self) -> str:
		"""
		Returns a display string identifying the GPU device.
		
		Retrieves the actual GPU name from NVML (e.g., "NVIDIA GeForce RTX 4090")
		and caches it to avoid repeated NVML calls.
		
		Returns:
			String in format "{gpu_name} (GPU {gpu_index})".
		"""
		if self._cached_device_name is None:
			self._cached_device_name = NvmlHandle.get().get_device_name(self.gpu_index)
		
		return f"{self._cached_device_name} (GPU {self.gpu_index})"
	
	
	def read(self) -> float:
		"""
		Reads GPU temperature via NVML.
		
		Returns:
			Temperature in degrees Celsius.
			
		Raises:
			SensorReadError: If the temperature cannot be read.
		"""
		# Use the NvmlHandle singleton to read the temperature for the specified GPU index.
		return NvmlHandle.get().get_temperature(self.gpu_index)



# ===================================================================================================
# ACTUATOR IMPLEMENTATIONS
# ===================================================================================================
# Concrete Actuator subclasses for different hardware interfaces.
# Extends the Actuator ABC (Abstract Base Class).

class HwmonActuator(Actuator):
	"""
	Controls fan/pump speed via Linux hwmon PWM interface.
	
	PWM files in hwmon:
		pwmN: Writes 0-255 to set duty cycle.
		pwmN_enable: Control mode: 0=off, 1=manual, 2=auto.
	
	Manual mode (pwmN_enable=1) must be set before PWM values take effect.
	"""
	
	def __init__(self, device_name: str, pwm_name: str, enable_name: str):
		"""
		Initialises the hwmon actuator.
		
		Args:
			device_name: hwmon device name (e.g., "kraken2023").
			pwm_name: PWM control file name (e.g., "pwm1").
			enable_name: PWM enable file name (e.g., "pwm1_enable").
		"""
		self.device_name = device_name
		self.pwm_name = pwm_name
		self.enable_name = enable_name
		self._cached_path: Optional[Path] = None
	

	def _get_hwmon_path(self) -> Path:
		"""Returns the cached hwmon directory path."""
		if self._cached_path is None:
			self._cached_path = discover_hwmon_device(self.device_name)
		return self._cached_path
	

	def get_device_info(self) -> str:
		"""
		Returns a display string identifying the actuator device.
		
		Returns:
			String in format "{device_name} is located at 'hwmonX' with PWM control '{pwm_name}'".
		"""
		hwmon_path = self._get_hwmon_path()	
		return f"{self.device_name} is located at '{hwmon_path.name}' with PWM control '{self.pwm_name}'"
	

	def enable_manual_control(self) -> None:
		"""
		Enables manual PWM control by writing PWM_MODE_MANUAL to pwmN_enable.
		
		PWM enable values: 0=off, 1=manual, 2=automatic.
		"""
		enable_path = self._get_hwmon_path() / self.enable_name
		
		try:
			enable_path.write_text(str(PWM_MODE_MANUAL))
		except OSError as e:
			raise ActuatorWriteError(f"Failed to enable manual control: {e}")
	

	def write(self, duty_pct: float) -> None:
		"""
		Writes duty cycle to the PWM file.
		
		Converts percentage (0-100) to PWM value (0-255).
		
		Args:
			duty_pct: Duty cycle as percentage (0.0 to 100.0).
		"""
		# Clamp to valid range [0, 100]
		duty_pct = max(0.0, min(100.0, duty_pct))
		
		# Convert percentage to PWM value (0-255)
		pwm_value = int(duty_pct * PWM_MAX / 100)
		
		pwm_path = self._get_hwmon_path() / self.pwm_name
		
		try:
			pwm_path.write_text(str(pwm_value))
		except OSError as e:
			raise ActuatorWriteError(f"Failed to write PWM: {e}")



class NvmlActuator(Actuator):
	"""
	Controls NVIDIA GPU fan speed via NVML (NVIDIA Management Library).
	Uses ctypes to call libnvidia-ml.so.1 directly. 
	
	NVML sets fan speed as an integer percentage (0-100). Manual control
	is implicit: calling nvmlDeviceSetFanSpeed_v2 automatically overrides
	the driver's automatic fan control.
	"""
	
	def __init__(self, gpu_index, fan_index):
		"""
		Initialises the NVML actuator.
		
		Args:
			gpu_index: GPU index for multi-GPU systems.
			fan_index: Fan index for GPUs with multiple fans.
		"""
		self.gpu_index = gpu_index
		self.fan_index = fan_index
		self._cached_device_name: Optional[str] = None
	
	
	def get_device_info(self) -> str:
		"""
		Returns a display string identifying the actuator device.
		
		Retrieves the actual GPU name from NVML (e.g., "NVIDIA GeForce RTX 4090")
		and caches it to avoid repeated NVML calls.
		
		Returns:
			String in format "{gpu_name} (GPU {gpu_index}, Fan {fan_index})".
		"""
		if self._cached_device_name is None:
			self._cached_device_name = NvmlHandle.get().get_device_name(self.gpu_index)
		
		return f"{self._cached_device_name} (GPU {self.gpu_index}, Fan {self.fan_index})"
	
	
	def enable_manual_control(self) -> None:
		"""
		Verifies NVML connectivity by reading the current fan speed.
		
		Manual control is implicitly enabled when nvmlDeviceSetFanSpeed_v2
		is called, so no explicit mode switch is needed. This method serves
		as a startup health check to confirm the GPU and fan are accessible.
		"""
		# Attempt to read the current fan speed to confirm NVML access.
		NvmlHandle.get().get_fan_speed(self.gpu_index, self.fan_index)
	
	
	def write(self, duty_pct: float) -> None:
		"""
		Sets the GPU fan speed via NVML.
		
		Args:
			duty_pct: Fan speed as percentage (0.0 to 100.0).
		"""
		# Clamp to valid range [0, 100]
		duty_pct = max(0.0, min(100.0, duty_pct))

		# Set the fan speed using the NvmlHandle singleton. 
		NvmlHandle.get().set_fan_speed(self.gpu_index, self.fan_index, duty_pct)



# ===================================================================================================
# CONTROLLER
# ===================================================================================================
# Controller class implements the core logic of mapping temperature to duty cycle.

class Controller:
	"""
	Maps temperature to duty cycle using piecewise-linear interpolation.
	
	Mathematical Background:
		Given breakpoints {(T₀, D₀), (T₁, D₁), ..., (Tₙ, Dₙ)} sorted by temperature,
		for temperature T where Tᵢ ≤ T ≤ Tᵢ₊₁:
		
		Parametric form:
			t = (T - Tᵢ) / (Tᵢ₊₁ - Tᵢ)		# Interpolation parameter, t ∈ [0, 1]
			D = Dᵢ + t x (Dᵢ₊₁ - Dᵢ)		# Interpolated duty cycle
	
	Hysteresis:
		Prevents oscillation from sensor noise by requiring a minimum temperature
		change before updating the duty cycle. Creates a "dead band" where small
		fluctuations are ignored.
	
	Attributes:
		name: Controller identifier for logging.
		sensors: List of input temperature sensors.
		aggregate: Method to combine sensor readings ("max", "min", "avg").
		actuator: Output fan/pump actuator.
		curve: List of {temp_c, duty_pct} breakpoints.
		hysteresis_c: Minimum temperature change to trigger update.
	"""
	
	def __init__(
		self,
		name: str,
		sensors: list[Sensor],
		actuator: Actuator,
		curve: list[dict],
		aggregate: str,
		hysteresis_c: float,
		test_mode: bool = False
	):
		# Initialises the controller.	
		self.name = name
		self.sensors = sensors
		self.aggregate = aggregate
		self.actuator = actuator
		self.hysteresis_c = hysteresis_c
		self.test_mode = test_mode
		
		# Sorts curve by temperature (required for interpolation algorithm)
		self.curve = sorted(curve, key=lambda p: p["temp_c"])
		
		# Output state (tracks what is currently applied to hardware)
		self._current_duty: Optional[float] = None
		
		# Last temperature readings (for logging)
		self._last_temps: list[float] = []
		
		# Hysteresis state (input-side filtering)
		self._last_decision_temp: Optional[float] = None
		self._target_duty: float = 0.0

	
	def _aggregate_temps(self, temps: list[float]) -> float:
		"""
		Combines multiple temperature readings into a single value.
		
		Aggregation methods:
			"max": Responds to hottest component (recommended).
			"min": Only ramps up when all components are hot.
			"avg": Smooths out outliers.
		"""
		if self.aggregate == "max":
			return max(temps)
		elif self.aggregate == "min":
			return min(temps)
		elif self.aggregate == "avg":
			return sum(temps) / len(temps)
		else:
			raise ConfigError(f"Unknown aggregation: {self.aggregate}")
		
	
	def _interpolate(self, temp: float) -> float:
		"""
		Computes duty cycle for a temperature using piecewise-linear interpolation.
		
		Args:
			temp: Input temperature in degrees celsius.
			
		Returns:
			Duty cycle percentage (0-100).
		"""
		# Edge case: single-point curve (constant output)
		if len(self.curve) == 1:
			return self.curve[0]["duty_pct"]
		
		# Below minimum temperature
		if temp <= self.curve[0]["temp_c"]:
			return self.curve[0]["duty_pct"]
		
		# Above maximum temperature
		if temp >= self.curve[-1]["temp_c"]:
			return self.curve[-1]["duty_pct"]
		
		# Find the enclosing segment [i, i+1]
		for i in range(len(self.curve) - 1):
			T_i = self.curve[i]["temp_c"]
			T_i1 = self.curve[i + 1]["temp_c"]
			D_i = self.curve[i]["duty_pct"]
			D_i1 = self.curve[i + 1]["duty_pct"]
			
			if T_i <= temp <= T_i1:
				# Parametric linear interpolation
				# t ∈ [0, 1] represents position within segment
				t = (temp - T_i) / (T_i1 - T_i)
				
				# Interpolated duty: D = D_i + t x (D_{i+1} - D_i)
				duty = D_i + t * (D_i1 - D_i)
				
				return duty
		
		# Should never reach here if curve is properly sorted
		return self.curve[-1]["duty_pct"]
	
	
	def read_temperature(self) -> float:
		"""
		Reads all input sensors and returns the aggregated temperature.
		
		Also stores individual readings in self._last_temps for logging.
		
		Raises:
			SensorReadError: If any sensor fails to read.
		"""
		temps: list[float] = []
		
		for sensor in self.sensors:
			temps.append(sensor.read())
		
		self._last_temps = temps
		return self._aggregate_temps(temps)
	
	
	def compute_duty(self, temp: float) -> float:
		"""
		Computes the target duty cycle, applying hysteresis.
		
		Only recomputes if temperature has changed by at least hysteresis_c
		degrees from the last decision point.
		
		Args:
			temp: Current temperature in degrees celsius.
			
		Returns:
			Target duty cycle percentage.
		"""
		
		# Format individual temps for display
		if len(self._last_temps) > 1:
			temps_str = ", ".join(f"{t:.1f}°C" for t in self._last_temps)
			temp_display = f"({temps_str}) = {temp:.1f}°C"
		else:
			temp_display = f"{temp:.1f}°C"
		
		# Check if we should update based on hysteresis
		hysteresis_check = (
			self._last_decision_temp is None # First run
			or abs(temp - self._last_decision_temp) >= self.hysteresis_c
		)
		
		if hysteresis_check:
			self._target_duty = self._interpolate(temp)
			self._last_decision_temp = temp
			log.debug(
				f"  - [{self.name}] | CURRENT_TEMP: {temp_display} | TARGET_DUTY_CYCLE: {self._target_duty:.1f}%"
			)
		else:
			current_duty_str = f"{self._current_duty:.1f}%" if self._current_duty is not None else "N/A"
			log.debug(
				f"  - [{self.name}] | Hysteresis hold applied"
			)
			log.debug(
				f"  - [{self.name}] | CURRENT_TEMP: {temp_display} | PREVIOUS_TEMP: {self._last_decision_temp:.1f}°C | CURRENT_DUTY_CYCLE: {current_duty_str}"
			)
		
		return self._target_duty
	
	
	def apply_duty(self, duty_pct: float, force: bool = False) -> bool:
		"""
		Writes the duty cycle to the actuator if the value has changed.
		
		Compares integer PWM values (0-255) to avoid floating-point precision issues.
		In test mode, updates internal state but skips hardware writes.
		
		Args:
			duty_pct: Duty cycle percentage (0.0 to 100.0).
			force: If True, writes regardless of previous value.
			
		Returns:
			True if value was written/updated, False if skipped.
		"""
		# Convert to integer PWM for comparison (matches hardware resolution)
		# This avoids issues like 50.0% vs 50.1% both mapping to PWM 127
		target_pwm = int(duty_pct * PWM_MAX / 100)
		
		if self._current_duty is not None and not force:
			current_pwm = int(self._current_duty * PWM_MAX / 100)
			
			if target_pwm == current_pwm:
				log.debug(
					f"  - [{self.name}] | TARGET_DUTY_CYCLE: {duty_pct:.1f}% | CURRENT_DUTY_CYCLE: {self._current_duty:.1f}% | PWM: {target_pwm}"
				)
				return False
		
		# Value changed (or first write / forced)
		self._current_duty = duty_pct
		
		if self.test_mode:
			# Test mode: log but don't write to hardware
			log.debug(
				f"  - [{self.name}] | [TEST] APPLIED: {duty_pct:.1f}% | PWM: {target_pwm}"
			)
		else:
			# Production mode: write to hardware
			self.actuator.write(duty_pct)
			log.debug(
				f"  - [{self.name}] | APPLIED: {duty_pct:.1f}% | PWM: {target_pwm}"
			)
		
		return True



# ===================================================================================================
# SENSOR FACTORY
# ===================================================================================================
# Factory Pattern: Centralises object creation, decoupling config from implementation.

def create_sensor(name: str, config: dict) -> Sensor:
	"""
	Creates a Sensor instance from configuration.
	
	Args:
		name: Sensor name (for error messages).
		config: Sensor configuration dict from JSON.
		
	Returns:
		Appropriate Sensor subclass instance.
		
	Raises:
		ConfigError: If sensor type is unknown or required fields are missing.
	"""
	sensor_type = config.get("type")
	
	if sensor_type == "hwmon":
		# Validate required fields
		if "device" not in config:
			raise ConfigError(
				f"Sensor '{name}': 'device' field is required for 'hwmon' sensors"
			)
		
		# Log defaults for optional fields
		if "match" not in config:
			log.debug(f"Sensor '{name}': 'match' field not specified, defaulting to 'temp*_input'")
		
		if "aggregate" not in config:
			log.debug(f"Sensor '{name}': 'aggregate' field not specified, defaulting to 'max'")
		
		# Build kwargs with validated required fields and defaults for optional fields
		return HwmonSensor(
			device_name=config["device"],
			match_pattern=config.get("match", "temp*_input"),
			aggregate=config.get("aggregate", "max")
		)
	
	elif sensor_type == "nvml":
		# Log defaults for optional fields
		if "gpu_index" not in config:
			log.debug(f"Sensor '{name}': 'gpu_index' field not specified, defaulting to '0'")
		
		return NvmlSensor(
			gpu_index=config.get("gpu_index", 0)
		)
	
	else:
		raise ConfigError(f"Unknown sensor type '{sensor_type}' for sensor '{name}'")



# ===================================================================================================
# ACTUATOR FACTORY
# ===================================================================================================
# Factory Pattern: Centralises object creation, decoupling config from implementation.

def create_actuator(config: dict) -> Actuator:
	"""
	Creates an Actuator instance from configuration.
	
	Args:
		config: Actuator configuration dict from JSON.
		
	Returns:
		Appropriate Actuator subclass instance.
		
	Raises:
		ConfigError: If actuator type is unknown or required fields are missing.
	"""
	actuator_type = config.get("type")
	
	if actuator_type == "hwmon":
		# Validate required fields
		if "device" not in config:
			raise ConfigError(
				f"Actuator: 'device' field is required for 'hwmon' actuators"
			)
		
		if "pwm" not in config:
			raise ConfigError(
				f"Actuator: 'pwm' field is required for 'hwmon' actuators"
			)
		
		if "enable" not in config:
			raise ConfigError(
				f"Actuator: 'enable' field is required for 'hwmon' actuators"
			)
		
		return HwmonActuator(
			device_name=config["device"],
			pwm_name=config["pwm"],
			enable_name=config["enable"]
		)
	
	elif actuator_type == "nvml":
		# Log defaults for optional fields
		if "gpu_index" not in config:
			log.debug(f"Actuator: Using default gpu_index '0'")
		
		if "fan_index" not in config:
			log.debug(f"Actuator: Using default fan_index '0'")
		
		return NvmlActuator(
			gpu_index=config.get("gpu_index", 0),
			fan_index=config.get("fan_index", 0)
		)
	
	else:
		raise ConfigError(f"Unknown actuator type: {actuator_type}")



# ===================================================================================================
# CONFIGURATION LOADING
# ===================================================================================================

def load_config(path: Path) -> tuple[RuntimeConfig, dict[str, Sensor], dict[str, Controller]]:
	"""
	Loads and parses the configuration file.
	
	Configuration is parsed into strongly-typed objects immediately, catching errors early rather than at runtime.
	
	Args:
		path: Path to the JSON configuration file.
		
	Returns:
		Tuple of (runtime_config, sensors_dict, controllers_dict).
		
	Raises:
		ConfigError: If configuration is invalid.
	"""
	try:
		with open(path) as f:
			raw = json.load(f)
	except (OSError, json.JSONDecodeError) as e:
		raise ConfigError(f"Failed to load config: {e}")
	
	# ==================================================================
	# Parse runtime configuration
	# ==================================================================
	rt = raw.get("runtime", {})

	runtime = RuntimeConfig(
		test_mode=rt.get("test_mode", True),
		verbose_logging=rt.get("verbose_logging", True),
		poll_interval_s=rt.get("poll_interval_s", 3),
		hysteresis_c=rt.get("hysteresis_c", 3.0),
		failsafe_duty_pct=rt.get("failsafe_duty_pct", 90)
	)
	
	# Configure logging based on runtime config
	configure_logging(runtime.verbose_logging)

	# Log defaults for runtime optional fields
	if "test_mode" not in rt:
		log.debug(f"Runtime config: Using default test_mode 'True'")
	
	if "verbose_logging" not in rt:
		log.debug(f"Runtime config: Using default verbose_logging 'True'")
	
	if "poll_interval_s" not in rt:
		log.debug(f"Runtime config: Using default poll_interval_s '3' seconds")
	
	if "hysteresis_c" not in rt:
		log.debug(f"Runtime config: Using default hysteresis_c '3.0' degrees celsius")
	
	if "failsafe_duty_pct" not in rt:
		log.debug(f"Runtime config: Using default failsafe_duty_pct '90%'")
	
	
	# ==================================================================
	# Create sensor instances
	# ==================================================================
	# Note: Sensor order in the config file matters for devices with 
	# duplicate names. Each sensor is discovered sequentially, and 
	# already-matched hwmon paths are excluded from subsequent searches.
	# This allows multiple RAM modules (all named "spd5118") to be 
	# correctly mapped to different hwmon devices.
	sensors: dict[str, Sensor] = {}
	for name, sensor_cfg in raw.get("sensors", {}).items():
		sensors[name] = create_sensor(name, sensor_cfg)
	
	
	# ==================================================================
	# Create controller instances
	# ==================================================================
	controllers: dict[str, Controller] = {}
	for name, ctrl_cfg in raw.get("controllers", {}).items():
		# Resolve sensor references to actual Sensor objects
		input_sensors = []
		for sensor_name in ctrl_cfg.get("inputs", []):
			if sensor_name not in sensors:
				raise ConfigError(
					f"Controller '{name}' references unknown sensor '{sensor_name}'"
				)
			input_sensors.append(sensors[sensor_name])
		
		actuator = create_actuator(ctrl_cfg["actuator"])
		
		# Log defaults for optional fields
		if "aggregate" not in ctrl_cfg:
			log.debug(f"Controller '{name}': Using default aggregation 'max'")

		# Validate required fields
		if "curve" not in ctrl_cfg:
			raise ConfigError(
				f"Controller '{name}': 'curve' field is required"
			)
		
		# Validate curve structure
		curve = ctrl_cfg["curve"]
		if not curve or len(curve) == 0:
			raise ConfigError(
				f"Controller '{name}': 'curve' must contain at least one point"
			)
		
		for i, point in enumerate(curve):
			if "temp_c" not in point:
				raise ConfigError(
					f"Controller '{name}': curve point {i} missing 'temp_c' field"
				)
			if "duty_pct" not in point:
				raise ConfigError(
					f"Controller '{name}': curve point {i} missing 'duty_pct' field"
				)
			
			# Validate temperature range (0-100°C is reasonable operating range)
			temp_c = point["temp_c"]
			if not 0 <= temp_c <= 100:
				raise ConfigError(
					f"Controller '{name}': curve point {i} has invalid temp_c={temp_c}. "
					f"Must be between 0 and 100°C."
				)
			
			# Validate duty cycle range (0-100%)
			duty_pct = point["duty_pct"]
			if not 0 <= duty_pct <= 100:
				raise ConfigError(
					f"Controller '{name}': curve point {i} has invalid duty_pct={duty_pct}. "
					f"Must be between 0 and 100%."
				)
		
		controller = Controller(
			name=name,
			sensors=input_sensors,
			actuator=actuator,
			curve=ctrl_cfg["curve"],
			aggregate=ctrl_cfg.get("aggregate", "max"),
			hysteresis_c=runtime.hysteresis_c,
			test_mode=runtime.test_mode
		)
		controllers[name] = controller
	
	return runtime, sensors, controllers



# ===================================================================================================
# MAIN DAEMON LOOP
# ===================================================================================================

class CoolDaemon:
	"""
	Main daemon class that orchestrates the control loop.
	
	Encapsulating the loop in a class provides clean state management,
	easy signal handling and testability.
	
	Lifecycle:
		1. __init__: Loads configuration and creates objects.
		2. run: Executes main loop until signalled to stop.
		3. Shutdown: Logs exit (fan control reverts to hardware default).
	"""
	
	def __init__(self, config_path: Path):
		"""
		Initialises the daemon by loading configuration.
		
		Args:
			config_path: Path to the JSON configuration file.
		"""
		self.config_path = config_path
		self.running = False
		
		# Load configuration
		self.runtime, self.sensors, self.controllers = load_config(config_path)
		
		# Log loaded configuration summary
		log.info("")
		log.info(f"Loaded Configuration File from '{config_path}'")

		# Detailed config logging
		log.info("")
		log.info("Runtime Configuration:")
		log.info(f"  - Test mode: {self.runtime.test_mode}")
		log.info(f"  - Verbose logging: {self.runtime.verbose_logging}")
		log.info(f"  - Poll interval: {self.runtime.poll_interval_s} seconds")
		log.info(f"  - Hysteresis: {self.runtime.hysteresis_c}°C")
		log.info(f"  - Sensors: {list(self.sensors.keys())}")
		log.info(f"  - Controllers: {list(self.controllers.keys())}")

	
	def _setup_signal_handlers(self) -> None:
		"""
		Registers Unix signal handlers for graceful shutdown.
		
		SIGTERM: Sent by systemd when stopping the service.
		SIGINT: Sent when pressing Ctrl+C (for testing).
		"""
		def handle_signal(signum, frame):
			log.info(f"Received signal \"{signum}\", shutting down...")
			self.running = False
		
		signal.signal(signal.SIGTERM, handle_signal)
		signal.signal(signal.SIGINT, handle_signal)

	
	def _initialise_sensors(self) -> None:
		"""
		Discovers and displays hardware mapping for all sensors.
		
		This method ensures that sensors with duplicate device names (e.g., multiple 
		RAM modules all named "spd5118") are correctly assigned to different hwmon 
		devices by tracking and excluding already-discovered paths.
		
		Logs the sensor name and its discovered hardware path for visibility.
		Should be called once during daemon startup before entering the control loop.
		"""
		log.info("")
		log.info("Initialising Sensors:")
		
		# Track hwmon paths that have been assigned to sensors
		excluded_hwmon_paths: list[Path] = []
		
		# Discover each sensor in configuration order
		for sensor_name, sensor in self.sensors.items():
			# Get device info for logging
			if isinstance(sensor, HwmonSensor):
				# Discover hwmon device, excluding already-assigned paths
				hwmon_path = sensor.discover_device(excluded_hwmon_paths)					
				# Add this path to exclusion list for subsequent sensors
				excluded_hwmon_paths.append(hwmon_path)					
				device_info = sensor.get_device_info()
			elif isinstance(sensor, NvmlSensor):
				# NVML sensors don't need exclusion tracking (GPU index is unique)
				device_info = sensor.get_device_info()
			else:
				device_info = "Unknown sensor type"
			
			# Log the sensor-to-hardware mapping
			log.info(f"  - [{sensor_name}]: {device_info}")

	
	def _enable_manual_control(self) -> None:
		"""
		Enables manual control on all actuators.
		
		Logs the actuator device information for visibility, showing which hardware 
		devices are being controlled.
		"""
		log.info("")
		log.info("Enabling manual control on all Actuators:")

		for controller in self.controllers.values():
			try:
				# Get device info for logging
				actuator = controller.actuator
				if isinstance(actuator, HwmonActuator):
					device_info = actuator.get_device_info()
				elif isinstance(actuator, NvmlActuator):
					device_info = actuator.get_device_info()
				else:
					device_info = "Unknown actuator type"
				
				# In test mode, skip actual hardware writes but log the intended action.
				if controller.test_mode:
					log.info(f"  - [{controller.name}]: [TEST] {device_info}")
				else:
					controller.actuator.enable_manual_control()
					log.info(f"  - [{controller.name}]: {device_info}")
			except ActuatorWriteError as e:
				log.error(f"[{controller.name}] Failed to enable manual control: {e}")

	
	def _set_failsafe(self) -> None:
		"""
		Sets all fans to failsafe (maximum) speed.
		
		Uses force=True to bypass the "skip if unchanged" optimisation.
		"""
		log.warning(f"FAILSAFE: Setting all fans to {self.runtime.failsafe_duty_pct}%")
		for controller in self.controllers.values():
			try:
				controller.apply_duty(self.runtime.failsafe_duty_pct, force=True)
			except ActuatorWriteError as e:
				log.error(f"[{controller.name}] Failed to set failsafe: {e}")

	
	def _control_cycle(self) -> bool:
		"""
		Executes one control cycle: reads sensors, computes duty, applies.
		
		Returns:
			True if cycle completed successfully, False if any sensor failed.
		"""
		success = True
		
		for controller in self.controllers.values():
			
			# Abort if shutdown signal received between controllers.
			if not self.running:
				# Not a sensor failure, so don't trigger failsafe.
				return True  
			
			try:
				# Read temperature from sensors
				temp = controller.read_temperature()
				
				# Compute target duty cycle
				duty = controller.compute_duty(temp)
				
				# Apply duty cycle 
				controller.apply_duty(duty)
					
			except SensorReadError as e:
				log.error(f"[{controller.name}] Sensor error: {e}")
				success = False
				
			except ActuatorWriteError as e:
				log.error(f"[{controller.name}] Actuator error: {e}")

			log.debug(f"")
		
		return success
	
	
	def run(self) -> None:
		"""
		Executes the main daemon loop.
		
		Loop structure:
			1. Discovers and maps all sensors to hardware devices.
			2. Enables manual control on all actuators.
			3. Repeats until signalled to stop:
			   a. Executes control cycle.
			   b. If sensor fails, sets failsafe.
			   c. Sleeps for poll interval.
			4. Logs shutdown on exit.
		"""

		# Set up signal handlers for graceful shutdown before any long-running operations.
		self._setup_signal_handlers()
		
		# Initialize sensors first (discovers hardware paths with duplicate name handling)
		self._initialise_sensors()
		
		# Enable manual control on actuators (requires sensor discovery to be complete)
		self._enable_manual_control()
		
		self.running = True
		log.info("")
		log.info("cooldx entering control loop...")
		log.info("")
		
		# Only track poll count when verbose logging is enabled
		poll_count = 1 if self.runtime.verbose_logging else None

		while self.running:
			try:

				if poll_count is not None:
					log.debug(f"Polling Loop Iteration: {poll_count}")
					poll_count += 1

				success = self._control_cycle()
				
				if not success and self.running:
					# At least one sensor failed during normal operation. Enter failsafe mode.
					# Skip failsafe during shutdown. 
					# Sensor failures are expected as dependent services are torn down by systemd.
					self._set_failsafe()
				
				time.sleep(self.runtime.poll_interval_s)
				
			except Exception as e:
				# Catch-all for unexpected errors
				log.exception(f"Unexpected error in control loop: {e}")
				self._set_failsafe()
				time.sleep(self.runtime.poll_interval_s)
		
		# Restore automatic GPU fan control and shut down NVML if it was used
		if NvmlHandle._instance is not None:
			try:
				NvmlHandle.get().shutdown()
			except Exception as e:
				log.warning(f"NVML shutdown error: {e}")
		
		log.info("")
		log.info("cooldx shutdown successful.")
		log.info("")



# ===================================================================================================
# ENTRY POINT
# ===================================================================================================

def main() -> int:
	"""
	Application entry point.
	
	Returns:
		Exit code (0 for success, 1 for error).
	"""
	try:
		config_path = get_config_path()
		daemon = CoolDaemon(config_path)
		daemon.run()
		return 0
		
	except ConfigError as e:
		# Use print for fatal errors before logging is configured
		print(f"Configuration error: {e}", file=sys.stderr)
		return 1
		
	except KeyboardInterrupt:
		# Clean exit on Ctrl+C
		print("\nInterrupted by user")
		return 0
		
	except Exception as e:
		print(f"Fatal error: {e}", file=sys.stderr)
		return 1


# Main guard ensures this code only runs when executed directly, not when imported.
if __name__ == "__main__":
	sys.exit(main())