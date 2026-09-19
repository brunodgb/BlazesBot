# O que o site oficial tem — varredura de 19/09/2026

Varredura de `www.talismanonline.com` feita para achar o nome de verdade dos
itens que o deletador mostra na janela de escolha. O `robots.txt` do site não
traz nenhuma restrição (só o texto legal de content-signals do Cloudflare, sem
`Disallow`), e a varredura foi de leitura, com pausa entre páginas.

**446 páginas** gravadas a partir da home + `sitemap.xml` (315 URLs), seguindo
todo link do mesmo host: 178 artigos de `newpage/`, 56 de `gameSystem_*`, 42 de
`gameWorld_*`, e o resto entre loja, suporte e guia de iniciante. O que o site
tem de aproveitável está resumido aqui — a varredura em si não ficou no
repositório porque o material dela cabe neste arquivo.

## 1. Os dez nomes que o site resolveu

A página do **Magicstone** (`gameSystem_otherSys.html`) enumera, com o nome
exato, os dez materiais que caem de monstro e entram na receita da pedra. Nove
deles estão na pasta do APP com o nome abreviado pelo arquivo, e três estavam
com o nome **errado**, não só abreviado:

| arquivo | rótulo antigo | rótulo agora | o que era |
|---|---|---|---|
| `ScarpPill.png` | Scarp Pill | **Green Scarp Pill** | faltava o "Green" |
| `Bjewel.png` | Bjewel | **Bandit Jewel** | `B` era "Bandit" |
| `ExoChip.png` | Exo Chip | **Exorcism Chip** | abreviação |
| `ApoCharm.png` | Apo Charm | **Apotropaion Charm** | abreviação |
| `DarkBed.png` | Dark Bed | **Dark Bead** | *bead*, não *bed* — erro no arquivo |
| `CrackBB.png` | Crack BB | **Cracked Buddha Bone** | `BB` era "Buddha Bone" |
| `Biddha-Bone.png` | Biddha Bone | **Buddha Bone** | grafia |
| `Rainnbow_Stone.png` | Rainnbow Stone | **Rainbow Stone** | grafia (dois `n`) |
| `greenid.png` | greenid | **Green Identify Gem** | o que ativa equipamento verde |
| `MDeearMeat.png` | MDeear Meat | **Musk Deer Meat** | ver a ressalva abaixo |

Os outros três da mesma lista — `PoisonCup.png`, `RottedSeed.png`,
`IceRime.png` — e também `Beast_Blood.png` já estavam certos; agora estão
**conferidos**, que é diferente de "parecia certo".

**A única inferência da tabela é `MDeearMeat.png`.** O site não nomeia a carne;
nomeia o bicho: *Musk Deer*, nível 61, no Bandit Lair (a faixa em que o APP
roda). Como as outras carnes da pasta seguem `<bicho> Meat` (Wolf Meat, Lion
Meat, Vulture Meat), "Musk Deer Meat" é a leitura óbvia de `MDeear` — mas é
leitura, não citação. As nove primeiras linhas são o nome como o site escreve.

## 2. O que o site NÃO resolve

**O site não tem banco de itens.** Não há tabela de materiais, nem drop por
monstro, nem ícone com nome. Os nomes acima apareceram em texto corrido de
guia, e é por isso que são dez e não duzentos.

Continuam com o nome do arquivo, sem confirmação de lugar nenhum: os minérios
(`AlmOre`, `BariteOre`, `MagOre`, `FlameOre`, `SpinelOre`, `StonOr`), as peles e
carnes (`AnFur`, `FireSneakMeat`, `PurBeastMeat`, `TigrMet`, `PhMet`), e os
soltos `Cowb`, `Durmarst`, `Nimbuz`, `FTMC`, `SF`, `Fig`, `dip`, `brtpil`,
`HoneW`, `HoneyS`, `GrosM`, `DfrmtJos`, `DarkSM`, `Crista_Bot`, `LascToken`,
`MysSkel`, `GlosBead`, `CIronShot`, `Gold_T`.

Os **sinos coloridos** (`Blue-bell`, `Red-bell`, `Silver-bell`, `Golden-bell`,
`Purple-bell`) também ficaram sem nome: o site só conhece **um** sino de
captura, o *Pet Capture Bell* do Tamer, sem variação de cor. Os cinco da pasta
são outra coisa, e o site não diz o quê.

**Onde procurar o que faltou:** o cliente do jogo. O nome que a janela do
inventário mostra sai dos dados do cliente, não da internet — e o bot já lê
memória. O caminho barato é passar o mouse no item dentro do jogo e ler o
tooltip; o caro, mas definitivo, é achar a tabela de itens nos arquivos do
cliente. **O wiki de fã que o site linka (`talismanonlinewiki.com`) está morto**
— responde 404 até na página principal. Os links que sobraram no HTML do site
ainda revelam alguns nomes de arquivo úteis (foi assim que `greenid` virou
*Green Identify Gem*): `Blue_Magic_Bead`, `Concentration_Pellet`,
`Green_Identify_Gem`, `Kernel_of_Water`, `Large_Emerald`, `Large_Ruby`,
`Small_Ruby`, `Phoenix_Jackstraw`, `Ring_of_Love`, `Ice_Moon_Cake`,
`Fighting_Healing_Potion`, `Purple_Charming_Sword`, `Bravo_Tiger`.

