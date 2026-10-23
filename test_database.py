import unittest
import os
import csv
from datetime import datetime
import database
from app import should_alert

TEST_DB = "test_meditrack.db"

class TestDatabase(unittest.TestCase):

    def setUp(self):
        database.DATABASE_FILE = TEST_DB
        database.create_users_table()
        database.create_medications_table()
        database.create_dose_records_table()
        database.create_care_recipients_table()
        database.add_recipient_id_column()
        database.add_quantity_and_expiry_columns()
        database.create_medication_schedules_table()
        database.add_schedule_id_column_to_dose_records()
        database.migrate_comma_times_to_schedules()

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

    def test_insert_medication_creates_schedules(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        med_id = database.insert_medication(user_id, "Metformin", "500mg", "08:00, 14:00, 20:00", "3x daily")
        schedules = database.get_schedules_for_medication(med_id)
        self.assertEqual(len(schedules), 3)
        times = [s[2] for s in schedules]
        self.assertEqual(times, ["08:00", "14:00", "20:00"])

    def test_update_medication_updates_schedules(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        med_id = database.insert_medication(user_id, "Metformin", "500mg", "08:00, 20:00", "twice daily")
        database.update_medication(med_id, "Metformin", "1000mg", "09:00", "once daily")
        schedules = database.get_schedules_for_medication(med_id)
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0][2], "09:00")

    def test_delete_medication_cascades_schedules(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        med_id = database.insert_medication(user_id, "Metformin", "500mg", "08:00, 20:00", "twice daily")
        schedules = database.get_schedules_for_medication(med_id)
        self.assertEqual(len(schedules), 2)

        database.delete_medication(med_id)
        schedules_after = database.get_schedules_for_medication(med_id)
        self.assertEqual(len(schedules_after), 0)

    def test_insert_dose_record_with_schedule(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        med_id = database.insert_medication(user_id, "Panadol", "500mg", "08:00", "daily")
        schedules = database.get_schedules_for_medication(med_id)
        sched_id = schedules[0][0]

        database.insert_dose_record(med_id, "taken", sched_id)
        history = database.get_dose_history_for_user(user_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0][0], "Panadol")
        self.assertEqual(history[0][1], "taken")
        self.assertEqual(history[0][3], "08:00")

    def test_migrate_comma_times_to_schedules_idempotent(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        # Simulate legacy insert without schedules by deleting schedules table entries
        med_id = database.insert_medication(user_id, "Aspirin", "100mg", "07:00, 19:00", "daily")
        conn = database.get_connection()
        conn.execute("DELETE FROM medication_schedules WHERE medication_id = ?", (med_id,))
        conn.commit()
        conn.close()

        self.assertEqual(len(database.get_schedules_for_medication(med_id)), 0)

        # Run migration
        database.migrate_comma_times_to_schedules()
        schedules = database.get_schedules_for_medication(med_id)
        self.assertEqual(len(schedules), 2)
        times = [s[2] for s in schedules]
        self.assertIn("07:00", times)
        self.assertIn("19:00", times)

        # Running again should not duplicate rows (idempotent)
        database.migrate_comma_times_to_schedules()
        schedules_again = database.get_schedules_for_medication(med_id)
        self.assertEqual(len(schedules_again), 2)

    def test_get_adherence_report_data_and_csv_export(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        database.insert_care_recipient(user_id, "Grandma", "Grandmother")
        recipients = database.get_care_recipients_for_caregiver(user_id)
        rec_id = recipients[0][0]

        med_id = database.insert_medication(user_id, "Lisinopril", "10mg", "08:00", "daily", recipient_id=rec_id)
        schedules = database.get_schedules_for_medication(med_id)
        sched_id = schedules[0][0]

        database.insert_dose_record(med_id, "taken", sched_id)
        database.insert_dose_record(med_id, "skipped", sched_id)

        report = database.get_adherence_report_data(user_id)
        self.assertEqual(len(report), 2)
        # Taken at, Name, Dosage, Scheduled Slot, Recipient Name, Status
        self.assertEqual(report[0][1], "Lisinopril")
        self.assertEqual(report[0][2], "10mg")
        self.assertEqual(report[0][3], "08:00")
        self.assertEqual(report[0][4], "Grandma")

        # Test CSV generation
        test_csv_path = "test_adherence_export.csv"
        try:
            success, path = database.export_adherence_to_csv(user_id, test_csv_path)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(test_csv_path))

            with open(test_csv_path, mode="r", encoding="utf-8") as f:
                reader = list(csv.reader(f))
                self.assertEqual(reader[0], ["Date & Time", "Medication", "Dosage", "Scheduled Slot", "Recipient", "Status"])
                self.assertEqual(len(reader), 3)  # header + 2 records
                self.assertEqual(reader[1][1], "Lisinopril")
                self.assertEqual(reader[1][4], "Grandma")
        finally:
            if os.path.exists(test_csv_path):
                os.remove(test_csv_path)

    def test_should_alert_window_timing(self):
        sched_time = "08:00"

        # Exactly at scheduled time
        dt_exact = datetime(2026, 10, 23, 8, 0, 0)
        self.assertTrue(should_alert(sched_time, dt_exact, window_minutes=15))

        # 5 minutes after scheduled time (within 15m window)
        dt_5m_after = datetime(2026, 10, 23, 8, 5, 0)
        self.assertTrue(should_alert(sched_time, dt_5m_after, window_minutes=15))

        # Exactly 15 minutes after (edge of window)
        dt_15m_after = datetime(2026, 10, 23, 8, 15, 0)
        self.assertTrue(should_alert(sched_time, dt_15m_after, window_minutes=15))

        # 16 minutes after scheduled time (past window)
        dt_16m_after = datetime(2026, 10, 23, 8, 16, 0)
        self.assertFalse(should_alert(sched_time, dt_16m_after, window_minutes=15))

        # 1 minute before scheduled time (too early)
        dt_1m_before = datetime(2026, 10, 23, 7, 59, 59)
        self.assertFalse(should_alert(sched_time, dt_1m_before, window_minutes=15))

        # Invalid strings
        self.assertFalse(should_alert("", dt_exact))
        self.assertFalse(should_alert("invalid", dt_exact))

    def test_refill_medication_increments_stock(self):
        database.insert_user("Test User", "test@example.com", "fakehash")
        user = database.get_user_by_email("test@example.com")
        user_id = user[0]

        med_id = database.insert_medication(user_id, "Metformin", "500mg", "08:00", "daily", quantity_remaining=10)
        database.refill_medication(med_id, 30)
        meds = database.get_medications_for_user(user_id)
        self.assertEqual(meds[0][9], 40)

        # Refill on medication with initially None stock
        med_id2 = database.insert_medication(user_id, "Aspirin", "100mg", "08:00", "daily", quantity_remaining=None)
        database.refill_medication(med_id2, 50)
        meds2 = database.get_medications_for_user(user_id)
        aspirin = next(m for m in meds2 if m[0] == med_id2)
        self.assertEqual(aspirin[9], 50)

if __name__ == "__main__":
    unittest.main()