// Copyright 2024 Marc Betoule
// 
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, version 2 of the License.
// 
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

#include <Arduino.h>
#include "bincoms.h"
#include <EEPROM.h>

/* The main fonction of the API. Send a pulse of a given duration on
   the given line.
 */ 
void program_pulse(uint8_t rb);
void start_program(uint8_t rb);
void stop_program(uint8_t rb);
void get_program(uint8_t rb);
void status(uint8_t rb);
void set_interrupt_mask(uint8_t rb);
void start_timer(uint8_t rb);
void get_time(uint8_t rb);
void get_clock_calibration(uint8_t rb);
void set_clock_calibration(uint8_t rb);
void switch_button();

uint32_t duration;
uint16_t duration_HB;
uint16_t duration_LB;
uint16_t timeHB;
uint8_t pin;

// The maximum number of programmable control pin changes
const uint8_t MAX_N_EVENTS=16;
// The maximum number of recordable events
const uint8_t MAX_N_RECORDS=16; 

uint8_t n_events;
uint8_t event = 0;
typedef struct {
  uint16_t time_LB;
  uint16_t time_HB;
  uint8_t pin;
} Event;

Event * active_program;
uint8_t active_nevent;

// This store the program
Event program[MAX_N_EVENTS];

// Those are 4 builtin programs to open and close the two shutters when the button are activated
Event OpenA[2] = {{20000, 0x0, 0b10}, {14464, 1, 0b10}};
Event CloseA[2] = {{20000, 0x0, 0b1}, {14464, 1, 0b1}};
Event OpenB[2] = {{20000, 0x0, 0b1000}, {14464, 1, 0b1000}};
Event CloseB[2] = {{20000, 0x0, 0b100}, {14464, 1, 0b100}};

// To record sensor event timings
Event sensor_timing_record[MAX_N_RECORDS];
uint8_t n_record = 0;

// Generic record interrupt handler. This interrupt handler need to
// handle timing rollover internally because it could mask the overflow
// interrupt and record incorrect timing because of that.
#define INTERRUPT_HANDLER(line)                                    \
  sensor_timing_record[n_record].time_LB = TCNT1;                   \
  if ((TIFR1 & 0b1) && (sensor_timing_record[n_record].time_LB < 10)){\
    timeHB++;							   \
    TIFR1 |= _BV(TOV1);						   \
  }								   \
  sensor_timing_record[n_record].pin = line;			   \
  sensor_timing_record[n_record].time_HB = timeHB;                  \
  if (n_record < MAX_N_RECORDS - 1) n_record++;                    \
  
// Macros to start and stop the 16-bit timer
#define STOP_TIMER TCCR1B = 0b00000000
#define START_TIMER TCCR1B = 0b00000010
// enable overflow and compare match A interupts on the 16 bit timer
#define ENABLE_INT TIMSK1 = 0b00000011
// Disable overflow and compare interrupts on the 16bit timer
#define DISABLE_INT TIMSK1 = 0b00000000
#define CLEAR_INT TIFR1 = _BV(OCF1A)

const uint8_t NFUNC = 2+10;
uint8_t narg[NFUNC];
// The exposed functions
void (*func[NFUNC])(uint8_t rb) =
  {// Communication protocol
   command_count,
   get_command_names,
   // user defined
   program_pulse,
   start_program,
   stop_program,
   get_program,
   status,
   set_interrupt_mask,
   start_timer,
   get_time,
   get_clock_calibration,
   set_clock_calibration,
  };

const char* command_names[NFUNC*3] =
  {"command_count", "", "B",
   "get_command_names", "BB", "s",
   // user defined
   "program_pulse", "BBI", "I",
   "start_program", "", "",
   "stop_program", "", "",
   "get_program", "BB", "IB",
   "raw_status", "", "BBBBB",
   "_set_interrupt_mask", "B", "",
   "_start_timer", "", "",
   "get_time", "", "I",
   "get_clock_calibration", "", "f",
   "set_clock_calibration", "f", "",
  };


