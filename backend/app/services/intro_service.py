"""剧场介绍服务：观众入场前的多语言语音介绍文案。

高内聚：介绍文案资源（预置多语言版本）、语言回退、动态翻译与缓存、
       机翻质量黑名单后检统一收敛在此模块。
低耦合：语音合成由前端调用 /api/tts/synthesize 完成（复用现有 TTS 能力），
       动态翻译复用 translation_service，本模块只产出纯文本。

策略：
  - 16 种常用语言（zh/en/ja/ko/es/fr/de/ru/hi/ar/pt/it/vi/th/tr/id）全部手写预置，
    覆盖系统语言表主流语言，保证剧场术语与实用信息质量
  - 未预置语言：首次请求时机翻中文原文并缓存；译文须通过「医院词黑名单」后检
    （历史教训：机翻曾把「本院」译作医院），可疑即弃用回退英文
  - 中文原文用词规避机翻歧义（R1 规范）：不用「本院」（医院歧义），
    用「声腔流派」而非「声腔」（解剖歧义）

名称（真实官方信息）：
  - 院名统一「四川省川剧院」（官网 www.sc-opera.com，省文旅厅直属）
  - 介绍仅在剧院内扫码进入服务页后播放，用户已在现场，故不含地址交通信息
"""

import logging

from app.core.languages import is_supported
from app.services.translation_service import translation_service

logger = logging.getLogger("intro")

# 中文 TTS 使用的语言码（与 voices.py 登记一致）
ZH = "zh-CN"

# 实用信息段：时长/中场/取票/迟到入场（用户已在剧院内，无需交通指引）
_PRACTICAL_ZH = (
    "本场演出约九十分钟，中场休息十五分钟。"
    "请提前三十分钟凭购票信息在售票厅取票。"
    "迟到观众请听从工作人员指引，于幕间入场。"
)

# ==================== 预置文案（16 种，全部手写） ====================

INTRO_ZH = (
    "欢迎来到四川省川剧院。本剧院以传承和弘扬川剧艺术为己任，"
    "川剧融汇高腔、昆腔、胡琴、弹戏、灯调五种声腔流派，"
    "尤以变脸、吐火两大绝技闻名于世。"
    "今晚的演出，将带您领略巴蜀戏曲的独特魅力。"
    "观演期间，请将手机调至静音，请勿使用闪光灯拍照。"
    "在收听席页面选择您的语言，即可获得实时的多语言讲解字幕。"
    + _PRACTICAL_ZH +
    "祝您观演愉快！"
)

INTRO_EN = (
    "Welcome to the Sichuan Opera Theatre. The theatre is dedicated to preserving and "
    "promoting the art of Sichuan Opera. Sichuan Opera blends five vocal styles — Gaoqiang, "
    "Kunqiang, Huqin, Tanxi and Dengdiao — and is world-famous for its two signature feats: "
    "face-changing and fire-spitting. Tonight's performance will lead you into the unique "
    "charm of Ba-Shu opera. During the show, please silence your mobile phone and refrain "
    "from flash photography. Select your language on the listening page to receive "
    "real-time multilingual captions. Tonight's performance lasts about ninety minutes, "
    "with a fifteen-minute intermission. Please arrive thirty minutes early to collect "
    "your tickets at the box office. Latecomers will be seated during the interval as "
    "directed by our staff. Enjoy the performance!"
)

INTRO_JA = (
    "四川省川劇院へようこそ。当劇院は川劇芸術の伝承と発展を使命としております。"
    "川劇は高腔・崑腔・胡琴・弾戯・灯調の五つの声腔流派を融合し、"
    "特に「変臉（変脸）」と「吐火」の二大秘技で世界に知られています。"
    "今夜の公演で、巴蜀戯曲ならではの魅力をご堪能ください。"
    "鑑賞中は携帯電話をマナーモードに設定し、フラッシュ撮影はご遠慮ください。"
    "リスニングページで言語を選択すると、リアルタイムの多言語字幕をご利用いただけます。"
    "本日の公演は約90分、途中に15分の休憩がございます。"
    "チケットは開演の30分前までにチケット売場でお受け取りください。"
    "遅れてご来場のお客様は、スタッフの誘導に従い幕間にご入場ください。"
    "どうぞごゆっくりお楽しみください。"
)

