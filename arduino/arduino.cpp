#include <Servo.h>

// --- CONFIGURATION ---
// The number of thrusters on your ROV.
const int NUM_THRUSTERS = 6;

// Define the Arduino pins connected to each ESC's signal wire.
// Make sure these match your physical wiring.
int escPins[NUM_THRUSTERS] = {3, 5, 6, 9, 10, 11}; // Example PWM pins

// --- GLOBALS ---
// Create an array of Servo objects to control the ESCs.
Servo thrusters[NUM_THRUSTERS];

// PWM values for neutral, min, and max throttle.
// 1500 microseconds is the standard for neutral/stop.
const int PWM_NEUTRAL = 1500;
const int PWM_MIN = 1100;
const int PWM_MAX = 1900;

// Buffer to store incoming serial data.
char serialBuffer[64];


void setup() {
  // Start serial communication for receiving data from the ROS 2 node.
  Serial.begin(115200);

  // --- VERY IMPORTANT: ESC ARMING SEQUENCE ---
  // This sequence ensures the ESCs recognize the neutral signal on startup.
  
  Serial.println("Attaching thrusters...");
  for (int i = 0; i < NUM_THRUSTERS; i++) {
    thrusters[i].attach(escPins[i]);
  }
  delay(10); // Short delay after attaching.

  Serial.println("Sending neutral arming signal to all ESCs...");
  for (int i = 0; i < NUM_THRUSTERS; i++) {
    // Use writeMicroseconds for precise control matching ROS script.
    thrusters[i].writeMicroseconds(PWM_NEUTRAL);
  }
  
  // Keep sending the neutral signal for 3 seconds to give ESCs
  // plenty of time to initialize and arm properly.
  Serial.println("Waiting for ESCs to arm (3 seconds)...");
  delay(3000); 
  
  Serial.println("Arming sequence complete. ROV is ready to receive commands.");
}


void loop() {
  // Check if there is data available to read from the serial port.
  if (Serial.available() > 0) {
    // Read the incoming data until a newline character is received.
    int bytesRead = Serial.readBytesUntil('\n', serialBuffer, sizeof(serialBuffer) - 1);
    
    // Add a null terminator to make it a valid C-string.
    serialBuffer[bytesRead] = '\0';
    
    // Parse the received string.
    parseAndSetPWM(serialBuffer);
  }
}

/**
 * @brief Parses a comma-separated string of PWM values and commands the thrusters.
 * @param pwmString The comma-separated string (e.g., "1500,1450,1550,1500,1500,1500").
 */
void parseAndSetPWM(char* pwmString) {
  // Use strtok to split the string by commas.
  char* token = strtok(pwmString, ",");
  int thrusterIndex = 0;
  
  while (token != NULL && thrusterIndex < NUM_THRUSTERS) {
    // Convert the token (string) to an integer.
    int pwmValue = atoi(token);
    
    // Constrain the PWM value to a safe range to prevent sending bad signals.
    pwmValue = constrain(pwmValue, PWM_MIN, PWM_MAX);
    
    // Write the final PWM value to the corresponding thruster.
    thrusters[thrusterIndex].writeMicroseconds(pwmValue);
    
    // Get the next token.
    token = strtok(NULL, ",");
    thrusterIndex++;
  }
  
  // Optional: For debugging, you can print a confirmation.
  // Be careful, as too much printing can slow down the loop.
  // if (thrusterIndex == NUM_THRUSTERS) {
  //   Serial.println("PWM values updated.");
  // }
}