void setup(){
  // Setup fast binary remote procedure call library
  setup_bincom();

  // Nano assignments
  // PORTB dedicated to outputs, PORTD to inputs

  // PORTB setup for output on arduino pin 8-13 (PB0 - PB5)
  DDRB   = _BV(PB0) | _BV(PB1) | _BV(PB2) | _BV(PB3) | _BV(PB4)| _BV(PB5);
  PORTB  = ~(_BV(PB0) | _BV(PB1) | _BV(PB2) | _BV(PB3) | _BV(PB4)| _BV(PB5));
  
  // PORTD used as input:
  // PD2/3 shutter detection line
  // PD4 free (for TTL ?)
  // PD5/6 button detection (PCINT21/22)
  // PD7 /sleep
  // setup for inputs
  DDRD &= ~(_BV(PD2) | _BV(PD3) | _BV(PD4) | _BV(5) | _BV(PD6));
  // Pull-up
  PORTD = (_BV(PD2) | _BV(PD3) | _BV(PD4) | _BV(5) | _BV(PD6));
  // Button detection
  PCMSK2 = _BV(PCINT21) | _BV(PCINT22);
  PCMSK0 = 0b00000000;
  PCICR = _BV(PCIE2);
  // Setup external interrupt as pin change interrupt for arduino pin D2 and D3
  EICRA = 0b0101;
  // Setup external interrupt rise for arduino pin 2 and 3 (INT0 and INT1)
  //EICRA |= _BV(ISC11) | _BV(ISC10) | _BV(ISC01) | _BV(ISC00);  
  //SET_TIMER1_CLOCK(TIMER_CLOCK_1);
  // 16-bit TIMER1 settings
  // This timer is used to follow the clock count
  // TCCR1A: COM1A1:COM1A0:COM1B1:COM1B0:0:0:WGM11:WGM10
  // TCCR1B: ICNC1:ICES1:0:WGM13:WGM12:CS12:CS11:CS10
  // TIMSK1: 0:0:ICIE1:0:0:OCIE1B:OCIE1A:TOIE1
  // COM1A: 0b01 toggle on compare match
  // COM1B: 0b01 toggle on compare match
  // WGM: 0b0100 CTC
  // WGM: 0b0000 Normal
  // CS1: 0b000 STOP
  TCCR1A = 0b00000000;
  STOP_TIMER;
  DISABLE_INT;
  
  // We disable the awful clock of the arduino IDE
  TCCR0B = 0b0;
  TIMSK0 = 0b0;
  TCCR2B = 0b0;
  TIMSK2 = 0b0;
  EIMSK = 0b0;
}



// Update high bytes of the timer counter
ISR(TIMER1_OVF_vect){
  timeHB++;
}

void _stop_program(){
  STOP_TIMER;
  DISABLE_INT;
  EIMSK = 0b0;
  event = 0;
  PORTB = 0;
}

// Timer Interruption handling
ISR(TIMER1_COMPA_vect){
  // Emulate 32 bit resolution by executing the code only if the high
  // bytes of the timer counter also match. The additionnal 16 bit
  // comparison adds a small (but constant) delay to the pin change.
  if (timeHB == active_program[event-1].time_HB){
    PINB = active_program[event-1].pin;
    if (event == active_nevent){
      _stop_program();
    }
    else{
      OCR1A = active_program[event].time_LB;
      event++;
    }
  }
}


// Button activation handling
ISR(PCINT2_vect){
  //PINB = _BV(PB5);
  switch_button();
}

// sensor detection on arduino pin D2
ISR(INT0_vect){
  INTERRUPT_HANDLER(0b1)
}
// sensor detection on arduino pin D3
ISR(INT1_vect){
  INTERRUPT_HANDLER(0b10)
}

void loop(){
  // This shunt the arduino loop
  client.serve_serial();
}

void set_interrupt_mask(uint8_t rb){
  /* This function can be used to enable/disable the button interrupt
   *
   * The function read the mask as 1 uint8_t argument from the communication buffer:
   */
    PCMSK2 = *((uint8_t *) (client.read_buffer + rb));
    client.sndstatus(STATUS_OK);
}

void program_pulse(uint8_t rb){
  /* Program one slot of the pulse program
   *
   * The function reads 3 arguments from the communication buffer:
   * pin: the pin to switch between 0 and 5 (Byte)
   * n_events: (Byte) the slot number in the program between 0 and MAX_N_EVENTS - 1
   * duration: (int) the timing of the switch in counts since the launch of the program. A count as a value of 0.5e-6 seconds.
   */
  client.readn(&rb, &pin, 1);
  client.readn(&rb, &n_events, 1);
  // We receive the duration as timer count with a resolution of
  // 0.5e-6s
  client.readn(&rb, (uint8_t*) &duration, 4);
  //pin = *((uint8_t *) (client.read_buffer + rb));
  //n_events = *((uint8_t *) (client.read_buffer + rb+1));
  //duration = *((uint32_t *) (client.read_buffer + rb + 2));
  if (n_events >= MAX_N_EVENTS){
    client.snd((uint8_t*) &duration, 4, VALUE_ERROR);
    return;
  }
  if (pin > 5){
    client.snd((uint8_t*) &duration, 4, VALUE_ERROR);
    return;
  } 
  else
    client.snd((uint8_t*) &duration, 4);

  // set up the pin sequence
  // Converting the pin number to bit positon
  program[n_events].pin = 1 << pin;

  // set up the timings
  program[n_events].time_LB = duration & 0xFFFF;
  program[n_events].time_HB = duration >> 16;
  n_events++;
}

