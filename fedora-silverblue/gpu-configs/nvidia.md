# 🎮 NVIDIA Drivers

The proprietary NVIDIA drivers are distributed through RPM Fusion for optimal graphics performance.  
While the open-source `nouveau` drivers are included in the Linux kernel, it does not take advantage of full hardware acceleration.  
Reference the official RPM Fusion documentation for a [How To Guide](https://rpmfusion.org/Howto/NVIDIA).

| Package | Description | Layer |
|:--------|:------------|:-----:|
| `akmod-nvidia` | Builds, installs and signs the NVIDIA kernel module (`nvidia.ko`) using the `akmods` framework. | Kernel |
| `xorg-x11-drv-nvidia` | Provides the NVIDIA X11/Wayland display driver and OpenGL support. | User |
| `xorg-x11-drv-nvidia-libs.i686` | Provides the 32-bit NVIDIA libraries including Vulkan support. | User |
| `xorg-x11-drv-nvidia-libs` | Provides the 64-bit NVIDIA libraries including Vulkan support. | User |
| `xorg-x11-drv-nvidia-cuda` | Adds CUDA (`libcuda.so`) and NVDEC/NVENC libraries for GPU computing and hardware video encoding/decoding. | User |


## ⚠️ Prerequisites
Complete the [Secure Boot](../secure-boot/README.md) and [Atomic Akmods](../secure-boot/atomic-akmods.md) sections before proceeding.



## 🔥 Install NVIDIA Drivers

🌱 It is important to perform the following steps **in sequence**:

1. **Install NVIDIA drivers:**
	```bash
	rpm-ostree install \
		akmod-nvidia \
		xorg-x11-drv-nvidia \
		xorg-x11-drv-nvidia-libs.i686 \
		xorg-x11-drv-nvidia-libs \
		xorg-x11-drv-nvidia-cuda
	```

1. **Reboot to apply the new deployment:**
	```bash
	systemctl reboot
	```

1. **Verify that the NVIDIA kernel module has been built and signed:**
	```bash
	modinfo nvidia | grep -E 'filename|signer'
	```

	Expected output:

	| Field | Description |
	|:-----:|-------------|
	| `filename` | Module Exists |
	| `signer` | Module is signed and valid for Secure Boot |


	Verify that all prior steps completed successfully:
	- Secure Boot is enabled
	- `akmods` was installed successfully
	- The private signing key and public certificate were successfully enrolled into the MOK database
	- `atomic-akmods` was installed successfully

	Display detailed information on all PCI (Peripheral Component Interconnect) devices:
	```bash
	lspci -k | grep -A 3 -i "VGA\|3D"
	```


1. **Confirm that the kernel module is loaded:**
	```bash
	lsmod | grep nvidia
	```

	If no output appears, the NVIDIA driver did **not** load and the system is still using the fallback `nouveau` driver.
	```bash
	lsmod | grep nouveau
	```

1. **Blacklist the `nouveau` driver:**  
	
	⚠️ Ensure the NVIDIA kernel module is **signed** before proceeding.  

	While `akmod-nvidia` blacklists the `nouveau` driver automatically, applying the blacklist manually ensures it remains disabled across all future deployments. This allows the NVIDIA driver to load reliably.

	| Kernel Argument | Description |
	|:----------------|-------------|
	| `rd.driver.blacklist=nouveau` | Disables the module before the root filesystem is mounted (`initramfs`) |
	| `modprobe.blacklist=nouveau` | Standard kernel-level blacklist during regular boot |
	| `nouveau.modeset=0` | Disables KMS (Kernel Mode Setting) fallback |

	```bash
	sudo rpm-ostree kargs \
		--append=rd.driver.blacklist=nouveau \
		--append=modprobe.blacklist=nouveau \
		--append=nouveau.modeset=0
	```

	To undo, remove the kernel arguments:
	```bash
	sudo rpm-ostree kargs \
		--delete=rd.driver.blacklist=nouveau \
		--delete=modprobe.blacklist=nouveau \
		--delete=nouveau.modeset=0
	```

1. **Reboot the system after blacklisting the driver:**
	```bash
	systemctl reboot
	```

1. **Confirm `nouveau` is blacklisted:**
	```bash
	cat /proc/cmdline | grep nouveau
	```

1. **Confirm the NVIDIA driver is operational:**  
	Shows the GPU model, driver version and active processes.
	```bash
	nvidia-smi
	```