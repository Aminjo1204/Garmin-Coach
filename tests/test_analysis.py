import unittest
from datetime import date, timedelta

from coach import analysis as an
from coach.config import RUN_ZONES


def act(aid, day, type_key="running", dur=2400, dist=6000, **kw):
    return {"activityId": aid, "startTimeLocal": f"{day} 18:00:00", "activityType": {"typeKey": type_key},
            "duration": dur, "movingDuration": dur, "distance": dist, **kw}


def sess(sid, day, week, sport="run", kind="easy", **kw):
    return {"id": sid, "date": day, "week": week, "sport": sport, "kind": kind, "title": sid, "key": False,
            "duration_min": 40, "steps": [], **kw}


WEEK = [sess("mo", "2026-11-09", 1, "strength", "strength"), sess("di", "2026-11-10", 1, "rest", "rest"),
        sess("mi", "2026-11-11", 1, kind="vo2"), sess("do", "2026-11-12", 1, "bike", "bike_z2"),
        sess("fr", "2026-11-13", 1), sess("sa", "2026-11-14", 1, "rest", "rest"), sess("so", "2026-11-15", 1, kind="long"),
        sess("mo2", "2026-11-16", 2, "strength", "strength")]


class Paces(unittest.TestCase):
    def test_range(self):
        self.assertEqual(an._pace_range("4:55–5:05"), (295, 305))

    def test_ten_minutes_and_slower(self):
        self.assertEqual(an._pace_range("10:25–11:05"), (625, 665))

    def test_no_pace(self):
        self.assertIsNone(an._pace_range("locker"))
        self.assertIsNone(an._pace_range(None))


class Matching(unittest.TestCase):
    def test_same_day_same_sport(self):
        self.assertEqual(an.match_sessions(WEEK, [act(1, "2026-11-11")]), {1: "mi"})

    def test_other_sport_is_not_matched_on_that_day(self):
        # Rad am Lauftag: nächste freie Rad-Einheit derselben Woche (Do), nicht der Lauf
        self.assertEqual(an.match_sessions(WEEK, [act(1, "2026-11-11", "cycling")]), {1: "do"})

    def test_shifted_within_week(self):
        # Lauf am Sa (Ruhetag) → nächstliegender Lauf der Woche
        self.assertEqual(an.match_sessions(WEEK, [act(1, "2026-11-14")]), {1: "fr"})

    def test_not_across_weeks(self):
        # Kraft am So gehört nicht zur Kraft-Einheit vom Montag der Folgewoche
        self.assertEqual(an.match_sessions(WEEK, [act(1, "2026-11-15", "strength_training")]), {})

    def test_before_plan_start_ignored(self):
        self.assertEqual(an.match_sessions(WEEK, [act(1, "2026-11-08")]), {})

    def test_moves(self):
        moved = an.apply_moves(WEEK, {"mi": "2026-11-12"})
        s = next(x for x in moved if x["id"] == "mi")
        self.assertEqual((s["date"], s["weekday"], s["moved_from"]), ("2026-11-12", "Do", "2026-11-11"))
        self.assertEqual(WEEK[2]["date"], "2026-11-11")  # Original bleibt unverändert


class BestSegment(unittest.TestCase):
    def test_constant_speed(self):
        pts = [(t, t * 3.0) for t in range(0, 2401)]  # 3 m/s, 7,2 km
        self.assertAlmostEqual(an.best_segment(pts, 5000), 5000 / 3, delta=1)

    def test_finds_fast_part(self):
        pts, d = [], 0.0
        for t in range(0, 3001):
            pts.append((t, d))
            d += 4.0 if 600 <= t < 1900 else 2.0  # 5,2 km mit 4 m/s mitten im Lauf
        self.assertAlmostEqual(an.best_segment(pts, 5000), 1250, delta=2)

    def test_too_short(self):
        self.assertIsNone(an.best_segment([(t, t * 3.0) for t in range(0, 1000)], 5000))

    def test_pause_counts(self):
        pts = [(t, t * 4.0) for t in range(0, 601)] + [(t, 2400 + (t - 900) * 4.0) for t in range(900, 1700)]
        self.assertGreater(an.best_segment(pts, 5000), 1250 + 290)

    def test_from_series_estimate(self):
        fit = {"series": [[t, 150, 3.0] for t in range(0, 2400, 10)]}
        t, approx = an._best_5k(fit)
        self.assertTrue(approx)
        self.assertAlmostEqual(t, 5000 / 3, delta=12)


