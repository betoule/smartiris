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

uint16_t duration_HB;
uint16_t duration_LB;
uint16_t timeHB;
uint8_t pin;

#define STOP_TIMER TCCR1B = 0b00000000
#define START_TIMER TCCR1B = 0b00000010

const uint8_t NFUNC = 2+1;
uint8_t narg[NFUNC];
// The exposed functions
void (*func[NFUNC])(uint8_t rb) =
  {// Communication protocol
   command_count,
   get_command_names,
   // user defined
   pulse,
  };

const char* command_names[NFUNC*3] =
  {"command_count", "", "B",
   "get_command_names", "BB", "s",
   // user defined
   "pulse", "BI", "I",
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
  // enable overflow and compare match A interupts
  TIMSK1 = 0b00000011; 

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

ISR(TIMER1_COMPA){
  if (timeHB == duration_HB){
    PINB = pin;
    STOP_TIMER;
  }
}

void loop(){
  client.serve_serial();
}

void pulse(uint8_t rb){
  pin = *((uint8_t *) (client.read_buffer+rb));
  if (pin > 5){
    client.snd((uint8_t*) &duration, 5, status=VALUE_ERROR);
    return
  }
  // Convert the pin number to bit positon
  pin = 1 << pin;
  // We receive the duration as timer count with a resolution of
  // 0.5e-6s
  uint32_t duration = *((uint32_t *) (client.read_buffer+rb+1));
  // Split that into a high and low resolution part
  OCR1A = duration & 0xFF;
  duration_HB = duration >> 16;
  // Reset the timer
  timeHB=0;
  TCNT1=0;
  START_TIMER;
  PORTB = pin;
  // Clear the interrupt vectors
  //CLEARINT;
  // Enable interrupt handling
  //ENABLEINT;
}


