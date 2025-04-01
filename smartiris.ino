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

/* The main fonction of the API. Send a pulse of a given duration on
   the given line.
 */ 
void program_pulse(uint8_t rb);
void start_program(uint8_t rb);
void stop_program(uint8_t rb);
void get_program(uint8_t rb);
void status(uint8_t rb);

uint32_t duration = 29;
uint16_t duration_HB;
uint16_t duration_LB;
uint16_t timeHB;
uint8_t pin;

// The number of programmable events
const uint8_t MAX_N_EVENTS=4;
uint8_t n_events;
uint8_t event;
uint8_t pin_array[MAX_N_EVENTS];
uint16_t LB_array[MAX_N_EVENTS];
uint16_t HB_array[MAX_N_EVENTS];

#define STOP_TIMER TCCR1B = 0b00000000
#define START_TIMER TCCR1B = 0b00000010
// enable overflow and compare match A interupts
#define ENABLE_INT TIMSK1 = 0b00000011
#define ENABLE_INTB TIMSK1 = 0b00000101
#define DISABLE_INT TIMSK1 = 0b00000000
#define CLEAR_INT TIFR1 = _BV(OCF1A)

const uint8_t NFUNC = 2+5;
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
  };

const char* command_names[NFUNC*3] =
  {"command_count", "", "B",
   "get_command_names", "BB", "s",
   // user defined
   "program_pulse", "BBI", "I",
   "start_program", "", "",
   "stop_program", "", "",
   "get_program", "B", "IB",
   "raw_status", "", "BBBB",
  };


void setup(){
  // Setup fast binary remote procedure call library
  setup_bincom();

  // Nano assignments
  // PORTB dedicated to outputs, PORTD to inputs

  // PORTB setup for output on arduino pin 8-13 (PB0 - PB5)
  DDRB   = _BV(PB0) | _BV(PB1) | _BV(PB2) | _BV(PB3) | _BV(PB4)| _BV(PB5);
  PORTB  = ~(_BV(PB0) | _BV(PB1) | _BV(PB2) | _BV(PB3) | _BV(PB4)| _BV(PB5));
  
  // PORTD PIN D2 and D3 
  PCMSK0 = 0b00000000;
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

// Timer Interruption handling
ISR(TIMER1_COMPA_vect){
  // Emulate 32 bit resolution by executing the code only if the high
  // bytes of the timer counter also match. The additionnal 16 bit
  // comparison adds a small (but constant) delay to the pin change.
  if (timeHB == HB_array[event-1]){
    PINB = pin_array[event-1];
    if (event == n_events){
      STOP_TIMER;
      DISABLE_INT;
      event = 0;
    }
    else{
      OCR1A = LB_array[event];
      event++;
    }
  }
}

void loop(){
  client.serve_serial();
}

void program_pulse(uint8_t rb){
  /* Program one slot of the pulse program
   *
   * The function reads 3 arguments from the communication buffer:
   * pin: the pin to switch between 0 and 5 (Byte)
   * n_events: (Byte) the slot number in the program between 0 and MAX_N_EVENTS - 1
   * duration: (int) the timing of the switch in counts since the launch of the program. A count as a value of 0.5e-6 seconds.
   */
  pin = *((uint8_t *) (client.read_buffer + rb));
  n_events = *((uint8_t *) (client.read_buffer + rb+1));
  // We receive the duration as timer count with a resolution of
  // 0.5e-6s
  duration = *((uint32_t *) (client.read_buffer + rb + 2));
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
  pin_array[n_events] = 1 << pin;

  // set up the timings
  LB_array[n_events] = duration & 0xFFFF;
  HB_array[n_events] = duration >> 16;
  n_events++;
}

void get_program(uint8_t rb){
  /* Query a slot of the pulse program
   *
   * The function reads 1 arguments from the communication buffer:
   * i: (Byte) the slot number in the program between 0 and MAX_N_EVENTS - 1
   *
   * It returns 2 values to the communication buffer:
   * duration: (Int) the timing of the pulse in slot i (in counts)
   * pin: (Byte) the index of the pin switched in the PORTB
   */
  uint8_t data[5];
  uint8_t i = *((uint8_t *) (client.read_buffer + rb));
  duration = HB_array[i];
  duration <<= 16;
  duration += LB_array[i];
  *((uint32_t*)(data)) = duration;
  data[4] = pin_array[i];
  client.snd((uint8_t*) data, 5, STATUS_OK);
}

void start_program(uint8_t rb){
  /* Start the execution of the pulse program
   */
  event = 1;
  
  // Split that into a high and low resolution part
  OCR1A = LB_array[0];

  // Reset the timer
  timeHB=0;
  TCNT1=0;
  CLEAR_INT;
  ENABLE_INT;
  START_TIMER;
  client.sndstatus(STATUS_OK);
}

void stop_program(uint8_t rb){
  /* Stop the program exectution
   */
  STOP_TIMER;
  DISABLE_INT;
  event = 0;
  PORTB = 0;
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
   */
  uint8_t data[4];
  data[0] = PINB;
  data[1] = PIND;
  data[2] = event;
  data[3] = n_events;
  client.snd((uint8_t*) &data, 4, STATUS_OK);
}
