# === CONFIG ===
MCU       = atmega328p
F_CPU     = 16000000
PORT      = /dev/ttyUSB0  # Linux/macOS: ls /dev/tty* | grep USB
# PORT    = COM3          # Windows
BAUD      = 115200         # Bootloader baud: 57600 for the classic Nano
                            # bootloader, 115200 for Optiboot
PROGRAMMER = arduino       # or wiring, stk500v1

# Firmware version, kept in sync with the python package release.
VERSION  = $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
VWORD    = $(subst ., ,$(VERSION))

# === TOOLS ===
CC      = avr-g++
OBJCOPY = avr-objcopy
AVRDUDE = avrdude

# === FILES ===
# Objects and binaries are named after the hardware revision the build
# targets: main builds and flashes for v2 boards, flashv1 for the
# legacy v1 boards.
SOURCES = main.cpp bincoms.cpp

# === FLAGS ===
CFLAGS = -Os -g -mmcu=$(MCU) -DF_CPU=$(F_CPU)UL -Wall \
         -DFIRMWARE_VERSION_MAJOR=$(word 1,$(VWORD)) \
         -DFIRMWARE_VERSION_MINOR=$(word 2,$(VWORD)) \
         -DFIRMWARE_VERSION_PATCH=$(word 3,$(VWORD))
LDFLAGS = -mmcu=$(MCU)

# === RULES ===
all: main_2.hex

# Pattern rules parameterized by board revision ($* is 1 or 2)
main_%.o: main.cpp
	$(CC) $(CFLAGS) -DBOARD_VERSION=$* -c $< -o $@

bincoms_%.o: bincoms.cpp
	$(CC) $(CFLAGS) -DBOARD_VERSION=$* -c $< -o $@

main_%.elf: main_%.o bincoms_%.o
	$(CC) $(LDFLAGS) -o $@ $^

main_%.hex: main_%.elf
	$(OBJCOPY) -O ihex -R .eeprom $< $@

# Keep pattern built objects and elf files (make would otherwise delete
# them as intermediates, forcing a full rebuild each time)
.PRECIOUS: main_%.o bincoms_%.o main_%.elf

# Flash the current (v2) boards
flash: main_2.hex
	$(AVRDUDE) -F -D -V -c$(PROGRAMMER) -p$(MCU) -P $(PORT) -b$(BAUD) -U flash:w:$<

# Flash the legacy v1 boards
flashv1: main_1.hex
	$(AVRDUDE) -F -D -V -c$(PROGRAMMER) -p$(MCU) -P $(PORT) -b$(BAUD) -U flash:w:$<

clean:
	rm -f main_*.elf main_*.hex *.o

.PHONY: all flash flashv1 clean
