import unittest

from quiz import (
    PROFILES,
    QUESTIONS,
    build_answer_snapshot,
    build_score_snapshot,
    calculate_profile,
)


class SulamitaQuizTests(unittest.TestCase):
    def answers(self, occasion, product, experience, news):
        return {
            "frequency": "first_time",
            "occasion": occasion,
            "product": product,
            "experience": experience,
            "news": news,
        }

    def test_all_five_profiles_can_be_returned(self):
        examples = {
            "raiz": self.answers("any_day", "quiches", "store_combo", "surprise"),
            "nutella": self.answers("at_home", "quiches", "delivery", "home_orders"),
            "no_pique": self.answers("after_workout", "fit_line", "store_combo", "fit_news"),
            "formiguinha": self.answers("any_day", "sweets", "coffee_chat", "new_flavors"),
            "mesa_cheia": self.answers("gathering", "empadao", "celebration", "surprise"),
        }

        self.assertEqual(
            {calculate_profile(answers) for answers in examples.values()},
            set(PROFILES),
        )

    def test_first_question_records_frequency_without_scoring(self):
        answers = self.answers("any_day", "quiches", "store_combo", "surprise")
        alternate_answers = {**answers, "frequency": "weekly"}

        self.assertEqual(calculate_profile(answers), calculate_profile(alternate_answers))
        self.assertEqual(build_score_snapshot(answers), build_score_snapshot(alternate_answers))
        self.assertEqual(build_score_snapshot(answers)["raiz"], 3)

    def test_tie_break_prefers_profile_from_question_three(self):
        answers = self.answers("any_day", "fit_line", "celebration", "surprise")

        self.assertEqual(calculate_profile(answers), "no_pique")

    def test_snapshot_keeps_stable_ids_and_presented_text(self):
        answers = {
            question["id"]: question["options"][0]["id"] for question in QUESTIONS
        }
        snapshot = build_answer_snapshot(answers)

        self.assertEqual(snapshot["frequency"]["answer_id"], "weekly")
        self.assertEqual(snapshot["frequency"]["answer"], "Toda semana tem Sulamita. Já faz parte da rotina!")
        self.assertEqual(snapshot["frequency"]["question"], QUESTIONS[0]["text"])

    def test_updated_occasion_answers_are_reflected_in_the_quiz(self):
        occasion_options = {
            option["id"]: option["text"] for option in QUESTIONS[1]["options"]
        }

        self.assertEqual(
            occasion_options["after_workout"],
            "Depois da corrida, caminhada ou treino. Afinal, eu treino pra isso!",
        )
        self.assertEqual(
            occasion_options["gathering"],
            "Os encontros com as pessoas que eu amo. Sempre cabe mais um à mesa!",
        )
