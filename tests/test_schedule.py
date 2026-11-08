import json
import tempfile
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import signage
from signage import allowed_now, load_config, parse_windows, windows_allow

# Fixed-offset stand-ins keep these tests independent of the machine's tz database
# (Windows Python often has no tzdata). Jakarta has no DST, so +7 is exact.
JAKARTA = timezone(timedelta(hours=7))
UTC = timezone.utc


def fake_zoneinfo(name):
    try:
        return {"Asia/Jakarta": JAKARTA, "UTC": UTC}[name]
    except KeyError:
        raise ZoneInfoNotFoundError(name) from None


def setUpModule():
    global _patch
    _patch = unittest.mock.patch.object(signage, "ZoneInfo", fake_zoneinfo)
    _patch.start()
    signage._parse_windows.cache_clear()


def tearDownModule():
    _patch.stop()
    signage._parse_windows.cache_clear()

BUSINESS = {"timezone": "Asia/Jakarta", "windows": [
    {"days": ["Mon", "Tue", "Wed", "Thu", "Fri"], "start": "08:00", "end": "01:00"},
    {"days": ["Sat"], "start": "10:00", "end": "22:00"},
]}


def at(day, hour, minute=0, tz=None):
    """2026-11-02 is a Monday; day is 0=Mon..6=Sun."""
    return datetime(2026, 11, 2 + day, hour, minute, tzinfo=tz or JAKARTA)


