"""
grading_core.py

The grading engine for the Weather Station Reports assignment (Project 2):
test plan, scoring rules (space-insensitive partial credit, free
dash/space equivalence, print-output substring checking) and the
per-student feedback text.

Used by grade_submissions.py (batch grading on your machine) and by the
student self-check web page (index.html, which runs this same file in
the browser with Pyodide). Edit scoring here and both stay in sync.

This assignment's total is 20 points: 16 auto-graded here (9 functions
+ 1 setup check) and 4 graded by hand from each student's bug log
(not part of this file).

No API key is used in this project, and grading never fetches the real
data from GitHub -- get_weather_reports() is replaced with a stub
returning fixed REFERENCE_STATIONS data, so grading is deterministic
and works offline.
"""

import copy
import io
import re
import contextlib
import unicodedata

MAX_POINTS = 16  # auto-graded portion only; +4 manual (bug log) = 20 total

# Map exact Canvas "Last, First Middle" name -> the exact name a student
# typed into their notebook's student_name field, for anyone whose name
# doesn't auto-match between the two (nickname, typo, etc.).
NAME_OVERRIDES = {
    # "Smith, Bob": "Robert Smith",
}

# Same data as stations.json in the projec2_data repo, embedded here so
# grading never depends on a network call or the repo being reachable.
REFERENCE_STATIONS = [
    {"station": "  ann arbor north  ", "raw_condition": "PARTLY CLOUDY   ", "raw_temp": "68F"},
    {"station": "west quad rooftop", "raw_condition": "  sunny", "raw_temp": " 82F"},
    {"station": "Pioneer High School", "raw_condition": "light rain ", "raw_temp": "59F "},
    {"station": "  DIAG CENTRAL  ", "raw_condition": "Clear Skies", "raw_temp": "75F"},
    {"station": "north campus", "raw_condition": "RAIN SHOWERS", "raw_temp": "61F"},
]


def stub_get_weather_reports():
    """Stand-in for the real get_weather_reports() so grading never needs
    network access or depends on the GitHub repo being reachable."""
    return REFERENCE_STATIONS


def strip_instructor_code(source):
    """Cut off everything from a '# Instructor code...' marker onward in
    a single cell's source, same pattern as Project 1."""
    lines = source.split("\n")
    kept = []
    for line in lines:
        if re.match(r"^\s*#\s*Instructor code", line, re.IGNORECASE):
            break
        kept.append(line)
    return "\n".join(kept)


def load_student_code(nb):
    """nb = a parsed .ipynb (dict). Return the source of every code cell
    (instructor-only portions stripped), skipping the cell that defines
    the real get_weather_reports()."""
    sources = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if "def get_weather_reports" in source:
            continue  # skip the provided function cell -- we supply a stub instead
        source = strip_instructor_code(source)
        sources.append(source)

    return "\n\n".join(sources)


def run_submission(nb):
    """Exec a student's code (nb = parsed .ipynb dict) in a fresh namespace
    and return that namespace, or None plus an error message if it crashes
    outright."""
    code = load_student_code(nb)
    namespace = {"__builtins__": __builtins__, "get_weather_reports": stub_get_weather_reports, "__student_source__": code}
    try:
        exec(code, namespace)
    except Exception as e:
        return None, f"Submission crashed while running: {type(e).__name__}: {e}"
    return namespace, None


# ---------------------------------------------------------------------------
# Test specs: each item defines its own set of cases so we can report the
# expected vs. actual value for every individual check, not just pass/fail.
#
# An item may carry a "partial" rule: if a case fails the exact comparison
# but passes after applying partial["normalize"] to both sides, the case is
# marked "near" and the item loses only partial["deduct"] points (as long as
# every case is either a pass or a near).
# ---------------------------------------------------------------------------

