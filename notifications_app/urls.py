from django.urls import path
from .views import (
    NotificationListView, NotificationMarkReadView,
    NotificationToggleReadView, NotificationPreferencesView,
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/read/', NotificationMarkReadView.as_view(), name='notification-read'),
    path('<int:pk>/toggle-read/', NotificationToggleReadView.as_view(), name='notification-toggle-read'),
    path('preferences/', NotificationPreferencesView.as_view(), name='notification-preferences'),
]
