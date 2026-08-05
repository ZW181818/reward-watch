import unittest

from app.ingestion.reward_amount import extract_cash_amount


class RewardAmountTests(unittest.TestCase):
    def test_parses_plain_and_scaled_cash_amounts(self):
        self.assertEqual(extract_cash_amount("Reward up to $25,000"), 25_000)
        self.assertEqual(extract_cash_amount("Reward up to $5 million"), 5_000_000)
        self.assertEqual(extract_cash_amount("Reward up to $2.5M"), 2_500_000)
        self.assertEqual(extract_cash_amount("A $100K bounty"), 100_000)

    def test_returns_largest_amount(self):
        self.assertEqual(
            extract_cash_amount("Individual rewards are $5 million, up to $20 million total."),
            20_000_000,
        )

    def test_requires_reward_context_when_requested(self):
        text = "Police seized $1,460 in cash during the investigation."
        self.assertEqual(extract_cash_amount(text, require_reward_context=True), 0)
        self.assertEqual(
            extract_cash_amount(
                text + " A reward of $10,000 is offered for information.",
                require_reward_context=True,
            ),
            10_000,
        )


if __name__ == "__main__":
    unittest.main()
