"""术语与唱段韵译库：字幕机翻质量的兜底与规范化层。

高内聚：川剧术语标准译名、机翻变体替换表、经典唱段韵译、看点解说文案统一在此维护。
低耦合：纯数据 + 纯函数，无 IO 无状态；live_hub 在翻译管线中调用，
       任何异常由调用方按需兜底，本模块自身不抛出业务异常。

三层能力：
  1. LYRICS       经典唱段整句韵译——命中直接替代机翻，保住诗意
  2. TERMS/VARIANTS 常用术语标准译名与机翻变体——机翻后做规范化替换
  3. TERM_INFO    绝技看点解说——ASR 命中术语时供 live_hub 升级为 highlight 推送

撰写规范（宁缺毋滥）：
  - 术语译文必须是业内通用译法；不确定的语言宁可不预置（回退机翻）
  - 唱段韵译以英文为主（海外观众主体），其余语言走「机翻 + 术语规范化」
"""

import re

# ==================== 术语标准译名 ====================
# zh 术语 -> {lang: 标准译名}（语言覆盖以宁缺毋滥为原则）
TERMS: dict[str, dict[str, str]] = {
    "变脸": {
        "en": "face-changing (Bianlian)", "ja": "変臉（变脸）", "ko": "변검(얼굴 바꾸기)",
        "es": "el cambio de rostro (Bianlian)", "fr": "le changement de visage (Bianlian)",
        "de": "das Gesichtwechseln (Bianlian)", "ru": "смена лица (Бяньлянь)",
    },
    "吐火": {
        "en": "fire-spitting (Tuhuo)", "ja": "吐火（火を吐く）", "ko": "불 뿜기",
        "es": "escupir fuego (Tuhuo)", "fr": "le crachement de feu (Tuhuo)",
        "de": "das Feuerspucken (Tuhuo)", "ru": "выдыхание огня (Тухо)",
    },
    "滚灯": {
        "en": "Rolling the Lamp (Gundeng)", "ja": "滾灯（頭上で灯を回す曲芸）", "ko": "등불 굴리기",
        "es": "rodar la lámpara (Gundeng)", "fr": "rouler la lampe (Gundeng)",
        "de": "die rollende Lampe (Gundeng)", "ru": "катание лампы (Гундэн)",
    },
    "水袖": {
        "en": "water sleeves", "ja": "水袖（長い袖）", "ko": "물소매",
        "es": "mangas de agua", "fr": "manches d'eau",
        "de": "Wasserärmel", "ru": "водяные рукава",
    },
    "帮腔": {
        "en": "backstage chorus (Bangqiang)", "ja": "幇腔（後方合唱）", "ko": "방창(뒤에서 받아치는 노래)",
        "es": "coro de apoyo (Bangqiang)", "fr": "chœur d'accompagnement (Bangqiang)",
        "de": "Hintergrundchor (Bangqiang)", "ru": "закулисный хор (Банцян)",
    },
    "高腔": {
        "en": "Gaoqiang (high-pitched singing)", "ja": "高腔", "ko": "가오창(고음 창법)",
        "es": "Gaoqiang (canto agudo)", "fr": "le Gaoqiang (chant aigu)",
        "de": "Gaoqiang (hoher Gesang)", "ru": "гаоцян (высокое пение)",
    },
    "折子戏": {
        "en": "opera excerpt (Zhezixi)", "ja": "折子戯（一幕物）", "ko": "절자희(단막극)",
        "es": "fragmento de ópera (Zhezixi)", "fr": "extrait d'opéra (Zhezixi)",
        "de": "Opernauszug (Zhezixi)", "ru": "фрагмент оперы (чжэцзыси)",
    },
    "旦角": {
        "en": "dan role (female role)", "ja": "旦角（女性役）", "ko": "단각(여성 역할)",
        "es": "papel dan (femenino)", "fr": "rôle dan (féminin)",
        "de": "Dan-Rolle (weiblich)", "ru": "амплуа дань (женская роль)",
    },
}

