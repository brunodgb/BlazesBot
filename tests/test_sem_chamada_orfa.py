"""NENHUM `self.x` SEM `x`, E NENHUM `memoria.x` SEM `x`.

Este defeito mordeu TRÊS VEZES em 25/08/2026, sempre igual: uma limpeza tirou
métodos de leitura de alvo do `Memory`, e quem chamava ficou para trás.

    'Memory' object has no attribute 'candidato_de_alvo'
    'Memory' object has no attribute 'target_detail'
    'Memory' object has no attribute '_parece_nome'

Nenhum apareceu em teste, porque nenhum caminho de teste passava ali -- os três
só estouraram com o jogo aberto, no meio do `2-DIAGNOSTICO`, DEPOIS de já ter
impresso meio relatório. O terceiro derrubou a varredura antes de ela chegar aos
outros 4 clientes.

Python só descobre atributo faltando na hora da chamada. Este arquivo descobre
antes, lendo o AST -- é a mesma ideia do `tests/test_ecossistemas.py`.

O QUE ELE NÃO PEGA: atributo criado por `setattr`, por metaclasse ou herdado de
classe de fora do projeto. Classes assim são PULADAS de propósito -- acusar o que
não dá para provar transformaria o teste em ruído, e teste ruidoso é desligado.
"""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "blazesbot"

# Métodos que o Python chama sozinho ou que vêm de fora de qualquer classe.
DE_GRACA = frozenset({
    "__class__", "__dict__", "__doc__", "__init__", "__enter__", "__exit__",
})


def _modulos() -> list[Path]:
    return sorted(PACOTE.rglob("*.py"))


def _todas_as_classes() -> dict[str, list[ast.ClassDef]]:
    """Toda classe do pacote, por nome -- para seguir as bases DO PROJETO."""
    mapa: dict[str, list[ast.ClassDef]] = {}
    for caminho in _modulos():
        for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ClassDef):
                mapa.setdefault(no.name, []).append(no)
    return mapa


def _superficie(classe: ast.ClassDef, mapa, vistos: tuple = ()) -> set[str] | None:
    """O que `self` tem: o da classe mais o das bases que são DO PROJETO.

    `None` = não dá para provar lendo o código -- base de fora (`Enum`,
    `Exception`...), base com nome ambíguo no pacote, ou metaclasse. Pular é a
    resposta honesta.

    SEGUIR A BASE DO PROJETO ENTROU EM 26/09/2026. Antes, herdar de qualquer
    coisa tirava a classe da conferência -- e a `JanelaDeVenda`, ao passar a
    herdar do mixin `LeituraDoSlot`, saiu dela sem aviso; as duas rotinas de
    cave, as maiores classes do projeto, sairiam também ao ganhar uma base.
    """
    if classe.keywords:
        return None
    nomes = _definidos(classe)
    for base in classe.bases:
        nome = getattr(base, "id", getattr(base, "attr", None))
        if nome == "object":
            continue
        candidatas = mapa.get(nome or "", [])
        if len(candidatas) != 1 or nome in vistos:
            return None
        herdado = _superficie(candidatas[0], mapa, (*vistos, nome))
        if herdado is None:
            return None
        nomes |= herdado
    return nomes


def _definidos(classe: ast.ClassDef) -> set[str]:
    nomes: set[str] = set()
    for no in classe.body:
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            nomes.add(no.name)
        elif isinstance(no, ast.Assign):
            nomes |= {t.id for t in no.targets if isinstance(t, ast.Name)}
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            nomes.add(no.target.id)
    # Atributos de instância: `self.x = ...` em qualquer método.
    for no in ast.walk(classe):
        alvos: list[ast.expr] = []
        if isinstance(no, ast.Assign):
            alvos = list(no.targets)
        elif isinstance(no, ast.AnnAssign | ast.AugAssign):
            alvos = [no.target]
        elif isinstance(no, ast.For):
            alvos = [no.target]
        elif isinstance(no, ast.With):
            alvos = [i.optional_vars for i in no.items if i.optional_vars]
        for t in alvos:
            for parte in ast.walk(t):
                if (isinstance(parte, ast.Attribute)
                        and isinstance(parte.value, ast.Name)
                        and parte.value.id == "self"):
                    nomes.add(parte.attr)
    return nomes


def _usa_atalho_dinamico(classe: ast.ClassDef) -> bool:
    """`setattr`/`__getattr__` fazem a superfície nascer em tempo de execução."""
    for no in ast.walk(classe):
        if isinstance(no, ast.FunctionDef) and no.name in {
                "__getattr__", "__getattribute__", "__setattr__"}:
            return True
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id in {"setattr", "getattr", "vars"}):
            return True
    return False


def test_nenhuma_classe_chama_self_ponto_nada():
    """`self.x` tem que existir na classe. É o que os três crashes violaram."""
    faltando: list[str] = []
    mapa = _todas_as_classes()

    for caminho in _modulos():
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for classe in [n for n in ast.walk(arvore) if isinstance(n, ast.ClassDef)]:
            superficie = _superficie(classe, mapa)
            if superficie is None or _usa_atalho_dinamico(classe):
                continue
            definidos = superficie | DE_GRACA
            for no in ast.walk(classe):
                if (isinstance(no, ast.Attribute)
                        and isinstance(no.value, ast.Name)
                        and no.value.id == "self"
                        and no.attr not in definidos):
                    faltando.append(
                        f"{caminho.relative_to(RAIZ)}:{no.lineno} "
                        f"{classe.name}.self.{no.attr}")

    assert not faltando, (
        "chamada órfã -- `self.<nome>` sem `<nome>` na classe. É o defeito que "
        "só aparece com o jogo aberto:\n  " + "\n  ".join(faltando))


