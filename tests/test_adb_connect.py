"""Pure-logic contract for `android/tools/adb_connect.sh` (the Pixel E4-archive
connect helper).

WHY THESE THREE FUNCTIONS. The script's whole value is telling two failures
apart that look identical from the outside:

  * "the wireless-debug port drifted again"  -> rescan, exit 3
  * "the device is right there but refuses this host's client cert" -> exit 4,
    which no amount of retrying fixes; it needs Joshua at the phone.

That discrimination is done entirely by parsing adb's text, so the parsers are
the thing worth pinning.

WHY WE SHELL OUT INSTEAD OF RE-IMPLEMENTING IN PYTHON. The functions ship as
bash. A Python port of them in the test file would be a *second* implementation
that could silently drift from the one that actually runs. So the script exposes
its pure functions through a `--selftest-fn` dispatcher and we call those --
these tests exercise the exact code path production uses.

PROVENANCE OF THE FIXTURES. Every string marked CAPTURED was recorded from
adb 37.0.0-14910828 on this box on 2026-08-12 against the real Pixel at
100.64.4.100 (see the git commit message for the session). Strings marked
UPSTREAM-FORMAT are the populated `adb mdns services` listing, which cannot be
produced here at all -- mDNS is link-local multicast and reaches neither across
tailscale nor into the WSL2 VM, so the list is always empty locally. Those cases
are shaped from adb's documented `name / service-type / host:port` columns and
the parser is deliberately written to be column-order tolerant so that the one
format we could not capture cannot break it.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest

SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "android" / "tools" / "adb_connect.sh"
)


def run_fn(fn: str, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    """Call one of the script's exported pure functions."""
    return subprocess.run(
        ["bash", str(SCRIPT), "--selftest-fn", fn, *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_script_exists_and_is_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, "adb_connect.sh must be executable"


def test_script_is_syntactically_valid():
    got = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert got.returncode == 0, got.stderr


# ---------------------------------------------------------------------------
# parse_port_range
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "spec,expected",
    [
        ("30000-50000", "30000 50000"),   # the default wireless-debug range
        ("44749", "44749 44749"),         # a bare port probes exactly that port
        ("1-65535", "1 65535"),           # full legal span
        ("5555-5555", "5555 5555"),       # degenerate but legal
    ],
)
def test_parse_port_range_accepts_valid(spec, expected):
    got = run_fn("parse_port_range", spec)
    assert got.returncode == 0, got.stderr
    assert got.stdout.strip() == expected


@pytest.mark.parametrize(
    "spec,because",
    [
        ("", "empty"),
        ("abc", "not numeric"),
        ("30000-", "half-open range"),
        ("-50000", "half-open range"),
        ("0-100", "port 0 is out of range"),
        ("30000-70000", "above 65535"),
        ("50000-30000", "reversed"),
        ("30000 50000", "space is not the separator"),
        ("3e4-5e4", "no scientific notation"),
    ],
)
def test_parse_port_range_rejects_invalid(spec, because):
    got = run_fn("parse_port_range", spec)
    assert got.returncode != 0, f"should have rejected {spec!r} ({because})"
    assert got.stdout.strip() == "", "must not emit a range when rejecting"
    assert "port-range" in got.stderr, "should say what was wrong"


# ---------------------------------------------------------------------------
# parse_mdns_services
# ---------------------------------------------------------------------------

# CAPTURED 2026-08-12: `adb mdns services` on this box. The daemon is running
# (`adb mdns check` reports "mdns daemon version [adb discovery 0.0.0]") and the
# list is STILL empty -- this is structural, not a transient miss.
MDNS_EMPTY_CAPTURED = "List of discovered mdns services\n\n"

# UPSTREAM-FORMAT (see module docstring): a populated listing.
MDNS_POPULATED = (
    "List of discovered mdns services\n"
    "adb-31161FDH2003ZW-K3sNIY\t_adb-tls-connect._tcp\t100.64.4.100:42423\n"
)

# UPSTREAM-FORMAT: both a pairing and a connect endpoint advertised at once.
# The pairing port MUST be ignored -- `adb connect` to a pairing port fails in a
# way that looks like a dead device, which is a classic hour-waster.
MDNS_BOTH = (
    "List of discovered mdns services\n"
    "adb-31161FDH2003ZW-K3sNIY\t_adb-tls-pairing._tcp\t100.64.4.100:37121\n"
    "adb-31161FDH2003ZW-K3sNIY\t_adb-tls-connect._tcp\t100.64.4.100:42423\n"
)


def test_parse_mdns_empty_captured_yields_nothing():
    got = run_fn("parse_mdns_services", stdin=MDNS_EMPTY_CAPTURED)
    assert got.returncode == 0, got.stderr
    assert got.stdout.strip() == ""


def test_parse_mdns_extracts_connect_endpoint():
    got = run_fn("parse_mdns_services", stdin=MDNS_POPULATED)
    assert got.returncode == 0, got.stderr
    assert got.stdout.strip() == "100.64.4.100:42423"


def test_parse_mdns_ignores_pairing_endpoint():
    got = run_fn("parse_mdns_services", stdin=MDNS_BOTH)
    assert got.returncode == 0, got.stderr
    lines = got.stdout.split()
    assert lines == ["100.64.4.100:42423"], (
        "the _adb-tls-pairing endpoint must never be offered as a connect target"
    )


def test_parse_mdns_tolerates_space_separated_columns():
    """Column-order/whitespace tolerance is deliberate -- adb 37 builds this
    listing in its Rust mdns bridge and the layout is not recoverable from the
    binary, so the parser keys off the service type, not a column index."""
    got = run_fn(
        "parse_mdns_services",
        stdin="List of discovered mdns services\n"
              "adb-XYZ   _adb-tls-connect._tcp   100.64.4.100:42423\n",
    )
    assert got.stdout.strip() == "100.64.4.100:42423"


def test_parse_mdns_ignores_unrelated_services():
    got = run_fn(
        "parse_mdns_services",
        stdin="List of discovered mdns services\n"
              "somehost\t_http._tcp\t192.168.0.5:80\n",
    )
    assert got.stdout.strip() == ""


# ---------------------------------------------------------------------------
# classify_connect_output
#
# THE LOAD-BEARING DISTINCTION. adb has two different failure format strings,
# both visible in the shipped binary:
#     "failed to connect to '%s:%d': %s"   <- socket-level: QUOTED, has a reason
#     "failed to connect to %s"            <- post-TCP:     UNQUOTED, no reason
# The unquoted form means the TCP connect SUCCEEDED and the TLS handshake then
# failed, i.e. the device is there and rejected our cert. Getting this backwards
# is the difference between "rescan" and "go pair the phone".
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "output,expected,provenance",
    [
        # CAPTURED: adb connect 127.0.0.1:45999 (nothing listening).
        ("failed to connect to '127.0.0.1:45999': Connection refused",
         "no-port", "CAPTURED"),
        # CAPTURED: adb connect 100.64.4.100:44749 -- the phone, unpaired host.
        # The adb server log for this exact attempt showed
        # "Post-handshake SSL_peek failed [SSLV3_ALERT_CERTIFICATE_UNKNOWN]".
        ("failed to connect to 100.64.4.100:44749", "cert-rejected", "CAPTURED"),
        # adb's success strings, both present in the binary.
        ("connected to 100.64.4.100:42423", "connected", "binary string"),
        ("already connected to 100.64.4.100:42423", "connected", "binary string"),
        # the other auth-failure format string in the binary
        ("failed to authenticate to 100.64.4.100:42423", "cert-rejected",
         "binary string"),
        # anything unrecognised must NOT be silently bucketed as success
        ("some future adb message we have never seen", "other", "synthetic"),
        ("", "other", "synthetic"),
    ],
)
def test_classify_connect_output(output, expected, provenance):
    got = run_fn("classify_connect_output", stdin=output + "\n")
    assert got.returncode == 0, got.stderr
    assert got.stdout.strip() == expected, f"({provenance}) {output!r}"


