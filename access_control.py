from dataclasses import dataclass
from typing import Optional


# Permissions assigned to each role
ROLE_PERMISSIONS = {
    "administrator": {
        "manage_users",
        "manage_access",
        "manage_system_settings",
    },
    "therapist": {
        "create_session",
        "view_session",
        "view_sensor_data",
        "view_results",
    },
    "patient": {
        "view_own_session",
        "view_own_results",
    },
}


@dataclass
class User:
    user_id: str
    role: str
    assigned_patient_ids: tuple = ()


@dataclass
class Resource:
    patient_id: str
    session_id: str


def has_permission(user: User, action: str) -> bool:
    """Check whether the user's role permits an action."""
    permissions = ROLE_PERMISSIONS.get(user.role, set())
    return action in permissions


def can_access_resource(
    user: User,
    action: str,
    resource: Resource,
) -> bool:
    """Check role permission and patient/session access scope."""

    if not has_permission(user, action):
        return False

    if user.role == "administrator":
        # Administrative permissions do not automatically
        # grant access to rehabilitation records.
        return False

    if user.role == "therapist":
        return resource.patient_id in user.assigned_patient_ids

    if user.role == "patient":
        return user.user_id == resource.patient_id

    return False


if __name__ == "__main__":
    therapist = User(
        user_id = "T001",
        role = "therapist",
        assigned_patient_ids = ("P001", "P002"),
    )

    patient = User(
        user_id = "P001",
        role = "patient",
    )

    admin = User(
        user_id = "A001",
        role = "administrator",
    )

    session = Resource(
        patient_id = "P001",
        session_id = "S001",
    )

    print(
        "Therapist access:",
        can_access_resource(
            therapist, "view_session", session
        ),
    )

    print(
        "Patient access:",
        can_access_resource(
            patient, "view_own_session", session
        ),
    )

    print(
        "Admin clinical-record access:",
        can_access_resource(
            admin, "view_session", session
        ),
    )