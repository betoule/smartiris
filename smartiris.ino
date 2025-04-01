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
void pulse(uint8_t rb);
void program_pulse(uint8_t rb);
void start_program(uint8_t rb);
void get_program(uint8_t rb);
void get_event(uint8_t rb);

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
   pulse,
   program_pulse,
   start_program,
   get_program,
   get_event,
  };

const char* command_names[NFUNC*3] =
  {"command_count", "", "B",
   "get_command_names", "BB", "s",
   // user defined
   "pulse", "BI", "I",
   "program_pulse", "BBI", "I",
   "start_program", "", "",
   "get_program", "B", "IB",
   "get_event", "", "B",
   //"enable_line", "Bc", "",
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

/*
ISR(TIMER1_COMPA_vect){
  if (timeHB == duration_HB){
    PINB = pin;
    STOP_TIMER;
    DISABLE_INT;
  }
}

ISR(TIMER1_COMPB_vect){
  if (timeHB == HB_array[event]){
    PINB = pin_array[event];
    event++;
    if (event == n_events){
      STOP_TIMER;
      DISABLE_INT;
      event = 0;
    }
    else
      OCR1B = LB_array[event];
  }
}
*/

ISR(TIMER1_COMPA_vect){
  if (timeHB == HB_array[event]){
    PINB = pin_array[event];
    event++;
    if (event == n_events){
      STOP_TIMER;
      DISABLE_INT;
      event = 0;
    }
    else
      OCR1A = LB_array[event];
  }
}

void loop(){
  client.serve_serial();
}

void pulse(uint8_t rb){
  pin = *((uint8_t *) (client.read_buffer+rb));
  // We receive the duration as timer count with a resolution of
  // 0.5e-6s
  duration = *((uint32_t *) (client.read_buffer+rb+1));
  if (pin > 5){
    client.snd((uint8_t*) &duration, 4, VALUE_ERROR);
    return;
  }
  else
    client.snd((uint8_t*) &duration, 4);
  // Convert the pin number to bit positon
  pin = 1 << pin;
  // Split that into a high and low resolution part
  OCR1A = duration & 0xFFFF;
  duration_HB = duration >> 16;
  // Reset the timer
  timeHB=0;
  TCNT1=0;
  CLEAR_INT;
  ENABLE_INT;
  START_TIMER;
  PINB = pin;
  //client.snd((uint8_t*) &duration, 4);
  // Clear the interrupt vectors
  //CLEARINT;
  // Enable interrupt handling
  //ENABLEINT;
}

void program_pulse(uint8_t rb){
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
  event = 0;
  
  // Split that into a high and low resolution part
  //OCR1B = LB_array[event];
  OCR1A = LB_array[event];

  // Reset the timer
  timeHB=0;
  TCNT1=0;
  CLEAR_INT;
  ENABLE_INT;
  START_TIMER;
  client.sndstatus(STATUS_OK);
}

void get_event(uint8_t rb){
  client.snd((uint8_t*) &event, 1, STATUS_OK);
}