def test_classify_prefers_failure_when_both_appear():
    """A run that reconnects can emit a stale success line alongside a failure.
    Never report `connected` when a failure line is present."""
    stdin = ("already connected to 100.64.4.100:42423\n"
             "failed to connect to 100.64.4.100:42423\n")
    got = run_fn("classify_connect_output", stdin=stdin)
    assert got.stdout.strip() == "cert-rejected"


def test_classify_is_not_fooled_by_the_word_connected_in_a_refusal():
    """`failed to connect to ...` contains "connect", not "connected" -- pin it,
    because a sloppier substring match here silently reports success."""
    got = run_fn("classify_connect_output",
                 stdin="failed to connect to '10.0.0.1:5555': Connection refused\n")
    assert got.stdout.strip() == "no-port"


# ---------------------------------------------------------------------------
# dispatcher + CLI surface
# ---------------------------------------------------------------------------

def test_selftest_dispatcher_refuses_arbitrary_functions():
    """The dispatcher must not become a way to run impure internals (or
    anything else) from the command line."""
    got = run_fn("cache_write", "9999")
    assert got.returncode == 2
    assert "not an exported pure function" in got.stderr


def test_help_documents_the_mdns_caveat_and_exit_codes():
    got = subprocess.run(["bash", str(SCRIPT), "--help"],
                         capture_output=True, text=True)
    assert got.returncode == 0
    out = got.stdout
    # the caveat exists so the next reader does not re-litigate mDNS
    assert "mDNS caveat" in out
    assert "tailscale" in out and "WSL2" in out
    # the exit-code legend is the tool's contract
    for code in ("0 connected", "3 no port found", "4 needs pairing"):
        assert code in out, f"missing exit-code doc: {code}"


@pytest.mark.parametrize("args", [["--nonsense"], ["--ip"], ["--port-range"],
                                  ["--timeout"], ["--port-range", "bogus"]])
def test_usage_errors_exit_2(args):
    got = subprocess.run(["bash", str(SCRIPT), *args],
                         capture_output=True, text=True)
    assert got.returncode == 2, f"{args} should be a usage error, got {got.returncode}"


def test_pairing_remedy_names_the_on_device_path_and_the_pair_command():
    """The remedy block is the entire point of the tool -- if it stops naming the
    on-device flow or the `adb pair HOST:PORT CODE` form, the tool has lost its
    value even though it still 'works'."""
    src = SCRIPT.read_text()
    assert "Pair device with pairing code" in src
    assert "Developer options" in src
    assert "Wireless debugging" in src
    assert "pair ${host}:<PAIRING_PORT> <6_DIGIT_CODE>" in src
