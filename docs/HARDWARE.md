# Nikon DS-Fi3: what is known about talking to it

Collected from public sources on 2026-11-12, **before the camera was ever
connected to a Linux machine**. Nothing here has been verified on hardware
yet. Each item is marked:

- **[source]** — stated by the linked page
- **[inferred]** — a conclusion drawn from sources, not stated anywhere
- **[unknown]** — looked for, not found

## Summary

There is no known way to drive the DS-Fi3 natively from Linux. Nikon's
SDK (`DSCam.dll`) is Windows-only, the camera is very probably not a standard
USB video device, and nobody has published the USB protocol. The first
plug-in on Linux settles the "is it a standard device" question in a minute:
run `tools/probe_camera.sh` and read the section [First plug-in](#first-plug-in).

## USB identity

| | |
|---|---|
| Vendor / product id | `04b0:7014` **[source]** — a third-party Windows driver database, not Nikon and not an `lsusb` dump: [treexy.com DS-Fi3](https://treexy.com/products/driver-fusion/database/imaging-and-cameras/nikon/ds-fi3/) |
| Windows driver | `dscamrev01.inf` v1.4.0.0 (2022-04-19) **[source]** same page |
| Sibling cameras, same INF | DS-Ri2 `7012`, DS-Qi2 `7013`, Digital Sight 10 `7016` **[source]** same database |
| USB device class | **[unknown]** — no descriptor dump is public |
| Standard class (UVC / PTP / USB3 Vision)? | Probably not **[inferred]**: Nikon ships its own "DS-Fi3 Camera Driver" ([Nikon firmware page](https://industry.nikon.com/en-gb/downloads/digital-sight-series-firmware-ds-fi3-ver1-10)); `04b0:7014` is not in the linux-usb `usb.ids` list and the kernel's `uvc_driver.c` has no Nikon quirk entry; libgphoto2, Aravis, python-microscope and Bio-Formats do not mention it; a DS-Qi2 was [not detected by NI MAX](https://forums.ni.com/t5/LabVIEW/Nikon-DS-Qi2/td-p/4348124) |
| USB controller | Likely a Cypress FX3 with bulk streaming **[inferred]** from a `wszFx3Version` field in the DS-Ri2/Qi2 SDK header ([KsCam.h](https://github.com/andrewgomella/NikonKsAdapter/blob/master/SDK/KsCam.h)) |

## Nikon's SDK

- Name: "DS-10-Fi3-Qi2-Ri2 SDK", library `DSCam.dll` (v3). The older v2 for
  DS-Ri2/Qi2 is called "KsCam". **[source]** [micro-manager.org/NikonKS](https://micro-manager.org/NikonKS),
  [PyNikonSciCam](https://github.com/JohanvdWesthuizen/PyNikonSciCam)
- Windows only. No Linux build was found. **[source]** both wrapper READMEs below / **[unknown]**
- Obtained through a developer account at `nisdk.recollective.com` plus an
  unzip password sent by e-mail; reported to take days. **[source]** same pages
- The kernel driver is not a public download ("ask a Nikon representative"). **[source]** micro-manager.org/NikonKS
- The SDK contains built-in simulated cameras, including "DS-Fi3(Sim)". **[source]** [laser-lab README](https://github.com/JedimasterLu/laser-lab)
- Call flow for live frames: `CAM_OpenDevices` → `CAM_Open` → `CAM_SetFeatures`
  → `CAM_Command(START_FRAMETRANSFER)` → `CAM_GetImage`. **[source]** laser-lab README, KsCam.h

The SDK is proprietary. Do not commit its DLLs or headers to this repository.

## Existing open-source code that drives a DS-Fi3

All of these call `DSCam.dll` on Windows. None has a licence file that GitHub
recognises — check before copying code.

| Project | What it is |
|---|---|
| [JohanvdWesthuizen/PyNikonSciCam](https://github.com/JohanvdWesthuizen/PyNikonSciCam) | Python `ctypes` wrapper; DS-Fi3 stills, RGB24 2880 × 2048 |
| [JedimasterLu/laser-lab](https://github.com/JedimasterLu/laser-lab) | Python `ctypes` wrapper (`NikonDSFi3Camera`) with continuous frame transfer; active in 2026-11 |
| [phenylshima/DSCam-rs](https://github.com/phenylshima/DSCam-rs) | Rust bindings |
| [micro-manager NikonKs adapter](https://github.com/micro-manager/mmCoreAndDevices/tree/main/DeviceAdapters/NikonKs) | Documented for DS-Ri2/Qi2 only; its device switch does not handle the Fi3 |

No report of any DS camera working on Linux, under Wine, in a VM with USB
passthrough or over usbip was found, and no USB-level reverse engineering of
any DS camera. **[unknown]**

## Camera specifications

From the [Nikon DS-Fi3 brochure](https://bioscience.fi/wp-content/uploads/2020/03/Nikon-DS-Fi3.pdf)
unless noted. The simulated camera (`camera/simulated.py`) follows these.

| | |
|---|---|
| Sensor | 1/1.8" colour CMOS, 6.91 × 4.92 mm, 5.9 MP |
| Full resolution | 2880 × 2048, up to 15 fps |
| Fast mode | 1440 × 1024 (2 × 2 average), up to 30 fps |
| SDK format modes | 1 = 2880 × 2048, 2 = 1440 × 1024 ROI, 3 = 1440 × 1024 averaged **[source]** PyNikonSciCam `constants.py` |
| Exposure | 100 µs – 30 s; the SDK unit is microseconds |
| Gain | ISO 50 – 3200 equivalent (a 64× span); SDK value range **[unknown]**, observed default 100 |
| Auto exposure | continuous, one-push, manual; average or peak metering; ±1 EV in 1/6 steps |
| Trigger | one external input; SDK modes Off / Hard / Soft |
| Pixel formats in the SDK | RGB24, YUV444, Mono16, RGB48, Y16, Raw16 **[source]** `constants.py` |
| Bit depth | **[unknown]** — query at runtime |
| Pixel pitch | ≈ 2.4 µm **[inferred]** (6.91 mm / 2880) |
| Bayer pattern order | **[unknown]** |

## Options for a real backend

| # | Route | Runs on Linux? | Confidence | Cost |
|---|---|---|---|---|
| 1 | `ctypes` backend over `DSCam.dll`, used directly on Windows | No | High — two independent wrappers do exactly this | Needs the Nikon SDK; small amount of code |
| 2 | Route 1 inside a Windows VM (KVM/QEMU, USB 3 passthrough of `04b0:7014`) or on a small Windows box, serving frames over TCP to the Linux GUI | Yes (GUI) | Medium — passthrough is untested for this camera | Route 1 plus a frame server and a `remote` backend; needs a Windows licence |
| 3 | Native `libusb` backend, protocol reverse-engineered from USBPcap captures of the Nikon software on Windows | Yes, fully | Low to medium | Weeks; needs a working Windows setup for the captures anyway; may need a firmware upload step |
| 4 | It turns out to be UVC / USB3 Vision / PTP after all | Yes | Very low (< 5 %) | Almost free — the probe script tells |
| 5 | `DSCam.dll` under Wine | — | Very low: the DLL needs Nikon's kernel driver | — |

Routes 1 and 2 share the `DSCam.dll` backend, and route 1 is also the
Windows support that is planned anyway. Route 3 is the only one that ends
with no Windows in the loop.

## First plug-in

Run `tools/probe_camera.sh` (ideally with `sudo`) and look at
`probe-output/<timestamp>/`:

1. **`lsusb.txt`** — is there a `04b0:7014` device? If instead (or first) a
   `04b4:00f3` Cypress device appears, the camera needs a firmware upload
   from the host before it becomes a Nikon device (bad news for route 3,
   but doable).
2. **`sysfs-nikon.txt`** — `bInterfaceClass` of each interface:
   `0e` = UVC (route 4, a `/dev/video*` should exist — check
   `v4l2-*.txt`), `06` = PTP/still image (try gphoto2), `ef` with
   subclass `05` = USB3 Vision (try Aravis), `ff` = vendor specific (routes
   1–3). Also note the endpoint types (bulk vs. isochronous) and `speed`
   (5000 = USB 3).
3. **`kernel-log.txt`** — which driver bound, any firmware requests, any
   re-enumeration.

Paste the interface/endpoint summary (without the serial number) into this
file under a new "Observed on hardware" heading and replace the **[unknown]**
items above.

For route 3, the matching observations from Windows are: the `.sys` file
behind `dscamrev01.inf` (Device Manager → driver details), a descriptor dump
from USBTreeView, and a USBPcap/Wireshark capture of: open camera, ~10 live
frames, one exposure change, one still.
