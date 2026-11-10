import unittest

from garmin_fit_sdk import Decoder, Stream

from coach import plan_builder as pb
from coach import workout_fit as wf


def decode(raw: bytes) -> dict:
    self_check = Decoder(Stream.from_byte_array(bytearray(raw)))
    assert self_check.is_fit() and self_check.check_integrity()
    msgs, errors = Decoder(Stream.from_byte_array(bytearray(raw))).read()
    assert not errors, errors
    return msgs


def session(s: dict, **kw) -> dict:
    return s | {"id": "x", "week": 1, "weekday": "Mi"} | kw


class WorkoutFit(unittest.TestCase):
    def test_intervals(self):
        s = session(pb.vo2(5, 3, 2.5))
        msgs = decode(wf.build(s))
        self.assertEqual(msgs["file_id_mesgs"][0]["type"], "workout")
        w = msgs["workout_mesgs"][0]
        self.assertEqual((w["sport"], w["num_valid_steps"], w["wkt_name"]), ("running", 5, "W01 Mi VO2max: 5 × 3 min"))
        st = msgs["workout_step_mesgs"]
        self.assertEqual([x["message_index"] for x in st], [0, 1, 2, 3, 4])
        self.assertEqual([x.get("intensity") for x in st], ["warmup", "active", "rest", None, "cooldown"])
        self.assertEqual((st[1]["duration_type"], st[1]["duration_time"]), ("time", 180))
        # Wiederholung: zurück zu Schritt 1, insgesamt 5 Durchgänge
        self.assertEqual((st[3]["duration_type"], st[3]["duration_step"], st[3]["repeat_steps"]),
                         ("repeat_until_steps_cmplt", 1, 5))

    def test_heart_rate_target_is_absolute_bpm(self):
        s = session(pb.vo2(4, 4, 3))
        work = decode(wf.build(s))["workout_step_mesgs"][1]
        lo, hi = s["steps"][1]["steps"][0]["hr"]
        self.assertEqual(work["target_type"], "heart_rate")
        self.assertEqual((work["custom_target_heart_rate_low"], work["custom_target_heart_rate_high"]), (lo + 100, hi + 100))

    def test_recovery_has_no_target(self):
        rec = decode(wf.build(session(pb.vo2(4, 4, 3))))["workout_step_mesgs"][2]
        self.assertEqual(rec["target_type"], "open")

    def test_distance_step(self):
        st = decode(wf.build(session(pb.distance_reps(5, 800, 2))))["workout_step_mesgs"][1]
        self.assertEqual((st["duration_type"], st["duration_distance"]), ("distance", 800))

    def test_strides_are_whole_seconds(self):
        st = decode(wf.build(session(pb.easy(40, 6))))["workout_step_mesgs"]
        self.assertEqual((st[1]["duration_time"], st[2]["duration_time"]), (20, 40))
        self.assertEqual((st[3]["duration_step"], st[3]["repeat_steps"]), (1, 6))

    def test_two_sets_point_to_their_own_block(self):
        st = decode(wf.build(session(pb.short_intervals(2, 10))))["workout_step_mesgs"]
        repeats = [(x["message_index"], x["duration_step"], x["repeat_steps"]) for x in st
                   if x["duration_type"] == "repeat_until_steps_cmplt"]
        # Einlaufen 0 · Satz 1: 1,2 + Wdh. 3 · Satzpause 4 · Satz 2: 5,6 + Wdh. 7 · Auslaufen 8
        self.assertEqual(repeats, [(3, 1, 10), (7, 5, 10)])

    def test_nested_repeat(self):
        inner = pb.rep(3, pb.work("schnell", 1), pb.jog(1))
        steps = wf.workout_steps([pb.warmup(10), pb.rep(2, inner, pb.jog(3)), pb.cooldown(5)])
        self.assertEqual([(i, s["duration_value"], s["target_value"]) for i, s in enumerate(steps)
                          if s["duration_type"] == "repeat_until_steps_cmplt"], [(3, 1, 3), (5, 1, 2)])

    def test_every_run_of_a_plan_can_be_built(self):
        runs = [s for s in pb.build()["sessions"] if wf.exportable(s)]
        self.assertGreater(len(runs), 20)
        for s in runs:
            msgs = decode(wf.build(s))
            self.assertEqual(len(msgs["workout_step_mesgs"]), msgs["workout_mesgs"][0]["num_valid_steps"])

    def test_not_exportable(self):
        self.assertFalse(wf.exportable({"sport": "strength", "steps": []}))
        with self.assertRaises(ValueError):
            wf.build({"sport": "rest", "steps": []})

    def test_names(self):
        self.assertEqual(wf.file_name("W01 Mi 5 × 3 min"), "W01_Mi_5_x_3_min.fit")
        self.assertEqual(wf.file_name("../../x"), "x.fit")
        self.assertLessEqual(len(wf.default_name(session(pb.easy(40, 6), title="x" * 80))), 40)


if __name__ == "__main__":
    unittest.main()
