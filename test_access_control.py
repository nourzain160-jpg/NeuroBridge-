import unittest

from access_control import (
    User,
    Resource,
    has_permission,
    can_access_resource,
)


class AccessControlTests(unittest.TestCase):

    def setUp(self):
        self.therapist = User(
            "T001", "therapist", ("P001",)
        )

        self.patient = User(
            "P001", "patient"
        )

        self.other_patient = User(
            "P002", "patient"
        )

        self.admin = User(
            "A001", "administrator"
        )

        self.session = Resource(
            "P001", "S001"
        )

    def test_therapist_can_view_assigned_patient(self):
        self.assertTrue(
            can_access_resource(
                self.therapist,
                "view_session",
                self.session,
            )
        )

    def test_therapist_cannot_view_unassigned_patient(self):
        other_session = Resource("P002", "S002")
        self.assertFalse(
            can_access_resource(
                self.therapist,
                "view_session",
                other_session,
            )
        )

    def test_patient_can_view_own_session(self):
        self.assertTrue(
            can_access_resource(
                self.patient,
                "view_own_session",
                self.session,
            )
        )

    def test_patient_cannot_view_another_patient_session(self):
        self.assertFalse(
            can_access_resource(
                self.other_patient,
                "view_own_session",
                self.session,
            )
        )

    def test_patient_cannot_manage_users(self):
        self.assertFalse(
            has_permission(
                self.patient,
                "manage_users",
            )
        )

    def test_admin_does_not_automatically_access_clinical_records(self):
        self.assertFalse(
            can_access_resource(
                self.admin,
                "view_session",
                self.session,
            )
        )

    def test_unknown_role_is_denied(self):
        unknown_user = User("U001", "unknown")
        self.assertFalse(
            has_permission(
                unknown_user,
                "view_session",
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity = 2)