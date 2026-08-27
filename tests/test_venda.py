

# ===========================================================================
# O RESPIRO EM VOLTA DO "SELL"
# ===========================================================================

def test_o_Sell_tem_respiro_ANTES_e_DEPOIS():
    """Relato do usuário em 25/08/2026: *"ao tentar clicar no botão 'Sell' está
    tudo tão rápido que acaba não clicando"*.

    O Sell é o único clique do bot que chega na cola de uma RAJADA -- até 24
    cliques nos slots a 0,065 s cada. Um Sell engolido marca a passada inteira
    como vendida **sem ter vendido nada**, e o item volta para a bolsa cheia.

    O "depois" já existia (era um `0.5` solto no meio do código); o que faltava
    era o "antes".
    """
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.bc import vendor

    fonte = textwrap.dedent(
        inspect.getsource(vendor.VendorService.sell_from_slot))

    # POR LINHA, e não por caminhada aninhada: percorrer a árvore duas vezes
    # conta cada chamada duas vezes, e o teste acusa dois Sell onde há um.
    marcas: list[tuple[int, str]] = []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call):
            continue
        alvo = getattr(no.func, "attr", "")
        if alvo == "click" and any(
                getattr(a, "id", "") == "botao_vender" for a in no.args):
            marcas.append((no.lineno, "SELL"))
        elif alvo == "tick" and no.args:
            nome = getattr(no.args[0], "id", "")
            if nome in ("ESPERA_ANTES_DO_SELL", "ESPERA_DEPOIS_DO_SELL"):
                marcas.append((no.lineno, nome))

    ordem = [nome for _linha, nome in sorted(marcas)]

    assert ordem.count("SELL") == 1, f"o Sell mudou de lugar: {ordem}"
    i = ordem.index("SELL")
    assert ordem[i - 1] == "ESPERA_ANTES_DO_SELL", (
        f"o Sell não tem respiro ANTES: {ordem}")
    assert ordem[i + 1] == "ESPERA_DEPOIS_DO_SELL", (
        f"o Sell não tem respiro DEPOIS: {ordem}")


def test_o_respiro_do_Sell_e_maior_que_a_cadencia_da_rajada():
    """Se o respiro fosse da ordem do intervalo entre os cliques dos slots, ele
    não seria respiro nenhum -- seria mais um clique da rajada."""
    from blazesbot.bot.bc import vendor

    assert vendor.ESPERA_ANTES_DO_SELL > vendor.ESPERA_ENTRE_CLIQUES_DA_VENDA * 3
    assert vendor.ESPERA_DEPOIS_DO_SELL >= vendor.ESPERA_ANTES_DO_SELL
