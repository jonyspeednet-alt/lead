"""Windows known-folder helpers (no third-party dependency)."""
import ctypes
import uuid
from ctypes import wintypes

FOLDERID_Desktop = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDERID_Programs = "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}"          # user Start Menu\Programs
FOLDERID_CommonPrograms = "{0139D44E-6AFE-49F2-8690-3DAFCAE6FFB8}"  # all-users Start Menu\Programs
FOLDERID_LocalAppData = "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}"


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def known_folder(guid_str):
    """Return the absolute path of a known folder, e.g. FOLDERID_Desktop."""
    folder_id = _GUID()
    ctypes.memmove(
        ctypes.byref(folder_id),
        uuid.UUID(guid_str).bytes_le,
        ctypes.sizeof(_GUID),
    )

    out = ctypes.c_void_p()
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(folder_id), 0, None, ctypes.byref(out)
    )
    if hr != 0:
        raise OSError(f"SHGetKnownFolderPath failed for {guid_str}: HRESULT 0x{hr & 0xFFFFFFFF:08X}")

    try:
        return ctypes.wstring_at(out)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


def desktop_dir():
    return known_folder(FOLDERID_Desktop)


def programs_dir():
    """Per-user Start Menu\\Programs (writable without administrator rights)."""
    return known_folder(FOLDERID_Programs)


def local_app_data():
    return known_folder(FOLDERID_LocalAppData)
