# === CONFIG ===
MCU       = atmega328p
F_CPU     = 16000000
PORT      = /dev/ttyUSB0  # Linux/macOS: ls /dev/tty* | grep USB
# PORT    = COM3          # Windows
BAUD      = 115200         # Bootloader baud: 57600 for the classic Nano
                            # bootloader, 115200 for Optiboot
PROGRAMMER = arduino       # or wiring, stk500v1

# === TOOLS ===
CC      = avr-g++
OBJCOPY = avr-objcopy
AVRDUDE = avrdude

# === FILES ===
TARGET  = main
SOURCES = main.cpp bincoms.cpp
OBJECTS = $(SOURCES:.cpp=.o)

# === FLAGS ===
CFLAGS = -Os -g -mmcu=$(MCU) -DF_CPU=$(F_CPU)UL -Wall
LDFLAGS = -mmcu=$(MCU)

# === RULES ===
all: $(TARGET).hex

$(TARGET).elf: $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

$(TARGET).hex: $(TARGET).elf
	$(OBJCOPY) -O ihex -R .eeprom $< $@

%.o: %.cpp
	$(CC) $(CFLAGS) -c $< -o $@

flash: $(TARGET).hex
	$(AVRDUDE) -F -D -V -c$(PROGRAMMER) -p$(MCU) -P $(PORT) -b$(BAUD) -U flash:w:$<

clean:
	rm -f $(TARGET).elf $(TARGET).hex *.o

.PHONY: all flash clean
