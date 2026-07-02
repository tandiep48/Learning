NUMBER_PART_ID = "H1_5_99"
NUMBER_PART_TITLE = "Number"

NUMBER_ROWS = [
    ("零", 69, "ling_69"),
    ("一", 59, "yi_59"),
    ("二", 60, "er_60"),
    ("三", 61, "san_61"),
    ("四", 62, "si_62"),
    ("五", 63, "wu_63"),
    ("六", 64, "liu_64"),
    ("七", 65, "qi_65"),
    ("八", 66, "ba_66"),
    ("九", 67, "jiu_67"),
    ("十", 68, "shi_68"),
    ("十一", 17612, "shiyi_17612"),
    ("十二", 17613, "shier_17613"),
    ("十三", 17614, "shisan_17614"),
    ("十四", 17615, "shisi_17615"),
    ("十五", 17616, "shiwu_17616"),
    ("十六", 17617, "shiliu_17617"),
    ("十七", 17618, "shiqi_17618"),
    ("十八", 17619, "shiba_17619"),
    ("十九", 17620, "shijiu_17620"),
    ("二十", 17621, "ershi_17621"),
    ("二十一", 17622, "ershiyi_17622"),
    ("二十二", 17623, "ershier_17623"),
    ("二十三", 17624, "ershisan_17624"),
    ("二十四", 17625, "ershisi_17625"),
    ("二十五", 17626, "ershiwu_17626"),
    ("二十六", 17627, "ershiliu_17627"),
    ("二十七", 17628, "ershiqi_17628"),
    ("二十八", 17629, "ershiba_17629"),
    ("二十九", 17630, "ershijiu_17630"),
    ("三十", 17631, "sanshi_17631"),
    ("三十一", 17632, "sanshiyi_17632"),
    ("三十二", 17633, "sanshier_17633"),
    ("三十三", 17634, "sanshisan_17634"),
    ("三十四", 17635, "sanshisi_17635"),
    ("三十五", 17636, "sanshiwu_17636"),
    ("三十六", 17637, "sanshiliu_17637"),
    ("三十七", 17638, "sanshiqi_17638"),
    ("三十八", 17639, "sanshiba_17639"),
    ("三十九", 17640, "sanshijiu_17640"),
    ("四十", 17641, "sishi_17641"),
    ("四十一", 17642, "sishiyi_17642"),
    ("四十二", 17643, "sishier_17643"),
    ("四十三", 17644, "sishisan_17644"),
    ("四十四", 17645, "sishisi_17645"),
    ("四十五", 17646, "sishiwu_17646"),
    ("四十六", 17647, "sishiliu_17647"),
    ("四十七", 17648, "sishiqi_17648"),
    ("四十八", 17649, "sishiba_17649"),
    ("四十九", 17650, "sishijiu_17650"),
    ("五十", 17651, "wushi_17651"),
    ("五十一", 17652, "wushiyi_17652"),
    ("五十二", 17653, "wushier_17653"),
    ("五十三", 17654, "wushisan_17654"),
    ("五十四", 17655, "wushisi_17655"),
    ("五十五", 17656, "wushiwu_17656"),
    ("五十六", 17657, "wushiliu_17657"),
    ("五十七", 17658, "wushiqi_17658"),
    ("五十八", 17659, "wushiba_17659"),
    ("五十九", 17660, "wushijiu_17660"),
    ("六十", 17661, "liushi_17661"),
    ("六十一", 17662, "liushiyi_17662"),
    ("六十二", 17663, "liushier_17663"),
    ("六十三", 17664, "liushisan_17664"),
    ("六十四", 17665, "liushisi_17665"),
    ("六十五", 17666, "liushiwu_17666"),
    ("六十六", 17667, "liushiliu_17667"),
    ("六十七", 17668, "liushiqi_17668"),
    ("六十八", 17669, "liushiba_17669"),
    ("六十九", 17670, "liushijiu_17670"),
    ("七十", 17671, "qishi_17671"),
    ("七十一", 17672, "qishiyi_17672"),
    ("七十二", 17673, "qishier_17673"),
    ("七十三", 17674, "qishisan_17674"),
    ("七十四", 17675, "qishisi_17675"),
    ("七十五", 17676, "qishiwu_17676"),
    ("七十六", 17677, "qishiliu_17677"),
    ("七十七", 17678, "qishiqi_17678"),
    ("七十八", 17679, "qishiba_17679"),
    ("七十九", 17680, "qishijiu_17680"),
    ("八十", 17681, "bashi_17681"),
    ("八十一", 17682, "bashiyi_17682"),
    ("八十二", 17683, "bashier_17683"),
    ("八十三", 17684, "bashisan_17684"),
    ("八十四", 17685, "bashisi_17685"),
    ("八十五", 17686, "bashiwu_17686"),
    ("八十六", 17687, "bashiliu_17687"),
    ("八十七", 17688, "bashiqi_17688"),
    ("八十八", 17689, "bashiba_17689"),
    ("八十九", 17690, "bashijiu_17690"),
    ("九十", 17691, "jiushi_17691"),
    ("九十一", 17692, "jiushiyi_17692"),
    ("九十二", 17693, "jiushier_17693"),
    ("九十三", 17694, "jiushisan_17694"),
    ("九十四", 17695, "jiushisi_17695"),
    ("九十五", 17696, "jiushiwu_17696"),
    ("九十六", 17697, "jiushiliu_17697"),
    ("九十七", 17698, "jiushiqi_17698"),
    ("九十八", 17699, "jiushiba_17699"),
    ("九十九", 17700, "jiushijiu_17700"),
]

_NUMBER_BY_WORD = {word: (word, vocab_id, audio_key) for word, vocab_id, audio_key in NUMBER_ROWS}


def is_number_part(passage_id):
    return str(passage_id or "") == NUMBER_PART_ID


def _pinyin_from_audio_key(audio_key):
    return str(audio_key or "").rsplit("_", 1)[0]


def _arabic_number_for_word(word):
    if word == "零":
        return 0
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if word in digits:
        return digits[word]
    if word == "十":
        return 10
    if word.startswith("十"):
        return 10 + digits.get(word[1:], 0)
    if word.endswith("十"):
        return digits.get(word[0], 0) * 10
    tens, ones = word.split("十", 1)
    return digits.get(tens, 0) * 10 + digits.get(ones, 0)


def number_vocab_rows():
    rows = []
    for word, _vocab_id, audio_key in NUMBER_ROWS[:11]:
        meaning = str(_arabic_number_for_word(word))
        rows.append({
            "word": word,
            "cn": word,
            "pinyin": _pinyin_from_audio_key(audio_key),
            "meaning_vn": meaning,
            "meaning_en": meaning,
            "audio_key": audio_key,
            "hsk_level": "HSK1",
            "level": "HSK1",
        })
    return rows
