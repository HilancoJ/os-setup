# 🚀 Enhanced GPU Configurations

This section is only required if enhanced GPU capabilities are needed.  
The default GPU drivers are sufficient for most practical purposes.



## 📚 RPM Fusion Repositories

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



## ⚙️ GPU Drivers

There are two main graphics stacks required:  
- **OpenGL:** A mature, widely-supported graphics API suitable for general 3D rendering used by legacy applications.  
- **Vulkan:** A modern, low-level graphics API that gives applications direct access to GPU hardware. Enabling higher performance, better multi-threading and lower CPU overhead compared to OpenGL.  

The setup guide is separated based on the GPU vendor:

- [AMD / Intel](amd-intel.md)
- NVIDIA
	- [Secure Boot](../secure-boot/README.md)
	- [Atomic Akmods](../secure-boot/atomic-akmods.md)
	- [NVIDIA Drivers](nvidia.md)