def same_dash(value):
    """Treat every dash-like character (hyphen, --, en dash, em dash,
    horizontal bar, minus sign, ...) as '-' and every kind of space
    (regular, non-breaking, ...) as ' '. Differences of this sort cost
    nothing."""
    out = []
    for ch in str(value):
        if ch == "-" or unicodedata.category(ch) == "Pd" or ch == "\u2212":
            out.append("-")
        elif ch.isspace():
            out.append(" ")
        else:
            out.append(ch)
    return re.sub(r"-{2,}", "-", "".join(out))


def first_difference(expected, actual):
    """Describe the first place two strings differ, showing code points so
    look-alike characters (em dash vs horizontal bar, NBSP vs space) are
    visible. Returns '' if the strings are identical or aren't both strings."""
    if not isinstance(expected, str) or not isinstance(actual, str) or expected == actual:
        return ""
    for i, (e, a) in enumerate(zip(expected, actual)):
        if e != a:
            return (f"first difference at index {i}: expected {e!r} (U+{ord(e):04X}), "
                    f"got {a!r} (U+{ord(a):04X})")
    if len(expected) > len(actual):
        return f"actual is missing the ending: {expected[len(actual):]!r}"
    return f"actual has extra text at the end: {actual[len(expected):]!r}"


def no_spaces(value):
    return same_dash(value).replace(" ", "")


