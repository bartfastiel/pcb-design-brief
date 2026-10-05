Hardware: PC (Windows, macOS or Linux), USB-C cable, a paper clip for the reset hole in the bottom of the case.
Software: rustup with the nightly toolchain and `rust-src`, avr-gcc (linker), dfu-programmer. Windows: install the
libusb driver for the "ATm32U4DFU" device once with Zadig.
1. Build: `cargo build --release`, then `avr-objcopy -O ihex target/avr-atmega32u4/release/gamepad.elf gamepad.hex`.
2. Plug in USB-C, press the reset button through the hole in the bottom: the bootloader enumerates as ATm32U4DFU.
3. `dfu-programmer atmega32u4 erase`, then `dfu-programmer atmega32u4 flash gamepad.hex`.
4. `dfu-programmer atmega32u4 launch` (or unplug and plug in): the gamepad enumerates, LED P1 lights.
5. Check in the system's game-controller dialog (Windows joy.cpl, Linux evtest) that every button reacts.
6. Recovery: the bootloader cannot be erased over DFU. If it ever is, program it with an ISP programmer: SCK, MOSI,
   MISO on the DOWN, LEFT and RIGHT button pads, RESET on test point TP6, 5 V and GND on TP2 and TP3.
