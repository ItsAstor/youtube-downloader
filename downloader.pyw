import sys
import subprocess
import importlib

# --- 1. Auto-Dependency & FFmpeg Installer ---
REQUIRED_PACKAGES = {
    "yt-dlp": "yt_dlp",
    "requests": "requests",
    "pillow": "PIL",
    "imageio-ffmpeg": "imageio_ffmpeg"
}

def ensure_dependencies():
    for package, module_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            print(f"Setting up missing requirement: {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", package])

ensure_dependencies()

# --- Standard & Third-Party Imports ---
import io
import json
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import requests
import yt_dlp
import imageio_ffmpeg

# --- Configuration & Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config_yt.json")
FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()

# --- Dark Palette Setup ---
BG_DARK = "#121212"
BG_CARD = "#1e1e1e"
ACCENT_RED = "#ff0033"
ACCENT_CYAN = "#00f2fe"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#a0a0a0"
BORDER_GRAY = "#2a2a2a"

YOUTUBE_URL_REGEX = re.compile(
    r'https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)[a-zA-Z0-9_-]+[^\s<>"\'`]*'
)

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader Pro")
        self.root.geometry("640x740")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)

        initial_path = self._load_saved_path()
        self.download_dir = tk.StringVar(value=initial_path)
        self.format_mode = tk.StringVar(value="mp4")
        self.status_text = tk.StringVar(value="Ready • Listening to clipboard")

        self.is_downloading = False
        self.last_clipboard = ""
        self.thumb_photo = None
        self.cached_info = None

        self._apply_styles()
        self._build_ui()
        self._setup_clipboard_listener()

    def _load_saved_path(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    saved = cfg.get("download_dir")
                    if saved and os.path.exists(saved):
                        return saved
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"download_dir": self.download_dir.get()}, f, indent=4)
        except Exception:
            pass

    def _apply_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Red.Horizontal.TProgressbar",
            troughcolor=BG_CARD,
            bordercolor=BORDER_GRAY,
            background=ACCENT_RED,
            lightcolor=ACCENT_RED,
            darkcolor=ACCENT_RED
        )

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG_DARK)
        header.pack(fill="x", padx=24, pady=(20, 10))

        title = tk.Label(header, text="YouTube Downloader", font=("Segoe UI", 18, "bold"), fg=TEXT_WHITE, bg=BG_DARK)
        title.pack(side="left")

        # URL Input Section
        url_box = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_GRAY)
        url_box.pack(fill="x", padx=24, pady=8)

        url_inner = tk.Frame(url_box, bg=BG_CARD)
        url_inner.pack(fill="x", padx=12, pady=10)

        tk.Label(url_inner, text="VIDEO URL", font=("Segoe UI", 8, "bold"), fg=ACCENT_CYAN, bg=BG_CARD).pack(anchor="w")

        input_row = tk.Frame(url_inner, bg=BG_CARD)
        input_row.pack(fill="x", pady=(4, 0))

        self.url_entry = tk.Entry(
            input_row, font=("Segoe UI", 10), bg="#2d2d2d", fg=TEXT_WHITE,
            insertbackground=TEXT_WHITE, relief="flat", highlightthickness=1, highlightbackground="#3d3d3d"
        )
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        fetch_btn = tk.Button(
            input_row, text="Fetch Preview", command=self._fetch_metadata_thread,
            bg=BORDER_GRAY, fg=TEXT_WHITE, activebackground="#3d3d3d", activeforeground=TEXT_WHITE,
            relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2", padx=12
        )
        fetch_btn.pack(side="right")

        # Preview Card
        self.preview_card = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_GRAY)
        self.preview_card.pack(fill="x", padx=24, pady=8)

        self.thumb_container = tk.Frame(self.preview_card, width=180, height=105, bg="#181818", highlightthickness=1, highlightbackground=BORDER_GRAY)
        self.thumb_container.pack_propagate(False)
        self.thumb_container.pack(side="left", padx=14, pady=14)

        self.thumb_label = tk.Label(self.thumb_container, text="No Preview", fg=TEXT_MUTED, bg="#181818", font=("Segoe UI", 9))
        self.thumb_label.pack(expand=True, fill="both")

        info_frame = tk.Frame(self.preview_card, bg=BG_CARD)
        info_frame.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=14)

        self.meta_channel = tk.Label(info_frame, text="@Channel", font=("Segoe UI", 10, "bold"), fg=ACCENT_RED, bg=BG_CARD, anchor="w")
        self.meta_channel.pack(fill="x")

        self.meta_title = tk.Label(
            info_frame, text="Paste or copy a YouTube link to load video metadata.",
            font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_CARD, wraplength=340, justify="left", anchor="nw"
        )
        self.meta_title.pack(fill="both", expand=True, pady=(4, 4))

        self.meta_stats = tk.Label(info_frame, text="Views: -   •   Duration: -", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_CARD, anchor="w")
        self.meta_stats.pack(fill="x")

        # Format Selection
        format_box = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_GRAY)
        format_box.pack(fill="x", padx=24, pady=6)

        format_inner = tk.Frame(format_box, bg=BG_CARD)
        format_inner.pack(fill="x", padx=12, pady=8)

        tk.Label(format_inner, text="FORMAT SELECTION", font=("Segoe UI", 8, "bold"), fg=ACCENT_CYAN, bg=BG_CARD).pack(anchor="w")

        radio_row = tk.Frame(format_inner, bg=BG_CARD)
        radio_row.pack(fill="x", pady=(4, 0))

        tk.Radiobutton(
            radio_row, text="Video (MP4 - Best Quality)", variable=self.format_mode, value="mp4",
            bg=BG_CARD, fg=TEXT_WHITE, selectcolor=BG_DARK, activebackground=BG_CARD,
            activeforeground=TEXT_WHITE, font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 20))

        tk.Radiobutton(
            radio_row, text="Audio Only (MP3)", variable=self.format_mode, value="mp3",
            bg=BG_CARD, fg=TEXT_WHITE, selectcolor=BG_DARK, activebackground=BG_CARD,
            activeforeground=TEXT_WHITE, font=("Segoe UI", 9)
        ).pack(side="left")

        # Save Directory
        path_box = tk.Frame(self.root, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER_GRAY)
        path_box.pack(fill="x", padx=24, pady=6)

        path_inner = tk.Frame(path_box, bg=BG_CARD)
        path_inner.pack(fill="x", padx=12, pady=8)

        tk.Label(path_inner, text="SAVE DIRECTORY", font=("Segoe UI", 8, "bold"), fg=ACCENT_CYAN, bg=BG_CARD).pack(anchor="w")

        path_row = tk.Frame(path_inner, bg=BG_CARD)
        path_row.pack(fill="x", pady=(4, 0))

        path_entry = tk.Entry(
            path_row, textvariable=self.download_dir, state="readonly",
            font=("Segoe UI", 9), bg="#2d2d2d", fg=TEXT_MUTED, relief="flat", highlightthickness=1, highlightbackground="#3d3d3d"
        )
        path_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

        browse_btn = tk.Button(
            path_row, text="Browse", command=self._browse_folder,
            bg=BORDER_GRAY, fg=TEXT_WHITE, activebackground="#3d3d3d", activeforeground=TEXT_WHITE,
            relief="flat", font=("Segoe UI", 9), cursor="hand2", padx=12
        )
        browse_btn.pack(side="right")

        # Progress & Status
        prog_frame = tk.Frame(self.root, bg=BG_DARK)
        prog_frame.pack(fill="x", padx=24, pady=4)

        self.progress_bar = ttk.Progressbar(prog_frame, style="Red.Horizontal.TProgressbar", mode="determinate")
        self.progress_bar.pack(fill="x", pady=(2, 6))

        self.status_label = tk.Label(prog_frame, textvariable=self.status_text, font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_DARK, anchor="w")
        self.status_label.pack(fill="x")

        # Download Button
        self.download_btn = tk.Button(
            self.root, text="DOWNLOAD MEDIA", command=self._start_download_thread,
            bg=ACCENT_RED, fg=TEXT_WHITE, activebackground="#cc0029", activeforeground=TEXT_WHITE,
            relief="flat", font=("Segoe UI", 11, "bold"), cursor="hand2", pady=10
        )
        self.download_btn.pack(fill="x", padx=24, pady=(8, 16))

    def _setup_clipboard_listener(self):
        self.root.bind("<FocusIn>", lambda e: self._check_clipboard())
        self._check_clipboard_loop()

    def _check_clipboard_loop(self):
        self._check_clipboard()
        self.root.after(2000, self._check_clipboard_loop)

    def _check_clipboard(self):
        try:
            clip = self.root.clipboard_get().strip()
            if clip and clip != self.last_clipboard:
                self.last_clipboard = clip
                match = YOUTUBE_URL_REGEX.search(clip)
                if match:
                    url = match.group(0)
                    if url != self.url_entry.get().strip():
                        self.url_entry.delete(0, tk.END)
                        self.url_entry.insert(0, url)
                        self.status_text.set("Auto-detected link from clipboard!")
                        self._fetch_metadata_thread()
        except tk.TclError:
            pass

    def _browse_folder(self):
        selected = filedialog.askdirectory(initialdir=self.download_dir.get())
        if selected:
            self.download_dir.set(selected)
            self._save_config()

    def _fetch_metadata_worker(self, url):
        try:
            self.status_text.set("Fetching video info...")
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self.cached_info = info

            thumb_url = info.get('thumbnail')
            if thumb_url:
                r = requests.get(thumb_url, timeout=10)
                img = Image.open(io.BytesIO(r.content))
                img = img.resize((180, 105), Image.Resampling.LANCZOS)
                self.thumb_photo = ImageTk.PhotoImage(img)
                self.thumb_label.config(image=self.thumb_photo, text="")

            channel = info.get('uploader') or info.get('channel') or "YouTube Creator"
            title_text = info.get('title') or "Untitled Video"
            views = info.get('view_count') or 0
            dur_sec = info.get('duration') or 0

            minutes, seconds = divmod(dur_sec, 60)
            hours, minutes = divmod(minutes, 60)
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"

            self.meta_channel.config(text=f"@{channel}")
            self.meta_title.config(text=title_text[:110] + ("..." if len(title_text) > 110 else ""))
            self.meta_stats.config(text=f"👁️ {views:,} views   •   ⏱️ {duration_str}")
            self.status_text.set("Ready to download.")

        except Exception:
            self.status_text.set("Failed to load video preview.")

    def _fetch_metadata_thread(self):
        url = self.url_entry.get().strip()
        if url:
            threading.Thread(target=self._fetch_metadata_worker, args=(url,), daemon=True).start()

    def _download_progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = (downloaded / total) * 100
                self.progress_bar['value'] = percent
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                speed = d.get('_speed_str', '').strip()
                self.status_text.set(f"Downloading: {percent:.1f}% ({mb_done:.1f}/{mb_total:.1f} MB) • {speed}")
            else:
                self.status_text.set("Downloading...")
        elif d['status'] == 'finished':
            self.progress_bar['value'] = 100
            self.status_text.set("Finalizing & merging streams with FFmpeg...")

    def _download_worker(self, url, out_folder, mode):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(out_folder, '%(title).80s [%(id)s].%(ext)s'),
                'ffmpeg_location': FFMPEG_BIN,
                'progress_hooks': [self._download_progress_hook],
                'quiet': True,
                'no_warnings': True,
            }

            if mode == "mp3":
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    # 'lang' first forces yt-dlp to prefer the ORIGINAL audio track
                    # over YouTube's auto-dubbed "translated" tracks before comparing bitrate.
                    'format_sort': ['lang', 'abr', 'br'],
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                # bv*+ba/b grabs the highest resolution vertical stream regardless of codec
                ydl_opts.update({
                    # Prefer H.264 (avc1) video when available. Many Shorts/high-res
                    # uploads only exist in VP9/AV1 though, so this alone isn't enough.
                    'format': 'bv*[vcodec^=avc1]+ba/bv*+ba/b',
                    'merge_output_format': 'mp4',
                    # 'lang' first forces yt-dlp to prefer the ORIGINAL audio track
                    # over YouTube's auto-dubbed "translated" tracks before comparing quality.
                    'format_sort': ['lang', 'vcodec:h264', 'res:1080', 'fps', 'br'],
                    # Force the merge step to ALWAYS transcode to H.264/AAC instead of
                    # stream-copying whatever codec was downloaded. This is what actually
                    # guarantees Premiere Pro compatibility even when only VP9/AV1 exists
                    # upstream (common on Shorts). Takes longer than a plain remux.
                    'postprocessor_args': {
                        'merger': ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-c:a', 'aac', '-b:a', '192k']
                    }
                })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.status_text.set("Completed successfully!")
            messagebox.showinfo("Success", f"Downloaded and saved to:\n{out_folder}")

        except Exception as e:
            self.status_text.set("Download failed.")
            messagebox.showerror("Error", f"Failed to download:\n{str(e)}")
        finally:
            self.is_downloading = False
            self.download_btn.config(state="normal")
            self.progress_bar['value'] = 0

    def _start_download_thread(self):
        url = self.url_entry.get().strip()
        path = self.download_dir.get().strip()
        mode = self.format_mode.get()

        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid YouTube URL.")
            return

        if self.is_downloading:
            return

        self.is_downloading = True
        self.download_btn.config(state="disabled")
        self.progress_bar['value'] = 0
        self.status_text.set("Initializing download stream...")

        threading.Thread(
            target=self._download_worker,
            args=(url, path, mode),
            daemon=True
        ).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()