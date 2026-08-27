"""
Descoberta automática do ponteiro base do jogador.

POR QUE ISTO EXISTE

O mapa de memória do BlazesBot herda os offsets dos bots do T-R0XX, feitos para
o cliente ver.6139. Os offsets DENTRO da struct do personagem (HP em 0x3B8,
coordenadas em 0x810/0x814) são estáveis desde a ver.5135 -- comparei três
versões e não mudaram. O que muda entre versões é o ENDEREÇO ESTÁTICO onde o
cliente guarda o ponteiro para essa struct.

Quando esse endereço muda, todas as leituras de memória falham em cascata: HP,
posição, nome, alvo. E como o bot usa essas leituras para saber se entrou no
mundo, ele passa a se comportar de forma errática.

COMO FUNCIONA A BUSCA

Em vez de pedir para você caçar o endereço no Cheat Engine, a busca usa o nome
do personagem como âncora:

  1. Procura a string do nome do personagem em toda a memória do processo.
  2. Para cada ocorrência, o começo da struct estaria em (endereço - 0xBC),
     porque o nome fica nesse offset dentro do objeto.
  3. Valida o candidato: HP, HP máximo, nível e coordenadas têm que fazer
     sentido. Isso descarta ocorrências do nome em outros lugares (chat, lista
     de amigos, cache de rede).
  4. Procura, na região do módulo do jogo, um endereço estático cujo valor
     aponte para a struct validada. Esse é o ponteiro base.
  5. Imprime o RVA pronto para colar em core/memory.py.
"""
from __future__ import annotations

import struct
from collections.abc import Iterator

import pymem

from ..core.entidades import (
    coordenada_plausivel,
    hp_plausivel,
    nivel_plausivel,
)
from ..core.memory import (
    IMAGE_BASE,
    OFF_HP,
    OFF_LEVEL,
    OFF_MAX_HP,
    OFF_NAME,
    OFF_X,
    OFF_Y,
)

# Faixa onde vale procurar o ponteiro estático: a imagem do executável mais uma
# margem generosa para os segmentos de dados do cliente.
STATIC_SCAN_START = IMAGE_BASE
STATIC_SCAN_END = IMAGE_BASE + 0x0140_0000
CHUNK = 0x10_0000


# OS FILTROS DE PLAUSIBILIDADE SUBIRAM para `core/entidades.py` em 26/08/2026,
# quando a investigação do alvo perdido (o `9-VIGIAR-COMBATE`) precisou fazer a
# MESMA pergunta -- e a reimplementou pela metade, aprovando `hp=1/390876288`
# como entidade na primeira medição com o jogo na frente. Ver o cabeçalho de
# lá. Os nomes locais ficam como apelido: o resto deste arquivo já os usa.
_plausible_hp = hp_plausivel
_plausible_level = nivel_plausivel
_plausible_coord = coordenada_plausivel


