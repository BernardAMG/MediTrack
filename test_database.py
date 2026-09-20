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


if __name__ == "__main__":
    unittest.main()