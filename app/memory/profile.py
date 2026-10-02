"""Default initial user profile template for open-source Echo.

When a user initializes Echo, this profile template is seeded into the database,
and Echo will dynamically learn and update fields during conversation.
"""

USER_PROFILE: dict[str, object] = {
    "name": "User",
    "preferred_name": "Friend",
    "nickname": "EchoUser",
    "occupation": [
        "Software Engineer",
    ],
    "interests": [
        "Artificial Intelligence",
        "Open Source",
        "Automation",
        "Technology",
    ],
    "diet": {
        "goal": "Maintain energy and general health.",
        "dietary_preferences": [
            "balanced meals",
            "whole foods",
        ],
        "favorite_foods": [],
        "disliked_foods": [],
        "habits": [],
    },
    "sports": {
        "favorite_sports": [],
    },
    "health_profile": {
        "primary_goal": "Stay healthy and fit",
        "exercise": [],
        "meal_reminders": False,
    },
    "current_projects": {},
    "work": {
        "company": "",
        "collaborators": [],
    },
    "relationships": {},
    "lifestyle": [],
    "goals": [
        "Build useful open-source AI tools",
    ],
}