class BaseFinder:
    def __init__(self, pid: int) -> None:
        self.pm = pymem.Pymem()
        self.pm.open_process_from_id(pid)
        self.pid = pid

    # -- leitura tolerante -------------------------------------------------

    def _int(self, addr: int) -> int | None:
        try:
            return self.pm.read_int(addr)
        except Exception:
            return None

    def _byte(self, addr: int) -> int | None:
        try:
            return self.pm.read_bytes(addr, 1)[0]
        except Exception:
            return None

    def _float(self, addr: int) -> float | None:
        try:
            return self.pm.read_float(addr)
        except Exception:
            return None

    # -- passo 1: achar a string do nome -----------------------------------

    def find_name_addresses(self, name: str, limit: int = 400) -> list[int]:
        """Endereços onde a string do nome do personagem aparece."""
        pattern = name.encode("utf-8") + b"\x00"
        try:
            hits = self.pm.pattern_scan_all(pattern, return_multiple=True)
        except Exception:
            hits = []
        if not hits:
            return []
        return list(hits)[:limit]

    # -- passo 2 e 3: validar o objeto do jogador ---------------------------

    def describe_object(self, obj: int, aceitar_morto: bool = False) -> dict | None:
        """Lê os campos conhecidos de um candidato a struct de entidade.

        TRÊS FILTROS ENTRARAM DEPOIS, cada um por um falso positivo REAL medido no
        jogo. Buscando `Snake Captor`, duas ocorrências na tabela de nomes do
        cliente passavam pela validação antiga e apareciam como se fossem mobs:

            0x05b47a65   nível 71   HP 353380/1245188   posição (0, 0)
            0x05b5767a   nível 71   HP 353380/1245188   posição (0, 0)

        E o estrago não era só cosmético: a âncora do mapeamento da grade era o
        candidato de MENOR endereço, então ela caía num desses, e o array de
        entidades não era mapeado -- o relatório dizia "só a própria âncora
        respondeu" com 8 mobs de verdade na lista.

        Os filtros, e o que cada um pega:

          1. ENDEREÇO ALINHADO em 4. Struct de objeto sempre é; `0x05b47a65`
             termina em 5. Sozinho este já derrubaria os dois.
          2. HP <= HP MÁXIMO. Relação que vale em qualquer entidade viva.
          3. POSIÇÃO NÃO É (0,0). Entidade no mundo tem coordenada; (0,0) é o que
             sobra quando os bytes lidos não são coordenada nenhuma.
        """
        if obj % 4:
            return None

        hp = self._int(obj + OFF_HP)
        max_hp = self._int(obj + OFF_MAX_HP)
        level = self._byte(obj + OFF_LEVEL)
        raw_x = self._float(obj + OFF_X)
        raw_y = self._float(obj + OFF_Y)

        # ===============================================================
        # `hp = 0` E ENTIDADE DE VERDADE -- e o filtro apagava todas
        # ===============================================================
        #
        # `_plausible_hp` exige `1 <= valor`, entao **todo cadaver era descartado
        # em silencio**. Medido em 20/08/2026: em nenhum dos seis relatorios do
        # `10-DESCOBRIR-ALVO` existe UMA linha com `hp = 0`, enquanto o
        # `combate.log` mostra o cadaver parado em `0/100` por 7 a 13 segundos.
        #
        # O estrago nao foi cosmetico. Eu li a grade cair **40 -> 39 -> 38** a
        # cada morte e conclui, em maiusculas, que *"a struct do mob morto e
        # REMOVIDA pelo cliente"*. Era o meu proprio filtro tirando a linha. A
        # conclusao virou regra no CLAUDE.md e sustentou uma decisao de desenho
        # sobre qual sinal de morte usar.
        #
        # `aceitar_morto` deixa o chamador escolher, e o default preserva o
        # comportamento antigo: quem procura a struct do JOGADOR (`find_base`)
        # nao ganha nada com cadaver na lista, e a busca dele foi calibrada com o
        # filtro ligado. Quem mapeia a GRADE precisa deles.
        #
        # Os outros tres filtros continuam inteiros -- alinhamento, `hp <=
        # max_hp` e posicao != (0,0) -- e sao eles que pegavam os falsos
        # positivos descritos abaixo.
        piso = 0 if aceitar_morto else 1
        if hp is None or not piso <= hp <= 5_000_000:
            return None
        if not _plausible_hp(max_hp):
            return None
        if hp > max_hp:
            return None
        if not _plausible_level(level):
            return None
        if not (_plausible_coord(raw_x) and _plausible_coord(raw_y)):
            return None
        if int(raw_x / 20.0) == 0 and int(raw_y / 20.0) == 0:
            return None

        return {
            "obj": obj,
            "hp": hp,
            "max_hp": max_hp,
            "level": level,
            "x": int(raw_x / 20.0),
            "y": int(raw_y / 20.0),
        }

    def candidate_objects(self, name: str) -> list[dict]:
        """Candidatos a struct do jogador, validados."""
        vistos: set[int] = set()
        resultado: list[dict] = []
        for addr in self.find_name_addresses(name):
            obj = addr - OFF_NAME
            if obj in vistos or obj <= 0:
                continue
            vistos.add(obj)
            info = self.describe_object(obj)
            if info:
                info["name_at"] = addr
                resultado.append(info)
        return resultado

    # -- passo 4: achar quem aponta para o objeto --------------------------

    def _iter_static_chunks(self) -> Iterator[tuple[int, bytes]]:
        addr = STATIC_SCAN_START
        while addr < STATIC_SCAN_END:
            size = min(CHUNK, STATIC_SCAN_END - addr)
            try:
                yield addr, self.pm.read_bytes(addr, size)
            except Exception:
                pass
            addr += size

    def find_pointers_to(self, obj: int, limit: int = 40) -> list[int]:
        """Endereços estáticos cujo valor é `obj`."""
        alvo = struct.pack("<I", obj)
        achados: list[int] = []
        for base, blob in self._iter_static_chunks():
            inicio = 0
            while True:
                pos = blob.find(alvo, inicio)
                if pos < 0:
                    break
                endereco = base + pos
                if endereco % 4 == 0:      # ponteiros são alinhados
                    achados.append(endereco)
                    if len(achados) >= limit:
                        return achados
                inicio = pos + 1
        return achados

    def close(self) -> None:
        try:
            self.pm.close_process()
        except Exception:
            pass