def build_test_plan(stations):
    """stations = the station list to test against (always
    REFERENCE_STATIONS). Returns the ordered list of graded items, each
    a dict with: key, label, points, kind, cases."""

    s0, s1, s2, s3, s4 = stations  # Mixed/68F, Sunny/82F, Rainy/59F, Sunny/75F, Rainy/61F

    return [
        {
            "key": "setup",
            "label": "Setup (student_name)",
            "points": 1,
            "kind": "props",
            "cases": [
                {
                    "desc": "student_name is a non-empty string",
                    "get_actual": lambda ns: repr(ns.get("student_name")),
                    "expected": "a non-empty string",
                    "check": lambda ns: isinstance(ns.get("student_name"), str) and ns.get("student_name", "").strip() != "",
                },
            ],
        },
        {
            "key": "clean_station_name", "label": "clean_station_name", "points": 2, "kind": "calls", "func": "clean_station_name",
            "cases": [
                {"desc": "clean_station_name('  ann arbor north  ')", "args": ("  ann arbor north  ",), "expected": "Ann Arbor North"},
                {"desc": "clean_station_name('west quad rooftop')", "args": ("west quad rooftop",), "expected": "West Quad Rooftop"},
                {"desc": "clean_station_name('  DIAG CENTRAL  ')", "args": ("  DIAG CENTRAL  ",), "expected": "Diag Central"},
            ],
        },
        {
            "key": "parse_temperature", "label": "parse_temperature", "points": 2, "kind": "calls", "func": "parse_temperature",
            "cases": [
                {"desc": "parse_temperature('68F')", "args": ("68F",), "expected": 68},
                {"desc": "parse_temperature(' 82F')", "args": (" 82F",), "expected": 82},
                {"desc": "parse_temperature('59F ')", "args": ("59F ",), "expected": 59},
            ],
        },
        {
            "key": "clean_condition", "label": "clean_condition", "points": 1, "kind": "calls", "func": "clean_condition",
            "cases": [
                {"desc": "clean_condition('PARTLY CLOUDY   ')", "args": ("PARTLY CLOUDY   ",), "expected": "partly cloudy"},
                {"desc": "clean_condition('  sunny')", "args": ("  sunny",), "expected": "sunny"},
            ],
        },
        {
            "key": "classify_condition", "label": "classify_condition", "points": 2, "kind": "calls", "func": "classify_condition",
            "cases": [
                {"desc": "classify_condition('light rain')", "args": ("light rain",), "expected": "Rainy"},
                {"desc": "classify_condition('sunny')", "args": ("sunny",), "expected": "Sunny"},
                {"desc": "classify_condition('clear skies')", "args": ("clear skies",), "expected": "Sunny"},
                {"desc": "classify_condition('partly cloudy')", "args": ("partly cloudy",), "expected": "Mixed"},
            ],
        },
        {
            "key": "suggest_outfit", "label": "suggest_outfit", "points": 2, "kind": "calls", "func": "suggest_outfit",
            "cases": [
                {"desc": "suggest_outfit(59, 'light rain')", "args": (59, "light rain"), "expected": "Bring an umbrella."},
                {"desc": "suggest_outfit(82, 'sunny')", "args": (82, "sunny"), "expected": "Wear light clothing and sunscreen."},
                {"desc": "suggest_outfit(68, 'partly cloudy')", "args": (68, "partly cloudy"), "expected": "A light jacket should do."},
                {"desc": "suggest_outfit(45, 'clear skies')", "args": (45, "clear skies"), "expected": "Bundle up, it's cold."},
            ],
        },
        {
            "key": "format_station_report", "label": "format_station_report", "points": 2, "kind": "calls", "func": "format_station_report",
            "equivalent": same_dash,  # differences that cost nothing (hyphen vs em dash)
            "partial": {"normalize": no_spaces, "deduct": 0.5, "note": "matches once all spaces are removed"},
            "cases": [
                {"desc": "format_station_report(s0)  # Ann Arbor North", "args": (s0,), "expected": "Ann Arbor North: Mixed (partly cloudy), 68°F — A light jacket should do."},
                {"desc": "format_station_report(s2)  # Pioneer High School", "args": (s2,), "expected": "Pioneer High School: Rainy (light rain), 59°F — Bring an umbrella."},
            ],
        },
        {
            "key": "print_all_reports", "label": "print_all_reports", "points": 2, "kind": "prints", "func": "print_all_reports",
            "equivalent": same_dash,
            "cases": [
                {
                    "desc": "print_all_reports(stations) includes a line for each station",
                    "args": (stations,),
                    "expected_lines": [
                        "Ann Arbor North: Mixed (partly cloudy), 68°F — A light jacket should do.",
                        "West Quad Rooftop: Sunny (sunny), 82°F — Wear light clothing and sunscreen.",
                        "Pioneer High School: Rainy (light rain), 59°F — Bring an umbrella.",
                        "Diag Central: Sunny (clear skies), 75°F — A light jacket should do.",
                        "North Campus: Rainy (rain showers), 61°F — Bring an umbrella.",
                    ],
                },
            ],
        },
        {
            "key": "count_stations_matching", "label": "count_stations_matching", "points": 1, "kind": "calls", "func": "count_stations_matching",
            "cases": [
                {"desc": "count_stations_matching(stations, 'rain')", "args": (stations, "rain"), "expected": 2},
                {"desc": "count_stations_matching(stations, 'sun')", "args": (stations, "sun"), "expected": 1},
                {"desc": "count_stations_matching(stations, 'RAIN')", "args": (stations, "RAIN"), "expected": 2},
                {"desc": "count_stations_matching(stations, 'snow')", "args": (stations, "snow"), "expected": 0},
            ],
        },
        {
            "key": "hottest_station", "label": "hottest_station", "points": 1, "kind": "calls", "func": "hottest_station",
            "cases": [
                {"desc": "hottest_station(stations)", "args": (stations,), "expected": ("West Quad Rooftop", 82)},
            ],
        },
    ]


