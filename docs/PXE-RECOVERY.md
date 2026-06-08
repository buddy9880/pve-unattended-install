# PXE Recovery Guide

This guide explains how to use network boot as the normal recovery path for
the Proxmox automated installer.

The Cloudflare Worker in this repo can stay the same. PXE only replaces the
physical USB drive. The recovery flow becomes:

1. Build a Proxmox automated installer ISO with `proxmox-auto-install-assistant`.
2. Put that ISO on a PXE/iPXE server.
3. Use MeshCommander/AMT or the firmware boot menu to do a one-time network
   boot.
4. The installer boots from the network and still downloads the node-specific
   answer file from the Cloudflare Worker.

## What PXE Does

PXE is a firmware network boot flow:

1. The node starts network boot from its NIC firmware.
2. The node asks DHCP for an IP address.
3. DHCP also tells it where the boot server is and what boot file to download.
4. The node downloads that first boot file with TFTP.
5. That boot file usually starts iPXE, which can download larger files over
   HTTP.
6. iPXE loads an installer, rescue tool, or boot menu.

TFTP is only good for small boot files. HTTP should serve the large installer
payloads.

## Raspberry Pi Zero 2 W Suitability

A Pi Zero 2 W is enough for DHCP helper, TFTP, and small HTTP boot files. It can
work as the always-on PXE control plane.

Use a USB Ethernet adapter if possible. PXE clients boot through their wired
NICs, and serving a full Proxmox ISO through a Pi on 2.4 GHz Wi-Fi can be slow
or unreliable. Wi-Fi can still work if the Pi and the PXE clients are on the
same bridged LAN, but it is a weaker recovery dependency.

The Pi should have:

- a static IP address, for example `192.168.1.253`
- enough storage for the Proxmox ISO if it serves full ISO images
- no firewall blocking DHCP/TFTP/HTTP on the local LAN

## Recommended Design

For this repo, the most practical primary plan is:

- Pi or another always-on box serves network boot
- Cloudflare Worker continues serving `/answer`
- MeshCommander/AMT triggers one-time PXE boot
- AMT virtual media remains the backup plan

Avoid leaving PXE first in the permanent boot order unless the PXE menu is
carefully guarded. A one-time PXE boot is safer because an accidental reinstall
path should not be available during normal reboots.

## Option A: iVentoy

iVentoy is the easiest way to PXE boot whole ISO files. Put the prepared
Proxmox ISO into iVentoy's ISO folder, start iVentoy, then PXE boot the node and
select the ISO.

This is the simplest primary recovery path because it mirrors the USB flow:

1. Prepare the ISO:

       proxmox-auto-install-assistant prepare-iso ./proxmox-ve_9.2-1.iso \
         --fetch-from http \
         --url "https://pve-answer.bdev.uk/answer" \
         --output ./proxmox-ve_9.2-1-auto.iso

2. Copy `proxmox-ve_9.2-1-auto.iso` into the iVentoy ISO directory.
3. Start iVentoy.
4. Configure DHCP for iVentoy, or use iVentoy's built-in DHCP mode if it fits
   your network.
5. Use MeshCommander/AMT to one-time boot the node from PXE.
6. Select the automated Proxmox ISO from the iVentoy menu.

Important Pi note: current iVentoy ARM64 server support is a Pro-edition
feature. That matters for a Raspberry Pi. If you want the free edition, run
iVentoy on an x86_64 Linux machine or VM instead.

## Option B: dnsmasq + netboot.xyz/iPXE

This is the most open and flexible Pi-friendly path. It is excellent for rescue
menus and general network boot. For a Proxmox automated ISO, it needs more
testing than iVentoy because Proxmox's automated installer must be activated in
the ISO and with the `proxmox-start-auto-installer` kernel argument.

Install the services on the Pi:

    sudo apt update
    sudo apt install -y dnsmasq nginx wget

Create TFTP and HTTP directories:

    sudo mkdir -p /srv/tftp /var/www/html/pxe
    sudo chown -R root:root /srv/tftp /var/www/html/pxe

Download netboot.xyz boot files:

    sudo wget -O /srv/tftp/netboot.xyz.kpxe https://boot.netboot.xyz/ipxe/netboot.xyz.kpxe
    sudo wget -O /srv/tftp/netboot.xyz.efi https://boot.netboot.xyz/ipxe/netboot.xyz.efi

