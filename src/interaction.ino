#include <AccelStepper.h>
#include <ctype.h>
#include <string.h>
#include <stdint.h>

/* =========================
   1) COMMAND TYPES & QUEUE
   ========================= */

// ---- Command enums FIRST ----
enum CmdType : uint8_t { CMD_NONE=0, CMD_MOVE, CMD_SPEED, CMD_ACCEL, CMD_WAIT, CMD_PULSE, CMD_STOP };
enum Axis    : uint8_t { AX_X=0, AX_Z=1, AX_NONE=2 };

// value: steps (MOVE), speed*1000 (SPEED), accel*1000 (ACCEL), ms (WAIT/PULSE)
struct Command {
  uint8_t type;  // CmdType
  uint8_t axis;  // Axis
  int32_t value; // payload
};

// ---- Queue storage & funcs NEXT ----
#define QUEUE_CAP 128                      // increased to 128 for long scripts
static Command q[QUEUE_CAP];
static uint8_t qHead=0, qTail=0;

inline bool qEmpty(){ return qHead==qTail; }
inline bool qFull(){ return (uint8_t)(qTail+1)%QUEUE_CAP==qHead; }
inline void qClear(){ qHead=qTail=0; }

bool enqueue(const Command& c){
  if (qFull()) return false;
  q[qTail] = c;
  qTail = (uint8_t)(qTail + 1) % QUEUE_CAP;
  return true;
}

bool qDequeue(Command &c){
  if (qEmpty()) return false;
  c = q[qHead];
  qHead = (uint8_t)(qHead + 1) % QUEUE_CAP;
  return true;
}

/* =========================
   2) HARDWARE / CONSTANTS
   ========================= */

// Pins (CNC Shield V3 defaults)
#define X_STEP_PIN 2
#define X_DIR_PIN  5
#define Z_STEP_PIN 4
#define Z_DIR_PIN  7
#define ENABLE_PIN 8   // shared enable (LOW = on)
#define MAGNET_PIN 12  // electromagnet pulse output

// Mechanics / Microstepping
#define MICROSTEP_X 32
#define MICROSTEP_Z 32   // Z now at 1/32
const float BASE_STEPS_PER_MM = 20.0f; // full-step steps/mm of your mechanics

// Derived
const float STEPS_PER_MM_X = BASE_STEPS_PER_MM * MICROSTEP_X;
const float STEPS_PER_MM_Z = BASE_STEPS_PER_MM * MICROSTEP_Z;

// Defaults (runtime changeable via serial)
float speed_mm_s_X = 2.0f;
float speed_mm_s_Z = 2.0f;
// Higher default acceleration for snappier motion; can be adjusted at runtime via 'accel x|z A'
float accel_mm_s2_X = 20.0f;
float accel_mm_s2_Z = 100.0f;

// Z soft-limit buffer: allow +Z up to this value (mm) beyond the zero baseline
const float Z_SOFT_LIMIT_BUFFER_MM = 2.0f;

// Electromagnet pulse timing
const unsigned long PULSE_BREAK_MS = 50;  // Break time between consecutive pulses (ms)

