import os
from typing import Any, Dict, List, Optional

_SUPABASE_URL = os.getenv('SUPABASE_URL')
_SUPABASE_KEY = os.getenv('SUPABASE_KEY')

_sb = None

def _client():
    global _sb
    if _sb is not None:
        return _sb
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
        _sb = create_client(_SUPABASE_URL, _SUPABASE_KEY)
        return _sb
    except Exception:
        return None

TABLE = os.getenv('SUPABASE_TABLE', 'user_keys')

def save_user_keys(user_id: str, device_token: Optional[str], public_key_pem: Optional[str], private_key_pem: Optional[str], extra: Optional[Dict[str, Any]] = None) -> bool:
    sb = _client()
    if sb is None:
        return False
    payload: Dict[str, Any] = {
        'user_id': user_id,
        'device_token': device_token,
        'public_key': public_key_pem,
        'private_key': private_key_pem,
    }
    if extra:
        for k, v in extra.items():
            payload[k] = v
    try:
        # Simple insert; rely on RLS policies configured in Supabase
        sb.table(TABLE).insert(payload).execute()
        return True
    except Exception:
        return False

def list_user_keys(user_id: str) -> List[Dict[str, Any]]:
    sb = _client()
    if sb is None:
        return []
    try:
        res = sb.table(TABLE).select('*').eq('user_id', user_id).order('created_at', desc=True).limit(50).execute()
        data = getattr(res, 'data', None)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []
