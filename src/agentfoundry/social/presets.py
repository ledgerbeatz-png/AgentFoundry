from __future__ import annotations

from .models import ApprovalMode, Campaign, Channel, ProjectBrand


def nearu_project() -> ProjectBrand:
    return ProjectBrand(
        project_id="nearu",
        name="NearU",
        summary=(
            "NearU startet bewusst lokal, damit Singles nicht wieder in einer leeren "
            "Dating-App landen. Founding-Mitglieder erhalten dauerhaft drei freie Matches pro Monat."
        ),
        audience="aktive Singles",
        objective="1.000 aktive Singles aus Frankfurt und Rhein-Main gewinnen",
        tone=("vertrauenswürdig", "direkt", "lokal", "respektvoll"),
        channels=(Channel.X, Channel.TIKTOK, Channel.INSTAGRAM, Channel.FACEBOOK),
        content_pillars=(
            "Founding 1000",
            "Dating im Rhein-Main-Gebiet",
            "Vertrauen und echte Profile",
            "Dating-Müdigkeit",
            "Community-Aufbau",
        ),
        region="Frankfurt und Rhein-Main",
        website="NearU60311",
        forbidden_claims=(
            "garantiertes match",
            "garantierter partner",
            "unbegrenzte freie matches",
            "4,99 €",
            "nur ein match",
        ),
        approval_mode=ApprovalMode.APPROVAL_REQUIRED,
    )


def nearu_founding_1000_campaign(
    start_date: str = "2026-09-21",
    end_date: str = "2026-09-27",
) -> Campaign:
    return Campaign(
        campaign_id="founding-1000",
        project_id="nearu",
        name="Founding 1000",
        goal="1.000 aktive Singles aus Frankfurt und Rhein-Main gewinnen",
        call_to_action="Werde Teil der Founding 1000: NearU60311",
        start_date=start_date,
        end_date=end_date,
        posts_per_week=5,
    )


NEARU_IDEAS = (
    "1.000 Singles. Eine Region. Dating neu gedacht.",
    "Warum lokale Dichte wichtiger ist als Millionen Karteileichen",
    "Drei freie Matches pro Monat – dauerhaft für die Founding 1000",
    "Dating ohne Fake-Profile und leere Versprechen",
    "Frankfurt, Offenbach, Wiesbaden, Mainz, Darmstadt und die Region kommen zusammen",
)