INTRO_KO = (
    "쓰촨성 촨쥐 극원(四川省川剧院)에 오신 것을 환영합니다. 저희 극원은 촨쥐(쓰촨 오페라) 예술의 계승과 발전을 사명으로 삼고 있습니다. "
    "촨쥐는 가오창, 쿤창, 후친, 탄시, 덩따오의 다섯 성강 유파를 융합하였으며, "
    "특히 '변검(얼굴 바꾸기)'과 '불 뿜기' 두 가지 절기로 세계적으로 유명합니다. "
    "오늘 밤 공연에서 바촉 희곡만의 매력을 느껴보시기 바랍니다. "
    "관람 중에는 휴대폰을 무음으로 설정해 주시고 플래시 촬영은 삼가해 주세요. "
    "청취 페이지에서 언어를 선택하시면 실시간 다국어 자막을 이용하실 수 있습니다. "
    "오늘 밤 공연은 약 90분이며 15분의 휴식 시간이 있습니다. 티켓은 공연 30분 전까지 매표소에서 수령해 주세요. "
    "늦게 도착하신 관객은 직원의 안내에 따라 막간에 입장하시면 됩니다. 즐거운 관람 되십시오!"
)

INTRO_ES = (
    "Bienvenidos al Teatro de la Ópera de Sichuan. El teatro se dedica a preservar y promover el "
    "arte de la ópera de Sichuan. La ópera de Sichuan fusiona cinco estilos vocales — "
    "Gaoqiang, Kunqiang, Huqin, Tanxi y Dengdiao — y es famosa en el mundo por sus dos "
    "técnicas insignia: el cambio de rostro y el escupir fuego. La función de esta noche "
    "le llevará a descubrir el encanto único de la ópera de Ba-Shu. Durante el espectáculo, "
    "silencie su teléfono móvil y absténgase de tomar fotos con flash. Seleccione su idioma "
    "en la página de escucha para recibir subtítulos multilingües en tiempo real. La función "
    "de esta noche dura unos noventa minutos, con un intermedio de quince minutos. Le "
    "recomendamos llegar treinta minutos antes para recoger sus entradas en taquilla. "
    "Los que lleguen tarde serán acomodados durante el intermedio según las "
    "indicaciones del personal. ¡Disfrute de la función!"
)

INTRO_FR = (
    "Bienvenue au Théâtre de l'opéra du Sichuan. Le théâtre s'est consacré à la préservation "
    "et à la promotion de l'art de l'opéra du Sichuan. L'opéra du Sichuan mêle cinq styles "
    "vocaux — le Gaoqiang, le Kunqiang, le Huqin, le Tanxi et le Dengdiao — et est "
    "mondialement célèbre pour ses deux prouesses emblématiques : le changement de visage "
    "et le crachement de feu. Le spectacle de ce soir vous fera découvrir le charme unique "
    "de l'opéra du Ba-Shu. Pendant la représentation, veuillez mettre votre téléphone en "
    "mode silencieux et vous abstenir de photographier avec flash. Sélectionnez votre langue "
    "sur la page d'écoute pour recevoir des sous-titres multilingues en temps réel. Le "
    "spectacle de ce soir dure environ quatre-vingt-dix minutes, avec un entracte de quinze "
    "minutes. Veuillez arriver trente minutes en avance pour retirer vos billets au "
    "guichet. Les retardataires seront placés pendant l'entracte, sur indication du "
    "personnel. Bon spectacle !"
)

