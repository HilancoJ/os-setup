# 📀 OS Installation

- [Download Fedora Silverblue](#-download-fedora-silverblue)
- [Install Fedora Silverblue](#-install-fedora-silverblue)



## 📥 Download Fedora Silverblue

1. **Download the ISO:**  
	The latest [Fedora Silverblue ISO](https://fedoraproject.org/atomic-desktops/silverblue/download) can be downloaded from the official website.

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



## 🔥 Install Fedora Silverblue

1. **Boot the installer:**  
	Boot the system in **UEFI/BIOS** mode and launch the prepared installation media. 

1. **Partitioning:**  
	The Fedora installer provides an automated partitioning option.  
	Alternatively, follow these steps for a custom partitioning setup. 

	| Partition | Description | Format | Size | Mountpoint |
	|:---------:|-------------|:------:|:----:|:-----------|
	| **EFI System Partition** | Stores the bootloader and UEFI firmware entries. | `efi` | 500 MB - 1 GB | `/boot/efi` |
	| **Boot Partition** | Contains the bootloader, kernel and drivers. | `ext4` | 2 GB - 10 GB | `/boot` |
	| **Operating System** | Holds the immutable OSTree deployment and system subvolumes. | `btrfs` | Remaining | `/` |
	| **Additional Storage** | Additional Storage Drives | `ext4` or `xfs` | 🌱 | `/var/mnt/` |

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

1. **Set the device hostname:** (Optional)  
	Set the `<hostname>` for your device.
	```bash
	hostnamectl hostname <hostname>
	```

1. **Verify that the new deployment was created:** (Optional)  
	This command can be reused after any `rpm-ostree` installation step.
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
	General purpose `systemd` boot Control:
	```bash
	bootctl status
	```
	Machine Owner Key Utility:
	```bash
	mokutil --sb-state
	```
