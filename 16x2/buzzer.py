import RPi.GPIO as GPIO
import time

# Set the GPIO mode (BCM or BOARD)
GPIO.setmode(GPIO.BCM)

# Define the GPIO pin number to which the buzzer is connected
BUZZER_PIN = 29

# Set up the GPIO pin as an output
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# Constants for note names and their corresponding frequencies
C4 = 261
G3 = 196
A3 = 220
B3 = 247

# Dictionary to map numeric values to note names
note_names = {
    C4: "C4",
    G3: "G3",
    A3: "A3",
    B3: "B3",
}

# List of notes in the melody
melody = [
    C4, G3, G3, A3, G3, C4, B3, C4
]

# List of note durations (in milliseconds)
note_durations = [
    400, 200, 200, 400, 400, 400, 400, 400
]

# Pause duration between notes (in milliseconds)
pause_duration = 300

def play_tone(pin, frequency, duration):
    # Calculate the period based on the frequency
    period = 1.0 / frequency
    
    # Calculate the time for half of the period
    half_period = period / 2.0
    
    # Calculate the number of cycles for the given duration
    cycles = int(duration / period)
    
    for _ in range(cycles):
        # Set the GPIO pin to HIGH
        GPIO.output(pin, GPIO.HIGH)
        
        # Wait for half of the period
        time.sleep(half_period)
        
        # Set the GPIO pin to LOW
        GPIO.output(pin, GPIO.LOW)
        
        # Wait for the other half of the period
        time.sleep(half_period)

try:
    while True:  # Infinite loop
        # Iterate over the notes of the melody
        for i in range(len(melody)):
            # To calculate the note duration, take the value from the list and divide it by 1,000 (convert to seconds)
            note_duration = note_durations[i] / 1000.0
            note_freq = melody[i]
            note_name = note_names.get(note_freq, "Pause")

            print(f"Playing {note_name} (Frequency: {note_freq} Hz) for {note_duration} seconds")
            
            # Play the tone
            play_tone(BUZZER_PIN, note_freq, note_duration)
            
            # Add a brief pause between notes (optional)
            time.sleep(pause_duration / 1000.0)
            
            # Stop the tone playing (optional)
            GPIO.output(BUZZER_PIN, GPIO.LOW)

# Allow the user to stop the buzzer by pressing Ctrl+C
except KeyboardInterrupt:
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    GPIO.cleanup()