INTRO_DE = (
    "Willkommen im Sichuan-Operntheater. Das Theater widmet sich der Bewahrung und "
    "Förderung der Kunst der Sichuan-Oper. Die Sichuan-Oper vereint fünf Gesangsstile — "
    "Gaoqiang, Kunqiang, Huqin, Tanxi und Dengdiao — und ist weltberühmt für ihre beiden "
    "legendären Kunststücke: das Gesichtwechseln und das Feuerspucken. Die heutige "
    "Vorführung führt Sie in den einzigartigen Charme der Ba-Shu-Oper ein. Während der "
    "Vorstellung stellen Sie bitte Ihr Mobiltelefon auf stumm und verzichten auf "
    "Blitzfotografie. Wählen Sie Ihre Sprache auf der Hörseite, um Untertitel in mehreren "
    "Sprachen in Echtzeit zu erhalten. Die heutige Vorstellung dauert etwa neunzig "
    "Minuten, mit einer fünfzehnminütigen Pause. Bitte kommen Sie dreißig Minuten früher, "
    "um Ihre Karten an der Kasse abzuholen. Später eintreffende Gäste "
    "werden während der Pause nach Anweisung des Personals eingelassen. Genießen Sie die "
    "Vorstellung!"
)

INTRO_RU = (
    "Добро пожаловать в Театр сычуаньской оперы. Театр посвятил себя сохранению и "
    "развитию искусства сычуаньской оперы. Сычуаньская опера сочетает пять вокальных "
    "стилей — гаоцян, куньцян, хуцинь, таньси и дэндяо — и славится во всём мире своими "
    "двумя фирменными номерами: сменой лица и выдыханием огня. Сегодняшнее представление "
    "познакомит вас с неповторимым очарованием оперы Ба-Шу. Во время спектакля, "
    "пожалуйста, переведите телефон в беззвучный режим и не фотографируйте со вспышкой. "
    "Выберите свой язык на странице прослушивания, чтобы получать субтитры на разных "
    "языках в реальном времени. Сегодняшний спектакль длится около девяноста минут с "
    "пятнадцатиминутным антрактом. Пожалуйста, приходите за тридцать минут до начала, "
    "чтобы получить билеты в кассе. Опоздавшие зрители будут впущены в антракте по "
    "указанию персонала. Приятного просмотра!"
)

INTRO_HI = (
    "सिचुआन ओपेरा थियेटर (四川省川剧院) में आपका स्वागत है। यह थियेटर सिचुआन ओपेरा की कला को विरासत और बढ़ावा देने के लिए समर्पित है। "
    "सिचुआन ओपेरा पांच गायन शैलियों — गाओचियांग, कुनचियांग, हुचिन, तानशी और देंगदियाओ — को मिलाता है, "
    "और चेहरा बदलने तथा आग थूकने की अपनी दो महान कलाओं के लिए विश्व भर में प्रसिद्ध है। "
    "आज रात का प्रदर्शन आपको बाशू ओपेरा का अनूठा आकर्षण दिखाएगा। "
    "प्रदर्शन के दौरान कृपया अपने फ़ोन को म्यूट करें और फ़्लैश के साथ फ़ोटो न लें। "
    "रियल-टाइम बहुभाषी कैप्शन पाने के लिए लिसनिंग पेज पर अपनी भाषा चुनें। "
    "आज रात का प्रदर्शन लगभग 90 मिनट का है, जिसमें 15 मिनट का अंतराल है। "
    "कृपया टिकट लेने के लिए 30 मिनट पहले पहुंचें। "
    "देर से पहुंचने वाले दर्शक कर्मचारियों के निर्देशानुसार अंतराल के दौरान प्रवेश करेंगे। "
    "कार्यक्रम का आनंद लें!"
)