def run(pid: int, char_name: str) -> int:
    """Executa a busca completa e imprime o resultado."""
    print("BlazesBot — busca do ponteiro base do jogador")
    print("-" * 68)
    print(f"PID {pid} | personagem '{char_name}'")
    print()

    try:
        finder = BaseFinder(pid)
    except Exception as exc:
        print(f"Não foi possível abrir o processo: {exc}")
        print("O BlazesBot precisa rodar COMO ADMINISTRADOR.")
        return 1

    print("[1/3] Procurando o nome do personagem na memória…")
    enderecos = finder.find_name_addresses(char_name)
    print(f"      {len(enderecos)} ocorrência(s) da string")
    if not enderecos:
        print()
        print("      Nenhuma ocorrência. Confira se:")
        print("        - o personagem está LOGADO no mundo")
        print("        - o nome foi digitado exatamente como aparece no jogo")
        finder.close()
        return 1

    print("[2/3] Validando quais são a struct do personagem…")
    candidatos = finder.candidate_objects(char_name)
    if not candidatos:
        print("      Nenhum candidato passou na validação.")
        print()
        print("      Isso indica que os offsets internos mudaram nesta versão,")
        print("      não só o endereço base. Nesse caso é preciso remapear no")
        print("      Cheat Engine (procedimento no README).")
        finder.close()
        return 1

    print(f"      {len(candidatos)} candidato(s) plausível(is):")
    print()
    print(f"      {'#':>2}  {'struct':>10}  {'nivel':>5}  {'HP':>9}  {'posicao':>14}")
    for i, c in enumerate(candidatos, 1):
        posicao = f"({c['x']}, {c['y']})"
        print(f"      {i:>2}  {c['obj']:#010x}  {c['level']:>5}  "
              f"{c['hp']:>4}/{c['max_hp']:<4}  {posicao:>14}")
    print()
    print("      Compare com o que o jogo mostra na tela. O candidato certo tem")
    print("      o SEU nível, o SEU HP e a SUA posição.")
    print()

    print("[3/3] Procurando o ponteiro estático de cada candidato…")
    algum = False
    for i, c in enumerate(candidatos, 1):
        ponteiros = finder.find_pointers_to(c["obj"])
        if not ponteiros:
            continue
        algum = True
        print()
        print(f"  Candidato {i} — struct {c['obj']:#010x} "
              f"(nível {c['level']}, HP {c['hp']}/{c['max_hp']}, "
              f"posição ({c['x']}, {c['y']}))")
        for ponteiro in ponteiros[:8]:
            rva = ponteiro - IMAGE_BASE
            print(f"     ponteiro em {ponteiro:#010x}   ->   RVA {rva:#010x}")

    finder.close()

    if not algum:
        print("      Nenhum ponteiro estático encontrado apontando para os")
        print("      candidatos. O cliente pode guardar a referência de forma")
        print("      indireta; nesse caso é preciso um pointer scan no Cheat Engine.")
        return 1

    print()
    print("-" * 68)
    from ..core.memory import PLAYER_BASE_RVA

    print(f"VALOR EM USO NO BOT AGORA: RVA {PLAYER_BASE_RVA:#010x}")
    print()
    print("Se o RVA encontrado acima é igual a este, o mapa já está correto e")
    print("não há nada a fazer. Se for diferente, siga abaixo.")
    print()
    print("COMO APLICAR")
    print()
    print("  1. Escolha a linha cujo candidato tem o SEU nível/HP/posição.")
    print("  2. Abra blazesbot/core/memory.py")
    print("  3. Troque o valor de PLAYER_BASE_RVA pelo RVA daquela linha")
    print("  4. Rode 2-DIAGNOSTICO.bat para confirmar")
    print()
    print("  Se houver vários ponteiros para o mesmo candidato, prefira o de")
    print("  RVA MENOR: costuma ser o mais estável entre reinícios do jogo.")
    print()
    print("  A melhor confirmação: rode isto com DOIS clientes logados em")
    print("  personagens diferentes. Se os dois apontarem para o mesmo RVA,")
    print("  o valor é o certo -- foi assim que o da ver.6400 foi confirmado.")
    return 0