# 机翻常见变体：lang -> 小写子串 -> 标准名（apply_terms 据此做替换）
# 变体只收录「确认见过/高度可预期」的机翻产物，避免误替换
_VARIANTS: dict[str, dict[str, str]] = {
    "en": {
        "face change": "face-changing (Bianlian)",
        "face-changing": "face-changing (Bianlian)",
        "changing face": "face-changing (Bianlian)",
        "change his face": "change his mask (Bianlian)",
        "spit fire": "spit fire — fire-spitting (Tuhuo)",
        "fire spitting": "fire-spitting (Tuhuo)",
        "rolling lamp": "Rolling the Lamp (Gundeng)",
        "roll the lamp": "Rolling the Lamp (Gundeng)",
    },
    "tr": {  # 历史实测：土语曾把吐火译作「点火」
        "ateş yakma": "ateş püskürtme",
        "ateş yakmak": "ateş püskürtme",
    },
}

# ==================== 经典唱段韵译 ====================
# key 为规范化中文原句（去标点/空白），value 为 {lang: 韵译}
LYRICS: dict[str, dict[str, str]] = {
    "别时容易见时难流水落花春去也": {
        "en": "Parting came easy; meeting again is hard — as blossoms fall and spring runs out.",
    },
    "天上人间": {
        "en": "One moment in heaven, a lifetime on earth.",
    },
    "轻舟已过万重山": {
        "en": "The light boat has slipped past ten thousand mountains.",
    },
    "问人间情是何物直教生死相许": {
        "en": "Ask the world what love can be, that makes us pledge it with our very lives.",
    },
}

# ==================== 绝技看点解说（highlight 用） ====================
# zh 术语 -> {lang: 看点一句话}（仅收录适合现场推送的绝技类术语）
TERM_INFO: dict[str, dict[str, str]] = {
    "变脸": {
        "zh": "看点：演员在抬手转身之间瞬间变换脸谱，全程不遮脸，猜猜机关在哪！",
        "en": "Watch for: the performer swaps painted masks in a split second — no hands ever touch the face. Where is the secret?",
        "ja": "注目ポイント：役者が一瞬の動作で顔の仮面を変えます。手は顔に触れません。種明かしはできる？",
        "ko": "관전 포인트: 배우가 손짓 한 번에 순식간에 가면을 바꿉니다. 얼굴에 손이 닿지 않아요. 비밀은 어디에?",
        "es": "Fíjese: el artista cambia de máscara en una fracción de segundo, sin tocar su rostro. ¿Dónde está el truco?",
        "fr": "Observez : l'artiste change de masque en une fraction de seconde, sans toucher son visage. Où est le secret ?",
        "de": "Achten Sie auf: Der Künstler wechselt die Maske in Sekundenbruchteilen, ohne das Gesicht zu berühren. Wo liegt das Geheimnis?",
        "ru": "Смотрите: артист меняет маску за долю секунды, не прикасаясь к лицу. В чём секрет?",
    },
    "吐火": {
        "zh": "看点：演员口吐烈焰，火舌最长可达数尺——这是真功夫，切勿模仿！",
        "en": "Watch for: jets of real flame leap from the performer's mouth — a true feat of breath control. Do not try this!",
        "ja": "注目ポイント：役者の口から本物の炎が噴き出します。呼吸法による真の技です。真似しないで！",
        "ko": "관전 포인트: 배우의 입에서 진짜 불꽃이 뿜어져 나옵니다. 호흡으로 만드는 진짜 기술입니다. 절대 따라하지 마세요!",
        "es": "Fíjese: llamas reales brotan de la boca del artista, todo un alarde de control de la respiración. ¡No lo intente!",
        "fr": "Observez : de vraies flammes jaillissent de la bouche de l'artiste — un exploit de maîtrise du souffle. N'essayez pas !",
        "de": "Achten Sie auf: Echte Flammen schießen aus dem Mund des Künstlers — eine wahre Beherrschung des Atems. Nicht nachmachen!",
        "ru": "Смотрите: изо рта артиста вырывается настоящее пламя — подлинное мастерство дыхания. Не пытайтесь повторить!",
    },
    "滚灯": {
        "zh": "看点：演员头顶点亮的油灯，钻板凳、翻滚腾挪而灯不灭——喜剧与功夫兼备的川剧独门绝技。",
        "en": "Watch for: with a lit oil lamp balanced on his head, the performer tumbles under benches — the flame never dies. Comedy and kung fu in one!",
        "ja": "注目ポイント：頭の上に灯った油ランプを乗せたまま、役者がベンチの下をくぐり転がります。炎は消えません。喜劇と功夫の共演！",
        "ko": "관전 포인트: 머리에 켠 등불을 얹은 채 배치 아래를 구르고 누빕니다. 불은 꺼지지 않아요. 희극과 무술이 하나로!",
        "es": "Fíjese: con una lámpara de aceite encendida sobre la cabeza, el artista rueda bajo los bancos sin que se apague. ¡Comedia y kung fu juntos!",
        "fr": "Observez : une lampe à huile allumée sur la tête, l'artiste roule sous les bancs sans qu'elle s'éteigne. Comédie et kung-fu réunis !",
        "de": "Achten Sie auf: Mit einer brennenden Öllampe auf dem Kopf rollt der Künstler unter den Bänken — die Flamme erlischt nie. Comedy und Kung Fu!",
        "ru": "Смотрите: с зажжённой масляной лампой на голове артист кувыркается под скамьями, и пламя не гаснет. Комедия и кунг-фу в одном номере!",
    },
}