INTRO_AR = (
    "مرحبًا بك في مسرح أوبرا سيتشوان. يلتزم هذا المسرح بوراثة فن أوبرا سيتشوان وترويجه. "
    "تمزج أوبرا سيتشوان بين خمسة أساليب غنائية: غاوتشيانغ، وكونتشيانغ، وهوتشين، وتانشي، ودنغدياو، "
    "وهي مشهورة عالميًا بفنّيها العظيمين: تغيير الوجه ونفث النار. "
    "سيمنحك أداء هذه الليلة فرصة الاستمتاع بسحر أوبرا باشو الفريد. "
    "يرجى كتم صوت هاتفك أثناء العرض وعدم التصوير باستخدام الفلاش. "
    "اختر لغتك في صفحة الاستماع للحصول على ترجمة فورية متعددة اللغات. "
    "يستمر أداء هذه الليلة حوالي 90 دقيقة مع استراحة لمدة 15 دقيقة. "
    "يرجى الحضور قبل 30 دقيقة لاستلام تذكرتك من شباك التذاكر. "
    "سيتم إدخال القادمين متأخرين خلال فترات الاستراحة بإرشاد الموظفين. استمتع بالعرض!"
)

INTRO_PT = (
    "Bem-vindo ao Teatro de Ópera de Sichuan. Este teatro dedica-se a preservar e "
    "promover a arte da ópera de Sichuan. A ópera de Sichuan combina cinco estilos "
    "vocais — Gaoqiang, Kunqiang, Huqin, Tanxi e Dengdiao — e é mundialmente famosa "
    "por suas duas grandes proezas: a troca de rosto e o cuspir fogo. O espetáculo "
    "desta noite mostrará o charme único da ópera de Ba-Shu. Durante o espetáculo, "
    "silencie o telefone e não tire fotos com flash. Selecione o seu idioma na página "
    "de escuta para receber legendas multilíngues em tempo real. A apresentação desta "
    "noite dura cerca de noventa minutos, com intervalo de quinze minutos. Chegue com "
    "trinta minutos de antecedência para retirar seu ingresso na bilheteria. Os "
    "atrasados entrarão nos intervalos, sob orientação da equipe. Aproveite o "
    "espetáculo!"
)

INTRO_IT = (
    "Benvenuti al Teatro dell'Opera del Sichuan. Questo teatro si dedica alla "
    "conservazione e alla promozione dell'arte dell'opera del Sichuan. L'opera del "
    "Sichuan unisce cinque stili vocali — Gaoqiang, Kunqiang, Huqin, Tanxi e "
    "Dengdiao — ed è famosa in tutto il mondo per le sue due grandi prodezze: il "
    "cambio del volto e lo sputo del fuoco. Lo spettacolo di stasera vi farà "
    "scoprire il fascino unico dell'opera di Ba-Shu. Durante lo spettacolo, "
    "silenziate il telefono e non scattate foto con il flash. Selezionate la vostra "
    "lingua nella pagina di ascolto per ricevere sottotitoli multilingue in tempo "
    "reale. Lo spettacolo di stasera dura circa novanta minuti, con un intervallo "
    "di quindici minuti. Arrivate trenta minuti prima per ritirare i biglietti in "
    "biglietteria. I ritardatari saranno fatti entrare "
    "negli intervalli, su indicazione del personale. Buon divertimento!"
)

INTRO_VI = (
    "Chào mừng bạn đến với Nhà hát Kịch Sichuan (四川省川剧院). Nhà hát này chịu trách nhiệm "
    "kế thừa và quảng bá nghệ thuật kịch Sichuan. Kịch Sichuan kết hợp năm trường phái thanh "
    "nhạc — Cao Khang (Gaoqiang), Côn Khang (Kunqiang), Hồ Cầm (Huqin), Đàn Hí (Tanxi) và "
    "Đăng Điệu (Dengdiao) — và nổi tiếng thế giới với hai tuyệt kỹ: đổi mặt và phun lửa. Màn "
    "biểu diễn tối nay sẽ cho bạn thấy sức quyến rũ độc đáo của hí khúc Ba Thục. Trong lúc "
    "xem, vui lòng để điện thoại ở chế độ im lặng và không chụp ảnh có đèn flash. Chọn "
    "ngôn ngữ của bạn tại trang nghe để nhận phụ đề đa ngôn ngữ theo thời gian thực. Buổi "
    "biểu diễn tối nay kéo dài khoảng 90 phút với 15 phút nghỉ giữa giờ. Vui lòng đến sớm "
    "30 phút để lấy vé tại quầy. Khách đến muộn sẽ được vào chỗ ngồi trong giờ nghỉ theo hướng dẫn của nhân "
    "viên. Chúc bạn xem vui vẻ!"
)

