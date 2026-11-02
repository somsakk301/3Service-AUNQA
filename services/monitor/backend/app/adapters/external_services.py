"""Integration boundaries for the two external services.

Service A -> TBD / SPEC GAP
Service B -> TBD / SPEC GAP

No endpoints, authentication, payloads or workflows are assumed. Methods are
added here once the interfaces are defined.

Document Generation (project owner, 2026-09-26) needs no adapter: it PULLS. It calls
`GET /api/monitor?curriculumCode=...`, reads `generationReadiness.status` (READY / NOT_READY) and
fetches what it generates from its own database. Mornitor makes no outbound call, push or webhook.
"""
from abc import ABC


class ExternalServiceAAdapter(ABC):
    """TBD / SPEC GAP"""


class ExternalServiceBAdapter(ABC):
    """TBD / SPEC GAP"""
