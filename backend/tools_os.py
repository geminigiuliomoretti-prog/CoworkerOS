import os
import re
import sys
import time
import base64
import shutil
import ctypes
import zipfile
import subprocess
import webbrowser
import threading
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import httpx

# CONCORRENZA E PERCORSI AUTORIZZATI (FASE 1: HARDENING)
FILE_OPERATION_LOCK = threading.Lock()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.resolve()
FORBIDDEN_FILES = {".env", "coworkers.db", "coworkers.db.bak"}


def get_allowed_roots() -> List[Path]:
    """Returns the list of explicitly authorized workspace directories."""
    roots = [PROJECT_ROOT]
    extra = os.getenv("COWORKEROS_WORKSPACE_DIR")
    if extra:
        try:
            extra_p = Path(extra).resolve()
            if extra_p.exists():
                roots.append(extra_p)
        except Exception:
            pass
    return roots


def validate_file_path(target_path: str, must_exist: bool = False) -> Tuple[bool, Optional[Path], str]:
    """
    Strictly validates that target_path:
    1. Resolves (realpath) inside one of get_allowed_roots().
    2. Blocks traversal via symlinks, junctions, or '..' to external paths.
    3. Blocks access to sensitive configuration files (.env, coworkers.db).
    """
    if not target_path or not str(target_path).strip():
        return False, None, "Percorso vuoto non valido."

    try:
        raw_path = Path(str(target_path).strip()).expanduser()
        if not raw_path.is_absolute():
            raw_path = PROJECT_ROOT / raw_path

        # Resolve all symlinks, junctions, and relative parent steps
        real_path_str = os.path.realpath(str(raw_path))
        canonical_p = Path(real_path_str).resolve()

        allowed_roots = get_allowed_roots()
        is_within_allowed = False
        for root in allowed_roots:
            try:
                canonical_p.relative_to(root)
                is_within_allowed = True
                break
            except ValueError:
                continue

        if not is_within_allowed:
            return False, None, (
                f"Accesso negato: il percorso '{target_path}' risolve a '{canonical_p}', "
                f"che si trova al di fuori delle directory autorizzate ({PROJECT_ROOT})."
            )

        if canonical_p.name.lower() in FORBIDDEN_FILES or any(part.startswith(".env") for part in canonical_p.parts):
            return False, None, f"Accesso negato: il file '{canonical_p.name}' è protetto e non accessibile dagli agenti."

        if must_exist and not canonical_p.exists():
            return False, None, f"Percorso non trovato: '{target_path}'"

        return True, canonical_p, ""
    except Exception as e:
        return False, None, f"Errore validazione percorso: {e}"

# CONFIGURAZIONE IMMEDIATA HIGH-DPI WINDOWS 11 (2880x1920 @ 200% SCALING)
if sys.platform == "win32":
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.user32.SetProcessDPIAware = lambda: 1
    except Exception:
        pass

import pyautogui
import pyperclip
import pygetwindow as gw
from PIL import Image, ImageDraw, ImageStat, ImageGrab
import mss

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.08

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0
BI_RGB = 0
SW_RESTORE = 9
SW_SHOW = 5
VK_MENU = 0x12
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", ctypes.c_uint32 * 3),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def get_physical_screen_size() -> Tuple[int, int]:
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            if w > 0 and h > 0:
                return int(w), int(h)
        except Exception:
            pass
    size = pyautogui.size()
    return int(size.width), int(size.height)


def _is_image_black(img: Optional[Image.Image]) -> bool:
    if img is None:
        return True
    try:
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        min_val, max_val = stat.extrema[0]
        mean_val = stat.mean[0]
        std_val = stat.stddev[0]
        if max_val < 10 or (mean_val < 1.8 and std_val < 1.2):
            return True
        return False
    except Exception:
        return True


