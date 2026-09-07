"""O PET BUG NATIVO -- o patch que saiu da engenharia reversa do patcher.

O porquê, os endereços e a desmontagem estão em
`docs/decisoes/pet-bug-engenharia-reversa.md`. Aqui se trava o comportamento,
e o que mais importa é o que ele RECUSA: são seis bytes escritos no CÓDIGO do
jogo, e escrever no lugar errado derruba o cliente do usuário.
"""

from __future__ import annotations

import logging

import pytest

from blazesbot.core import patch_do_cliente as mod

LOG = logging.getLogger("teste.petbug")

BASE = 0x400000
A = mod.ASSINATURAS[0]
B = mod.ASSINATURAS[1]


class Cliente:
    """Um `client.exe` de mentira: uma imagem de bytes que se pode escrever."""

    def __init__(self, imagem: bytes | None = None, pode_abrir=True,
                 tem_modulo=True, escrita_falha=False, protecao_falha=False):
        if imagem is None:
            imagem = bytearray(b"\x00" * 0x400)
            imagem[0x100:0x106] = A.bytes_
            imagem[0x200:0x206] = B.bytes_
        self.imagem = bytearray(imagem)
        self._pode_abrir = pode_abrir
        self._tem_modulo = tem_modulo
        self._escrita_falha = escrita_falha
        self._protecao_falha = protecao_falha
        self.protecoes: list[tuple[int, int]] = []
        self.escritas: list[tuple[int, bytes]] = []

    # -- as pecas que `aplicar` consome --------------------------------
    def abrir(self, pid):
        return 0x1234 if self._pode_abrir else 0

    def fechar(self, handle):
        pass

    def modulo(self, pid):
        return (BASE, len(self.imagem)) if self._tem_modulo else None

    def ler(self, handle, endereco, tamanho):
        i = endereco - BASE
        if i < 0 or i + tamanho > len(self.imagem):
            return None
        return bytes(self.imagem[i:i + tamanho])

    def proteger(self, handle, endereco, tamanho, protecao):
        if self._protecao_falha:
            return None
        self.protecoes.append((endereco, protecao))
        return 0x20

    def escrever(self, handle, endereco, dados):
        if self._escrita_falha:
            return False
        i = endereco - BASE
        self.imagem[i:i + len(dados)] = dados
        self.escritas.append((endereco, bytes(dados)))
        return True


@pytest.fixture(autouse=True)
def _sem_memoria_entre_testes():
    mod.esquecer_o_que_aprendeu()
    yield
    mod.esquecer_o_que_aprendeu()


# ---------------------------------------------------------------------------
# O CAMINHO FELIZ
# ---------------------------------------------------------------------------

def test_patcheia_os_DOIS_sitios():
    c = Cliente()
    r = mod.aplicar(1, LOG, pecas=c)
    assert r.ok and r.aplicou == 2, str(r)
    assert bytes(c.imagem[0x100:0x106]) == mod.SUBSTITUICAO
    assert bytes(c.imagem[0x200:0x206]) == mod.SUBSTITUICAO


def test_devolve_a_protecao_antiga():
    """Deixar a página do CÓDIGO gravável é um presente para qualquer coisa."""
    c = Cliente()
    mod.aplicar(1, LOG, pecas=c)
    for endereco in (BASE + 0x100, BASE + 0x200):
        deste = [p for e, p in c.protecoes if e == endereco]
        assert deste == [mod.PAGE_EXECUTE_READWRITE, 0x20], deste


def test_rodar_DE_NOVO_nao_escreve_nada():
    """Idempotente: sítio já com NOPs não é reescrito."""
    c = Cliente()
    mod.aplicar(1, LOG, pecas=c)
    c.escritas.clear()
    r = mod.aplicar(1, LOG, pecas=c)
    assert r.ok and r.aplicou == 0 and r.ja_estavam == 2, str(r)
    assert c.escritas == []


# ---------------------------------------------------------------------------
# O QUE ELE RECUSA -- a parte que protege o cliente do usuário
# ---------------------------------------------------------------------------

def test_padrao_que_aparece_DUAS_vezes_e_RECUSADO():
    """Com dois candidatos não se sabe qual é o certo, e o errado derruba."""
    imagem = bytearray(b"\x00" * 0x400)
    imagem[0x100:0x106] = A.bytes_
    imagem[0x180:0x186] = A.bytes_        # o duplicado
    imagem[0x200:0x206] = B.bytes_
    c = Cliente(imagem)
    r = mod.aplicar(1, LOG, pecas=c)

    assert not r.ok
    assert any("guardar" in x for x in r.recusados), r.recusados
    assert bytes(c.imagem[0x100:0x106]) == A.bytes_, "escreveu mesmo assim"
    assert r.aplicou == 1, "o outro sítio, que é único, tinha de ser aplicado"


