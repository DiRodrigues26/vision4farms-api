from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from .models import Notifications, NotificationPreferences


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notifications
        fields = [
            'notification_id', 'notification_type', 'notification_title',
            'notification_body', 'notification_read', 'notification_read_at',
            'farm_id', 'land_id', 'activity_id', 'agenda_id',
            'observation_id', 'created_at',
        ]


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notifications.objects.filter(
            user=self.request.user,
            deleted_at__isnull=True
        ).order_by('-created_at')


class NotificationMarkReadView(APIView):
    """Marca uma notificação como lida."""

    def patch(self, request, pk):
        try:
            n = Notifications.objects.get(
                notification_id=pk, user=request.user
            )
            n.notification_read = 1
            n.notification_read_at = timezone.now()
            n.save(update_fields=['notification_read', 'notification_read_at'])
            return Response({'detail': 'Marcada como lida.'})
        except Notifications.DoesNotExist:
            return Response({'detail': 'Não encontrada.'}, status=status.HTTP_404_NOT_FOUND)


class NotificationToggleReadView(APIView):
    """Alterna o estado lido/não lido de uma notificação."""

    def patch(self, request, pk):
        try:
            n = Notifications.objects.get(
                notification_id=pk, user=request.user
            )
            if n.notification_read == 1:
                n.notification_read = 0
                n.notification_read_at = None
            else:
                n.notification_read = 1
                n.notification_read_at = timezone.now()
            n.save(update_fields=['notification_read', 'notification_read_at'])
            return Response(NotificationSerializer(n).data)
        except Notifications.DoesNotExist:
            return Response({'detail': 'Não encontrada.'}, status=status.HTTP_404_NOT_FOUND)


class NotificationPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreferences
        fields = [
            'notify_activity', 'notify_agenda', 'notify_observation',
            'notify_irrigation', 'notify_system', 'reminder_hours',
        ]


class NotificationPreferencesView(APIView):
    """GET — devolve preferências do user (cria defaults se não existir).
       PATCH — atualiza preferências."""

    def get(self, request):
        prefs, _ = NotificationPreferences.objects.get_or_create(user=request.user)
        return Response(NotificationPreferencesSerializer(prefs).data)

    def patch(self, request):
        prefs, _ = NotificationPreferences.objects.get_or_create(user=request.user)
        ser = NotificationPreferencesSerializer(prefs, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
