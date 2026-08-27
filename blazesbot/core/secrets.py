"""
Criptografia de senhas com DPAPI do Windows.

Por que DPAPI: a chave é derivada da conta de usuário do Windows, então não
existe chave para gerenciar nem embutir no binário. Um arquivo de contas
copiado para outra máquina/usuário simplesmente não descriptografa.

Os bots open source de referência guardam senha em texto puro no
accounts.json. Como o BlazesBot vai ser compartilhado, isso não é aceitável.
"""
from __future__ import annotations

import base64

try:
    import win32crypt
    _HAS_DPAPI = True
except ImportError:  # pragma: no cover
    _HAS_DPAPI = False

_PREFIX = "dpapi:"
_ENTROPY = b"BlazesBot/v1"


def encrypt(plaintext: str) -> str:
    """Cifra uma senha. Devolve string com prefixo identificador."""
    if not plaintext:
        return ""
    if not _HAS_DPAPI:
        return plaintext
    blob = win32crypt.CryptProtectData(
        plaintext.encode("utf-8"), "BlazesBot", _ENTROPY, None, None, 0
    )
    return _PREFIX + base64.b64encode(blob).decode("ascii")


def decrypt(stored: str) -> str:
    """Decifra. Aceita valor em texto puro (retrocompatível) sem quebrar."""
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored  # texto puro legado
    if not _HAS_DPAPI:
        raise RuntimeError("pywin32 ausente: não é possível decifrar senhas.")
    blob = base64.b64decode(stored[len(_PREFIX):])
    _, data = win32crypt.CryptUnprotectData(blob, _ENTROPY, None, None, 0)
    return data.decode("utf-8")


def is_encrypted(stored: str) -> bool:
    return bool(stored) and stored.startswith(_PREFIX)


def dpapi_available() -> bool:
    return _HAS_DPAPI
