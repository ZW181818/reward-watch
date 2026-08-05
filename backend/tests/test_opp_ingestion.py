import unittest

from app.ingestion.opp import normalize_opp_record


def make_record(**overrides):
    record = {
        "_id": {"$id": "official-test-id"},
        "circularname": "OFFICIAL PARSER TEST",
        "circulartype": "mostwanted",
        "engsummary": "WANTED FOR ARREST",
        "engdescription": (
            "<p>The Ontario Provincial Police is requesting public information "
            "about a fictional $3,500,000 loss in this parser fixture. "
            "A reward of up to $25,000 is listed.</p>"
            "<h2>Details</h2>"
            "<p><strong>Date:</strong> 7 May 2024<br>"
            "<strong>ALIASE(S):</strong> Test One, Test Two<br>"
            "<strong>AGE:</strong> 34 years<br>"
            "<strong>DOB:</strong> 01 January 1990<br>"
            "<strong>PLACE OF BIRTH:</strong> Example, Ontario<br>"
            "<strong>CITIZENSHIP:</strong> Canadian<br>"
            "<strong>HEIGHT:</strong> 180 cm<br>"
            "<strong>WEIGHT:</strong> 80 kg<br>"
            "<strong>HAIR:</strong> Brown<br>"
            "<strong>EYES:</strong> Green<br>"
            "<strong>SCARS &amp; MARKS:</strong> Fictional test mark</p>"
        ),
        "timestamp": {"$date": {"$numberLong": "1715126400000"}},
        "state": "1",
        "files": [
            {
                "file": {
                    "_id": {"$id": "original-image-id"},
                    "fileinputid": "primaryfile",
                    "filetype": "image/jpeg",
                    "imagetype": "original",
                    "filename": "test.jpg",
                    "guid": "test-image",
                }
            },
            {
                "file": {
                    "_id": {"$id": "resized-image-id"},
                    "fileinputid": "primaryfile",
                    "filetype": "image/jpeg",
                    "imagetype": "resized",
                    "filename": "test.jpg",
                    "guid": "test-image",
                }
            },
        ],
    }
    record.update(overrides)
    return record


class OppIngestionTests(unittest.TestCase):
    def test_maps_official_record_with_rich_fields(self):
        result = normalize_opp_record(make_record())

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["id"], "opp-official-test-id")
        self.assertEqual(result["country"], "Canada")
        self.assertEqual(result["regions"], ["Ontario"])
        self.assertEqual(result["reward"], 25000)
        self.assertEqual(result["publishedDate"], "2024-05-07")
        self.assertEqual(result["aliases"], ["Test One", "Test Two"])
        self.assertEqual(result["age"], "34 years")
        self.assertEqual(result["nationality"], "Canadian")
        self.assertEqual(result["height"], "180 cm")
        self.assertEqual(result["distinguishingFeatures"], "Fictional test mark")
        self.assertIn("resized-image-id", result["imageUrl"])
        self.assertEqual(len(result["imageUrls"]), 1)

    def test_excludes_missing_person_and_inactive_records(self):
        self.assertIsNone(normalize_opp_record(make_record(circulartype="missing")))
        self.assertIsNone(normalize_opp_record(make_record(state="0")))

    def test_excludes_records_without_real_images(self):
        self.assertIsNone(normalize_opp_record(make_record(files=[])))


if __name__ == "__main__":
    unittest.main()