def test_o_main_so_chama_o_que_o_Memory_tem():
    """O `2-DIAGNOSTICO` é o maior consumidor do `Memory`, e é onde os três
    crashes saíram. Ele não tem classe, então o teste acima não o cobre."""
    from blazesbot.core.memory import Memory

    fonte = (RAIZ / "main.py").read_text(encoding="utf-8")
    tem = {n for n in dir(Memory) if not n.startswith("__")}

    faltando = sorted(
        f"main.py:{n.lineno} memoria.{n.attr}"
        for n in ast.walk(ast.parse(fonte))
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
        and n.value.id == "memoria" and n.attr not in tem)

    assert not faltando, (
        "o main.py chama método que o Memory não tem:\n  " + "\n  ".join(faltando))


def test_parece_nome_separa_nome_de_lixo_binario():
    """`read_string_direct` decodifica com `errors="ignore"`: QUALQUER endereço
    devolve string. Sem o filtro, o censo de entidades vira ficção."""
    from blazesbot.core.memory import Memory

    for nome in ("Blaze Skull Marshal", "Cemetery Guard", "Gun Witch",
                 "BlazesOfGamer", "Ka"):
        assert Memory._parece_nome(nome), nome

    for lixo in ("", "A", "1 ", "12345", "\x01\x02\x03", "x" * 40,
                 "no\x00me", "nome�"):
        assert not Memory._parece_nome(lixo), repr(lixo)



# ===========================================================================
# `settings.<grupo>.<campo>` TAMBÉM É CHAMADA ÓRFÃ
# ===========================================================================
#
# QUARTA VEZ que este defeito morde, em 25/08/2026:
#
#     AttributeError: 'PotionConfig' object has no attribute 'hp_potion'
#
# A tecla de poção mora em `KeyBinds` (tecla descreve o JOGO); o `PotionConfig`
# guarda os LIMIARES. Escrever `settings.potions.hp_potion` passa no ruff, passa
# no import, passa na suíte inteira -- e estoura na PRIMEIRA CURA de verdade,
# porque a leitura vivia dentro de um `lambda` que só é avaliado ali.
#
# Nenhum teste podia pegar isso, porque nenhum teste chega a curar com o jogo
# aberto. Este pega lendo o AST.

def _grupos_de_settings() -> dict[str, set[str]]:
    """Cada grupo de `AccountSettings` e os campos que ele tem."""
    import dataclasses

    from blazesbot.config import AccountSettings

    grupos: dict[str, set[str]] = {}
    for campo in dataclasses.fields(AccountSettings):
        tipo = campo.type
        if isinstance(tipo, str):
            from blazesbot import config as mod
            tipo = getattr(mod, tipo, None)
        if tipo is None or not dataclasses.is_dataclass(tipo):
            continue
        grupos[campo.name] = {f.name for f in dataclasses.fields(tipo)}
        # Propriedades também respondem, e não são campos.
        grupos[campo.name] |= {n for n in dir(tipo) if not n.startswith("_")}
    return grupos


def test_nenhum_settings_ponto_grupo_ponto_campo_inexistente():
    """`settings.potions.hp_potion` compila, importa, e estoura na primeira cura.

    O que este teste lê é a cadeia `<algo>.settings.<grupo>.<campo>`: se o
    `<grupo>` é um dos grupos de `AccountSettings`, o `<campo>` TEM que existir
    nele.
    """
    grupos = _grupos_de_settings()
    faltando: list[str] = []

    for caminho in _modulos():
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            # o nó é `X.<grupo>.<campo>`; o pai imediato precisa ser `.settings`
            if not isinstance(no, ast.Attribute):
                continue
            meio = no.value
            if not isinstance(meio, ast.Attribute):
                continue
            if meio.attr not in grupos:
                continue
            raiz = meio.value
            if not (isinstance(raiz, ast.Attribute) and raiz.attr == "settings"):
                continue
            if no.attr in grupos[meio.attr]:
                continue
            faltando.append(
                f"{caminho.relative_to(RAIZ)}:{no.lineno} "
                f"settings.{meio.attr}.{no.attr}")

    assert not faltando, (
        "campo que NÃO existe no grupo de configuração. Compila, importa, e "
        "estoura só quando aquela linha roda de verdade:\n  "
        + "\n  ".join(faltando))


def test_a_tecla_de_pocao_e_de_sentar_moram_nas_TECLAS():
    """Tecla descreve o JOGO, não o ecossistema -- por isso mora em `KeyBinds`,
    compartilhada. `PotionConfig` guarda os LIMIARES, que são de quem decide."""
    import dataclasses

    from blazesbot.config import KeyBinds, PotionConfig

    teclas = {f.name for f in dataclasses.fields(KeyBinds)}
    limiares = {f.name for f in dataclasses.fields(PotionConfig)}

    assert {"hp_potion", "battle_hp_potion", "sit"} <= teclas
    assert not ({"hp_potion", "sit"} & limiares)
    assert {"hp_pct", "battle_hp_pct"} <= limiares