def _capture_via_win32_bitblt_captureblt(width: int, height: int) -> Optional[Image.Image]:
    if sys.platform != "win32":
        return None
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hdesktop = user32.GetDesktopWindow()
    hdc_screen = user32.GetWindowDC(hdesktop)
    if not hdc_screen:
        return None
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    if not hbmp:
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hdesktop, hdc_screen)
        return None

    old_obj = gdi32.SelectObject(hdc_mem, hbmp)
    try:
        ok = gdi32.BitBlt(
            hdc_mem, 0, 0, width, height,
            hdc_screen, 0, 0, SRCCOPY | CAPTUREBLT
        )
        if not ok:
            return None

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf_len = width * height * 4
        buffer = ctypes.create_string_buffer(buf_len)
        lines = gdi32.GetDIBits(
            hdc_mem, hbmp, 0, height, buffer, ctypes.byref(bmi), DIB_RGB_COLORS
        )
        if lines != height:
            return None

        img = Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
        return img.copy()
    except Exception:
        return None
    finally:
        gdi32.SelectObject(hdc_mem, old_obj)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hdesktop, hdc_screen)


def _capture_via_powershell_dotnet() -> Optional[Image.Image]:
    if sys.platform != "win32":
        return None
    try:
        tmp_path = Path(os.environ.get("TEMP", ".")) / "coworkeros_cap.png"
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height); "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
            f"$bmp.Save('{str(tmp_path)}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$g.Dispose(); $bmp.Dispose();"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            timeout=3.5,
            check=False,
            creationflags=creationflags
        )
        if tmp_path.exists():
            img = Image.open(tmp_path).convert("RGB")
            return img.copy()
    except Exception:
        pass
    return None


