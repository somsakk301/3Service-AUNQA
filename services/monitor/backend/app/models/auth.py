"""Identity of a signed-in user (project owner, 2026-10-04: Authentication), used only to say who recorded a
review (`review.recordedBy`). Not a role or a permission: no such concept exists in this round — any signed-in
user may record a review of a PS the configuration reviews by the user."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    name: str
