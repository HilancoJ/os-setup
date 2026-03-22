Name:           atomic-akmods
Version:        1
Release:        1
Summary:        Packages signing keys for akmods on Atomic Fedora Desktops
License:        Unlicensed
BuildArch:      noarch

Source0:        public_key.der
Source1:        private_key.priv

# Removed `Requires` field to prevent `rpmbuild` from layering it automatically into the local package. Bypassing MOK enrollment steps.
# Requires:       akmods

%description
Packages the private key and public certificate into the OSTree staged deployment. Enabling akmods to sign kernel modules during rpm-ostree transactions.

%prep
%build

%install
# Create destination directories and install keys at the paths akmods expects
install -d %{buildroot}%{_sysconfdir}/pki/akmods/certs
install -d %{buildroot}%{_sysconfdir}/pki/akmods/private
install -m 0400 %{SOURCE0} %{buildroot}%{_sysconfdir}/pki/akmods/certs/public_key.der
install -m 0400 %{SOURCE1} %{buildroot}%{_sysconfdir}/pki/akmods/private/private_key.priv

%files
%attr(0400, root, root) %{_sysconfdir}/pki/akmods/certs/public_key.der
%attr(0400, root, root) %{_sysconfdir}/pki/akmods/private/private_key.priv