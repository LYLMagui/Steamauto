# Tkinter Desktop GUI Development Guidelines

> This document outlines conventions and thread-safety guidelines for desktop GUI development using Tkinter.

---

## 1. Thread Safety & Real-time Console Logs

**Rule**: Never write to or update Tkinter UI widgets directly from a background worker thread. Doing so will lead to UI freezes, race conditions, or hard segmentation faults in Tcl/Tk.

**Pattern**: Use a thread-safe `queue.Queue` to pipe string messages (like logs) from background threads to the main GUI thread. The main thread must poll this queue periodically using `widget.after()`.

**Example**:
```python
# In logger.py:
import queue
gui_log_queue = queue.Queue()

class GuiLogHandler(logging.Handler):
    def emit(self, record):
        gui_log_queue.put((record.levelname, self.format(record)))

# In gui.py:
def poll_logs(self):
    try:
        while True:
            lvl, msg = gui_log_queue.get_nowait()
            self.append_text_widget(lvl, msg)
    except queue.Empty:
        pass
    self.root.after(100, self.poll_logs)  # Poll every 100ms
```

---

## 2. Preventing Thread Deadlocks on Console Inputs

**Rule**: Background workers running scripts originally written for CLI may contain blocking console calls like `input()`. If executed under GUI mode, the thread will hang indefinitely.

**Pattern**: Check a global run flag (e.g. `getattr(static, "is_gui_mode", False)`) and wrap blocking commands into non-blocking Tkinter standard popup dialogs (e.g. `simpledialog.askstring`).

**Example**:
```python
# CLI blocking call:
# sms_code = input("Enter verification code: ")

# GUI compatibility wrapper:
if getattr(static, "is_gui_mode", False):
    from tkinter import simpledialog
    sms_code = simpledialog.askstring("OTP Code", "Enter verification code:")
else:
    sms_code = input("Enter verification code: ")
```

---

## 3. Native Tkinter Styling Tokens

**Rule**: To maintain high-fidelity visual design, avoid using default Windows 95 grey buttons. Implement flat theme structures using Tkinter base parameters.
- Foreground/Background pairings should use cohesive dark color hex values (e.g. `#121214` and `#1A1A1E`).
- Round entry controls and styled borders should be masked using card configurations.
- Use explicit font hierarchies: Title (Segoe UI 14 Bold), Forms (Microsoft YaHei 10), Terminal logs (Courier New 9).