# 同一术语看点推送的冷却秒数（防讲解员反复提及刷屏）
HIGHLIGHT_COOLDOWN = 60.0

# 规范化：去空白与标点（中英句读统一剥离），用于唱段/术语匹配
_STRIP_RE = re.compile(r"[\s，。！？、；：""''.,!?;:'\"()\[\]（）—\-·]+")


def _normalize(text: str) -> str:
    return _STRIP_RE.sub("", text or "")


def lookup_lyric(text: str, lang: str) -> str | None:
    """整句唱段韵译命中：返回该语言韵译，未命中返回 None。"""
    entry = LYRICS.get(_normalize(text))
    if not entry:
        return None
    return entry.get(lang)


def match_terms(text: str) -> list[str]:
    """返回句中出现的术语（按 TERMS 键整词匹配，保序去重）。"""
    found: list[str] = []
    for term in TERMS:
        if term in text and term not in found:
            found.append(term)
    return found


def apply_terms(source_zh: str, lang: str, translated: str) -> str:
    """机翻后处理：按变体表把术语的机翻产物规范化为标准译名。

    仅替换「源句确实含有该术语」的变体，避免无关句误伤；
    标准译名若本身含另一变体（如 "face-changing (Bianlian)" 含变体
    "face-changing"）则跳过该变体，防止二次替换产生叠词。
    """
    if not translated:
        return translated
    variants = _VARIANTS.get(lang)
    if not variants:
        return translated
    terms_in_source = set(match_terms(source_zh))
    # 变体表中与术语相关的键才允许替换（如 en 表全为变脸/吐火/滚灯类）
    related: set[str] = set()
    for term in terms_in_source:
        related.update(_variants_of(term, lang))
    if not related:
        return translated
    out = translated
    inserted: list[str] = []
    # 键长降序：先长后短，避免短键先替换破坏长键
    for variant in sorted(related, key=len, reverse=True):
        std = variants[variant]
        if not re.search(re.escape(variant), out, re.IGNORECASE):
            continue
        # 已插入的标准名包含该变体（如 face-changing (Bianlian) ⊃ face-changing）：跳过防叠词
        if any(variant in done.lower() for done in inserted):
            continue
        out = re.sub(re.escape(variant), std, out, flags=re.IGNORECASE)
        inserted.append(std)
    return out


def _variants_of(term: str, lang: str) -> list[str]:
    """该术语在该语言下可替换的变体键（按语义分组，粗粒度映射）。"""
    groups = {
        "变脸": ["face change", "face-changing", "changing face", "change his face"],
        "吐火": ["spit fire", "fire spitting", "ateş yakma", "ateş yakmak"],
        "滚灯": ["rolling lamp", "roll the lamp"],
    }
    return [v for v in groups.get(term, []) if v in _VARIANTS.get(lang, {})]