def _draw_som_grid_and_crosshair(
    img: Image.Image,
    real_w: int,
    real_h: int,
    highlight_x: Optional[int] = None,
    highlight_y: Optional[int] = None,
    draw_grid: bool = False
) -> Image.Image:
    annotated = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", annotated.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    out_w, out_h = annotated.size

    if draw_grid:
        for step in range(100, 1000, 100):
            gx = int((step / 1000.0) * out_w)
            gy = int((step / 1000.0) * out_h)
            draw.line([(gx, 0), (gx, out_h)], fill=(255, 255, 255, 45), width=1)
            draw.line([(0, gy), (out_w, gy)], fill=(255, 255, 255, 45), width=1)
        for nx in range(200, 1000, 200):
            for ny in range(200, 1000, 200):
                px = int((nx / 1000.0) * out_w)
                py = int((ny / 1000.0) * out_h)
                label = f"{nx},{ny}"
                draw.rectangle([px - 22, py - 8, px + 22, py + 8], fill=(17, 24, 39, 155))
                draw.text((px - 19, py - 6), label, fill=(255, 255, 255, 230))

    if highlight_x is not None and highlight_y is not None and real_w > 0 and real_h > 0:
        cx = int((highlight_x / float(real_w)) * out_w)
        cy = int((highlight_y / float(real_h)) * out_h)
        r_outer = 22
        r_inner = 7
        draw.ellipse(
            [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
            fill=(249, 115, 22, 75),
            outline=(249, 115, 22, 245),
            width=3
        )
        draw.ellipse(
            [cx - r_inner - 2, cy - r_inner - 2, cx + r_inner + 2, cy + r_inner + 2],
            fill=(255, 255, 255, 255)
        )
        draw.ellipse(
            [cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
            fill=(249, 115, 22, 255)
        )
        draw.line([(cx - 30, cy), (cx + 30, cy)], fill=(249, 115, 22, 230), width=2)
        draw.line([(cx, cy - 30), (cx, cy + 30)], fill=(249, 115, 22, 230), width=2)

    return Image.alpha_composite(annotated, overlay).convert("RGB")


def capture_screen_b64(
    highlight_x: Optional[int] = None,
    highlight_y: Optional[int] = None,
    draw_som_grid: bool = False
) -> Dict[str, Any]:
    real_w, real_h = get_physical_screen_size()
    captured_img: Optional[Image.Image] = None
    capture_method = "none"

    try:
        img1 = ImageGrab.grab(all_screens=False, include_layered_windows=True)
        if not _is_image_black(img1):
            captured_img = img1.convert("RGB")
            capture_method = "PIL.ImageGrab(layered)"
    except Exception:
        pass

    if captured_img is None:
        try:
            img2 = _capture_via_win32_bitblt_captureblt(real_w, real_h)
            if not _is_image_black(img2):
                captured_img = img2
                capture_method = "Win32.BitBlt(CAPTUREBLT)"
        except Exception:
            pass

    if captured_img is None:
        try:
            import dxcam  # type: ignore
            camera = dxcam.create(output_color="RGB")
            frame = camera.grab(new_frame_only=False)
            if frame is not None:
                img3 = Image.fromarray(frame)
                if not _is_image_black(img3):
                    captured_img = img3
                    capture_method = "DXcam.DXGI"
        except Exception:
            pass

    if captured_img is None:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                img_mss = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                if not _is_image_black(img_mss):
                    captured_img = img_mss
                    capture_method = "mss"
        except Exception:
            pass

    if captured_img is None:
        img4 = _capture_via_powershell_dotnet()
        if not _is_image_black(img4):
            captured_img = img4
            capture_method = "PowerShell.CopyFromScreen"

    if captured_img is None:
        captured_img = Image.new("RGB", (real_w, real_h), (28, 32, 42))
        d = ImageDraw.Draw(captured_img)
        d.text((60, 50), f"Desktop Map ({real_w}x{real_h})", fill=(255, 255, 255))
        for w_info in list_open_windows().get("windows_detailed", [])[:8]:
            b = w_info.get("bounds", {})
            l, t, r, btm = b.get("left", 100), b.get("top", 100), b.get("right", 800), b.get("bottom", 600)
            d.rectangle([l, t, r, btm], outline=(96, 165, 250), fill=(38, 45, 64), width=3)
            d.text((l + 20, t + 20), w_info.get("title", "Window"), fill=(255, 255, 255))
        capture_method = "Win32.WindowMapFallback"

    real_w, real_h = captured_img.size
    preview_img = captured_img.copy()
    preview_img.thumbnail((1440, 960), Image.Resampling.LANCZOS)

    annotated_img = _draw_som_grid_and_crosshair(
        preview_img,
        real_w=real_w,
        real_h=real_h,
        highlight_x=highlight_x,
        highlight_y=highlight_y,
        draw_grid=draw_som_grid
    )

    buf = BytesIO()
    annotated_img.save(buf, format="JPEG", quality=84)
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    norm_pct_x = round((highlight_x / float(real_w)) * 100.0, 1) if highlight_x is not None else 50.0
    norm_pct_y = round((highlight_y / float(real_h)) * 100.0, 1) if highlight_y is not None else 50.0

    return {
        "status": "ok",
        "capture_method": capture_method,
        "screenshot_b64": b64_str,
        "screen_width": real_w,
        "screen_height": real_h,
        "x": highlight_x,
        "y": highlight_y,
        "norm_pct_x": norm_pct_x,
        "norm_pct_y": norm_pct_y,
    }


def list_open_windows() -> Dict[str, Any]:
    windows_detailed: List[Dict[str, Any]] = []
    titles: List[str] = []

    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title and title not in ("Program Manager", "Settings", "Windows Input Experience"):
                        rect = RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > 80 and h > 80:
                            titles.append(title)
                            windows_detailed.append({
                                "hwnd": int(hwnd),
                                "title": title,
                                "bounds": {
                                    "left": int(rect.left),
                                    "top": int(rect.top),
                                    "right": int(rect.right),
                                    "bottom": int(rect.bottom),
                                    "width": int(w),
                                    "height": int(h),
                                }
                            })
            return True

        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
    else:
        try:
            for w in gw.getAllWindows():
                if w.title and w.visible:
                    titles.append(w.title)
        except Exception:
            pass

    return {
        "status": "ok",
        "count": len(titles),
        "windows": titles,
        "windows_detailed": windows_detailed,
    }


def force_activate_window(window_title_substring: str) -> Dict[str, Any]:
    target_sub = window_title_substring.strip().lower()
    win_data = list_open_windows().get("windows_detailed", [])

    candidates = [
        w for w in win_data
        if target_sub in w["title"].lower() and "coworkeros" not in w["title"].lower()
    ]
    if not candidates:
        candidates = [w for w in win_data if target_sub in w["title"].lower()]

    if not candidates:
        return {
            "status": "error",
            "message": f"Finestra '{window_title_substring}' non trovata.",
            "available_windows": [w["title"] for w in win_data[:12]],
        }

    chosen = candidates[0]
    hwnd = chosen["hwnd"]

    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.25)
            else:
                user32.ShowWindow(hwnd, SW_SHOW)

            user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

            fg_hwnd = user32.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
            target_tid = user32.GetWindowThreadProcessId(hwnd, None)
            cur_tid = kernel32.GetCurrentThreadId()

            if fg_tid and fg_tid != cur_tid:
                user32.AttachThreadInput(fg_tid, cur_tid, True)
            if target_tid and target_tid != cur_tid:
                user32.AttachThreadInput(target_tid, cur_tid, True)

            try:
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetFocus(hwnd)
            finally:
                if fg_tid and fg_tid != cur_tid:
                    user32.AttachThreadInput(fg_tid, cur_tid, False)
                if target_tid and target_tid != cur_tid:
                    user32.AttachThreadInput(target_tid, cur_tid, False)

            time.sleep(0.55)
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            chosen["bounds"] = {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
                "width": int(rect.right - rect.left),
                "height": int(rect.bottom - rect.top),
            }
        except Exception as e:
            return {"status": "error", "message": f"Errore attivazione finestra: {e}"}

    return {
        "status": "ok",
        "window_title": chosen["title"],
        "hwnd": hwnd,
        "bounds": chosen["bounds"],
    }


def norm_to_physical_coords(norm_x: int, norm_y: int) -> Tuple[int, int]:
    real_w, real_h = get_physical_screen_size()
    clamped_x = max(0, min(1000, int(norm_x)))
    clamped_y = max(0, min(1000, int(norm_y)))
    phys_x = int((clamped_x / 1000.0) * (real_w - 1))
    phys_y = int((clamped_y / 1000.0) * (real_h - 1))
    return phys_x, phys_y


def click_at_normalized_coords(
    norm_x: int,
    norm_y: int,
    double_click: bool = False,
    text_to_type: Optional[str] = None,
    press_enter: bool = False,
    approved: bool = False,
) -> Dict[str, Any]:
    if not approved:
        return {
            "status": "waiting_approval",
            "requires_approval": True,
            "action_type": "desktop_click",
            "norm_x": norm_x,
            "norm_y": norm_y,
            "text_to_type": text_to_type,
            "message": f"Clic alle coordinate ({norm_x}, {norm_y}) sul desktop richiede approvazione esplicita dell'utente.",
        }

    try:
        real_x, real_y = norm_to_physical_coords(norm_x, norm_y)
        pyautogui.moveTo(real_x, real_y, duration=0.28)
        if double_click:
            pyautogui.doubleClick(real_x, real_y)
        else:
            pyautogui.click(real_x, real_y)

        if text_to_type:
            time.sleep(0.18)
            pyperclip.copy(text_to_type)
            paste_key = "command" if sys.platform == "darwin" else "ctrl"
            pyautogui.hotkey(paste_key, "v")
            time.sleep(0.25)

        if press_enter:
            pyautogui.press("enter")
            time.sleep(0.35)

        cap = capture_screen_b64(highlight_x=real_x, highlight_y=real_y)
        return {
            "status": "ok",
            "message": f"Clic eseguito a ({real_x}, {real_y}) [norm: {norm_x}, {norm_y}]",
            "real_x": real_x,
            "real_y": real_y,
            **cap,
        }
    except Exception as e:
        cap = capture_screen_b64()
        return {"status": "error", "message": f"Errore clic: {e}", **cap}


def focus_and_paste_into_app(
    window_title_substring: str,
    text_to_paste: str,
    click_norm_x: Optional[int] = None,
    click_norm_y: Optional[int] = None,
    press_enter: bool = True,
    approved: bool = False,
) -> Dict[str, Any]:
    if not approved:
        return {
            "status": "waiting_approval",
            "requires_approval": True,
            "action_type": "desktop_paste",
            "window_title_substring": window_title_substring,
            "text_snippet": (text_to_paste[:80] + "...") if len(text_to_paste) > 80 else text_to_paste,
            "message": f"Attivazione finestra '{window_title_substring}' e invio testo richiedono approvazione esplicita dell'utente.",
        }

    focus_res = force_activate_window(window_title_substring)
    if focus_res.get("status") != "ok":
        cap = capture_screen_b64()
        return {**focus_res, **cap}

    bounds = focus_res["bounds"]
    real_w, real_h = get_physical_screen_size()

    if click_norm_x is not None and click_norm_y is not None:
        target_x, target_y = norm_to_physical_coords(click_norm_x, click_norm_y)
    else:
        win_left = max(0, bounds["left"])
        win_top = max(0, bounds["top"])
        win_w = min(real_w - win_left, bounds["width"])
        win_h = min(real_h - win_top, bounds["height"])
        target_x = int(win_left + win_w * 0.78)
        target_y = int(win_top + win_h * 0.88)

    try:
        pyperclip.copy(text_to_paste)
        pyautogui.moveTo(target_x, target_y, duration=0.3)
        pyautogui.click(target_x, target_y)
        time.sleep(0.22)

        paste_mod = "command" if sys.platform == "darwin" else "ctrl"
        pyautogui.hotkey(paste_mod, "v")
        time.sleep(0.35)

        if press_enter:
            pyautogui.press("enter")
            time.sleep(0.45)

        cap = capture_screen_b64(highlight_x=target_x, highlight_y=target_y)
        return {
            "status": "ok",
            "message": f"Finestra '{focus_res['window_title']}' attivata e testo incollato a ({target_x}, {target_y}).",
            "window_title": focus_res["window_title"],
            "real_x": target_x,
            "real_y": target_y,
            **cap,
        }
    except Exception as e:
        cap = capture_screen_b64()
        return {"status": "error", "message": f"Errore incollaggio: {e}", **cap}


def open_url_or_app(target: str, approved: bool = False) -> Dict[str, Any]:
    if not approved:
        return {
            "status": "waiting_approval",
            "requires_approval": True,
            "action_type": "open_target",
            "target": target,
            "message": f"Apertura applicazione o URL '{target}' richiede approvazione esplicita dell'utente.",
        }

    try:
        target_clean = target.strip()
        if target_clean.startswith("http://") or target_clean.startswith("https://"):
            webbrowser.open(target_clean)
            time.sleep(1.8)
        else:
            subprocess.Popen(target_clean, shell=True)
            time.sleep(1.5)
        cap = capture_screen_b64()
        return {"status": "ok", "message": f"Aperto target: {target_clean}", **cap}
    except Exception as e:
        cap = capture_screen_b64()
        return {"status": "error", "message": f"Impossibile aprire '{target}': {e}", **cap}


def manage_files(
    action: str,
    path: str,
    content: Optional[str] = None,
    destination: Optional[str] = None,
    approved: bool = False,
) -> Dict[str, Any]:
    act = action.lower().strip()
    is_mutation = act in ("write", "mkdir", "move", "delete")

    # 1. Require explicit user approval for destructive/mutating file operations
    if is_mutation and not approved:
        return {
            "status": "waiting_approval",
            "requires_approval": True,
            "action_type": f"file_{act}",
            "action": act,
            "path": path,
            "destination": destination,
            "message": f"Azione di modifica file '{act}' per il percorso '{path}' richiede approvazione esplicita dell'utente.",
        }

    # 2. Strict path validation against allowed workspace directories & forbidden files
    is_valid, p, err = validate_file_path(path, must_exist=(act in ("read", "list")))
    if not is_valid or p is None:
        return {"status": "error", "message": err, "blocked": True}

    if destination and act == "move":
        dest_valid, dest_p, dest_err = validate_file_path(destination, must_exist=False)
        if not dest_valid or dest_p is None:
            return {"status": "error", "message": f"Destinazione non valida: {dest_err}", "blocked": True}
    else:
        dest_p = None

    # 3. Synchronized file mutation with concurrency lock
    with FILE_OPERATION_LOCK:
        try:
            if act == "list":
                if not p.exists():
                    return {"status": "error", "message": f"Percorso non trovato: {p}"}
                items = [
                    {"name": item.name, "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else 0}
                    for item in list(p.iterdir())[:100]
                    if item.name.lower() not in FORBIDDEN_FILES
                ]
                return {"status": "ok", "path": str(p), "items": items}
            elif act == "read":
                text = p.read_text(encoding="utf-8", errors="replace")
                return {"status": "ok", "path": str(p), "content": text[:15000]}
            elif act == "write":
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content or "", encoding="utf-8")
                return {"status": "ok", "path": str(p), "message": f"Scritto file ({len(content or '')} caratteri)."}
            elif act == "mkdir":
                p.mkdir(parents=True, exist_ok=True)
                return {"status": "ok", "path": str(p), "message": "Cartella creata."}
            elif act == "move" and dest_p:
                dest_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dest_p))
                return {"status": "ok", "message": f"Spostato da {p} a {dest_p}."}
            elif act == "delete":
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()
                return {"status": "ok", "message": f"Eliminato {p}."}
            return {"status": "error", "message": f"Azione non supportata: {action}"}
        except Exception as e:
            return {"status": "error", "message": f"Errore file system: {e}"}