INTRO_TH = (
    "ยินดีต้อนรับสู่โรงละครอุปรากรเสฉวน โรงละครแห่งนี้ทุ่มเทให้กับการสืบทอดและส่งเสริมศิลปะอุปรากรเสฉวน "
    "อุปรากรเสฉวนผสมผสานรูปแบบการร้องห้าแขนง ได้แก่ เกาเฉียง คุนเฉียง หูฉิน ถานซี และเติงเต้า "
    "และมีชื่อเสียงไปทั่วโลกด้วยสองศิลปะชั้นสูง คือ การเปลี่ยนหน้าและการพ่นไฟ "
    "การแสดงในคืนนี้จะพาคุณสัมผัสเสน่ห์อันเป็นเอกลักษณ์ของอุปรากรปาซู "
    "ระหว่างการแสดงโปรดปิดเสียงโทรศัพท์และงดถ่ายภาพด้วยแฟลช "
    "เลือกภาษาของคุณในหน้ารับฟังเพื่อรับคำบรรยายหลายภาษาแบบเรียลไทม์ "
    "การแสดงคืนนี้มีระยะเวลาประมาณ 90 นาที พร้อมพักการแสดง 15 นาที โปรดมาก่อนเวลา 30 นาทีเพื่อรับบัตรที่จุดจำหน่าย "
    "ผู้ชมที่มาสายจะได้เข้าในช่วงพักตามคำแนะนำของเจ้าหน้าที่ ขอให้สนุกกับการชมการแสดง!"
)

INTRO_TR = (
    "Sichuan Opera Tiyatrosu'na hoş geldiniz. Bu tiyatro, Sichuan operası sanatını korumaya "
    "ve tanıtmaya adanmıştır. Sichuan operası beş şarkı tarzını — Gaoqiang, Kunqiang, "
    "Huqin, Tanxi ve Dengdiao — bir araya getirir ve yüz değiştirme ile ateş püskürtme "
    "gibi iki büyük ustalığıyla dünyaca ünlüdür. Bu geceki performans size Ba-Shu "
    "operasının eşsiz cazibesini sunacak. Gösteri sırasında lütfen telefonunuzu sessize "
    "alın ve flaşla fotoğraf çekmeyin. Gerçek zamanlı çok dilli alt yazılar almak için "
    "dinleme sayfasından dilinizi seçin. Bu akşamki gösteri yaklaşık doksan dakika sürer "
    "ve on beş dakikalık ara vardır. Biletinizi almak için otuz dakika önce gelin. "
    "Geç gelen seyirciler, personelin yönlendirmesiyle aralarda içeri "
    "alınacaktır. Gösterinin tadını çıkarın!"
)

