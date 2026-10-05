Write the firmware for a USB gamepad in Rust. Ask nothing; where a fact below is marked UNKNOWN, implement the stated
safe behaviour and make the value a constant.

Hardware: Microchip ATmega32U4-AU (TQFP-44), 16 MHz crystal, 5 V from USB-C (VBUS through a 500 mA PTC), native USB
2.0 full speed. No other supply. Factory DFU bootloader in the boot section; HWB (PE2) is pulled to GND, so an
external reset (reset button) starts the bootloader, power-on starts the application, provided the HWBE fuse is
programmed as on parts shipped with the DFU bootloader (UNKNOWN for a given batch: if the reset button starts the
application instead, report it).

Pins (MCU pin / port / function / notes):
- 8 PB0 UP, 9 PB1 DOWN, 10 PB2 LEFT, 11 PB3 RIGHT (D-pad); 30 PB6 A, 29 PB5 B, 28 PB4 X, 27 PD7 Y; 18 PD0 START,
  19 PD1 SELECT. Buttons close to GND: inputs with internal pull-up, pressed = low.
- 31 PC6 LED P1, 32 PC7 LED P2, 26 PD6 LED ST: outputs, high = on, 3 mA each through 1 k.
- 3 D-, 4 D+ (22 Ohm series), 6 UCAP (1 uF), 7 VBUS: USB, handled by the USB controller.
- All unused pins (PE6, PB7, PD2, PD3, PD4, PD5, PF0, PF1, PF4 ... PF7, AREF): inputs with pull-up.
- PB1 ... PB3 double as the ISP lines (SCK, MOSI, MISO); never drive them as outputs.

Behaviour:
- Start: set the clock prescaler to 1 (CLKPR) regardless of the CKDIV8 fuse, start the USB PLL for the 16 MHz crystal,
  enable the watchdog (250 ms).
- USB HID gamepad: VID/PID constants (use the pid.codes test ID 1209:0001 until a real one is assigned), product
  string "USB gamepad", report every 1 ms (interval 1): 8 buttons A, B, X, Y, START, SELECT plus a hat switch from
  the D-pad (opposite directions pressed together count as neither). Report descriptor as a standard gamepad that
  Windows, Linux and macOS accept without a driver.
- Debounce: a change counts after 5 ms stable.
- LEDs: P1 on while enumerated and configured; P2 free for the host (output report, optional); ST blinks 2 Hz while
  not configured, off when configured.
- USB current: declare 50 mA in the configuration descriptor (real draw is below 30 mA).

Software: Rust nightly with the avr-atmega32u4 target (`-Zbuild-std=core`), avr-device and avr-hal (atmega-hal), USB
through the usb-device crate with atmega-usbd as the bus driver and usbd-hid for the report. Pin the crate versions.
Output an Intel HEX for the DFU bootloader. If the Rust USB stack does not enumerate reliably, report it with the
log of what was tried instead of switching to another language.

Acceptance tests: host-side unit tests for debounce and the D-pad to hat conversion; a written manual test: the
device enumerates as a gamepad on Windows and Linux (`evtest` / joy.cpl), every button maps to the right control,
P1 lights when configured, unplug/replug ten times without a hang.
