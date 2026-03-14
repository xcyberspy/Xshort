import customtkinter as ctk
import requests
import json
import os
import webbrowser
import threading
from datetime import datetime
from tkinter import messagebox
from PIL import Image, ImageTk

BITLY_TOKEN  = "YOUR API TOKEN HERE"
BITLY_BASE   = "https://api-ssl.bitly.com/v4"
HISTORY_FILE = "url_history.json"

HEADERS = {
    "Authorization": f"Bearer {BITLY_TOKEN}",
    "Content-Type":  "application/json",
}


def get_default_group():
    try:
        r = requests.get(f"{BITLY_BASE}/user", headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json().get("default_group_guid")
    except requests.RequestException:
        pass
    return None


def check_alias_availability(alias):
    try:
        r = requests.get(
            f"{BITLY_BASE}/bitlinks/bit.ly/{alias}",
            headers=HEADERS,
            timeout=6,
        )
        return r.status_code == 404
    except requests.RequestException:
        return False


def shorten_url(long_url, alias=""):
    group_guid = get_default_group()
    payload = {"long_url": long_url}
    if group_guid:
        payload["group_guid"] = group_guid
    if alias.strip():
        payload["custom_bitlinks"] = [f"bit.ly/{alias.strip()}"]
    try:
        r = requests.post(f"{BITLY_BASE}/shorten", headers=HEADERS,
                          json=payload, timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            short_link = data.get("link", "")
            if alias.strip() and group_guid and short_link:
                _apply_custom_alias(short_link, alias.strip(), group_guid)
                short_link = f"https://bit.ly/{alias.strip()}"
            return {"success": True, "link": short_link, "id": data.get("id", "")}
        else:
            err = r.json().get("description", r.text)
            return {"success": False, "error": err}
    except requests.RequestException as exc:
        return {"success": False, "error": str(exc)}


def _apply_custom_alias(bitlink_id, alias, group_guid):
    try:
        payload = {
            "custom_bitlink": f"bit.ly/{alias}",
            "bitlink_id": bitlink_id.replace("https://", ""),
        }
        requests.post(f"{BITLY_BASE}/custom_bitlinks",
                      headers=HEADERS, json=payload, timeout=8)
    except requests.RequestException:
        pass


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except IOError as exc:
        print(f"Could not save history: {exc}")


class URLShortenerApp(ctk.CTk):

    CLR_BG      = "#0d0d0d"
    CLR_SURFACE = "#161616"
    CLR_BORDER  = "#2a2a2a"
    CLR_ACCENT  = "#00e5a0"
    CLR_ACCENT2 = "#0099ff"
    CLR_TEXT    = "#e8e8e8"
    CLR_SUBTEXT = "#707070"
    CLR_OK      = "#00c87a"
    CLR_ERR     = "#ff4d6d"

    def __init__(self):
        super().__init__()

        self.title("XShort — URL Shortener")
        self.geometry("820x860")
        self.minsize(700, 720)
        self.configure(fg_color=self.CLR_BG)
        ctk.set_appearance_mode("dark")

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "url.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                try:
                    img = Image.open(icon_path)
                    self._icon_photo = ImageTk.PhotoImage(img)
                    self.iconphoto(True, self._icon_photo)
                except Exception:
                    pass

        self.history          = load_history()
        self.current_short    = ""
        self._alias_check_id  = None
        self._alias_available = None

        self._build_ui()
        self._refresh_history_list()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color=self.CLR_SURFACE,
                              corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        self.back_btn = ctk.CTkButton(
            header,
            text="← Back",
            width=80, height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1e1e1e",
            hover_color="#2a2a2a",
            text_color=self.CLR_SUBTEXT,
            border_width=1,
            border_color=self.CLR_BORDER,
            corner_radius=7,
            command=self._go_back,
        )
        self.back_btn.grid(row=0, column=0, padx=16, pady=16, sticky="w")

        ctk.CTkLabel(
            header,
            text="✂  XShort",
            font=ctk.CTkFont(family="Courier New", size=26, weight="bold"),
            text_color=self.CLR_ACCENT,
        ).grid(row=0, column=0, padx=0, pady=16)

        ctk.CTkLabel(
            header,
            text="Powered by xcyberspy",
            font=ctk.CTkFont(size=11),
            text_color=self.CLR_SUBTEXT,
        ).grid(row=0, column=0, padx=24, pady=16, sticky="e")

        card = ctk.CTkFrame(self, fg_color=self.CLR_SURFACE,
                            corner_radius=12, border_width=1,
                            border_color=self.CLR_BORDER)
        card.grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 8))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Long URL",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self.CLR_SUBTEXT).grid(
            row=0, column=0, padx=(20, 10), pady=(20, 4), sticky="w")

        self.url_entry = ctk.CTkEntry(
            card,
            placeholder_text="https://example.com/very/long/path?query=value",
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color="#1e1e1e",
            border_color=self.CLR_BORDER,
            text_color=self.CLR_TEXT,
        )
        self.url_entry.grid(row=0, column=1, columnspan=2,
                            padx=(0, 20), pady=(20, 4), sticky="ew")

        ctk.CTkLabel(card, text="Custom Alias",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self.CLR_SUBTEXT).grid(
            row=1, column=0, padx=(20, 10), pady=(4, 4), sticky="w")

        alias_frame = ctk.CTkFrame(card, fg_color="transparent")
        alias_frame.grid(row=1, column=1, columnspan=2,
                         padx=(0, 20), pady=(4, 4), sticky="ew")
        alias_frame.grid_columnconfigure(0, weight=1)

        prefix = ctk.CTkFrame(alias_frame, fg_color="#1e1e1e",
                              corner_radius=6, border_width=1,
                              border_color=self.CLR_BORDER, height=42)
        prefix.grid(row=0, column=0, sticky="ew")
        prefix.grid_propagate(False)
        prefix.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(prefix, text="bit.ly/",
                     font=ctk.CTkFont(family="Courier New", size=13),
                     text_color=self.CLR_SUBTEXT).grid(
            row=0, column=0, padx=(10, 0), sticky="w")

        self.alias_entry = ctk.CTkEntry(
            prefix,
            placeholder_text="(optional) Maximum:40 characters",
            height=42, border_width=0,
            fg_color="transparent",
            font=ctk.CTkFont(family="Courier New", size=13),
            text_color=self.CLR_TEXT,
        )
        self.alias_entry.grid(row=0, column=1, sticky="ew", padx=(4, 4))
        self.alias_entry.bind("<KeyRelease>", self._on_alias_keyrelease)

        self.alias_badge = ctk.CTkLabel(
            alias_frame, text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=110,
        )
        self.alias_badge.grid(row=0, column=1, padx=(8, 0))

        self.shorten_btn = ctk.CTkButton(
            card,
            text="✂  Shorten URL",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.CLR_ACCENT,
            hover_color="#00c48a",
            text_color="#000000",
            corner_radius=8,
            command=self._on_shorten,
        )
        self.shorten_btn.grid(row=2, column=0, columnspan=3,
                              padx=20, pady=(12, 20), sticky="ew")

        self.result_frame = ctk.CTkFrame(
            self, fg_color=self.CLR_SURFACE, corner_radius=12,
            border_width=1, border_color=self.CLR_BORDER,
        )
        self.result_frame.grid(row=1, column=0, sticky="ew",
                               padx=20, pady=(0, 8))
        self.result_frame.grid_columnconfigure(0, weight=1)
        self.result_frame.grid_remove()

        ctk.CTkLabel(self.result_frame, text="Shortened URL",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=self.CLR_SUBTEXT).grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        self.result_label = ctk.CTkLabel(
            self.result_frame, text="",
            font=ctk.CTkFont(family="Courier New", size=15, weight="bold"),
            text_color=self.CLR_ACCENT,
        )
        self.result_label.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        btn_row = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="w")

        self.open_btn = ctk.CTkButton(
            btn_row, text="↗  Open",
            width=110, height=36,
            font=ctk.CTkFont(size=13),
            fg_color=self.CLR_ACCENT2,
            hover_color="#007acc",
            text_color="#ffffff",
            corner_radius=6,
            command=self._open_in_browser,
        )
        self.open_btn.pack(side="left", padx=(0, 8))

        self.copy_btn = ctk.CTkButton(
            btn_row, text="⎘  Copy",
            width=110, height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#2a2a2a",
            hover_color="#3a3a3a",
            text_color=self.CLR_TEXT,
            border_width=1,
            border_color=self.CLR_BORDER,
            corner_radius=6,
            command=self._copy_to_clipboard,
        )
        self.copy_btn.pack(side="left")

        history_header = ctk.CTkFrame(self, fg_color="transparent")
        history_header.grid(row=2, column=0, sticky="new", padx=20, pady=(4, 0))
        history_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(history_header, text="History",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=self.CLR_TEXT).grid(
            row=0, column=0, sticky="w")

        self.history_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=self.CLR_SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=self.CLR_BORDER,
            scrollbar_button_color=self.CLR_BORDER,
        )
        self.history_scroll.grid(row=2, column=0, sticky="nsew",
                                 padx=20, pady=(8, 20))
        self.history_scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

    def _on_alias_keyrelease(self, _event=None):
        if self._alias_check_id:
            self.after_cancel(self._alias_check_id)
        alias = self.alias_entry.get().strip()
        if not alias:
            self.alias_badge.configure(text="")
            return
        self.alias_badge.configure(text="⏳ checking…", text_color=self.CLR_SUBTEXT)
        self._alias_check_id = self.after(600, self._run_alias_check)

    def _run_alias_check(self):
        alias = self.alias_entry.get().strip()
        if not alias:
            return
        threading.Thread(
            target=self._fetch_alias_availability,
            args=(alias,), daemon=True,
        ).start()

    def _fetch_alias_availability(self, alias):
        available = check_alias_availability(alias)
        self._alias_available = available
        self.after(0, self._update_alias_badge, available)

    def _update_alias_badge(self, available):
        if available:
            self.alias_badge.configure(text="✔ Available", text_color=self.CLR_OK)
        else:
            self.alias_badge.configure(text="✖ Taken", text_color=self.CLR_ERR)

    def _on_shorten(self):
        long_url = self.url_entry.get().strip()
        alias    = self.alias_entry.get().strip()

        if not long_url:
            messagebox.showwarning("Missing URL", "Please enter a URL to shorten.")
            return

        if not long_url.startswith(("http://", "https://")):
            long_url = "https://" + long_url
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, long_url)

        for entry in self.history:
            if entry["long_url"].rstrip("/") == long_url.rstrip("/"):
                messagebox.showerror(
                    "Already Shortened",
                    f"This link has already been shortened.\n\n"
                    f"Your short URL:  {entry['short_url']}\n\n"
                    f"You can find it in your history below.",
                )
                return

        self.shorten_btn.configure(state="disabled", text="⏳  Working…")
        threading.Thread(
            target=self._shorten_worker,
            args=(long_url, alias), daemon=True,
        ).start()

    def _shorten_worker(self, long_url, alias):
        result = shorten_url(long_url, alias)
        self.after(0, self._handle_shorten_result, result, long_url)

    def _handle_shorten_result(self, result, long_url):
        self.shorten_btn.configure(state="normal", text="✂  Shorten URL")

        if result["success"]:
            short_link = result["link"]
            self.current_short = short_link

            self.result_frame.grid()
            self.result_label.configure(text=short_link)

            entry = {
                "long_url":   long_url,
                "short_url":  short_link,
                "id":         result.get("id", short_link.replace("https://", "")),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            self.history.insert(0, entry)
            save_history(self.history)
            self._refresh_history_list()
        else:
            messagebox.showerror("Bitly Error", result.get("error", "Unknown error"))

    def _open_in_browser(self):
        if not self.current_short:
            return
        webbrowser.open(self.current_short)

    def _copy_to_clipboard(self):
        if not self.current_short:
            return
        self.clipboard_clear()
        self.clipboard_append(self.current_short)
        self.copy_btn.configure(text="✔  Copied!")
        self.after(1500, lambda: self.copy_btn.configure(text="⎘  Copy"))

    def _refresh_history_list(self):
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        if not self.history:
            ctk.CTkLabel(
                self.history_scroll,
                text="No history yet — shorten a URL to get started.",
                font=ctk.CTkFont(size=12),
                text_color=self.CLR_SUBTEXT,
            ).grid(row=0, column=0, padx=20, pady=30)
            return

        for idx, entry in enumerate(self.history):
            self._build_history_row(idx, entry)

    def _build_history_row(self, idx, entry):
        row_frame = ctk.CTkFrame(
            self.history_scroll,
            fg_color="#1a1a1a",
            corner_radius=8,
            border_width=1,
            border_color=self.CLR_BORDER,
        )
        row_frame.grid(row=idx, column=0, sticky="ew", padx=8, pady=4)
        row_frame.grid_columnconfigure(0, weight=1)
        self.history_scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            row_frame,
            text=entry["short_url"],
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            text_color=self.CLR_ACCENT,
            cursor="hand2",
        ).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")

        long_display = entry["long_url"]
        if len(long_display) > 70:
            long_display = long_display[:68] + "…"
        ctk.CTkLabel(
            row_frame,
            text=long_display,
            font=ctk.CTkFont(size=11),
            text_color=self.CLR_SUBTEXT,
        ).grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        meta = ctk.CTkFrame(row_frame, fg_color="transparent")
        meta.grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="ew")
        meta.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            meta,
            text=entry.get("created_at", ""),
            font=ctk.CTkFont(size=10),
            text_color=self.CLR_SUBTEXT,
        ).grid(row=0, column=0, padx=(0, 16))

        ctk.CTkButton(
            meta,
            text="Open",
            width=60, height=26,
            font=ctk.CTkFont(size=11),
            fg_color=self.CLR_ACCENT2,
            hover_color="#007acc",
            text_color="#fff",
            corner_radius=5,
            command=lambda e=entry: self._open_history_entry(e),
        ).grid(row=0, column=2, padx=(8, 0))

        ctk.CTkButton(
            meta,
            text="Copy",
            width=60, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#2a2a2a",
            hover_color="#3a3a3a",
            text_color=self.CLR_TEXT,
            border_width=1,
            border_color=self.CLR_BORDER,
            corner_radius=5,
            command=lambda url=entry["short_url"]: self._copy_arbitrary(url),
        ).grid(row=0, column=3, padx=(4, 0))

        ctk.CTkButton(
            meta,
            text="Delete",
            width=60, height=26,
            font=ctk.CTkFont(size=11),
            fg_color=self.CLR_ERR,
            hover_color="#d63854",
            text_color="#fff",
            corner_radius=5,
            command=lambda idx=idx: self._delete_history_entry(idx),
        ).grid(row=0, column=4, padx=(4, 0))

    def _open_history_entry(self, entry):
        webbrowser.open(entry["short_url"])

    def _copy_arbitrary(self, url):
        self.clipboard_clear()
        self.clipboard_append(url)

    def _delete_history_entry(self, idx):
        if 0 <= idx < len(self.history):
            self.history.pop(idx)
            save_history(self.history)
            self._refresh_history_list()

    def _go_back(self):
        self.result_frame.grid_remove()
        self.url_entry.delete(0, "end")
        self.alias_entry.delete(0, "end")
        self.alias_badge.configure(text="")
        self.current_short = ""


if __name__ == "__main__":
    app = URLShortenerApp()
    app.mainloop()