def test_padrao_que_NAO_aparece_e_RECUSADO():
    """Zero ocorrências = o jogo mudou. Recusa e grita, não adivinha."""
    imagem = bytearray(b"\x00" * 0x400)
    imagem[0x200:0x206] = B.bytes_
    c = Cliente(imagem)
    r = mod.aplicar(1, LOG, pecas=c)
    assert not r.ok
    assert any("guardar" in x and "0 ocorrência" in x for x in r.recusados)


def test_o_RVA_GUARDADO_e_conferido_antes_de_escrever():
    """O atalho sem ASLR só é seguro porque os bytes são conferidos.

    Aqui o cliente MUDA embaixo do endereço aprendido -- e o patch tem de
    recusar em vez de NOPar o que estiver ali.
    """
    c = Cliente()
    mod.aplicar(1, LOG, pecas=c)          # aprende os RVAs
    outro = Cliente()
    outro.imagem[0x100:0x106] = b"\x11\x22\x33\x44\x55\x66"
    r = mod.aplicar(2, LOG, pecas=outro)

    assert any("guardar" in x for x in r.recusados), r.recusados
    assert bytes(outro.imagem[0x100:0x106]) == b"\x11\x22\x33\x44\x55\x66"


def test_a_escrita_que_falha_NAO_vira_sucesso():
    c = Cliente(escrita_falha=True)
    r = mod.aplicar(1, LOG, pecas=c)
    assert not r.ok and r.aplicou == 0
    assert len(r.recusados) == 2


def test_sem_VirtualProtectEx_nao_escreve():
    c = Cliente(protecao_falha=True)
    r = mod.aplicar(1, LOG, pecas=c)
    assert not r.ok and c.escritas == []


def test_sem_permissao_no_processo():
    r = mod.aplicar(1, LOG, pecas=Cliente(pode_abrir=False))
    assert not r.ok and "administrador" in (r.erro or "")


def test_sem_o_modulo_do_cliente():
    r = mod.aplicar(1, LOG, pecas=Cliente(tem_modulo=False))
    assert not r.ok and "client.exe" in (r.erro or "")


def test_o_interruptor_DESLIGA_tudo(monkeypatch):
    monkeypatch.setattr(mod, "ATIVADO", False)
    c = Cliente()
    r = mod.aplicar(1, LOG, pecas=c)
    assert not r.ok and c.escritas == []


# ---------------------------------------------------------------------------
# OS BYTES -- eles vieram de uma medição, e não podem mudar por acidente
# ---------------------------------------------------------------------------

def test_os_bytes_sao_os_MESMOS_do_patcher():
    """Extraídos do inicializador estático do `BlazesBot - PetBug.exe`.

    Se alguém "arrumar" um destes valores sem medir de novo, o patch passa a
    escrever outra coisa no código do jogo. Ver
    `docs/decisoes/pet-bug-engenharia-reversa.md`.
    """
    assert A.bytes_ == bytes.fromhex("898fa8100000")   # mov [edi+0x10A8], ecx
    assert B.bytes_ == bytes.fromhex("89bea8100000")   # mov [esi+0x10A8], edi
    assert mod.SUBSTITUICAO == b"\x90" * 6
    assert len(A.bytes_) == len(B.bytes_) == len(mod.SUBSTITUICAO) == 6


# ---------------------------------------------------------------------------
# QUEM RECEBE O PATCH -- decisão do usuário, 07/09/2026
# ---------------------------------------------------------------------------

def test_so_quem_farma_CAVE_recebe_o_patch():
    """*"Vamos executar apenas nos que tiverem executando cave, HH e BC. Os APP
    não precisa aplicar"* — usuário, 07/09/2026.

    `Account.farms` é exatamente `bc_farm or hh_farm`, e é ELE que guarda a
    chamada no supervisor. Uma conta de APP puro fica de fora sozinha.
    """
    from blazesbot.config import Account

    app_puro = Account(login="app")
    assert app_puro.farms is False, "conta de APP entraria no patch"

    for cave in ("bc_farm", "hh_farm"):
        conta = Account(login=cave)
        setattr(conta, cave, True)
        assert conta.farms is True, f"{cave} ficaria SEM o patch"


def test_o_supervisor_guarda_a_chamada_pelo_farms():
    """A trava é o `if`, e ele não pode ser alargado sem alguém perceber.

    Sem esta conferência, mover a chamada para fora do `if self.account.farms`
    passaria despercebido -- e o patch começaria a escrever no cliente de conta
    de APP, que o usuário disse explicitamente para não tocar.
    """
    import inspect
    import re

    from blazesbot.bot import supervisor

    fonte = inspect.getsource(supervisor.AccountSupervisor)
    trecho = re.search(
        r"if self\.account\.farms:\s*\n\s*self\._aplicar_petbug\(\)", fonte)
    assert trecho, ("a chamada do patch saiu de dentro do "
                    "`if self.account.farms:` — contas de APP passariam a ser "
                    "patcheadas")