def run_terminal_command(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Arbitrary shell commands are explicitly disabled for agent safety in Phase 1."""
    return {
        "status": "error",
        "message": "Esecuzione comandi shell disabilitata per motivi di sicurezza (Hardening Fase 1).",
        "blocked": True,
    }


def search_files(query: str, path: str = ".", max_results: int = 50) -> Dict[str, Any]:
    """
    Cerca file o cartelle ricorsivamente nell'area di lavoro autorizzata in base al nome o pattern.
    Esclude automaticamente directory pesanti (node_modules, .git, venv) e file protetti (.env).
    """
    if not query or not query.strip():
        return {"status": "error", "message": "Query di ricerca non valida o vuota."}

    is_valid, base_p, err = validate_file_path(path, must_exist=True)
    if not is_valid or base_p is None:
        return {"status": "error", "message": err, "blocked": True}

    q = query.strip().lower()
    matches = []
    ignored_dirs = {"node_modules", ".git", "venv", "__pycache__", ".idea", ".vscode", "dist", "build"}

    try:
        for root, dirs, files in os.walk(base_p):
            dirs[:] = [d for d in dirs if d.lower() not in ignored_dirs and not d.startswith(".")]
            for f in files:
                if f.lower() in FORBIDDEN_FILES or f.startswith(".env"):
                    continue
                file_full = Path(root) / f
                rel = str(file_full.relative_to(PROJECT_ROOT)).replace("\\", "/")
                if q in f.lower() or q in rel.lower():
                    matches.append({
                        "name": f,
                        "relative_path": rel,
                        "size_bytes": file_full.stat().st_size if file_full.exists() else 0,
                    })
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        return {
            "status": "ok",
            "query": query,
            "total_matches": len(matches),
            "matches": matches,
        }
    except Exception as e:
        return {"status": "error", "message": f"Errore durante la ricerca file: {e}"}


def read_document(path: str, max_lines: int = 250, max_chars: int = 25000) -> Dict[str, Any]:
    """
    Legge un documento di testo, markdown, codice, json o csv con limiti di sicurezza.
    """
    is_valid, p, err = validate_file_path(path, must_exist=True)
    if not is_valid or p is None:
        return {"status": "error", "message": err, "blocked": True}

    if p.is_dir():
        return {
            "status": "error",
            "message": f"'{path}' è una cartella, non un file. Usa manage_files con action='list' per esaminarla."
        }

    try:
        raw_text = p.read_text(encoding="utf-8", errors="replace")
        lines = raw_text.splitlines()
        truncated = False
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        content = "\n".join(lines)
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True

        return {
            "status": "ok",
            "path": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "file_name": p.name,
            "line_count": len(lines),
            "truncated": truncated,
            "content": content,
        }
    except Exception as e:
        return {"status": "error", "message": f"Errore lettura documento '{path}': {e}"}


def inspect_zip(zip_path: str, action: str = "list", file_to_read: Optional[str] = None) -> Dict[str, Any]:
    """
    Ispezione sicura di archivi ZIP in sola lettura.
    Previene attacchi di path traversal (Zip Slip) e non estrae file su disco.
    """
    is_valid, p, err = validate_file_path(zip_path, must_exist=True)
    if not is_valid or p is None:
        return {"status": "error", "message": err, "blocked": True}

    if not zipfile.is_zipfile(p):
        return {"status": "error", "message": f"Il file '{zip_path}' non è un archivio ZIP valido."}

    try:
        with zipfile.ZipFile(p, "r") as zf:
            if action == "list":
                entries = []
                for info in zf.infolist()[:120]:
                    entries.append({
                        "filename": info.filename,
                        "file_size": info.file_size,
                        "compress_size": info.compress_size,
                        "is_dir": info.is_dir(),
                    })
                return {
                    "status": "ok",
                    "zip_path": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "total_entries": len(zf.namelist()),
                    "entries": entries,
                }
            elif action == "read":
                if not file_to_read:
                    return {"status": "error", "message": "Specifica 'file_to_read' per leggere un file dall'archivio ZIP."}
                clean_target = file_to_read.strip().replace("\\", "/").lstrip("/")
                if ".." in clean_target:
                    return {"status": "error", "message": "Percorso non consentito all'interno dell'archivio (path traversal bloccato)."}

                matching = [n for n in zf.namelist() if n == clean_target or n.endswith("/" + clean_target)]
                if not matching:
                    return {"status": "error", "message": f"File '{file_to_read}' non trovato all'interno dell'archivio ZIP."}

                target_name = matching[0]
                with zf.open(target_name) as f_entry:
                    content_bytes = f_entry.read(25000)
                    content_text = content_bytes.decode("utf-8", errors="replace")

                return {
                    "status": "ok",
                    "zip_path": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "file_name": target_name,
                    "content": content_text,
                }
            else:
                return {"status": "error", "message": f"Azione '{action}' non supportata su archivio ZIP (usa 'list' o 'read')."}
    except Exception as e:
        return {"status": "error", "message": f"Errore ispezione archivio ZIP: {e}"}


def browse_url(url: str, max_chars: int = 5000) -> Dict[str, Any]:
    """
    Legge il contenuto testuale di una pagina web tramite richiesta HTTP sicura in sola lettura.
    """
    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        return {"status": "error", "message": "URL non valido: deve iniziare con http:// o https://"}

    try:
        headers = {"User-Agent": "CoworkerOS/1.0 (Windows 11; x64; Research Agent)"}
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(clean_url)
            if resp.status_code >= 400:
                return {"status": "error", "message": f"Il server remoto ha risposto con codice HTTP {resp.status_code}."}

            content_type = resp.headers.get("content-type", "").lower()
            if "text" not in content_type and "json" not in content_type and "html" not in content_type:
                return {
                    "status": "ok",
                    "url": clean_url,
                    "content_type": content_type,
                    "message": f"Risorsa non testuale ricevuta ({content_type}, {len(resp.content)} bytes).",
                }

            html = resp.text
            # Estrazione titolo
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Senza titolo"

            # Rimozione script, style e tag HTML per ottenere testo pulito
            clean_text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()

            return {
                "status": "ok",
                "url": clean_url,
                "title": title,
                "text": clean_text[:max_chars],
                "text_content": clean_text[:max_chars],
            }
    except Exception as e:
        return {"status": "error", "message": f"Impossibile consultare '{url}': {e}"}


def list_windows(filter_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Elenca le finestre attualmente aperte sul desktop Windows 11 con filtro opzionale.
    """
    raw_res = list_open_windows()
    if not filter_str:
        return raw_res

    f_sub = filter_str.strip().lower()
    filtered = [w for w in raw_res.get("windows_detailed", []) if f_sub in w["title"].lower()]
    return {
        "status": "ok",
        "filter": filter_str,
        "count": len(filtered),
        "windows": [w["title"] for w in filtered],
        "windows_detailed": filtered,
    }

