import unittest
import os
import database

TEST_DB = "test_meditrack.db"

class TestDatabase(unittest.TestCase):

    def setUp(self):
        database.DATABASE_FILE = TEST_DB
        database.create_users_table()
        database.create_medications_table()
        database.create_care_recipients_table()
        database.add_recipient_id_column()
        database.add_quantity_and_expiry_columns()

    def tearDown(self):
        """Runs after every single test method — cleans up the test database file."""
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_insert_user_succeeds(self):
        success, message = database.insert_user("Test User", "test@example.com", "fakehash")
        self.assertTrue(success)

    def test_insert_duplicate_email_fails(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        success, message = database.insert_user("Another User", "test@example.com", "fakehash")
        self.assertFalse(success)

    def test_login_with_correct_password_succeeds(self):
        hashed = database.hash_password("mypassword")
        database.insert_user("Test User", "test@example.com", hashed)
        success, message = database.login_user("test@example.com", "mypassword")
        self.assertTrue(success)

    def test_login_with_wrong_password_fails(self):
        hashed = database.hash_password("mypassword")
        database.insert_user("Test User", "test@example.com", hashed)
        success, message = database.login_user("test@example.com", "wrongpassword")
        self.assertFalse(success)

    def test_login_with_unknown_email_fails(self):
        success, message = database.login_user("nobody@example.com", "anything")
        self.assertFalse(success)

    def test_insert_and_retrieve_medication(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        database.insert_medication(user_id, "Panadol", "500mg", "08:00", "daily")
        meds = database.get_medications_for_user(user_id)

        self.assertEqual(len(meds), 1)
        self.assertEqual(meds[0][2], "Panadol")

    def test_decrement_quantity_reduces_by_one(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        database.insert_medication(user_id, "Panadol", "500mg", "08:00", "daily", quantity_remaining=10)
        meds = database.get_medications_for_user(user_id)
        medication_id = meds[0][0]

        database.decrement_quantity(medication_id)
        meds = database.get_medications_for_user(user_id)
        self.assertEqual(meds[0][9], 9)

    def test_insert_medications_batch(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        batch = [
            ("Amlodipine", "5mg", "08:00", "daily", None, 30, None),
            ("Metformin", "500mg", "08:00, 20:00", "twice daily", None, 60, None),
        ]
        database.insert_medications_batch(user_id, batch)
        meds = database.get_medications_for_user(user_id)
        self.assertEqual(len(meds), 2)
        names = [m[2] for m in meds]
        self.assertIn("Amlodipine", names)
        self.assertIn("Metformin", names)

    def test_update_care_recipient(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        database.insert_care_recipient(user_id, "Mothe", "Mothe")
        recipients = database.get_care_recipients_for_caregiver(user_id)
        rec_id = recipients[0][0]

        database.update_care_recipient(rec_id, "Mother", "Mother")
        updated = database.get_care_recipients_for_caregiver(user_id)
        self.assertEqual(updated[0][2], "Mother")
        self.assertEqual(updated[0][3], "Mother")

    def test_delete_care_recipient_unlinks_medications(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        database.insert_care_recipient(user_id, "Mother", "Mother")
        recipients = database.get_care_recipients_for_caregiver(user_id)
        rec_id = recipients[0][0]

        database.insert_medication(user_id, "Panadol", "500mg", "08:00", "daily", recipient_id=rec_id)
        meds = database.get_medications_for_user(user_id)
        self.assertEqual(meds[0][7], rec_id)

        database.delete_care_recipient(rec_id)
        remaining_recipients = database.get_care_recipients_for_caregiver(user_id)
        self.assertEqual(len(remaining_recipients), 0)

        # Medication should still exist, but recipient_id is now None
        meds_after = database.get_medications_for_user(user_id)
        self.assertEqual(len(meds_after), 1)
        self.assertIsNone(meds_after[0][7])

if __name__ == "__main__":
    unittest.main()