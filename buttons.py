# --- buttons.py ---
# The PiTFT Plus has 4 tactile buttons wired to GPIO 17, 22, 23, 27.
# They're wired to ground, so we use internal pull-ups and treat a LOW
# reading as "pressed". No overlay/driver needed - gpiozero reads them
# directly.
#
# Mapping (adjust here if your physical buttons are in a different order
# than you expect once you test it):
#   GPIO17 -> UP
#   GPIO22 -> DOWN
#   GPIO23 -> SELECT
#   GPIO27 -> BACK
#
# Confirmed by physical test (`python3 buttons.py`, pressing left-to-right):
# left-to-right on this unit is GPIO17, 22, 23, 27 regardless of the
# display's rotate= setting - software rotation only changes what's drawn
# on screen, it doesn't change which physical button is wired to which
# GPIO pin.

from gpiozero import Button

PIN_UP = 17
PIN_DOWN = 22
PIN_SELECT = 23
PIN_BACK = 27

class Buttons:
    def __init__(self, on_up, on_down, on_select, on_back, bounce_time=0.08):
        self.up = Button(PIN_UP, pull_up=True, bounce_time=bounce_time)
        self.down = Button(PIN_DOWN, pull_up=True, bounce_time=bounce_time)
        self.select = Button(PIN_SELECT, pull_up=True, bounce_time=bounce_time)
        self.back = Button(PIN_BACK, pull_up=True, bounce_time=bounce_time)

        self.up.when_pressed = on_up
        self.down.when_pressed = on_down
        self.select.when_pressed = on_select
        self.back.when_pressed = on_back


if __name__ == "__main__":
    # quick manual test - press each button, confirm it prints the right label
    import time
    b = Buttons(
        on_up=lambda: print("UP"),
        on_down=lambda: print("DOWN"),
        on_select=lambda: print("SELECT"),
        on_back=lambda: print("BACK"),
    )
    print("Press buttons, Ctrl+C to quit")
    while True:
        time.sleep(1)
