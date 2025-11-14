/*
 * Electromagnet Pulse Controller
 * 
 * Controls an electromagnet on pin 12 via serial commands.
 * Command: pulse <duration_ms>
 * Example: pulse 100  (activates electromagnet for 100ms)
 * 
 * Separators: comma, semicolon, or newline
 * Multiple commands can be queued.
 */

// Pin configuration
#define MAGNET_PIN 12

// Timing configuration
const unsigned long PULSE_BREAK_MS = 50;  // Break time between consecutive pulses (ms)

// Command queue
#define QUEUE_CAP 32
struct PulseCommand {
  unsigned long duration_ms;
};

static PulseCommand q[QUEUE_CAP];
static uint8_t qHead = 0, qTail = 0;

inline bool qEmpty() { return qHead == qTail; }
inline bool qFull() { return (uint8_t)(qTail + 1) % QUEUE_CAP == qHead; }
inline void qClear() { qHead = qTail = 0; }

bool enqueue(unsigned long duration) {
  if (qFull()) return false;
  q[qTail].duration_ms = duration;
  qTail = (uint8_t)(qTail + 1) % QUEUE_CAP;
  return true;
}

bool dequeue(PulseCommand &cmd) {
  if (qEmpty()) return false;
  cmd = q[qHead];
  qHead = (uint8_t)(qHead + 1) % QUEUE_CAP;
  return true;
}

// Runtime state
bool pulsing = false;
unsigned long pulseEndTime = 0;
bool inBreak = false;
unsigned long breakEndTime = 0;

// Input buffer
char inputBuf[64];
uint8_t inputLen = 0;

// Parser utilities
static inline void skipSpaces(const char *&p) {
  while (*p && isspace((unsigned char)*p)) ++p;
}

static inline bool matchKeyword(const char *&p, const char *kw) {
  const char *s = p;
  while (*kw && *s) {
    if (tolower((unsigned char)*s) != tolower((unsigned char)*kw)) return false;
    ++s; ++kw;
  }
  if (*kw == 0) { p = s; return true; }
  return false;
}

static bool parseNumber(const char *&p, long &out) {
  skipSpaces(p);
  if (!isdigit((unsigned char)*p)) return false;
  long v = 0;
  while (isdigit((unsigned char)*p)) {
    v = v * 10 + (*p - '0');
    ++p;
  }
  out = v;
  return true;
}

// Parse command
void parseCommand(char *buf) {
  const char *p = buf;
  skipSpaces(p);
  if (*p == 0) return;

  // pulse <duration_ms>
  if (matchKeyword(p, "pulse")) {
    long duration = 0;
    if (!parseNumber(p, duration)) {
      Serial.println(F("[error] pulse requires duration in ms (e.g., pulse 100)"));
      return;
    }
    if (duration < 0) duration = 0;
    if (duration > 5000) {
      Serial.println(F("[warning] duration capped at 5000ms for safety"));
      duration = 5000;
    }
    
    if (!enqueue((unsigned long)duration)) {
      Serial.println(F("[error] queue full, wait for pulses to complete"));
    } else {
      Serial.print(F("[queued] pulse "));
      Serial.print(duration);
      Serial.println(F(" ms"));
    }
    return;
  }

  // clear - clear pending queue
  if (matchKeyword(p, "clear")) {
    qClear();
    Serial.println(F("[info] queue cleared"));
    return;
  }

  // status - show queue status
  if (matchKeyword(p, "status")) {
    uint8_t count = (qTail >= qHead) ? (qTail - qHead) : (QUEUE_CAP - qHead + qTail);
    Serial.print(F("[status] queued: "));
    Serial.print(count);
    Serial.print(F("/"));
    Serial.print(QUEUE_CAP);
    Serial.print(F(", pulsing: "));
    Serial.println(pulsing ? F("YES") : F("NO"));
    return;
  }

  Serial.println(F("[error] unknown command. Use: pulse <ms> | clear | status"));
}

void setup() {
  pinMode(MAGNET_PIN, OUTPUT);
  digitalWrite(MAGNET_PIN, LOW);  // Ensure magnet is off at startup
  
  Serial.begin(115200);
  Serial.println(F("=== Electromagnet Pulse Controller ==="));
  Serial.println(F("Commands:"));
  Serial.println(F("  pulse <ms>  - Activate magnet for specified milliseconds"));
  Serial.println(F("  clear       - Clear pending pulses"));
  Serial.println(F("  status      - Show queue status"));
  Serial.println(F("Separate commands with ',' ';' or newline"));
  Serial.println(F("Ready."));
}

void loop() {
  // Read serial input
  while (Serial.available()) {
    char c = (char)Serial.read();
    
    // Command separators
    if (c == ',' || c == ';' || c == '\n' || c == '\r') {
      inputBuf[inputLen] = 0;
      parseCommand(inputBuf);
      inputLen = 0;
    } else {
      if (inputLen < sizeof(inputBuf) - 1) {
        inputBuf[inputLen++] = c;
      } else {
        // Buffer overflow - parse what we have
        inputBuf[inputLen] = 0;
        parseCommand(inputBuf);
        inputLen = 0;
      }
    }
  }

  // Execute pulsing state machine
  if (!pulsing && !inBreak && !qEmpty()) {
    // Start new pulse
    PulseCommand cmd;
    dequeue(cmd);
    
    digitalWrite(MAGNET_PIN, HIGH);
    pulseEndTime = millis() + cmd.duration_ms;
    pulsing = true;
    
    Serial.print(F("[pulse] START - "));
    Serial.print(cmd.duration_ms);
    Serial.println(F(" ms"));
  }

  if (pulsing) {
    // Check if pulse is complete (wrap-safe)
    if ((long)(millis() - pulseEndTime) >= 0) {
      digitalWrite(MAGNET_PIN, LOW);
      pulsing = false;
      Serial.println(F("[pulse] END"));
      
      // Start break period if more pulses are queued
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
}