Add a dnsmasq PXE config:

    sudo tee /etc/dnsmasq.d/pxe.conf >/dev/null <<'EOF'
    port=0
    log-dhcp
    interface=eth0
    bind-interfaces
    dhcp-range=192.168.1.0,proxy,255.255.255.0
    dhcp-no-override
    enable-tftp
    tftp-root=/srv/tftp
    pxe-service=X86PC,"netboot.xyz BIOS",netboot.xyz.kpxe,192.168.1.253
    pxe-service=BC_EFI,"netboot.xyz UEFI",netboot.xyz.efi,192.168.1.253
    pxe-service=X86-64_EFI,"netboot.xyz UEFI",netboot.xyz.efi,192.168.1.253
    EOF

This config assumes your router is still the real DHCP server and the Pi only
answers PXE boot-file requests. Change `interface=eth0` to the Pi interface
that is on the PXE client LAN. Change `192.168.1.0` and `255.255.255.0` to your
LAN subnet and netmask.

If your router can set DHCP option 66/67 directly, you can point option 66 at
the Pi IP and option 67 at the correct boot file instead. In that case, you may
not need ProxyDHCP from dnsmasq.

Restart dnsmasq:

    sudo systemctl restart dnsmasq
    sudo systemctl status dnsmasq --no-pager

Test TFTP from another machine:

    tftp 192.168.1.253 -c get netboot.xyz.efi

Replace `192.168.1.253` with the Pi IP.

At this point, PXE boot should load netboot.xyz. This gives you a useful
recovery menu even before Proxmox automation is wired in.

## Automatic Proxmox Boot

Once the node reaches the netboot.xyz menu, the network boot foundation is
working. The next step is to replace the generic menu with a local iPXE script
that defaults to the Proxmox automated installer.

There are two practical ways to boot the installer:

- ISO-aware PXE tooling, such as iVentoy, can boot the same prepared ISO that
  you would write to USB.
- Direct iPXE boot loads the Proxmox kernel, initrd, and prepared ISO over HTTP.
  This path still uses the prepared ISO, but it bypasses the ISO bootloader, so
  the iPXE script must pass `proxmox-start-auto-installer`.

For direct iPXE, host these three files from the Pi:

    /var/www/html/pxe/proxmox/vmlinuz
    /var/www/html/pxe/proxmox/initrd
    /var/www/html/pxe/proxmox/proxmox-auto.iso

`proxmox-auto.iso` should be created with the same command used for the USB
flow:

    proxmox-auto-install-assistant prepare-iso ./proxmox-ve_9.2-1.iso \
      --fetch-from http \
      --url "https://pve-answer.bdev.uk/answer" \
      --output ./proxmox-auto.iso

Then create a local iPXE script on the Pi:

    sudo tee /var/www/html/pxe/auto-proxmox.ipxe >/dev/null <<'EOF'
    #!ipxe
    dhcp
    set pxe_base http://192.168.1.253/pxe/proxmox
    imgfree
    kernel ${pxe_base}/vmlinuz vga=791 video=vesafb:ywrap,mtrr ramdisk_size=16777216 rw quiet splash=silent proxmox-start-auto-installer initrd=initrd.magic
    initrd ${pxe_base}/initrd
    initrd ${pxe_base}/proxmox-auto.iso /proxmox.iso
    boot
    EOF

To boot that script automatically, use an iPXE first-stage bootloader that
chains to:

    http://192.168.1.253/pxe/auto-proxmox.ipxe

If using netboot.xyz, a useful compromise is to keep the normal netboot.xyz boot
files but add a MAC-gated and manually armed `autoexec.ipxe` file. netboot.xyz
checks for that file while starting. Known Proxmox nodes can chain into the
automated installer only when recovery is explicitly armed. If disarmed, known
Proxmox nodes reboot so firmware can return to the normal NVMe/proxmox boot
order. Unknown PXE clients can continue to the normal menu:

    sudo tee /srv/tftp/autoexec.ipxe >/dev/null <<'EOF'
    #!ipxe
    set auto_url http://192.168.1.253/pxe/auto-proxmox.ipxe
    set armed_url http://192.168.1.253/pxe/proxmox/ARMED
    
    iseq ${net0/mac} 10:62:e5:00:17:8d && goto maybe_auto ||
    iseq ${net0/mac} 90:8d:6e:8c:45:cf && goto maybe_auto ||
    exit
    
    :maybe_auto
    imgfetch --timeout 3000 ${armed_url} && chain ${auto_url} || goto disarmed
    
    :disarmed
    echo Proxmox PXE installer is not armed. Rebooting to normal boot order...
    sleep 3
    reboot
    EOF

