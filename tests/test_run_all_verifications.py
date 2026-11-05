import io
import sys

from scripts.run_all_verifications import _run


def test_run_streams_utf8_output_to_a_legacy_windows_console(monkeypatch):
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)

    code = _run(
        "UTF-8 output probe",
        [sys.executable, "-X", "utf8", "-c", "print(chr(0x2714))"],
        False,
        io.StringIO(),
    )

    console.flush()
    assert code == 0
    assert "✔" in console.buffer.getvalue().decode("utf-8")