class Analyze(unittest.TestCase):
    def test_easy_run_in_zone(self):
        r = an.analyze(act(1, "2026-11-13"), {"zone_sec": [600, 1560, 240, 0, 0]}, sess("fr", "2026-11-13", 1))
        self.assertEqual(r["rating"], "Stark")
        self.assertEqual(r["metrics"]["easy_pct"], 90)

    def test_easy_run_too_hard(self):
        r = an.analyze(act(1, "2026-11-13", averageHR=RUN_ZONES[1]["hi"] + 15), {"zone_sec": [0, 600, 1200, 600, 0]},
                       sess("fr", "2026-11-13", 1))
        self.assertIn("bad", [p["level"] for p in r["points"]])
        self.assertLess(r["score"], 70)

    def test_extra_activity_has_no_score(self):
        r = an.analyze(act(1, "2026-11-13"), None, None, plan_first="2026-11-09")
        self.assertEqual((r["score"], r["rating"]), (None, "Zusatz"))

    def test_5k_test_from_lap(self):
        fit = {"laps": [{"intensity": "active", "sec": 1500, "dist": 5000, "pace_s": 300, "avg_hr": 185, "max_hr": 195}]}
        r = an.analyze(act(1, "2026-12-06"), fit, sess("t", "2026-12-06", 4, kind="test"))
        self.assertEqual(r["metrics"]["test_5k"], "25:00")

    def test_5k_test_with_auto_laps(self):
        laps = [{"intensity": "active", "sec": 300, "dist": 1000, "pace_s": 300, "avg_hr": 185, "max_hr": 195}] * 7
        r = an.analyze(act(1, "2026-12-06", dist=7000), {"laps": laps, "best_5k_sec": 1490},
                       sess("t", "2026-12-06", 4, kind="test"))
        self.assertEqual(r["metrics"]["test_5k"], "24:50")

    def test_5k_test_too_short(self):
        r = an.analyze(act(1, "2026-12-06", dist=3000), {"laps": [], "series": [[t, 150, 3.0] for t in range(0, 900, 10)]},
                       sess("t", "2026-12-06", 4, kind="test"))
        self.assertNotIn("test_5k", r["metrics"])


def day(**kw):
    base = {"date": "2026-11-10", "hrv": None, "hrv_low": None, "hrv_high": None, "hrv_status": None, "rhr": None,
            "sleep_h": None, "sleep_score": None, "bb_max": None}
    return base | kw


class Readiness(unittest.TestCase):
    past = [day(rhr=56) for _ in range(14)]

    def test_all_good_is_green(self):
        t = day(hrv=67, hrv_low=61, hrv_high=87, hrv_status="BALANCED", rhr=57, sleep_h=7.8, sleep_score=85, bb_max=92)
        r = an.readiness_today(self.past + [t], None)
        self.assertEqual(r["level"], "green")

    def test_only_resting_hr_is_not_green(self):
        r = an.readiness_today(self.past + [day(rhr=56, bb_max=80)], None)
        self.assertEqual(r["level"], "yellow")
        self.assertTrue(any("unsicher" in text for _, text in r["factors"]))

    def test_bad_night_on_key_day_is_red(self):
        t = day(hrv=45, hrv_low=61, hrv_high=87, hrv_status="LOW", rhr=64, sleep_h=5.0, sleep_score=48, bb_max=35)
        r = an.readiness_today(self.past + [t], {"key": True, "sport": "run"})
        self.assertEqual(r["level"], "red")
        self.assertIn("tauschen", r["advice"])

    def test_no_data(self):
        r = an.readiness_today(self.past + [day()], None)
        self.assertEqual(r["factors"], [])
        self.assertIn("Noch keine Erholungsdaten", r["advice"])

    def test_high_load_lowers_score(self):
        t = day(hrv=67, hrv_low=61, hrv_status="BALANCED", rhr=57, sleep_score=85, sleep_h=8)
        a = an.readiness_today(self.past + [t], None, acwr=1.0)["score"]
        b = an.readiness_today(self.past + [t], None, acwr=1.6)["score"]
        self.assertLess(b, a)


class Load(unittest.TestCase):
    def test_trimp(self):
        self.assertEqual(an.activity_load({}, {"zone_sec": [600, 600, 0, 0, 300]}), 10 * 1 + 10 * 2 + 5 * 5)
        self.assertEqual(an.activity_load({"duration": 3600}, None), 90)

    def test_acwr_needs_four_weeks(self):
        today = date.today()
        short = [act(i, (today - timedelta(days=i)).isoformat()) for i in range(10)]
        self.assertIsNone(an.load_series(short, {})["today"]["acwr"])
        steady = [act(i, (today - timedelta(days=i)).isoformat()) for i in range(40)]
        t = an.load_series(steady, {})["today"]
        self.assertEqual(t["acwr"], 1.0)
        self.assertEqual(t["level"]["key"], "ok")


class Prediction(unittest.TestCase):
    def test_vdot_matches_daniels(self):
        self.assertAlmostEqual(an.vdot_from(5000, 20 * 60), 49.8, delta=0.1)

    def test_time_for_is_inverse(self):
        self.assertAlmostEqual(an.time_for(an.vdot_from(5000, 1535), 5000), 1535, delta=1)

    def test_times(self):
        self.assertEqual(an.fmt_time(7065), "1:57:45")
        self.assertEqual(an.fmt_pace(305), "5:05")
        self.assertEqual(an._mmss_to_sec("1:57:45"), 7065)


if __name__ == "__main__":
    unittest.main()
