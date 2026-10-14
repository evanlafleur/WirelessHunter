# --- settings_base.py ---
# Shared base for the Settings app's sub-screens. SettingsApp keeps a
# stack of these; a screen navigates with self.app.push()/pop().

from keyboard import TextInput

class SettingsScreen:
    def __init__(self, app):
        self.app = app

    def on_enter(self):
        pass

    def update(self):
        """Called once per frame before draw() - poll background tasks here."""

    def down(self, x, y):
        pass

    def tap(self, x, y):
        pass

    def swipe(self, dx, dy):
        pass

    def draw(self, surface):
        pass


class KeyboardScreen(SettingsScreen):
    """Full-screen text entry. Calls on_done(text) after popping itself
    when the user taps OK; CANCEL just pops."""
    def __init__(self, app, title, on_done, initial="", secret=False, max_len=63):
        super().__init__(app)
        self.on_done = on_done
        self.input = TextInput()
        self.input.start(title, initial=initial, secret=secret, max_len=max_len)

    def down(self, x, y):
        self.input.down(x, y)

    def swipe(self, dx, dy):
        self.input.clear_down()

    def tap(self, x, y):
        result = self.input.tap(x, y)
        if result == "cancel":
            self.app.pop()
        elif result == "ok":
            text = self.input.text
            self.app.pop()
            self.on_done(text)

    def draw(self, surface):
        self.input.draw(surface)
