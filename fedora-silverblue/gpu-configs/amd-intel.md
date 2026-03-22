# 🎮 AMD / Intel Drivers

[Mesa 3D](https://mesa3d.org/) provides the open-source drivers for rendering interactive 3D graphics.

| Package | Description | Pre-installed |
|:--------|:------------|:-------------:|
| `mesa-dri-drivers` | Provides OpenGL support. | 🟢 |
| `mesa-vulkan-drivers` | Provides Vulkan support. | 🟢 |
| `mesa-va-drivers-freeworld` | Enables hardware-accelerated video decoding and encoding for patented codecs. | ❌ |

AMD / Intel drivers are open-source and included in the Linux kernel by default, allowing Fedora to sign them for Secure Boot.



## 🔥 Install AMD / Intel Drivers

1. **Install the drivers:**  
	```bash
	rpm-ostree install mesa-va-drivers-freeworld
	```

1. **Reboot the system after installation:**
	```bash
	systemctl reboot
	```