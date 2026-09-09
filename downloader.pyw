import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yt_dlp

class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("520x330")
        self.root.resizable(False, False)

        # Output directory & format selection
        self.download_path = tk.StringVar(value=os.path.expanduser("~/Downloads"))
        self.format_mode = tk.StringVar(value="Video (MP4)")

        self._build_ui()

    def _build_ui(self):
        # URL Input
        lbl_url = ttk.Label(self.root, text="Video URL:")
        lbl_url.pack(anchor="w", padx=20, pady=(15, 5))

        self.entry_url = ttk.Entry(self.root, width=58)
        self.entry_url.pack(padx=20, pady=0)

        # Path Selection
        lbl_dir = ttk.Label(self.root, text="Save To:")
        lbl_dir.pack(anchor="w", padx=20, pady=(12, 5))

        dir_frame = ttk.Frame(self.root)
        dir_frame.pack(fill="x", padx=20)

        self.entry_path = ttk.Entry(dir_frame, textvariable=self.download_path, width=45)
        self.entry_path.pack(side="left", fill="x", expand=True)

        btn_browse = ttk.Button(dir_frame, text="Browse", command=self._browse_dir)
        btn_browse.pack(side="right", padx=(8, 0))

        # Format / Mode Selection
        format_frame = ttk.Frame(self.root)
        format_frame.pack(fill="x", padx=20, pady=(12, 0))

        lbl_format = ttk.Label(format_frame, text="Download As:")
        lbl_format.pack(side="left")

        combo_format = ttk.Combobox(
            format_frame, 
            textvariable=self.format_mode, 
            values=["Video (MP4)", "Audio Only (MP3)"], 
            state="readonly",
            width=18
        )
        combo_format.pack(side="left", padx=(10, 0))

        # Status & Progress
        self.lbl_status = ttk.Label(self.root, text="Ready", foreground="gray")
        self.lbl_status.pack(padx=20, pady=(15, 5))

        # Download Button
        self.btn_download = ttk.Button(self.root, text="Download", command=self._start_download_thread)
        self.btn_download.pack(pady=5)

    def _browse_dir(self):
        selected_dir = filedialog.askdirectory(initialdir=self.download_path.get())
        if selected_dir:
            self.download_path.set(selected_dir)

    def _update_status(self, text, color="black"):
        self.lbl_status.config(text=text, foreground=color)

    def _download_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            speed = d.get('_speed_str', '').strip()
            eta = d.get('_eta_str', '').strip()
            self._update_status(f"Downloading: {percent} | Speed: {speed} | ETA: {eta}")
        elif d['status'] == 'finished':
            self._update_status("Processing file with FFmpeg...", "blue")

    def _run_download(self, url, output_dir, mode):
        ydl_opts = {
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [self._download_hook],
            'quiet': True,
            'no_warnings': True,
        }

        if mode == "Audio Only (MP3)":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Targets AVC (H.264) video and m4a (AAC) audio for native Windows playback
            ydl_opts.update({
                'format': 'bestvideo[vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self._update_status("Download Complete!", "green")
            messagebox.showinfo("Success", f"{mode} downloaded successfully!")
        except Exception as e:
            self._update_status("Download Failed", "red")
            messagebox.showerror("Error", f"Failed to download:\n{str(e)}")
        finally:
            self.btn_download.config(state="normal")

    def _start_download_thread(self):
        url = self.entry_url.get().strip()
        path = self.download_path.get().strip()
        mode = self.format_mode.get()

        if not url:
            messagebox.showwarning("Warning", "Please enter a valid YouTube URL.")
            return

        if not os.path.isdir(path):
            messagebox.showwarning("Warning", "Selected save directory does not exist.")
            return

        self.btn_download.config(state="disabled")
        self._update_status("Fetching stream info...", "blue")

        worker = threading.Thread(
            target=self._run_download, 
            args=(url, path, mode), 
            daemon=True
        )
        worker.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderApp(root)
    root.mainloop()