class WindowScheduleTests(unittest.TestCase):
    def setUp(self):
        signage._LAST_GOOD.clear()
        signage._LOGGED.clear()
        self.schedule = parse_windows(BUSINESS)

    def test_weekday_anchor(self):
        self.assertEqual(at(0, 0).weekday(), 0)

    def test_inside_and_outside_a_same_day_window(self):
        self.assertFalse(windows_allow(self.schedule, at(0, 7, 59)))
        self.assertTrue(windows_allow(self.schedule, at(0, 8)))
        self.assertTrue(windows_allow(self.schedule, at(0, 20)))

    def test_window_crossing_midnight_belongs_to_start_day(self):
        self.assertTrue(windows_allow(self.schedule, at(4, 23, 30)))   # Fri 23:30
        self.assertTrue(windows_allow(self.schedule, at(5, 0, 30)))    # Sat 00:30, Friday's window
        self.assertFalse(windows_allow(self.schedule, at(5, 1)))       # Sat 01:00 closed
        self.assertFalse(windows_allow(self.schedule, at(5, 9, 59)))   # Sat before its own window
        self.assertTrue(windows_allow(self.schedule, at(5, 10)))

    def test_day_without_window_is_off_and_previous_overflow_is_not_invented(self):
        self.assertFalse(windows_allow(self.schedule, at(6, 12)))      # Sunday has no window
        self.assertFalse(windows_allow(self.schedule, at(6, 0, 30)))   # Saturday's window ends 22:00
        self.assertFalse(windows_allow(self.schedule, at(0, 0, 30)))   # Sunday had none, so Monday 00:30 is off

    def test_24_00_end_and_full_day(self):
        until_midnight = parse_windows({"windows": [{"days": ["Mon"], "start": "08:00", "end": "24:00"}]})
        self.assertTrue(windows_allow(until_midnight, at(0, 23, 59)))
        self.assertFalse(windows_allow(until_midnight, at(1, 0)))
        full = parse_windows({"windows": [{"days": ["Mon"], "start": "00:00", "end": "24:00"}]})
        self.assertTrue(windows_allow(full, at(0, 0)))
        self.assertTrue(windows_allow(full, at(0, 23, 59)))
        self.assertFalse(windows_allow(full, at(1, 0)))

    def test_timezone_is_the_schedule_zone_not_the_clock_of_the_caller(self):
        # Friday 16:30 UTC is Friday 23:30 in Jakarta (+7): inside Friday's window.
        self.assertTrue(windows_allow(self.schedule, at(4, 16, 30, tz=UTC)))
        # Saturday 18:30 UTC is Sunday 01:30 in Jakarta: closed.
        self.assertFalse(windows_allow(self.schedule, at(5, 18, 30, tz=UTC)))

    def test_validation_errors(self):
        good = {"days": ["Mon"], "start": "08:00", "end": "17:00"}
        for bad in (
            {"windows": []},
            {"windows": [{**good, "start": "08:00", "end": "08:00"}]},
            {"windows": [{**good, "days": ["Monday"]}]},
            {"windows": [{**good, "days": []}]},
            {"windows": [{**good, "start": "24:00"}]},
            {"windows": [{**good, "end": "25:00"}]},
            {"windows": [{**good, "start": "8:00"}]},
            {"windows": [good], "timezone": "Mars/Base"},
            {"windows": [good], "timezone": 7},
            {},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_windows(bad)

    def test_missing_days_are_reported_once(self):
        with self.assertLogs("pi5-signage", "WARNING") as logs:
            parse_windows({"windows": [{"days": ["Mon"], "start": "08:00", "end": "17:00"}]})
        self.assertIn("Tue", logs.output[0])
        self.assertIn("Sun", logs.output[0])


class WindowPrecedenceTests(unittest.TestCase):
    def setUp(self):
        signage._LAST_GOOD.clear()
        signage._LOGGED.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cms = self.root / "schedules.json"
        self.base = {"profile": "pi5", "media_dir": self.temp.name, "display": "HDMI-A-1",
                     "audio": False, "audio_device": "x", "retry_seconds": 5}

    def config(self, **extra):
        path = self.root / "config.json"
        path.write_text(json.dumps({**self.base, **extra}), encoding="utf-8")
        return load_config(path)

    def check(self, config, when):
        with unittest.mock.patch.object(signage, "operation_mode", return_value="auto"), \
             unittest.mock.patch.object(signage, "datetime") as fake:
            fake.now.side_effect = lambda tz=None: when if tz is None else when.astimezone(tz)
            fake.combine = datetime.combine
            return allowed_now(config)

    def test_config_windows_do_not_need_start_end(self):
        config = self.config(windows=[{"days": ["Mon"], "start": "08:00", "end": "17:00"}], timezone="Asia/Jakarta")
        self.assertTrue(self.check(config, at(0, 9)))
        self.assertFalse(self.check(config, at(0, 18)))

    def test_always_on_with_windows_is_rejected(self):
        with self.assertRaises(ValueError):
            self.config(always_on=True, windows=[{"days": ["Mon"], "start": "08:00", "end": "17:00"}])

    def test_cms_windows_override_config_windows(self):
        self.cms.write_text(json.dumps({"timezone": "Asia/Jakarta",
                                        "windows": [{"days": ["Mon"], "start": "20:00", "end": "22:00"}]}))
        config = self.config(schedules_file=str(self.cms),
                             windows=[{"days": ["Mon"], "start": "08:00", "end": "17:00"}], timezone="Asia/Jakarta")
        self.assertFalse(self.check(config, at(0, 9)))
        self.assertTrue(self.check(config, at(0, 21)))

    def test_invalid_cms_schedule_keeps_last_good_then_falls_back(self):
        good = {"timezone": "Asia/Jakarta", "windows": [{"days": ["Mon"], "start": "08:00", "end": "17:00"}]}
        config = self.config(schedules_file=str(self.cms), start="00:00", end="23:59", always_on=True)
        self.cms.write_text(json.dumps(good))
        self.assertTrue(self.check(config, at(0, 9)))
        self.assertFalse(self.check(config, at(0, 18)))
        self.cms.write_text(json.dumps({"windows": [{"days": ["Mon"], "start": "09:00", "end": "09:00"}]}))
        self.assertFalse(self.check(config, at(0, 18)))   # last good still in force, not "allow"
        self.cms.write_text("{broken")
        self.assertFalse(self.check(config, at(0, 18)))
        signage._LAST_GOOD.clear()
        self.cms.write_text(json.dumps({"windows": []}))  # invalid and nothing good: config always_on applies
        self.assertTrue(self.check(config, at(0, 18)))

    def test_cms_file_without_windows_uses_legacy_rules(self):
        self.cms.write_text(json.dumps({"events": []}))
        config = self.config(schedules_file=str(self.cms), start="00:00", end="23:59", always_on=True)
        self.assertTrue(self.check(config, at(0, 3)))


if __name__ == "__main__":
    unittest.main()
