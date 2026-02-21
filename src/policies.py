POLICIES = {
    "quiet_hours": {
        "enabled": True,
        "timezone": "UTC",
        "start": "22:00",
        "end": "06:00",
        "behavior": "queue",  # hold alerts unless severity is RED
    },
    "alert_ratelimit": {
        "window_minutes": 60,
        "max_alerts": 2,
    },
    "approvals": {
        "require_manager_ack_for_red": True,
    },
}
