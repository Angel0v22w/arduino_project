#include <Arduino.h>

namespace {

constexpr uint8_t CHANNEL_U1 = A0;
constexpr uint8_t CHANNEL_U2 = A1;
constexpr uint8_t AVERAGING_SAMPLES = 8;
constexpr float ADC_REFERENCE_VOLTAGE = 5.0F;
constexpr float ADC_MAX_VALUE = 1023.0F;
constexpr unsigned long SAMPLE_INTERVAL_MS = 100;

float readVoltage(const uint8_t pin) {
  // The Uno uses one ADC and an analogue multiplexer. Discarding the first
  // conversion after switching channels gives the sample-and-hold capacitor
  // time to settle, which is also useful when this code is moved to hardware.
  analogRead(pin);

  uint32_t sum = 0;
  for (uint8_t index = 0; index < AVERAGING_SAMPLES; ++index) {
    sum += analogRead(pin);
  }

  const float averageAdc =
      static_cast<float>(sum) / static_cast<float>(AVERAGING_SAMPLES);
  return averageAdc * ADC_REFERENCE_VOLTAGE / ADC_MAX_VALUE;
}

}  // namespace

void setup() {
  Serial.begin(115200);
}

void loop() {
  static unsigned long previousSampleMs = 0;
  const unsigned long nowMs = millis();

  if (nowMs - previousSampleMs < SAMPLE_INTERVAL_MS) {
    return;
  }
  previousSampleMs = nowMs;

  const float voltageU1 = readVoltage(CHANNEL_U1);
  const float voltageU2 = readVoltage(CHANNEL_U2);

  // Machine-readable protocol: one sample per line, two comma-separated volts.
  Serial.print(voltageU1, 3);
  Serial.print(',');
  Serial.println(voltageU2, 3);
}

