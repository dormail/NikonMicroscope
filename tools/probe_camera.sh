#!/usr/bin/env bash
# Collect everything needed to decide how to talk to the camera on Linux.
#
# Plug the DS-Fi3 into a USB 3 port, switch it on, wait ~10 s and run:
#
#     tools/probe_camera.sh          (or: sudo tools/probe_camera.sh)
#
# Output goes to probe-output/<timestamp>/ (git-ignored: it contains serial
# numbers). Nothing is changed on the system. With sudo the USB descriptors
# and the kernel log are complete; without it some sections may be cut short.
#
# How to read the result is explained in docs/HARDWARE.md.

set -u

NIKON_VID="04b0"
# Cypress FX3 in bootloader mode. If the camera shows up as this first and
# re-enumerates as 04b0:xxxx later, the host has to upload firmware to it.
FX3_BOOTLOADER="04b4:00f3"
out="probe-output/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$out"

run() { # run <output-file> <command...>
    local file="$out/$1"
    shift
    {
        echo "\$ $*"
        "$@" 2>&1
        echo "[exit status $?]"
    } >"$file"
}

have() { command -v "$1" >/dev/null 2>&1; }

run system.txt uname -a
cat /etc/os-release >>"$out/system.txt" 2>&1

run lsusb.txt lsusb
run lsusb-tree.txt lsusb -t
# Full descriptors of every Nikon device: interface class tells us whether the
# camera is UVC (class 0x0e), PTP/still image (0x06) or vendor specific (0xff),
# and the endpoint list tells us bulk vs. isochronous transfer.
run lsusb-nikon-verbose.txt lsusb -v -d "${NIKON_VID}:"

# The same information straight from sysfs (works without lsusb / sudo).
{
    for dev in /sys/bus/usb/devices/*; do
        [ -f "$dev/idVendor" ] || continue
        [ "$(cat "$dev/idVendor")" = "$NIKON_VID" ] || continue
        echo "== $dev"
        for attr in idVendor idProduct bcdDevice manufacturer product serial speed version \
            bDeviceClass bDeviceSubClass bDeviceProtocol bNumConfigurations bNumInterfaces; do
            [ -f "$dev/$attr" ] && echo "$attr: $(cat "$dev/$attr")"
        done
        for intf in "$dev":*; do
            [ -d "$intf" ] || continue
            echo "-- interface $(basename "$intf")"
            for attr in bInterfaceClass bInterfaceSubClass bInterfaceProtocol bNumEndpoints interface; do
                [ -f "$intf/$attr" ] && echo "   $attr: $(cat "$intf/$attr")"
            done
            if [ -e "$intf/driver" ]; then
                echo "   driver: $(basename "$(readlink -f "$intf/driver")")"
            else
                echo "   driver: (none bound)"
            fi
            for ep in "$intf"/ep_*; do
                [ -d "$ep" ] || continue
                echo "   $(basename "$ep"): type=$(cat "$ep/type") dir=$(cat "$ep/direction")" \
                    "maxpacket=$(cat "$ep/wMaxPacketSize") interval=$(cat "$ep/interval")"
            done
        done
    done
} >"$out/sysfs-nikon.txt" 2>&1

# Kernel messages around the plug-in event (firmware requests, driver binding).
if have journalctl; then
    run kernel-log.txt journalctl -k -b --no-pager -n 300
else
    run kernel-log.txt dmesg
fi

# Did a standard driver claim it?
if have v4l2-ctl; then
    run v4l2-devices.txt v4l2-ctl --list-devices
    for node in /dev/video*; do
        [ -e "$node" ] || continue
        run "v4l2-$(basename "$node").txt" v4l2-ctl -d "$node" --all --list-formats-ext
    done
else
    echo "v4l2-ctl not installed (sudo apt install v4l-utils)" >"$out/v4l2-devices.txt"
fi
ls -l /dev/video* >"$out/dev-video.txt" 2>&1

if have gphoto2; then
    run gphoto2.txt gphoto2 --auto-detect
fi

# USB3 Vision / GenICam cameras show up here (sudo apt install aravis-tools).
for tool in arv-tool-0.10 arv-tool-0.8; do
    if have "$tool"; then
        run aravis.txt "$tool"
        break
    fi
done

# udev's view of each Nikon device (attributes usable in a udev rule later).
for dev in /sys/bus/usb/devices/*; do
    [ -f "$dev/idVendor" ] && [ "$(cat "$dev/idVendor")" = "$NIKON_VID" ] || continue
    run "udev-$(basename "$dev").txt" udevadm info -a -p "$dev"
done

if grep -qi "ID ${FX3_BOOTLOADER}" "$out/lsusb.txt"; then
    echo "NOTE: a Cypress FX3 bootloader (${FX3_BOOTLOADER}) is present: the camera is waiting" \
        "for a firmware upload from the host." | tee "$out/NOTE-fx3-bootloader.txt"
fi

if ! grep -qi "ID ${NIKON_VID}:" "$out/lsusb.txt"; then
    echo "WARNING: no USB device with Nikon vendor id ${NIKON_VID} found." | tee "$out/WARNING.txt"
    echo "Check cable, power, and that the port is USB 3. Other vendors' ids are in $out/lsusb.txt."
fi

echo "Probe written to $out/"
echo "Start with: $out/sysfs-nikon.txt and $out/lsusb-nikon-verbose.txt"