INTRO_ID = (
    "Selamat datang di Teater Opera Sichuan. Teater ini berdedikasi untuk melestarikan "
    "dan mempromosikan seni opera Sichuan. Opera Sichuan memadukan lima gaya vokal — "
    "Gaoqiang, Kunqiang, Huqin, Tanxi, dan Dengdiao — dan terkenal di dunia karena dua "
    "keahlian besarnya: pergantian wajah dan menyemburkan api. Pertunjukan malam ini "
    "akan memperkenalkan pesona unik opera Ba-Shu kepada Anda. Selama pertunjukan, "
    "mohon senyapkan ponsel Anda dan jangan mengambil foto dengan lampu kilat. Pilih "
    "bahasa Anda di halaman mendengarkan untuk mendapatkan takarir multibahasa secara "
    "real-time. Pertunjukan malam ini berlangsung sekitar sembilan puluh menit dengan "
    "jeda lima belas menit. Mohon datang tiga puluh menit lebih awal untuk mengambil "
    "tiket Anda di loket. Penonton yang datang terlambat akan dimasukkan "
    "saat jeda sesuai arahan petugas. Selamat menikmati pertunjukan!"
)

# 语言码 -> 介绍文案（预置 + 运行时翻译缓存）
# 覆盖前端 8 种可选语言与语言表主流语言，共 16 种预置；动态翻译仅兜未列出的语言
INTRO_TEXTS: dict[str, str] = {
    "zh": INTRO_ZH, "en": INTRO_EN, "ja": INTRO_JA, "ko": INTRO_KO,
    "es": INTRO_ES, "fr": INTRO_FR, "de": INTRO_DE, "ru": INTRO_RU,
    "hi": INTRO_HI, "ar": INTRO_AR, "pt": INTRO_PT, "it": INTRO_IT,
    "vi": INTRO_VI, "th": INTRO_TH, "tr": INTRO_TR, "id": INTRO_ID,
}

# 机翻质量黑名单（R3）：译文命中任一「医院」词即视为严重误译，弃用回退英文。
# 历史教训：中文「本院」曾被 8/8 语言译作医院，品牌灾难级错误必须硬拦。
_HOSPITAL_MARKS: tuple[str, ...] = (
    "hospital", "ospedale", "hôpital", "hospital ", "hastane", "rumah sakit",
    "krankenhaus", "клиник", "больниц", "अस्पताल", "مستشفى", "bệnh viện",
    "โรงพยาบาล", "病院", "医院", "ziekenhuis", "szpital", "nemocnic", "орулахана",
)


def _looks_like_hospital(text: str) -> bool:
    """译文是否含「医院」类词汇（小写化后匹配拉丁系，其余原样）。"""
    lowered = text.lower()
    return any(mark in lowered for mark in _HOSPITAL_MARKS)


def get_intro_text(lang: str) -> tuple[str, str]:
    """取某语言的介绍文案，返回 (语言码, 文案)。

    预置命中直接返回；未预置但支持的语言翻译中文原文并缓存；
    译文过「医院词黑名单」后检，可疑即弃用；不支持或失败回退英文版。
    """
    lang = (lang or "").strip()
    if lang.startswith("zh"):  # zh / zh-CN / zh-TW 等统一归中文
        lang = "zh"
    # 预置版本优先命中（注意须先于 is_supported 检查：系统语言表中中文登记为 zh-CN）
    if lang in INTRO_TEXTS:
        return (lang, INTRO_TEXTS[lang])
    if not is_supported(lang):
        return ("en", INTRO_TEXTS["en"])

    # 未预置语言：翻译中文原文（首次）并缓存；黑名单后检防机翻灾难
    try:
        translated = translation_service.translate(INTRO_ZH, lang)
        if translated and translated.strip():
            if _looks_like_hospital(translated):
                logger.warning("剧场介绍译文含医院词，弃用回退英文（%s）", lang)
                return ("en", INTRO_TEXTS["en"])
            INTRO_TEXTS[lang] = translated.strip()
            return (lang, INTRO_TEXTS[lang])
    except Exception as exc:  # noqa: BLE001 - 翻译失败回退英文，不阻断入场介绍
        logger.warning("剧场介绍翻译失败（%s）：%s", lang, exc)
    return ("en", INTRO_TEXTS["en"])


def tts_lang(lang: str) -> str:
    """介绍语言码 → TTS 语言码（中文 zh → zh-CN，其余原样）。"""
    return ZH if lang == "zh" else lang