// AccelStepper
AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperZ(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

// Enable gating (keep cool)
bool driversEnabled = false;
inline void enableDrivers(bool on){
  if (on != driversEnabled) {
    digitalWrite(ENABLE_PIN, on ? LOW : HIGH); // LOW = enabled
    driversEnabled = on;
  }
}

/* =========================
   3) RUNTIME STATE
   ========================= */

bool cmdActive=false;
Command curr;
bool  waiting=false;
unsigned long waitUntil=0;
uint8_t movingAxis=AX_NONE;
// Soft-limit tracking for Z: prevent going below 0 after runtime zeroing
long z_future_pos_steps = 0; // predicted Z position in steps (includes queued moves)
// Electromagnet pulse state
bool pulsing=false;
unsigned long pulseEndTime=0;
bool inBreak=false;
unsigned long breakEndTime=0;

/* =========================
   4) EMERGENCY STOP (IMMEDIATE)
   ========================= */

void emergencyStop(const __FlashStringHelper* reason /*=nullptr*/) {
  if (!reason) reason = F("STOP");

  // Request decelerating stop
  stepperX.stop();
  stepperZ.stop();

  // Force target = current so distanceToGo() == 0 (hard snap)
  long cx = stepperX.currentPosition();
  long cz = stepperZ.currentPosition();
  stepperX.setCurrentPosition(cx);
  stepperZ.setCurrentPosition(cz);
  stepperX.moveTo(cx);
  stepperZ.moveTo(cz);

  // Keep predicted Z in sync with actual after stop
  z_future_pos_steps = stepperZ.currentPosition();

  // Clear any pending commands/state
  qClear();
  cmdActive   = false;
  waiting     = false;
  movingAxis  = AX_NONE;
  pulsing     = false;
  inBreak     = false;
  digitalWrite(MAGNET_PIN, LOW);  // ensure magnet is off

  // Power down to keep cool
  enableDrivers(false);

  Serial.print(F("[exec] ")); Serial.print(reason); Serial.println(F(": EMERGENCY HALT, queue cleared"));
}


/* =========================
   5) PARSER UTILITIES
   ========================= */

static inline void skipSpaces(const char *&p){ while(*p && isspace((unsigned char)*p)) ++p; }

// case-insensitive match at start; advances p on success
static inline bool ieq(const char* &p, const char* kw){
  const char* s=p;
  while(*kw && *s){
    if (tolower((unsigned char)*s) != tolower((unsigned char)*kw)) return false;
    ++s; ++kw;
  }
  if (*kw==0){ p=s; return true; }
  return false;
}

// integer (supports +/-)
static bool parseNumber(const char *&p, long &out){
  skipSpaces(p);
  bool neg=false; if(*p=='+'||*p=='-'){ neg=(*p=='-'); ++p; }
  if(!isdigit((unsigned char)*p)) return false;
  long v=0;
  while(isdigit((unsigned char)*p)){ v = v*10 + (*p-'0'); ++p; }
  out = neg ? -v : v;
  return true;
}

// float to fixed-point (*1000)
static bool parseFloat1000(const char *&p, long &out){
  skipSpaces(p);
  bool neg=false; if(*p=='+'||*p=='-'){ neg=(*p=='-'); ++p; }
  if(!(isdigit((unsigned char)*p) || *p=='.')) return false;
  long intPart=0, fracPart=0, fracPow=1;
  while(isdigit((unsigned char)*p)){ intPart=intPart*10+(*p-'0'); ++p; }
  if(*p=='.'){
    ++p;
    while(isdigit((unsigned char)*p) && fracPow<1000){ fracPart=fracPart*10+(*p-'0'); fracPow*=10; ++p; }
    while(isdigit((unsigned char)*p)) ++p; // skip extra decimals
  }
  long scaled = intPart*1000 + (fracPow>1 ? (fracPart*(1000/fracPow)) : 0);
  out = neg ? -scaled : scaled;
  return true;
}

inline long mm_to_steps(float mm, bool isX){
  float stepsPerMM = isX ? STEPS_PER_MM_X : STEPS_PER_MM_Z;
  return (long)(mm * stepsPerMM);
}

/* =========================
   6) CLAUSE PARSER (stream)
   ========================= */

char clauseBuf[64];
uint8_t clauseLen=0;

void parseClause(char *buf){
  const char *p = buf;
  skipSpaces(p);
  if(*p==0) return;

  // zero z  (Set current Z as new 0 soft-limit baseline)
  {
    const char* t = p;
    if (ieq(t, "zero")) {
      skipSpaces(t);
      if(*t==0){ Serial.println(F("[parse] zero axis?")); return; }
      char ax = tolower((unsigned char)*t); ++t;
      if(ax!='z'){ Serial.println(F("[parse] zero supports only 'z'")); return; }
      // Lightweight zero: do not emergency stop; just redefine baseline.
      // Keep current queued moves; recompute predicted future Z from queue + current.
      long actualSteps = stepperZ.currentPosition();
      stepperZ.setCurrentPosition(0); // new logical baseline
      // Recompute z_future_pos_steps from remaining queued Z moves plus any active motion distanceToGo.
      long future = 0;
      // Include active motion still to go if Z is moving
      if (movingAxis == AX_Z) {
        future += stepperZ.distanceToGo();
      }
      // Scan queue for pending Z moves
      uint8_t idx = qHead;
      while (idx != qTail) {
        const Command &qc = q[idx];
        if (qc.type == CMD_MOVE && qc.axis == AX_Z) future += qc.value;
        idx = (uint8_t)(idx + 1) % QUEUE_CAP;
      }
      z_future_pos_steps = future;
      Serial.println(F("[info] Z baseline reset (no stop). Soft-limit baseline set to 0."));
      return;
    }
  }

  // stop  (IMMEDIATE, do not enqueue)
  {
    const char* t = p;
    if (ieq(t, "stop")) {
      emergencyStop(F("STOP"));
      return;
    }
  }

  // report z  (Instant status of current & predicted Z position)
  {
    const char* t = p;
    if (ieq(t, "report")) {
      skipSpaces(t);
      if (*t==0){ Serial.println(F("[parse] report axis?")); return; }
      char ax = tolower((unsigned char)*t); ++t;
      if (ax!='z'){ Serial.println(F("[parse] report supports only 'z'")); return; }
      long curSteps = stepperZ.currentPosition();
      float curMM = (float)curSteps / STEPS_PER_MM_Z;
      float futureMM = (float)z_future_pos_steps / STEPS_PER_MM_Z;
      Serial.print(F("[z] current ")); Serial.print(curMM,2); Serial.print(F(" mm (")); Serial.print(curSteps); Serial.print(F(" steps), future "));
      Serial.print(futureMM,2); Serial.print(F(" mm (")); Serial.print(z_future_pos_steps); Serial.println(F(" steps)"));
      return;
    }
  }

  // wait T
  {
    const char* t=p;
    if(ieq(t,"wait")){
      long T=0;
      if(!parseNumber(t,T)){ Serial.println(F("[parse] wait T?")); return; }
      if(T<0) T=0;
      enqueue(Command{CMD_WAIT, AX_NONE, (int32_t)T});
      Serial.print(F("[queued] wait ")); Serial.println((unsigned long)T);
      return;
    }
  }

  // pulse T  (electromagnet pulse)
  {
    const char* t=p;
    if(ieq(t,"pulse")){
      long T=0;
      if(!parseNumber(t,T)){ Serial.println(F("[parse] pulse T?")); return; }
      if(T<0) T=0;
      if(T>5000){
        Serial.println(F("[warning] pulse duration capped at 5000ms for safety"));
        T=5000;
      }
      enqueue(Command{CMD_PULSE, AX_NONE, (int32_t)T});
      Serial.print(F("[queued] pulse ")); Serial.print((unsigned long)T); Serial.println(F(" ms"));
      return;
    }
  }

  // move x/z D
  {
    const char* t=p;
    if(ieq(t,"move")){
      skipSpaces(t);
      if(*t==0){ Serial.println(F("[parse] move axis?")); return; }
      char ax = tolower((unsigned char)*t); ++t;
      if(ax!='x' && ax!='z'){ Serial.println(F("[parse] axis x/z?")); return; }
      long D_scaled=0;  // Distance in mm * 1000 for 1 decimal place precision
      if(!parseFloat1000(t,D_scaled)){ Serial.println(F("[parse] move mm?")); return; }
      float D_mm = (float)D_scaled / 1000.0f;  // Convert back to mm as float
      long steps = mm_to_steps(D_mm, ax=='x');
  // Soft-limit guard for Z: with +Z = down, baseline 0 is the contact.
  // We allow Z up to Z_SOFT_LIMIT_BUFFER_MM (e.g., 2.0mm) beyond 0 for small adjustments.
      if(ax=='z'){
        long predicted = z_future_pos_steps + steps;
        float predicted_mm = (float)predicted / STEPS_PER_MM_Z;
        if (predicted_mm > Z_SOFT_LIMIT_BUFFER_MM) {
          Serial.print(F("[limit] Z move would exceed buffer ("));
          Serial.print(Z_SOFT_LIMIT_BUFFER_MM);
          Serial.println(F("mm); use 'zero z' at the contact point or reduce move."));
          return;
        }
      }
      if(!enqueue(Command{CMD_MOVE, (uint8_t)(ax=='x'?AX_X:AX_Z), steps}))
        Serial.println(F("[queue] full (QUEUE_CAP=128). Increase QUEUE_CAP in firmware if needed."));
      else{
        if(ax=='z'){ z_future_pos_steps += steps; }
        Serial.print(F("[queued] move ")); Serial.print((ax=='x')?'X':'Z');
        Serial.print(F(" ")); Serial.print(D_mm,1); Serial.print(F(" mm ("));
        Serial.print(steps); Serial.println(F(" steps)"));
      }
      return;
    }
  }

  // speed x/z S
  {
    const char* t=p;
    if(ieq(t,"speed")){
      skipSpaces(t);
      if(*t==0){ Serial.println(F("[parse] speed axis?")); return; }
      char ax = tolower((unsigned char)*t); ++t;
      long S1000=0;
      if(!parseFloat1000(t,S1000)){ Serial.println(F("[parse] speed mm/s?")); return; }
      if(!enqueue(Command{CMD_SPEED, (uint8_t)(ax=='x'?AX_X:AX_Z), (int32_t)S1000}))
        Serial.println(F("[queue] full (QUEUE_CAP=128). Increase QUEUE_CAP in firmware if needed."));
      else{
        Serial.print(F("[queued] speed ")); Serial.print((ax=='x')?'X':'Z');
        Serial.print(F(" ")); Serial.print(S1000/1000); Serial.print('.');
        Serial.println((int)(abs(S1000)%1000));
      }
      return;
    }
  }

  Serial.println(F("[parse] unknown clause"));
}

/* =========================
   7) COMMAND EXECUTION
   ========================= */

void beginCommand(const Command &c){
  curr = c; cmdActive = true; waiting = false; movingAxis = AX_NONE;

  switch (c.type){
    case CMD_MOVE:
      if(c.axis==AX_X){ stepperX.move(c.value); movingAxis = AX_X; }
      else            { stepperZ.move(c.value); movingAxis = AX_Z; }
      enableDrivers(true);
      break;

    case CMD_SPEED: {
      float sp = (float)c.value * 0.001f;
      if(c.axis==AX_X){
        speed_mm_s_X = sp;
        stepperX.setMaxSpeed(STEPS_PER_MM_X * speed_mm_s_X);
      }else{
        speed_mm_s_Z = sp;
        stepperZ.setMaxSpeed(STEPS_PER_MM_Z * speed_mm_s_Z);
      }
      cmdActive = false; // instantaneous
    } break;

    case CMD_WAIT:
      waiting = true;
      waitUntil = millis() + (unsigned long)c.value;
      enableDrivers(false);
      break;

    case CMD_PULSE:
      // Start pulse immediately (scheduler guarantees !pulsing && !inBreak)
      digitalWrite(MAGNET_PIN, HIGH);
      pulseEndTime = millis() + (unsigned long)c.value;
      pulsing = true;
      Serial.print(F("[pulse] START - "));
      Serial.print((unsigned long)c.value);
      Serial.println(F(" ms"));
      cmdActive = false;  // pulse runs in background
      break;

    default:
      cmdActive = false;
      break;
  }
}

// Finished? (wrap-safe for wait)
bool commandFinished(){
  if(!cmdActive) return true;
  if(waiting){
    return (long)(millis() - waitUntil) >= 0;
  }
  if(curr.type==CMD_MOVE){
    if(movingAxis==AX_X) return stepperX.distanceToGo()==0;
    if(movingAxis==AX_Z) return stepperZ.distanceToGo()==0;
  }
  return true;
}

/* =========================
   8) SETUP / LOOP
   ========================= */

void setup(){
  pinMode(ENABLE_PIN, OUTPUT);
  enableDrivers(false); // cool at boot

  pinMode(MAGNET_PIN, OUTPUT);
  digitalWrite(MAGNET_PIN, LOW);  // ensure magnet is off at boot

  Serial.begin(115200);

  stepperX.setMaxSpeed(STEPS_PER_MM_X * speed_mm_s_X);
  stepperX.setAcceleration(STEPS_PER_MM_X * accel_mm_s2_X);
  stepperX.setCurrentPosition(0);

  stepperZ.setMaxSpeed(STEPS_PER_MM_Z * speed_mm_s_Z);
  stepperZ.setAcceleration(STEPS_PER_MM_Z * accel_mm_s2_Z);
  stepperZ.setCurrentPosition(0);
  // Start Z tracking at -50mm (safe distance from contact point)
  // User will move closer and use 'zero z' to set actual contact baseline
  // Establish a logical starting offset of -50mm (above the contact baseline) so early downward (+Z) moves are allowed.
  // We align both the physical currentPosition and our predictive accumulator so 'report z' is intuitive at startup.
  stepperZ.setCurrentPosition(mm_to_steps(-50.0f, false));
  z_future_pos_steps = stepperZ.currentPosition();

  Serial.println(F("Ready. Commands: move x/z D | speed x/z S | wait T | pulse T | zero z | report z | stop (IMMEDIATE) | ! (panic)"));
  Serial.println(F("Separate with ',', ';', or newline. 'stop' triggers even without separator."));
}

void loop(){
  // --- stream input with immediate STOP detection ---
  while (Serial.available()){
    char c = (char)Serial.read();

    // 1) single-byte panic
    if (c == '!') {
      emergencyStop(F("!"));
      clauseLen = 0; // discard partial clause
      continue;
    }

    // normal clause separation
    if (c==',' || c==';' || c=='\n' || c=='\r'){
      clauseBuf[clauseLen] = 0;
      parseClause(clauseBuf);
      clauseLen = 0;
    } else {
      if (clauseLen < sizeof(clauseBuf)-1) {
        clauseBuf[clauseLen++] = c;
        clauseBuf[clauseLen] = 0;

        // 2) immediate "stop" without needing a separator
        // trim + compare to "stop"
        uint8_t i = 0; while (i < clauseLen && isspace((unsigned char)clauseBuf[i])) ++i;
        int8_t j = (int8_t)clauseLen - 1; while (j >= 0 && isspace((unsigned char)clauseBuf[j])) --j;
        if (j >= i) {
          const char* word = "stop";
          bool match = (j - i + 1 == 4);
          for (uint8_t k=0; match && k<4; ++k)
            match = (tolower((unsigned char)clauseBuf[i+k]) == (unsigned char)word[k]);
          if (match) {
            emergencyStop(F("STOP"));
            clauseLen = 0;
            continue;
          }
        }
      } else {
        // overflow: parse what we have
        clauseBuf[clauseLen] = 0;
        parseClause(clauseBuf);
        clauseLen = 0;
      }
    }
  }

  // --- scheduler: one command at a time (no queued STOP path) ---
  // Do not dequeue new commands while a pulse is active or during enforced break,
  // so that queued CMD_PULSE commands execute strictly one-by-one with spacing.
  if (!cmdActive && !qEmpty() && !pulsing && !inBreak){
    Command n; qDequeue(n);
    beginCommand(n);
  }

  // service active motion only; keep cool otherwise
  if (movingAxis==AX_X && driversEnabled) stepperX.run();
  if (movingAxis==AX_Z && driversEnabled) stepperZ.run();

  // --- electromagnet pulse state machine ---
  if (pulsing) {
    // Check if pulse is complete (wrap-safe)
    if ((long)(millis() - pulseEndTime) >= 0) {
      digitalWrite(MAGNET_PIN, LOW);
      pulsing = false;
      Serial.println(F("[pulse] END"));
      
      // Start break period if more commands are queued
      if (!qEmpty()) {
        inBreak = true;
        breakEndTime = millis() + PULSE_BREAK_MS;
        Serial.print(F("[break] "));
        Serial.print(PULSE_BREAK_MS);
        Serial.println(F(" ms"));
      }
    }
  }

  if (inBreak) {
    // Check if break is complete (wrap-safe)
    if ((long)(millis() - breakEndTime) >= 0) {
      inBreak = false;
    }
  }

  // complete command / power down after motion
  if (cmdActive && commandFinished()){
    if (curr.type==CMD_MOVE) enableDrivers(false);
    cmdActive = false;
    movingAxis = AX_NONE;
  }

  if (!cmdActive && qEmpty()){
    enableDrivers(false); // fully idle
  }
}