def run_case_calls(func, case, partial=None, equivalent=None):
    """Run one 'calls'-kind case. Returns (status, actual_repr, mutated, diff)
    where status is 'pass', 'near' (only matches under the item's partial
    rule), or 'fail', and mutated is True if the function changed its input
    arguments."""
    args = copy.deepcopy(case["args"])
    try:
        actual = func(*args)
    except Exception as e:
        return "fail", f"raised {type(e).__name__}: {e}", False, ""
    mutated = args != tuple(case["args"])
    if equivalent is not None and isinstance(actual, str) and isinstance(case["expected"], str):
        diff = first_difference(equivalent(case["expected"]), equivalent(actual))
    else:
        diff = first_difference(case["expected"], actual)
    if actual == case["expected"]:
        return "pass", repr(actual), mutated, ""
    if equivalent is not None and isinstance(actual, str) and isinstance(case["expected"], str):
        if equivalent(actual) == equivalent(case["expected"]):
            return "pass", repr(actual), mutated, ""
    if partial is not None and isinstance(actual, str) and isinstance(case["expected"], str):
        norm = partial["normalize"]
        if norm(actual) == norm(case["expected"]):
            return "near", repr(actual), mutated, diff
    return "fail", repr(actual), mutated, diff


def run_case_props(ns, case):
    """Run one 'props'-kind case. Returns (status, actual_repr)."""
    try:
        passed = bool(case["check"](ns))
        actual = case["get_actual"](ns)
    except Exception as e:
        return "fail", f"raised {type(e).__name__}: {e}"
    return ("pass" if passed else "fail"), actual


def run_case_prints(func, case, equivalent=None):
    """Run one 'prints'-kind case. Captures whatever the function prints
    while it runs and checks that every line in case['expected_lines']
    appears somewhere in that output -- as a substring, not an exact
    match, so a student's extra print statements (headers, debug output,
    blank lines) never cost points. Returns (status, actual, diff)."""
    args = copy.deepcopy(case["args"])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            func(*args)
    except Exception as e:
        return "fail", f"raised {type(e).__name__}: {e}", ""
    captured = buf.getvalue()
    haystack = equivalent(captured) if equivalent else captured
    missing = []
    for line in case["expected_lines"]:
        needle = equivalent(line) if equivalent else line
        if needle not in haystack:
            missing.append(line)
    actual_display = captured if captured.strip() else "(nothing was printed)"
    if not missing:
        return "pass", actual_display, ""
    diff = "missing line(s): " + " | ".join(missing)
    return "fail", actual_display, diff


def grade_namespace(ns):
    """Runs the full test plan against a submission's namespace. Returns
    (total_score, item_results) where item_results is a list of dicts:
    {key, label, points_earned, max_points, case_results} and
    case_results is a list of {desc, expected, actual, status, passed}."""

    # Always test against the reference stations. The expected values
    # below are fixed, so using a live fetch would make correct code
    # fail if the hosted file ever changes.
    stations = REFERENCE_STATIONS

    plan = build_test_plan(stations)
    item_results = []

    for item in plan:
        partial = item.get("partial")
        not_defined = False
        case_results = []
        if item["kind"] == "props":
            for case in item["cases"]:
                status, actual = run_case_props(ns, case)
                case_results.append({"desc": case["desc"], "expected": case["expected"], "actual": actual,
                                     "status": status, "passed": status == "pass"})
        elif item["kind"] == "calls":
            func = ns.get(item["func"])
            if func is None or not callable(func):
                not_defined = True
                for case in item["cases"]:
                    case_results.append({
                        "desc": case["desc"], "expected": repr(case["expected"]),
                        "actual": f"'{item['func']}' is not defined", "status": "fail", "passed": False,
                    })
            else:
                for case in item["cases"]:
                    status, actual, mutated, diff = run_case_calls(func, case, partial, item.get("equivalent"))
                    case_results.append({"desc": case["desc"], "expected": repr(case["expected"]), "actual": actual,
                                         "status": status, "passed": status == "pass", "mutated": mutated, "diff": diff})
        elif item["kind"] == "prints":
            func = ns.get(item["func"])
            if func is None or not callable(func):
                not_defined = True
                for case in item["cases"]:
                    case_results.append({
                        "desc": case["desc"], "expected": " | ".join(case["expected_lines"]),
                        "actual": f"'{item['func']}' is not defined", "status": "fail", "passed": False,
                    })
            else:
                for case in item["cases"]:
                    status, actual, diff = run_case_prints(func, case, item.get("equivalent"))
                    case_results.append({"desc": case["desc"], "expected": " | ".join(case["expected_lines"]), "actual": actual,
                                         "status": status, "passed": status == "pass", "mutated": False, "diff": diff})

        statuses = [c["status"] for c in case_results]
        if all(s == "pass" for s in statuses):
            points_earned = item["points"]
        elif partial is not None and all(s in ("pass", "near") for s in statuses):
            points_earned = item["points"] - partial["deduct"]
        else:
            points_earned = 0

        item_results.append({
            "key": item["key"], "label": item["label"],
            "points_earned": points_earned, "max_points": item["points"],
            "partial_note": partial["note"] if partial else None,
            "not_defined": not_defined,
            "case_results": case_results,
        })

    total = sum(r["points_earned"] for r in item_results)
    return total, item_results


