"""
Router barrel export — import all routers in one line from main.py.

Usage:
    from app.routers import all_routers
    for prefix, router, tags in all_routers:
        app.include_router(router, prefix=prefix, tags=tags)
"""

from fastapi import APIRouter

from app.api.v1.analytics_router import router as analytics_router
from app.api.v1.auth_router import router as auth_router
from app.api.v1.notification_router import router as notification_router
from app.api.v1.permissions_router import router as permission_router
from app.api.v1.profile_router import router as profile_router
from app.api.v1.ticket_router import router as ticket_router
from app.api.v1.user_router import router as user_router
from app.api.v1.feedback_router import router as feedback_router

# Use list[str] directly — matches FastAPI's expected type
all_routers: list[tuple[str, APIRouter, list[str]]] = [
    ("/auth",          auth_router,         ["Auth"]),
    ("/users",         user_router,         ["Users"]),
    ("/profile",       profile_router,      ["Profile"]),
    ("/tickets",       ticket_router,       ["Tickets"]),
    ("/notifications", notification_router, ["Notifications"]),
    ("/permissions",   permission_router,   ["Permissions"]),
    ("/analytics",     analytics_router,    ["Analytics"]),
   ("/feedback", feedback_router, ["Feedback"]),

]

__all__ = [
    "all_routers",
    "analytics_router",
    "auth_router",
    "notification_router",
    "permission_router",
    "profile_router",
    "ticket_router",
    "user_router",
]