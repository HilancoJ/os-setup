# Fedora Silverblue Setup Guide

This guide covers the steps for setting up [Fedora Silverblue](https://fedoraproject.org/atomic-desktops/silverblue/).  
Including the operating system installation, layering system drivers and installing applications.



## 📜 Table of Contents
- [Download and Install Fedora Silverblue](#-download-and-install-fedora-silverblue)
- [Enhanced GPU Configurations](#-enhanced-gpu-configurations)
  - [AMD / Intel Drivers](#-amd--intel-drivers)
  - [NVIDIA Drivers](#-nvidia-drivers)
- [Hardware Monitoring and Cooling](#️-hardware-monitoring-and-cooling)
- [User Applications](#-user-applications)
- [Troubleshooting](#-troubleshooting)



## 📥 Download and Install Fedora Silverblue

1. **Download the ISO:**  
	The latest [Fedora Silverblue ISO](https://fedoraproject.org/atomic-desktops/silverblue/download) image can be downloaded from the official website.

1. **Verify the ISO:**  
	Verify the downloaded image [checksum](https://fedoraproject.org/security) and signature to ensure its authenticity.  
	- Linux:
		```bash
		sha256sum Fedora-Silverblue-ostree-*.iso
		```
	- Windows (Command Prompt):
		```cmd
		certutil -hashfile "Fedora-Silverblue-ostree-*.iso" SHA256
		```
	- Windows (PowerShell):
		```powershell
		Get-FileHash "Fedora-Silverblue-ostree-*.iso" -Algorithm SHA256
		```

1. **Create Installation Media**:  
	Use [Fedora Media Writer](https://docs.fedoraproject.org/en-US/fedora/latest/preparing-boot-media/#_fedora_media_writer) or a similar tool to create a bootable USB drive.

1. **Boot the installer:**  
	Boot the system in **UEFI/BIOS** mode and launch the prepared installation media. 

1. **Partitioning:**  
	The Fedora installer provides an automated partitioning option.  
	Alternatively, follow these steps for a custom partitioning setup. 

	| Partition | Description | Format | Size | Mountpoint |
	|-----------|-------------|--------|------|------------|
	| **EFI System Partition** | Stores the bootloader and UEFI firmware entries. | `efi` | 500 MB - 1 GB | `/boot/efi` |
	| **Boot Partition** | Contains the bootloader, kernel and drivers. | `ext4` | 2 GB - 10 GB | `/boot` |
	| **Operating System** | Holds the immutable OSTree deployment and system subvolumes. | `btrfs` | Remaining | `/` |
	| **Additional Storage** | Additional Storage Drives | `ext4` or `xfs` | | `/var/mnt/` |

	
	Depending on the use case, the following filesystems are available.

	| Filesystem | Description |
	|:----------:|-------------|
	| `btrfs` | Modern CoW (copy-on-write) filesystem supporting **snapshots**, subvolumes, transparent compression, checksums, send/receive and built-in RAID. Excellent for systems that rely on **rollback** features. |
	| `ext2` | A simple legacy filesystem without journaling. Lightweight but mostly obsolete due to the lack of modern reliability features. |
	| `ext3` | An ext2-based filesystem with journaling. More reliable than ext2 but slower and largely replaced by ext4. |
	| `ext4` | Most common Linux filesystem. Fast, stable, widely supported and low overhead. Good for external SSDs, servers and general-purpose storage. Does not provide built-in **snapshot** capabilities. |
	| `f2fs` | Flash-friendly filesystem optimized for SSDs, SD cards and mobile devices. Offers excellent performance on flash media. |
	| `ntfs` | The primary Windows filesystem. Appropriate for external drives that need Windows compatibility. Linux support is provided through drivers with varying performance. |
	| `xfs` | A high-performance filesystem optimized for large files and parallel I/O. Ideal for servers, NAS systems, media processing and large data volumes. |

1. **Upgrade Base System:**  
	Fetch the latest base image and upgrade all core system packages. A new immutable deployment will be created.
	```bash
	rpm-ostree upgrade
	```

1. **Verify that the new deployment was created:** (Optional)  
	This command can be reused after any major installation step.
	```bash
	rpm-ostree status
	```  

	Expected output: A new deployment entry appears with **(pending)**.

	| Field | Description |
	|:-----:|-------------|
	| `Version` | Current Fedora Silverblue release and revision. |
	| `BaseCommit` | OSTree commit hash for the deployed base image. |
	| `GPGSignature` | Confirms the deployment is trusted and correctly signed. |
	| `LayeredPackages` | Packages layered on top of the immutable base. |
	| `LocalPackages` | Locally provided RPMs. |

1. **Reboot the system to apply the new deployment:**
	```bash
	systemctl reboot
	```

1. **Ensure Secure Boot is enabled:** 
	```bash
	bootctl status
	```



## 🚀 Enhanced GPU Configurations
⚠️ This section is only required if enhanced GPU capabilities are needed.  
The default GPU drivers are sufficient for all practical purposes. 

1. **Enable RPM Fusion Repositories:**  
	[RPM Fusion](https://rpmfusion.org/) is a community-maintained third-party repository that provides additional software not included in Fedora due to licensing, patent or policy restrictions.  

	Both **Free** and **Non-Free** [repositories](https://rpmfusion.org/Configuration) are required for full codec and hardware support.

	1. **Install RPM Fusion Repositories:**
		```bash
		rpm-ostree install \
			https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
			https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
		```

	1. **Reboot the system after installation:**
		```bash
		systemctl reboot
		```

1. **Install GPU Drivers:**  
	There are two main graphics stacks required:  
	- **OpenGL:** A mature, widely-supported graphics API suitable for general 3D rendering used by legacy applications.  
	- **Vulkan:** A modern, low-level graphics API that gives applications direct access to GPU hardware. Enabling higher performance, better multi-threading and lower CPU overhead compared to OpenGL.  

	The instructions differ depending on the GPU vendor.

	---
	### 💎 AMD / Intel Drivers
	---
	[Mesa 3D](https://mesa3d.org/) provides the open-source drivers for rendering interactive 3D graphics.  
	
	| Package | Description | Pre-installed |
	|:-------:|:------------|:-------------:|
	| `mesa-dri-drivers` | Provides OpenGL support. | 🟢 |
	| `mesa-vulkan-drivers` | Provides Vulkan support. | 🟢 |
	| `mesa-va-drivers-freeworld` | Enables hardware-accelerated video decoding and encoding for patented codecs. | ❌ |

	AMD / Intel drivers are open-source and included in the Linux kernel by default, allowing Fedora to sign them for Secure Boot.

	1. **Install the drivers:**  
		```bash
		rpm-ostree install mesa-va-drivers-freeworld
		```  
	
	1. **Reboot the system after installation:**
		```bash
		systemctl reboot
		```

	---
	### 💊 NVIDIA Drivers
	---
	The proprietary NVIDIA drivers are distributed through RPM Fusion for optimal graphics performance.  
	While the open-source `nouveau` driver is included in the Linux kernel, it does not take advantage of full hardware acceleration.  
	Reference the official RPM Fusion documentation for a [How To Guide](https://rpmfusion.org/Howto/NVIDIA).  

	| Package | Description | Pre-installed |
	|:-------:|:------------|:-------------:|
	| `akmod-nvidia` | Builds, installs and signs the NVIDIA kernel module using the `akmods` framework. | ❌ |
	| `xorg-x11-drv-nvidia` | Provides the NVIDIA X11/Wayland display driver and OpenGL support. | Installed by `akmods-nvidia` |
	| `xorg-x11-drv-nvidia-libs` | Provides the NVIDIA user-space libraries including Vulkan support. | Installed by `akmods-nvidia` |
	| `xorg-x11-drv-nvidia-cuda` | Adds CUDA and NVDEC/NVENC support for GPU computing and video encoding/decoding. | ❌ |


	⚠️ [Secure Boot](https://fedoraproject.org/wiki/Secureboot) requires all kernel modules to be signed with a key trusted by the System Firmware (UEFI/BIOS).  
	Since the NVIDIA kernel module is **not** signed by default, Secure Boot will reject it at load time.  
	To load the driver, the module must be **built and manually signed** with a trusted Machine Owner Key (MOK).
	
	High-level Workflow:   
	1. Install Signing Tools
	1. Generate the Keys (`kmodgenca`)
	1. Enroll the Keys (`mokutil`)
	1. Ensure Keys are layered into staged deployments (`atomic-akmods`)
	1. Install NVIDIA Drivers
	1. Verify Drivers are built and signed (`akmods`)
	1. Blacklist `nouveau` drivers

	The process is based on the [RPM Fusion Secure Boot](https://rpmfusion.org/Howto/Secure%20Boot) guide.  
	The following packages are required:

	| Package | Description | Pre-installed |
	|:-------:|:------------|:-------------:|
	| `akmods` | Automatically rebuilds and signs kernel modules when a new kernel is installed. | ❌ |
	| `kmodgenca` | Generates a private key and public certificate used for signing kernel modules. | Installed by `akmods` |
	| `kmodtool` | Helps create the directory structure, metadata and specification files for building kernel modules. <br>Internal helper used by `akmods`. | ❌ |
	| `mokutil` | Manages Machine Owner Keys (MOK) for Secure Boot. Allows importing custom keys that the UEFI Firmware will trust. | 🟢 |
	| `openssl` | Provides cryptographic utilities for generating and managing private keys and certificates. <br>Internal helper used by `kmodgenca`. | 🟢 |


	🌱 It is important to perform the following steps **in sequence**:  

	1. **Install the signing tools:**
		```bash
		rpm-ostree install akmods kmodtool
		```

	1. **Reboot the system after installation:** 
		```bash
		systemctl reboot
		```

	1. **Generate a Secure Boot signing key:**   
		Generates a new private and public key pair used to sign kernel modules for Secure Boot.
		```bash
		sudo kmodgenca -a
		```

		This creates:

		| File | Location |
		|------|----------|
		| Configuration File | `/etc/akmods/cacert.conf` |
		| Private Key (PRIV) | `/etc/pki/akmods/private/<hostname>_<hash>.priv` |
		| Private Key Symlink | `/etc/pki/akmods/private/private_key.priv` |
		| Public Certificate (DER) | `/etc/pki/akmods/certs/<hostname>_<hash>.der` |
		| Public Certificate Symlink | `/etc/pki/akmods/certs/public_key.der` |
		

	1. **Import the public certificate into MOK:**  
		```bash
		sudo mokutil --import /etc/pki/akmods/certs/public_key.der
		```
		- Set a password when prompted.
		- The password will be used to enroll the key with the next reboot.
		
		⚠️ After UEFI/BIOS Firmware updates, the MOK database may be cleared. If that happens, simply re-import the same key using the command above.

	1. **Reboot and enroll the key:** 
		```bash
		systemctl reboot
		```
		During boot, the MOK Manager will appear:
		- Choose Enroll MOK
		- Enter the password
		- Confirm enrollment

	1. **Ensure Secure Boot is enabled:** 
		```bash
		bootctl status          # General purpose systemd-boot Control
		mokutil --sb-state      # Machine Owner Key Utility 
		```

	1. **Install [`atomic-akmods`](atomic-akmods/README.md) to ensure Keys are layered into staged deployments:**  
		1. Make the [installation script](atomic-akmods/atomic_akmods_install.sh) executable:
			```bash
			chmod +x atomic-akmods/atomic_akmods_install.sh
			```
		
		1. Execute the installation script:
			```bash
			sudo atomic-akmods/atomic_akmods_install.sh
			```

	1. **Install NVIDIA drivers:**  
		```bash
		rpm-ostree install akmod-nvidia xorg-x11-drv-nvidia-cuda
		```

	1. **Reboot to apply the new deployment:**  
		```bash
		systemctl reboot
		```
		
	1. **🛠️ Verify that the NVIDIA module has been built and signed:**  
		```bash
		modinfo nvidia | grep -E 'filename|signer'
		```                
		
		Expected output:

		| Field | Description |
		|:-----:|-------------|
		| `filename` | Module Exists |
		| `signer` | Module is signed and valid for Secure Boot |


	1. **Verify the NVIDIA driver is loaded:**  

		- **Confirm that the kernel module is loaded:** 
			```bash
			lsmod | grep nvidia
			```
			
			If no output appears, the NVIDIA driver did **not** load and the system is still using the fallback `nouveau` driver.  
			```bash
			lsmod | grep nouveau
			```

			Verify that all prior steps completed successfully:  
			- `akmods` and `atomic-akmods` were installed successfully
			- The MOK signing keys was enrolled successfully 
			- Secure Boot is enabled
			- `akmods` built and signed the NVIDIA module

			Display detailed information on all PCI (Peripheral Component Interconnect) devices: 
			```bash
			lspci -k | grep -A 3 -i "VGA\|3D"
			```

		- **Confirm the NVIDIA driver is operational:**  
			Shows the GPU model, driver version and active processes.
			```bash
			nvidia-smi
			``` 
			
			⚠️ The NVIDIA kernel module **must** be **signed** before proceeding.  

	1. **Blacklist the `nouveau` driver:**  
		Although `akmods-nvidia` already blacklists the `nouveau` driver, manually apply the blacklist.  
		This will guarantee that `nouveau` stays disabled across all future deployments.  

		| Kernel Argument | Description |
		|:---------------:|-------------|
		| `rd.driver.blacklist=nouveau` | Disables the module before the root filesystem is mounted (Initramfs) |
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

	1. **Confirm `nouveau` is blacklisted.**
		```bash
		cat /proc/cmdline | grep nouveau
		```


## ❄️ Hardware Monitoring and Cooling

Most fan curve applications include unnecessary dependencies that introduce system overhead.  
To provide a lightweight alternative, a minimal fan and pump controller daemon was developed.  
For custom fan curve configurations, refer to the [cooldx](cooldx/README.md) (Cooling Daemon eXtended) documentation.



## 📦 User Applications

1. **Enable the Flathub Repository:**  
	Add the [Flathub](https://flathub.org/en) Repository. It is the primary source for Flatpak applications.

	```bash
	flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
	```

1. **Update Existing Flatpak Applications:**  
	Ensure all installed Flatpak applications are up to date.

	```bash
	flatpak update
	```

1. **Install Applications via Flatpak:**  
	1. Search for an application: (e.g Monero)

		```bash
		flatpak search Monero
		```
		Expected output:
		| Name | Description | Application ID | Version | Branch | Remotes |
		|------|-------------|----------------|---------|--------|---------| 
		|Monero GUI | Monero: the secure, private, untraceable cryptocurrency | org.getmonero.Monero | 0.18.4.5 | stable | flathub |


	1. Install the application: (e.g Monero)

		```bash
		flatpak install flathub org.getmonero.Monero
		```

1. **Batch Install Flatpak Apps:**  
	1. Maintain a list of preferred applications in [Flatpak App List](flatpak/flatpak_app_list.md) using the following format:  
		```markdown
		- App Name: FlatpakID
		```

	1. Make the [installation script](flatpak/flatpak_app_install.sh) executable:
		```bash
		chmod +x flatpak/flatpak_app_install.sh
		```

	1. Install all applications listed in the file:
		```bash
		flatpak/flatpak_app_install.sh flatpak/flatpak_app_list.md
		```



## 🔧 Troubleshooting

1. **Flatpak application not using Wayland:**  
	[Qt-based](https://wiki.qt.io/About_Qt) Flatpak applications may default to X11 instead of native Wayland.

	- **Wayland**: The modern display protocol used by GNOME on Silverblue.
	- **X11/XWayland**: The legacy protocol, run through a compatibility layer.

	The application will still render a UI, but it runs through the XWayland compatibility layer.  
	This can cause blurry rendering, missing Wayland-specific features and slightly higher resource usage.  

	Override the environment to force native Wayland:
	```bash
	flatpak override --user --env=QT_QPA_PLATFORM=wayland --socket=wayland <app.id>
	```

1. **Sound device not loading after boot:**  
	[PipeWire](https://pipewire.org/) and [WirePlumber](https://pipewire.pages.freedesktop.org/wireplumber/) run as **user services** and may start before the audio hardware is fully initialised by the kernel.  
	This is common with USB DACs (digital‑to‑analogue converters), HDMI audio or after suspend/resume cycles. 

	Restarting the services forces `WirePlumber` to re-scan for audio devices:
	```bash
	systemctl --user restart wireplumber pipewire pipewire-pulse
	```
