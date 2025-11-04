#include <AccelStepper.h>

// Pin configuration (adjust as needed)
const int X_STEP_PIN = 2;
const int X_DIR_PIN  = 5;
const int Z_STEP_PIN = 3;
const int Z_DIR_PIN  = 6;
const int EN_PIN     = -1; // set to a valid pin if using enable

// Steps per unit calibration (edit to match mechanics)
volatile float steps_per_unit_x = 80.0f;   // e.g., GT2 20T pulley at 16 microsteps with 200 steps/rev -> 200*16 / (20*2*pi) ~ 25.5; use your value
volatile float steps_per_unit_z = 400.0f;  // example for leadscrew; adjust

AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperZ(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

// Motion state
volatile bool running = false;      // currently executing a move (low-level)
volatile bool stop_requested = false;

// Program representation
struct OscilBlock {
  char axis;        // 'X' or 'Z'
  long neg_steps;   // steps for negative direction (executed first)
  long pos_steps;   // steps for positive direction (executed second)
  float speed;      // steps/s (positive)
  long rep;         // number of cycles; -1 means infinite
};

const int MAX_BLOCKS = 32;  // Increased from 16 (safe for Uno's 2KB SRAM)
OscilBlock programBlocks[MAX_BLOCKS];
int programLen = 0;
bool programLoop = true;  // whether to loop the whole program
bool programLoaded = false;

// Execution state
int currentBlock = 0;
long currentCycleRemaining = 0; // remaining cycles for current block (-1 for infinite)
bool phasePositive = false;      // false => executing negative move; true => positive move

void setup() {
  if (EN_PIN >= 0) {
    pinMode(EN_PIN, OUTPUT);
    digitalWrite(EN_PIN, LOW); // enable
  }
  Serial.begin(115200);

  stepperX.setMaxSpeed(2000);
  stepperZ.setMaxSpeed(2000);
  stepperX.setAcceleration(2000);
  stepperZ.setAcceleration(2000);

  Serial.println("READY");
}

void loop() {
  // Non-blocking run loop
  if (running) {
    // Which stepper and continue stepping
    // We'll choose by block axis when a move is started
    stepperX.run();
    stepperZ.run();

    if (stop_requested) {
      stepperX.stop();
      stepperZ.stop();
      if (stepperX.distanceToGo() == 0 && stepperZ.distanceToGo() == 0) {
        running = false;
        stop_requested = false;
        Serial.println("STOPPED");
      }
      return;
    }

    // If both axes idle, decide next action
    if (stepperX.distanceToGo() == 0 && stepperZ.distanceToGo() == 0) {
      if (!programLoaded || programLen <= 0) {
        running = false;
        Serial.println("DONE");
        return;
      }

      if (currentBlock >= programLen) {
        if (programLoop) {
          currentBlock = 0;
        } else {
          running = false;
          Serial.println("DONE");
          return;
        }
      }

      OscilBlock &blk = programBlocks[currentBlock];
      AccelStepper &s = (blk.axis == 'X') ? stepperX : stepperZ;
      s.setMaxSpeed(blk.speed);

      if (!phasePositive) {
        // Start negative phase
        long steps = blk.neg_steps; // should be negative
        float spd = (steps >= 0) ? blk.speed : -blk.speed;
        s.setSpeed(spd);
        s.move(steps);
        phasePositive = true; // next phase will be positive
      } else {
        // Start positive phase
        long steps = blk.pos_steps; // should be positive
        float spd = (steps >= 0) ? blk.speed : -blk.speed;
        s.setSpeed(spd);
        s.move(steps);
        phasePositive = false; // next cycle returns to negative

        // After scheduling the positive phase, when it completes, we'll decrement cycle
        if (blk.rep > 0) {
          blk.rep -= 1;
        }
        if (blk.rep == 0) {
          // move to next block after positive phase completes
          currentBlock += 1;
        }
      }
    }
  }

  // Process serial input when idle or running
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    if (line.equalsIgnoreCase("PING")) {
      Serial.println("PONG");
      return;
    }
    if (line.equalsIgnoreCase("STATUS")) {
      if (running) {
        Serial.println("STATUS RUNNING");
      } else if (programLoaded) {
        Serial.println("STATUS READY");
      } else {
        Serial.println("STATUS IDLE");
      }
      return;
    }
    if (line.equalsIgnoreCase("STOP")) {
      stop_requested = true;
      Serial.println("OK");
      return;
    }

    // Program protocol
    // PROG BEGIN
    // OSCIL <axis> <neg_steps> <pos_steps> SPD <v> REP <n>
    // PROG END [LOOP|ONCE]
    // RUN
    if (line.startsWith("PROG ")) {
      if (line.equalsIgnoreCase("PROG BEGIN")) {
        if (running) { Serial.println("ERR busy"); return; }
        programLen = 0;
        programLoaded = false;
        Serial.println("OK");
        return;
      }
      if (line.startsWith("PROG END")) {
        if (line.indexOf("LOOP") >= 0) programLoop = true; else programLoop = false;
        programLoaded = (programLen > 0);
        Serial.println("OK");
        return;
      }
      Serial.println("ERR syntax");
      return;
    }

    if (line.startsWith("OSCIL ")) {
      if (running) { Serial.println("ERR busy"); return; }
      if (programLen >= MAX_BLOCKS) { Serial.println("ERR full"); return; }
      // Expected: OSCIL <axis> <neg_steps> <pos_steps> SPD <v> REP <n>
      int i = 6;
      while (i < line.length() && line.charAt(i) == ' ') i++;
      if (i >= line.length()) { Serial.println("ERR axis"); return; }
      char ax = toupper(line.charAt(i));
      if (ax != 'X' && ax != 'Z') { Serial.println("ERR axis"); return; }

      // Find SPD and REP keywords
      int idxSPD = line.indexOf("SPD", i);
      int idxREP = line.indexOf("REP", i);
      if (idxSPD < 0 || idxREP < 0) { Serial.println("ERR syntax"); return; }

      // Extract numbers between axis and SPD/REP
      // We'll parse the first two numbers after axis as neg and pos
      // Simplistic parsing using substring and toInt/toFloat
      // Extract segment after axis
      String rest = line.substring(i + 1);
      rest.trim();
      // First two tokens should be neg and pos
      long neg = 0;
      long pos = 0;
      int space1 = rest.indexOf(' ');
      if (space1 < 0) { Serial.println("ERR neg"); return; }
      String t1 = rest.substring(0, space1);
      rest = rest.substring(space1 + 1);
      rest.trim();
      int space2 = rest.indexOf(' ');
      if (space2 < 0) { Serial.println("ERR pos"); return; }
      String t2 = rest.substring(0, space2);
      neg = t1.toInt();
      pos = t2.toInt();

      float spd = 0.0f;
      long rep = 1;
      spd = line.substring(idxSPD + 3).toFloat();
      rep = line.substring(idxREP + 3).toInt();
      if (spd <= 0) { Serial.println("ERR spd"); return; }
      // rep can be -1 for infinite; otherwise must be >=1
      if (!(rep == -1 || rep >= 1)) { Serial.println("ERR rep"); return; }

      OscilBlock blk;
      blk.axis = ax;
      blk.neg_steps = neg;
      blk.pos_steps = pos;
      blk.speed = spd;
      blk.rep = rep;
      programBlocks[programLen++] = blk;
      Serial.println("OK");
      return;
    }

    if (line.equalsIgnoreCase("RUN")) {
      if (!programLoaded) { Serial.println("ERR noprogram"); return; }
      if (running) { Serial.println("ERR busy"); return; }
      // Reset state
      currentBlock = 0;
      phasePositive = false;
      // For finite reps, rep already stored; for infinite, blk.rep=-1
      // Ensure steppers idle
      stepperX.stop();
      stepperZ.stop();
      running = true;
      Serial.println("OK");
      return;
    }

    // Optional: set calibration
    // SET SPU X <val> Z <val>
    if (line.startsWith("SET SPU ")) {
      int idxX = line.indexOf('X');
      int idxZ = line.indexOf('Z');
      if (idxX >= 0) {
        steps_per_unit_x = line.substring(idxX + 1).toFloat();
      }
      if (idxZ >= 0) {
        steps_per_unit_z = line.substring(idxZ + 1).toFloat();
      }
      Serial.println("OK");
      return;
    }

    Serial.println("ERR unknown");
  }
}
