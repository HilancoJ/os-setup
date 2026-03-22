# 🔐 Secure Boot

[Secure Boot](https://fedoraproject.org/wiki/Secureboot) requires all kernel modules to be signed with a key trusted by the System Firmware (UEFI). Unsigned modules are rejected at boot.  
To load third-party kernel modules (e.g. NVIDIA drivers), the module must be **built and signed** with a trusted Machine Owner Key (MOK).

- [Terminology](#-terminology)
- [Required Packages](#-required-packages)
- [Setup Machine Owner Keys](#-setup-machine-owner-keys)



## 📜 Terminology

| Term | Role |
|:-----|:-----|
| Private Key | Used to **sign** kernel modules. Do not share or export. |
| Public Certificate | The shareable half of the key pair. Distributed to systems that need to verify signatures. |
| Machine Owner Key (MOK) | A public certificate enrolled into the UEFI trusted key database, linking the key pair for Secure Boot. |



## 📦 Required Packages

The process is based on the [RPM Fusion Secure Boot](https://rpmfusion.org/Howto/Secure%20Boot) guide.

| Package | Description | Pre-installed |
|:--------|:------------|:-------------:|
| `akmods` | Automatically rebuilds and signs kernel modules when a new kernel is installed. | ❌ |
| `kmodgenca` | Generates a private key and public certificate used for signing kernel modules. | Installed by `akmods` |
| `kmodtool` | Helps create the directory structure, metadata and specification files for building kernel modules. <br>Internal helper used by `akmods`. | ❌ |
| `mokutil` | Manages Machine Owner Keys (MOK) for Secure Boot. Allows importing custom keys that the UEFI will trust. | 🟢 |
| `openssl` | Provides cryptographic utilities for generating private key and public certificates. Internal helper used by `kmodgenca`. | 🟢 |

1. **Install the signing tools:**
	```bash
	rpm-ostree install akmods kmodtool
	```

1. **Reboot the system after installation:**
	```bash
	systemctl reboot
	```


## 🔑 Setup Machine Owner Keys

🌱 It is important to perform the following steps **in sequence**:

1. **Generate signing keys:**  
	Generates a new private key and public certificate pair used to sign kernel modules.  
	Only required if keys were not generated when `akmods` was installed.
	```bash
	sudo kmodgenca -a
	```

	This creates:

	| File | Location |
	|------|----------|
	| Configuration File | `/etc/pki/akmods/cacert.conf` |
	| Private Key (`priv`) | `/etc/pki/akmods/private/<hostname>_<hash>.priv` |
	| Private Key Symlink | `/etc/pki/akmods/private/private_key.priv` |
	| Public Certificate (`der`) | `/etc/pki/akmods/certs/<hostname>_<hash>.der` |
	| Public Certificate Symlink | `/etc/pki/akmods/certs/public_key.der` |

1. **Queue the public certificate for MOK enrollment:**
	```bash
	sudo mokutil --import /etc/pki/akmods/certs/public_key.der
	```
	- Set a password when prompted.
	- The password will be used to enroll the key with the next reboot.

	⚠️ After UEFI updates, the MOK database may be cleared.  
	If that happens, simply re-import the same key using the command above.

1. **Reboot and enroll the key:**
	```bash
	systemctl reboot
	```
	During boot, the MOK Manager will appear:
	- Choose enroll MOK
	- Enter the password
	- Confirm enrollment

1. **Ensure Secure Boot is enabled:**  
	General purpose `systemd` boot Control:
	```bash
	bootctl status
	```
	Machine Owner Key Utility:
	```bash
	mokutil --sb-state
	```