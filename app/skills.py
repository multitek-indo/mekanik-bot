SKILL_LEVEL_TEXT = {
    0: "Belum pernah menangani",
    1: "Tahu dasar / pernah melihat atau mengoperasikan",
    2: "Bisa setting dan maintenance ringan",
    3: "Bisa service umum secara mandiri",
    4: "Bisa troubleshooting kompleks, bongkar, timing, atau kalibrasi",
    5: "Spesialis; mampu menangani kasus berat dan membimbing teknisi lain",
}

SKILLS = [
    {
        "code": "JARUM_1",
        "name": "Jarum 1",
        "keywords": ["JARUM 1", "1 JARUM", "SINGLE NEEDLE", "DDL"],
        "questions": [
            "Jika hasil jahitan loncat atau benang tidak tertangkap, jelaskan urutan pemeriksaan Anda.",
            "Jelaskan bagaimana Anda memeriksa dan menyetel hubungan timing jarum dengan hook setelah mesin dibongkar.",
            "Jika mesin terasa berat atau cepat panas setelah servis, bagian apa saja yang Anda periksa sebelum menyerahkan mesin ke customer?",
        ],
    },
    {
        "code": "JARUM_2",
        "name": "Jarum 2",
        "keywords": ["JARUM 2", "2 JARUM", "DOUBLE NEEDLE", "TWIN NEEDLE", "LH"],
        "questions": [
            "Jika hanya satu sisi jahitan sering loncat, apa urutan pemeriksaan Anda?",
            "Jelaskan bagaimana Anda memastikan timing kedua jarum terhadap hook atau looper tetap seimbang.",
            "Jika hasil dua jalur jahitan tidak sama atau material bergeser, bagian mekanisme feed apa yang Anda evaluasi?",
        ],
    },
    {
        "code": "OBRAS",
        "name": "Obras",
        "keywords": ["OBRAS", "OBRA", "OVERLOCK", "MO-"],
        "questions": [
            "Jika rantai benang tidak terbentuk dan benang mudah putus, apa urutan pemeriksaan Anda?",
            "Jelaskan cara Anda memeriksa hubungan timing jarum, upper looper, dan lower looper.",
            "Jika hasil obras mengerut atau melebar tidak normal, bagaimana Anda mengecek differential feed dan tension?",
        ],
    },
    {
        "code": "OVERDECK",
        "name": "Overdeck",
        "keywords": ["OVERDECK", "COVERSTITCH", "COVER STITCH", "MF-"],
        "questions": [
            "Jika jahitan bawah tidak membentuk rantai dengan baik, apa yang Anda cek terlebih dahulu?",
            "Jelaskan bagaimana Anda memeriksa timing looper dan spreader pada mesin overdeck.",
            "Jika kain bergelombang atau hasil jahitan tidak rata, bagaimana Anda menilai differential feed dan thread tension?",
        ],
    },
    {
        "code": "KANSAI",
        "name": "Kansai",
        "keywords": ["KANSAI", "MULTI NEEDLE", "CHAINSTITCH", "CHAIN STITCH"],
        "questions": [
            "Jika salah satu jalur jahitan tidak terbentuk, apa urutan pemeriksaan Anda pada jarum, looper, dan tension?",
            "Bagaimana Anda memeriksa sinkronisasi feed atau puller dengan pembentukan stitch?",
            "Sebutkan contoh masalah Kansai yang pernah Anda tangani dan bagaimana Anda memastikan hasil akhir stabil setelah repair.",
        ],
    },
    {
        "code": "BARTACK",
        "name": "Bartack",
        "keywords": ["BARTACK", "BAR TACK", "LK-"],
        "questions": [
            "Jika pola bartack tidak selesai atau posisi jahitan bergeser, apa yang Anda periksa?",
            "Bagaimana Anda membedakan masalah mekanik hook/timing dengan masalah sensor atau kontrol pada bartack elektronik?",
            "Jika thread trimming gagal setelah jahitan selesai, bagaimana urutan diagnosis Anda?",
        ],
    },
    {
        "code": "LUBANG_KANCING",
        "name": "Lubang Kancing",
        "keywords": ["LUBANG KANCING", "BUTTONHOLE", "BUTTON HOLE"],
        "questions": [
            "Jika ukuran atau bentuk lubang kancing tidak konsisten, bagian apa saja yang Anda periksa?",
            "Bagaimana Anda memeriksa hubungan timing jahitan dengan mekanisme pisau pemotong?",
            "Pada mesin elektronik, bagaimana Anda membedakan gangguan mekanik dengan sensor atau kontrol?",
        ],
    },
    {
        "code": "PASANG_KANCING",
        "name": "Pasang Kancing",
        "keywords": ["PASANG KANCING", "BUTTON ATTACH", "BUTTON SEWER"],
        "questions": [
            "Jika posisi kancing sering meleset, apa yang Anda periksa pada clamp, holder, dan pola jahitan?",
            "Jika mesin gagal memotong benang setelah pemasangan kancing, apa urutan diagnosis Anda?",
            "Bagaimana Anda memastikan ukuran atau pola kancing yang berbeda tidak menyebabkan benturan jarum?",
        ],
    },
    {
        "code": "WALKINGFOOT",
        "name": "Walkingfoot",
        "keywords": ["WALKINGFOOT", "WALKING FOOT", "UNISON FEED"],
        "questions": [
            "Bagaimana Anda memeriksa sinkronisasi needle feed, feed dog, dan walking foot?",
            "Jika material tebal bergeser atau stitch length tidak konsisten, apa yang Anda cek?",
            "Setelah bongkar mekanisme feed, bagaimana Anda memastikan mesin kembali ringan dan tidak macet saat beban tinggi?",
        ],
    },
    {
        "code": "ZIGZAG",
        "name": "Zigzag",
        "keywords": ["ZIGZAG", "ZIG ZAG"],
        "questions": [
            "Jika lebar zigzag tidak simetris antara kiri dan kanan, bagian apa yang Anda periksa?",
            "Bagaimana Anda memeriksa timing hook ketika jarum bergerak ke posisi kiri dan kanan?",
            "Jika pola zigzag berubah saat kecepatan tinggi, apa kemungkinan area mekanik atau kontrol yang Anda cek?",
        ],
    },
    {
        "code": "DIE_CUTTING",
        "name": "Die Cutting",
        "keywords": ["DIE CUTTING", "DIECUT", "DIE CUT"],
        "questions": [
            "Jika hasil potong tidak rata, bagaimana Anda memeriksa tekanan, posisi die, dan permukaan cutting?",
            "Jika mesin tidak mencapai tekanan kerja, sistem apa saja yang Anda periksa sebelum menyimpulkan kerusakan utama?",
            "Bagaimana Anda melakukan pemeriksaan keselamatan sebelum menjalankan kembali mesin die cutting setelah repair?",
        ],
    },
    {
        "code": "AUTO_CUTTER",
        "name": "Auto Cutter",
        "keywords": ["AUTO CUTTER", "AUTOCUTTER", "AUTO CUTTING", "CUTTING MACHINE"],
        "questions": [
            "Jika mesin gagal homing atau berhenti di tengah proses cutting, apa urutan pemeriksaan Anda?",
            "Bagaimana Anda membedakan masalah blade atau mekanik dengan servo, sensor, atau motion control?",
            "Jika file cutting terbaca tetapi hasil potong bergeser, apa yang Anda cek pada kalibrasi, origin, dan setting software?",
        ],
    },
    {
        "code": "AUTO_SPREADING",
        "name": "Auto Spreading",
        "keywords": ["AUTO SPREADING", "AUTOSPREADING", "SPREADER", "SPREADING MACHINE"],
        "questions": [
            "Jika kain bergeser atau tension tidak stabil saat spreading, apa yang Anda periksa?",
            "Bagaimana Anda mendiagnosis mesin yang berhenti karena sensor, motor, atau limit tidak terbaca?",
            "Jelaskan bagaimana Anda memverifikasi layer count, panjang spread, dan alignment setelah servis.",
        ],
    },
    {
        "code": "ELEKTRONIK_SERVO",
        "name": "Elektronik Servo",
        "keywords": ["ELEKTRONIK SERVO", "SERVO", "SERVO DRIVE", "SERVO MOTOR", "INVERTER"],
        "questions": [
            "Saat servo tidak start atau muncul alarm, data apa yang Anda kumpulkan sebelum mengganti komponen?",
            "Jelaskan alat ukur yang biasa Anda gunakan untuk membedakan masalah power, driver, motor, sensor, atau encoder.",
            "Sebutkan satu contoh kerusakan servo elektronik yang pernah Anda tangani dan bagaimana Anda membuktikan sumber masalahnya.",
        ],
    },
    {
        "code": "LUBANG_RIS",
        "name": "Lubang Ris",
        "keywords": ["LUBANG RIS", "RIS"],
        "questions": [
            "Jelaskan proses kerja mesin lubang ris yang Anda kuasai dan titik setting yang paling sering berubah.",
            "Jika hasil lubang tidak simetris, tidak bersih, atau posisi meleset, apa urutan pemeriksaan Anda?",
            "Bagaimana Anda mengecek kondisi tooling, mekanisme penekan, sensor, dan alignment sebelum menyimpulkan kerusakan?",
        ],
    },
    {
        "code": "BOBOK_KANTONG",
        "name": "Bobok Kantong",
        "keywords": ["BOBOK KANTONG", "POCKET WELT", "POCKET MACHINE"],
        "questions": [
            "Jika posisi bobok atau jahitan kantong bergeser, apa yang Anda periksa pada clamp, jig, dan origin?",
            "Bagaimana Anda mendiagnosis urutan kerja pisau, clamp, dan proses jahit yang tidak sinkron?",
            "Jika mesin berhenti pada salah satu step otomatis, bagaimana Anda memeriksa sensor dan interlock sebelum mengganti komponen?",
        ],
    },
    {
        "code": "AUTO_TEMPLATE",
        "name": "Auto Template",
        "keywords": ["AUTO TEMPLATE", "TEMPLATE MACHINE", "PATTERN SEWER"],
        "questions": [
            "Jika hasil pola bergeser dari template, bagaimana Anda memeriksa origin, clamp, dan kalibrasi XY?",
            "Bagaimana Anda membedakan masalah mekanik carriage dengan servo, sensor, atau parameter kontrol?",
            "Jika pattern baru gagal dijalankan tetapi pattern lama normal, apa saja yang Anda cek pada file, parameter, dan software?",
        ],
    },
    {
        "code": "SOFTWARE_DESIGN",
        "name": "Software Design",
        "keywords": ["SOFTWARE DESIGN", "CAD", "PATTERN DESIGN", "MARKER", "NESTING"],
        "questions": [
            "Software design atau CAD garment apa yang pernah Anda gunakan dan pekerjaan apa yang dapat Anda lakukan secara mandiri?",
            "Jelaskan alur Anda dari membuat atau mengedit pattern sampai file siap digunakan oleh mesin atau proses produksi.",
            "Jika file tidak terbaca, ukuran berubah, atau komunikasi software ke mesin gagal, bagaimana Anda melakukan troubleshooting?",
        ],
    },
]

SKILL_BY_CODE = {item["code"]: item for item in SKILLS}
SKILL_BY_NUMBER = {idx + 1: item for idx, item in enumerate(SKILLS)}


def skills_menu() -> str:
    return "\n".join(f"{idx}. {item['name']}" for idx, item in SKILL_BY_NUMBER.items())


def level_menu() -> str:
    return "\n".join(f"{level} = {text}" for level, text in SKILL_LEVEL_TEXT.items())


def detect_skill_code(text: str | None) -> str | None:
    hay = (text or "").upper()
    for item in SKILLS:
        for keyword in item["keywords"]:
            if keyword in hay:
                return item["code"]
    return None


def parse_top_skill_numbers(text: str) -> list[int]:
    raw = (text or "").replace(";", ",").replace(" ", ",")
    values = []
    for part in raw.split(","):
        if not part:
            continue
        if not part.isdigit():
            return []
        value = int(part)
        if value not in SKILL_BY_NUMBER:
            return []
        if value not in values:
            values.append(value)
    return values
