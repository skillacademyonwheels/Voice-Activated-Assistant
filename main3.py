import threading
from queue import Queue, Empty
from datetime import datetime

import speech_recognition as sr
import pyttsx3


# -------------------- Text-to-speech helpers -------------------- #

def init_tts_engine():
    """Create and configure a single pyttsx3 engine (used only in one thread)."""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    return engine


def speak(engine, text: str):
    """Speak text using the given engine. Call this from a single thread only."""
    engine.say(text)
    engine.runAndWait()


# -------------------- Voice command logic -------------------- #

def respond_to_command(command: str, engine, stop_event: threading.Event) -> bool:
    """
    Handle recognized commands.
    Return False when we want to exit the assistant.
    """
    if "hello" in command:
        speak(engine, "Hi there! How can I help you today?")
    elif "your name" in command:
        speak(engine, "I am your Python voice assistant.")
    elif "time" in command:
        now = datetime.now().strftime("%H:%M")
        speak(engine, f"The time is {now}")
    elif "exit" in command or "stop" in command:
        speak(engine, "Goodbye!")
        # Signal everyone to stop
        stop_event.set()
        return False
    else:
        speak(engine, "I'm not sure how to help with that.")

    return True


# -------------------- Listener thread -------------------- #

def listener_thread(recognizer: sr.Recognizer,
                    microphone: sr.Microphone,
                    command_queue: Queue,
                    stop_event: threading.Event):
    """
    Continuously listen on the microphone, recognize speech,
    and push recognized text into the command_queue.
    """
    print("🎧 Listener thread started.")

    # Open the microphone in THIS thread
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("✅ Adjusted for ambient noise. Ready to listen.")

        while not stop_event.is_set():
            try:
                print("🎤 Speak now...")
                audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)

                try:
                    command = recognizer.recognize_google(audio)
                    command = command.lower()
                    print(f"✅ You said: {command}")
                    command_queue.put(command)   # push to queue
                except sr.UnknownValueError:
                    print("❌ Could not understand.")
                except sr.RequestError as e:
                    print(f"❌ API Error: {e}")

            except Exception as e:
                # Catch any microphone/listening errors
                print(f"⚠️ Listener error: {e}")

    print("🛑 Listener thread exiting.")


# -------------------- Worker/speaker thread -------------------- #

def worker_thread(command_queue: Queue, stop_event: threading.Event):
    """
    Pull commands from the queue and respond to them.
    All TTS happens in this single thread.
    """
    print("🧠 Worker thread started.")
    engine = init_tts_engine()
    speak(engine, "Voice assistant activated. Say something!")

    while not stop_event.is_set():
        try:
            # Wait for a command for up to 0.5s; if none, loop again so we can see stop_event
            command = command_queue.get(timeout=0.5)
        except Empty:
            continue

        if command is None:
            # Optional: sentinel to force exit
            break

        print(f"📝 Worker got command: {command}")
        should_continue = respond_to_command(command, engine, stop_event)
        if not should_continue:
            break

    print("🛑 Worker thread exiting.")
    # Let engine clean up
    engine.stop()


# -------------------- Main -------------------- #

def main():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    command_queue = Queue()
    stop_event = threading.Event()

    # Create threads
    listener = threading.Thread(
        target=listener_thread,
        args=(recognizer, microphone, command_queue, stop_event),
        daemon=True
    )
    worker = threading.Thread(
        target=worker_thread,
        args=(command_queue, stop_event),
        daemon=True
    )

    # Start threads
    listener.start()
    worker.start()

    try:
        # Main thread just waits until stop_event is set (e.g. user says "exit")
        stop_event.wait()
    except KeyboardInterrupt:
        print("\n⌨️ KeyboardInterrupt received. Stopping...")
        stop_event.set()
    finally:
        # Optionally push sentinel to unblock worker if it's stuck on queue.get()
        command_queue.put(None)

        listener.join(timeout=2)
        worker.join(timeout=2)
        print("✅ Assistant completely stopped.")


if __name__ == "__main__":
    main()