## 3. Os talismãs assistentes — a pasta da HH inteira

A pasta `data/templates/deletar_hh/` tem 16 modelos, e **os 16 são talismãs
assistentes**, todos com o nome certo (conferidos em `gameWorld_skill*` e nas
recompensas de missão de `gameSystem_quest*`). O site lista **20**:

> Ice Shield · Longbrow Needle · Tao Symbol · Warm Jade · Diamond Sutra ·
> Heart Lotus · Treasure Loop · Buddha Bone · Hasty Shoes · Theurgy Bell ·
> Array Flag · Dragon Roc · Treasure Leaf · Wonder Needle · Purple Cloud ·
> Purple Cowry · Pet Bell · Jade Vessel · Nature Booklet · Trap Meshwork

**Quatro não têm modelo na pasta: Treasure Loop, Array Flag, Purple Cloud e
Nature Booklet.** Se eles caem na Happiness Hall, hoje passam batido pelo
deletador — vale conferir no jogo antes de recortar template à toa.

## 4. O escadão de equipamento, por classe

`gameWorld_equip1*.html` traz a tabela de equipamento básico das cinco classes
com o nível exigido de cada peça. Ela **confirma a regra de numeração** que os
nomes de arquivo usam: a unidade é a peça (2 Cuff, 3 Armguard, 4 Kneepad,
5 Boots, 6 Belt, 8 a veste) e a dezena é o tier.

| classe | tiers, na ordem (faixa de nível) |
|---|---|
| Wizard | Green Elf 2-8 · Red Fire 12-18 · Bule Jade 22-28 · Ice Freezing 32-38 · Fire Dragon 42-48 · Seven Stars 52-58 · Four Void 62-68 · Real Valiant 72-78 |
| Monk | Grey Cloth · Commandment · Sky Drum · Wild Vision · Thunder Sound · Buddha Vigor · All Heaven / Holy Jade / Tiger Rage · Arhat |
| Assassin | Blue Field · Purple Crystal · Sky Thunder · Hundred Fights · Demon Ruin · Greedy Wolf · Loyal Toast / Rage Burst / Holy Justice · Valiant Song |
| Fairy | Rosebush · Redbud · Cherry · Orchid · Lily · Willow · Daphne / Heaven / Rose · Vanilla |
| Tamer | Hill Finch · Green Swift · Night Hawk · Silver Gull · Blue Snipe · Red Ibis · Black Falcon / Musk Charm / Blood Fury · Grand Swan |

As faixas seguem o mesmo passo de 10 em todas as classes. Do tier 62 em diante
aparecem variantes (`Elite`, `Holy`) no mesmo degrau — é por isso que existem
três nomes por classe ali.

O site escreve **Kneepad**; o dicionário do bot escreve "Kneedpad". Ficou como
está: o usuário pediu para não mexer nos equipamentos, e o rótulo é para ele
reconhecer o ícone, não para bater com o site.

## 5. O que mais o site tem, e pode servir depois

- **484 monstros com nível e área**, em 140 áreas, do nível 1 ao 80 —
  `gameWorld_maps.html`. Salvo em **`docs/monstros-do-site.json`**
  (`{nome, nivel, area}`). Nada no bot consome esse arquivo hoje: ele está aqui
  porque o site é antigo e um dia sai do ar, e refazer isso depois é caro.
- **Coordenadas dos mercadores de reputação**, uma por região
  (`gameWorld_equip3*.html`): (140,519) · (280,-135) · (24,-968) · (311,-354) ·
  (-259,-479) · (-400,-891) · (-1110,-1325) · (-1136,-975) · (854,-582) ·
  (2173,-574). São coordenadas do jogo, no mesmo sistema que o Navigator usa.
- **Sistemas explicados em texto**: Magicstone (decompor item vira cristal),
  Pérola Celestial, Soul Infusion, Reputação, Pesca e Culinária — esta última
  confirma que carne de monstro e peixe viram comida com buff, que é o que a
  pasta de carnes do APP está jogando fora.
- **Missões com recompensa item por item** (`gameSystem_quest*.html`), que é de
  onde saiu *Rainbow Stone*.

## 6. Como refazer a varredura

O `sitemap.xml` continua no ar e lista 315 URLs; a partir dele e da home, um
BFS de mesmo host em 446 páginas leva uns dois minutos com 0,15 s de pausa.
Depois é tirar as tags e grepar — foi assim que os dez nomes apareceram, todos
em texto corrido. Duas armadilhas que custaram tempo: a lista da comunidade
pagina por `__doPostBack` (os artigos, porém, são os mesmos `newpage/*.html` do
sitemap), e várias páginas são molduras de 400 bytes, com o conteúdo num
`_1`, `_2`, `_3` ao lado.