Arm automatic reinstall only when needed:

    ssh buddy@192.168.1.253 '/home/buddy/pxe-installer-control.sh arm'

Disarm it after the recovery boot starts:

    ssh buddy@192.168.1.253 '/home/buddy/pxe-installer-control.sh disarm'

Check status:

    ssh buddy@192.168.1.253 '/home/buddy/pxe-installer-control.sh status'

Running `/home/buddy/pxe-installer-control.sh` on the Pi without arguments
shows status and prompts for `arm`, `disarm`, `status`, or `quit`.

Keep a manual netboot.xyz entry or AMT virtual media available as the fallback.
Do not make this the permanent default until it has been tested on a disposable
disk or a node you are intentionally reinstalling.

## Proxmox Automated PXE Notes

The Proxmox automated installer is not enabled by the stock ISO. Continue using
`proxmox-auto-install-assistant prepare-iso` even if the answer file comes from
HTTP.

For network boot paths that extract the ISO and boot the kernel/initrd directly,
the boot entry must include:

    proxmox-start-auto-installer

In practice, direct Proxmox PXE boot often requires either:

- serving a prepared ISO through an ISO-aware PXE tool such as iVentoy
- repacking the Proxmox initrd with the installer ISO or required squashfs files
- using a tested netboot.xyz customization that does the same work

That is why iVentoy is the better first primary path if you want reliability
quickly.

## DHCP Choices

There are three common ways to point nodes at the PXE server:

- Router DHCP options: set next-server/option 66 to the Pi IP and boot
  filename/option 67 to the boot file.
- ProxyDHCP from dnsmasq: keep the router as DHCP server and let the Pi provide
  only PXE boot information.
- iVentoy DHCP: use iVentoy's built-in DHCP/PXE service for a small isolated
  recovery VLAN or maintenance network.

Do not run two normal DHCP servers on the same LAN unless one is deliberately
configured as ProxyDHCP.

For a limited ISP router, use ProxyDHCP on the Pi. The router continues giving
normal addresses, gateway, and DNS. The Pi answers only PXE boot requests with
the boot server and boot filename. The PXE client combines both answers during
the same boot attempt.

You normally cannot tell a standard firmware PXE client to fetch its bootloader
from an arbitrary IP without DHCP or ProxyDHCP. The practical exceptions are:

- some UEFI firmware supports manually configured HTTP Boot URLs
- an iPXE shell can manually run `chain http://...` commands after iPXE is
  already loaded
- AMT virtual media can boot a small iPXE ISO, then iPXE can fetch from the Pi

Those are useful fallbacks, but ProxyDHCP is the normal no-router-control
solution.

## Test Plan

Test in this order:

1. Confirm the Worker still serves answers:

       curl -X POST "https://pve-answer.bdev.uk/answer" \
         -H 'content-type: application/json' \
         --data '{"network_interfaces":[{"mac":"10:62:E5:00:17:8D"}]}'

2. PXE boot a disposable VM on the same LAN if possible.
3. PXE boot one physical node but stop at the boot menu.
4. Boot the automated ISO on a node only when its answer file has been reviewed.
5. Keep AMT virtual media available as the fallback if PXE breaks.

## Troubleshooting

If the node never sees PXE:

- confirm network boot is enabled in firmware
- confirm the node is on the same LAN/VLAN as the PXE service
- check `sudo journalctl -u dnsmasq -f` on the Pi
- check whether the router supports DHCP option 66/67 or whether ProxyDHCP is
  needed

If the boot file downloads but the installer is slow:

- move the Pi from Wi-Fi to USB Ethernet
- serve ISO files over HTTP, not TFTP
- consider running iVentoy on a faster x86_64 machine

If Proxmox boots but never requests the answer file:

- confirm the ISO was prepared with `proxmox-auto-install-assistant`
- confirm the boot command includes `proxmox-start-auto-installer`
- confirm the Worker URL was baked into the prepared ISO
- check whether the installer chose the wrong NIC on a multi-NIC host
