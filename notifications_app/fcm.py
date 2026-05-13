"""Helper para envio de notificações push via Firebase Cloud Messaging.

A inicialização do Firebase Admin SDK é feita uma única vez por processo,
usando credenciais lidas do filesystem (`firebase-service-account.json`)
ou da variável de ambiente `FIREBASE_SERVICE_ACCOUNT_JSON` (preferido em
produção — Railway etc.).

Uso:
    from notifications_app.fcm import send_push_to_user
    send_push_to_user(user_id=42, title='Olá', body='Mundo', data={'type': 'agenda'})
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, messaging

from .models import FcmTokens

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_initialized = False


def _load_credentials() -> Optional[credentials.Certificate]:
    """Carrega credenciais do service account.

    1º preferência: env var ``FIREBASE_SERVICE_ACCOUNT_JSON`` (conteúdo JSON
       inline — para Railway, sem expor o ficheiro no container).
    2º preferência: ficheiro ``firebase-service-account.json`` ao lado do
       ``manage.py``.

    Devolve ``None`` se não houver credenciais — o helper passa a ser no-op
    em vez de rebentar (útil para ambientes de teste).
    """
    raw = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
    if raw:
        try:
            data = json.loads(raw)
            return credentials.Certificate(data)
        except Exception as e:
            logger.error('FIREBASE_SERVICE_ACCOUNT_JSON inválido: %s', e)

    candidate = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'firebase-service-account.json',
    )
    if os.path.exists(candidate):
        return credentials.Certificate(candidate)
    return None


def _ensure_initialized() -> bool:
    global _initialized
    if _initialized:
        return True
    with _init_lock:
        if _initialized:
            return True
        try:
            if firebase_admin._apps:
                _initialized = True
                return True
            cred = _load_credentials()
            if cred is None:
                logger.warning(
                    'Firebase Admin SDK sem credenciais — push '
                    'notifications desativadas.'
                )
                return False
            firebase_admin.initialize_app(cred)
            _initialized = True
            return True
        except Exception as e:
            logger.error('Falha a inicializar Firebase Admin: %s', e)
            return False


def send_push_to_user(
    user_id: int,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> int:
    """Envia push para todos os tokens registados deste utilizador.

    Devolve o número de tokens para os quais o envio teve sucesso.
    Tokens inválidos são removidos automaticamente da BD.
    """
    if not _ensure_initialized():
        return 0

    tokens_qs = FcmTokens.objects.filter(user_id=user_id)
    tokens = list(tokens_qs.values_list('token', flat=True))
    if not tokens:
        return 0

    payload = {k: str(v) for k, v in (data or {}).items()}

    # Em batches de 500 (limite FCM por chamada send_each_for_multicast)
    success = 0
    failed_tokens: list[str] = []
    for i in range(0, len(tokens), 500):
        chunk = tokens[i:i + 500]
        try:
            response = messaging.send_each_for_multicast(
                messaging.MulticastMessage(
                    tokens=chunk,
                    notification=messaging.Notification(title=title, body=body),
                    data=payload,
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotificationConfig(
                            channel_id='vision4farms_default',
                            sound='default',
                        ),
                    ),
                )
            )
            for idx, resp in enumerate(response.responses):
                if resp.success:
                    success += 1
                else:
                    err = resp.exception
                    code = getattr(err, 'code', '')
                    if code in (
                        'registration-token-not-registered',
                        'invalid-argument',
                    ):
                        failed_tokens.append(chunk[idx])
                    logger.info('FCM falhou para token: %s', err)
        except Exception as e:
            logger.error('Erro a enviar FCM batch: %s', e)

    if failed_tokens:
        FcmTokens.objects.filter(token__in=failed_tokens).delete()

    return success