def fmt_points(p):
    """16 -> '16', 14.5 -> '14.5'"""
    return f"{int(p)}" if float(p).is_integer() else f"{p}"


def item_marker(item):
    if item["points_earned"] == item["max_points"]:
        return "PASS"
    if item["points_earned"] > 0:
        return "PARTIAL"
    return "FAIL"


# ---------------------------------------------------------------------------
# Feedback text and the one-notebook entry point
# ---------------------------------------------------------------------------

def safe_filename(name):
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return name.strip("_") or "unknown"


def feedback_lines(result):
    """The per-student feedback as a list of text lines."""
    label = result["student_name"] or result["rel_path"]
    lines = []
    lines.append(f"Weather Station Reports Assignment (Project 2) -- Feedback for {label}")
    lines.append(f"Submission file: {result['rel_path']}")
    lines.append(f"Auto-graded score: {fmt_points(result['total'])}/{MAX_POINTS}")
    lines.append("This covers the 9 functions + setup check only. The bug log")
    lines.append("(4 pts) is graded separately and is not reflected here.")
    lines.append("=" * 60)

    if result["crashed"]:
        lines.append("")
        lines.append("This submission crashed before any checks could run:")
        lines.append(f"  {result['crash_error']}")
        lines.append("")
        lines.append("No further detail is available -- fix the error above and resubmit to see a full breakdown.")
    else:
        missed = [item for item in result["item_results"] if item["points_earned"] < item["max_points"]]
        if not missed:
            lines.append("")
            lines.append("Every check passed.")
        for item in missed:
            marker = item_marker(item)
            lines.append("")
            lines.append(f"[{marker}] {item['label']}  ({fmt_points(item['points_earned'])}/{item['max_points']} pts)")
            if marker == "PARTIAL" and item["partial_note"] and any(c["status"] == "near" for c in item["case_results"]):
                lines.append(f"    (partial credit: {item['partial_note']})")
            if item.get("not_defined"):
                lines.append(f"    ERROR: function '{item['label']}' is not defined -- check the name and that the cell ran")
            for c in item["case_results"]:
                if c["status"] == "pass":
                    continue
                status = {"pass": "ok", "near": "CLOSE", "fail": "MISSED"}[c["status"]]
                lines.append(f"    {c['desc']}")
                lines.append(f"        expected: {c['expected']}")
                lines.append(f"        actual:   {c['actual']}   [{status}]")
                if c.get("diff"):
                    lines.append(f"        {c['diff']}")

    return lines


def grade_notebook(nb, rel_path=""):
    """Grade one parsed .ipynb dict. Returns the result dict used by every
    output: rel_path, student_name, total, item_results, crashed,
    crash_error."""
    ns, error = run_submission(nb)
    if ns is None:
        return {
            "rel_path": rel_path, "student_name": None,
            "total": 0, "item_results": [], "crashed": True, "crash_error": error,
        }
    total, item_results = grade_namespace(ns)
    return {
        "rel_path": rel_path, "student_name": ns.get("student_name"),
        "total": total, "item_results": item_results, "crashed": False, "crash_error": None,
    }