void get_program(uint8_t rb){
  /* Query a slot of the pulse program
   *
   * The function reads 2 arguments from the communication buffer:
   * i: (Byte) the slot number in the program between 0 and MAX_N_EVENTS - 1
   * p: (Byte) the index of the program to read
   * It returns 2 values to the communication buffer:
   * duration: (Int) the timing of the pulse in slot i (in counts)
   * pin: (Byte) the index of the pin switched in the PORTB
   */
  uint8_t data[5];
  uint8_t i = *((uint8_t *) (client.read_buffer + rb));
  uint8_t program_num = *((uint8_t *) (client.read_buffer + (rb + 1)));
  Event * program_slot;
  if (program_num == 1)
    program_slot = sensor_timing_record;
  else
    program_slot = program;
  duration = program_slot[i].time_HB;
  duration <<= 16;
  duration += program_slot[i].time_LB;
  *((uint32_t*)(data)) = duration;
  data[4] = program_slot[i].pin;
  client.snd((uint8_t*) data, 5, STATUS_OK);
}

void _start_program(){
  // Split that into a high and low resolution part
  OCR1A = active_program[0].time_LB;

  // Reset the timer
  timeHB=0;
  TCNT1=0;
  CLEAR_INT;
  n_record=0;
  EIMSK = 0b11;
  ENABLE_INT;
  START_TIMER;
}

void start_program(uint8_t rb){
  /* Start the execution of the pulse program
   */
  event = 1;
  active_program = program;
  active_nevent = n_events;
  _start_program();
  client.sndstatus(STATUS_OK);
}

void start_timer(uint8_t rb){
  /* Start the timer execution without program
    (Usually used for clock calibration purpose)
   */
  _stop_program();
  // Reset the timer
  timeHB=0;
  TCNT1=0;
  CLEAR_INT;
  // Enable timer overflow but not the other instructions
  TIMSK1 = 0b00000001;
  START_TIMER;
  client.sndstatus(STATUS_OK);
}

void get_time(uint8_t rb){
  duration = timeHB;
  duration <<= 16;
  duration += TCNT1;
  client.snd((uint8_t*) &duration, 4, STATUS_OK);
}

void stop_program(uint8_t rb){
  /* Stop the program exectution
   */
  _stop_program();
  client.sndstatus(STATUS_OK);
}

void status(uint8_t rb){
  /* Return the status of device
   *
   * The function return 4 bytes to communication buffer:
   * PINB the state of the 8 GPIO pins in Port B
   * PIND the state of the 8 GPIO pins in Port D
   * event the current index of the slot in program
   * n_events the length of the program
   * the number of recorded events
   */
  uint8_t data[5];
  data[0] = PINB;
  data[1] = PIND;
  data[2] = event;
  //data[3] = n_events;
  data[3] = active_nevent;
  data[4] = n_record;
  client.snd((uint8_t*) &data, 5, STATUS_OK);
}

void get_clock_calibration(uint8_t rb){
  float calibration_constant = 2e6;
  EEPROM.get(0, calibration_constant);
  client.snd((uint8_t*) &calibration_constant, 4, STATUS_OK);
}

void set_clock_calibration(uint8_t rb){
  float calibration_constant = 2e6;
  client.readn(&rb, (uint8_t*) &calibration_constant, 4);
  EEPROM.put(0, calibration_constant);
  client.sndstatus(STATUS_OK);
}


void switch_button(){
  //if (event == 0){
  _stop_program();
  if (!(PIND & 0b100000)){//buttonA
    if (PIND & 0b100) //closed
      {
	event = 1;
	active_program = OpenA;
	active_nevent = 2;
	_start_program();
      }
    else
      {
	event = 1;
	active_program = CloseA;
	active_nevent = 2;
	_start_program();
      }
  }
  else if (!(PIND & 0b1000000)){//buttonB
    if (PIND & 0b1000) //closed
      {
	event = 1;
	active_program = OpenB;
	active_nevent = 2;
	_start_program();
      }
    else
      {
	event = 1;
	active_program = CloseB;
	active_nevent = 2;
	_start_program();
      }
  }
}
