# [Fedora Silverblue](setup_guide.md)

## 🔒 [Immutable OS Concept](https://docs.fedoraproject.org/en-US/atomic-desktops/)
The operating system is **read-only** at runtime, ensuring the base image remains untouched. Any modification happens by **rebuilding** or **layering** a new image instead of mutating system files in place.  
- **_Benefits_**: Deterministic, reproducible systems with atomic upgrades, instant rollbacks and strong isolation between the base system and user space.  
- **_Trade-offs_**: Low-level changes (e.g. kernel modules, hardware drivers and system packages) require inclusion in the base image and activation via reboot.

Further background on [Technical Information](https://docs.fedoraproject.org/en-US/atomic-desktops/technical-information/).


## [Fedora Silverblue OS](https://fedoraproject.org/atomic-desktops/silverblue/)
An **immutable** desktop variant of Fedora built around [OSTree](https://ostreedev.github.io/ostree/) (`rpm-ostree`). The system image is managed as atomic deployments.  
Upgrades replace the OS image entirely and require a reboot to activate.  
This approach enables safe, consistent upgrades and effortless rollbacks.


## 📦 [Flatpak](https://flatpak.org/)
A containerized, **application framework** that runs apps in isolated sandboxes.  
Flatpaks install their own runtimes and dependencies in user space (or system-wide), preserving the integrity of the immutable OS.  
Perfect for desktop apps, distributed via [Flathub](https://flathub.org/en), which offers a wide range of software.


## 🧰 [Toolbox](https://docs.fedoraproject.org/en-US/fedora-silverblue/toolbox/)
A containerized, **mutable development environment** (based on Podman) that provides a distro-like shell with package manager access.  
Provides a writable container for compiling, packaging or running tooling that shouldn't be installed into the immutable OS.


## ⚙️ Driver Integration on the Base OS Image 
**Drivers** that rely on kernel modules must be part of the active OSTree deployment to load correctly at boot.  
This ensures both kernel and user-space components remain in sync within the immutable image.  
Typical examples include:
- GPU drivers
- Wi-Fi and Network Adapters
- VirtualBox
- Other low-level hardware drivers

**Flatpaks** and **Toolbox** containers cannot supply host kernel modules, they only provide user-space functionality. 