"""Generate a local, non-publishing NearU Social Command test run."""

from __future__ import annotations

import json

from agentfoundry.social import (
    NEARU_IDEAS,
    Channel,
    SocialMediaManager,
    nearu_founding_1000_campaign,
    nearu_project,
)


def main() -> None:
    manager = SocialMediaManager()
    project = nearu_project()
    campaign = nearu_founding_1000_campaign()
    manager.add_project(project)
    calendar = manager.build_calendar(campaign)
    drafts = []
    for index, entry in enumerate(calendar):
        draft = manager.create_draft(
            campaign=campaign,
            channel=Channel(entry["channel"]),
            pillar=entry["pillar"],
            idea=NEARU_IDEAS[index % len(NEARU_IDEAS)],
            scheduled_for=entry["date"],
        )
        drafts.append({
            "date": draft.scheduled_for,
            "channel": draft.channel.value,
            "pillar": draft.pillar,
            "hook": draft.hook,
            "body": draft.body,
            "call_to_action": draft.call_to_action,
            "hashtags": draft.hashtags,
            "status": draft.status.value,
        })
    print(json.dumps({
        "project": project.name,
        "campaign": campaign.name,
        "public_actions_performed": 0,
        "drafts": drafts,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
