"""Country rules (POLICY.md principles 5 and 6).

Names, ISO codes and nationalities all resolve to one ISO 3166 two-letter code.
Territories keep their own code. "International" and "Europe" are not countries.
"""
import re

from .textutil import fold

# code | ISO3 | names and aliases | nationalities
_TABLE = """
AF|AFG|Afghanistan|Afghan; Afghani
AX|ALA|Aland Islands; Aland|
AL|ALB|Albania|Albanian
DZ|DZA|Algeria|Algerian
AS|ASM|American Samoa|American Samoan
AD|AND|Andorra|Andorran
AO|AGO|Angola|Angolan
AI|AIA|Anguilla|Anguillan
AQ|ATA|Antarctica|
AG|ATG|Antigua and Barbuda; Antigua & Barbuda; Antigua|Antiguan; Barbudan
AR|ARG|Argentina; Argentine Republic|Argentine; Argentinian; Argentinean
AM|ARM|Armenia|Armenian
AW|ABW|Aruba|Aruban
AU|AUS|Australia; Commonwealth of Australia|Australian
AT|AUT|Austria|Austrian
AZ|AZE|Azerbaijan|Azerbaijani; Azeri
BS|BHS|Bahamas; The Bahamas|Bahamian
BH|BHR|Bahrain|Bahraini
BD|BGD|Bangladesh|Bangladeshi
BB|BRB|Barbados|Barbadian; Bajan
BY|BLR|Belarus; Byelorussia|Belarusian; Belarussian
BE|BEL|Belgium|Belgian
BZ|BLZ|Belize|Belizean
BJ|BEN|Benin|Beninese
BM|BMU|Bermuda|Bermudian; Bermudan
BT|BTN|Bhutan|Bhutanese
BO|BOL|Bolivia; Plurinational State of Bolivia; Bolivia, Plurinational State of|Bolivian
BQ|BES|Bonaire, Sint Eustatius and Saba; Bonaire; Caribbean Netherlands|
BA|BIH|Bosnia and Herzegovina; Bosnia & Herzegovina; Bosnia-Herzegovina; Bosnia Herzegovina; Bosnia|Bosnian; Herzegovinian
BW|BWA|Botswana|Botswanan; Motswana; Batswana
BV|BVT|Bouvet Island|
BR|BRA|Brazil; Brasil|Brazilian
IO|IOT|British Indian Ocean Territory|
BN|BRN|Brunei; Brunei Darussalam|Bruneian
BG|BGR|Bulgaria|Bulgarian
BF|BFA|Burkina Faso|Burkinabe
BI|BDI|Burundi|Burundian
CV|CPV|Cabo Verde; Cape Verde|Cape Verdean; Cabo Verdean
KH|KHM|Cambodia|Cambodian
CM|CMR|Cameroon; Cameroun|Cameroonian
CA|CAN|Canada|Canadian
KY|CYM|Cayman Islands; Caymans|Caymanian
CF|CAF|Central African Republic|Central African
TD|TCD|Chad|Chadian
CL|CHL|Chile|Chilean
CN|CHN|China; People's Republic of China; Peoples Republic of China; PRC; Mainland China|Chinese
CX|CXR|Christmas Island|
CC|CCK|Cocos (Keeling) Islands; Cocos Islands; Keeling Islands|
CO|COL|Colombia|Colombian
KM|COM|Comoros|Comorian; Comoran
CG|COG|Congo; Republic of the Congo; Republic of Congo; Congo-Brazzaville; Congo Brazzaville; Congo (Brazzaville)|Congolese
CD|COD|Democratic Republic of the Congo; Democratic Republic of Congo; DR Congo; DRC; Congo-Kinshasa; Congo Kinshasa; Congo (Kinshasa); Congo, Democratic Republic of the; Congo, The Democratic Republic of the; Zaire|
CK|COK|Cook Islands|Cook Islander
CR|CRI|Costa Rica|Costa Rican
CI|CIV|Cote d'Ivoire; Cote d Ivoire; Ivory Coast|Ivorian; Ivoirian
HR|HRV|Croatia|Croatian; Croat
CU|CUB|Cuba|Cuban
CW|CUW|Curacao|Curacaoan
CY|CYP|Cyprus|Cypriot
CZ|CZE|Czechia; Czech Republic|Czech
DK|DNK|Denmark|Danish; Dane
DJ|DJI|Djibouti|Djiboutian
DM|DMA|Dominica|
DO|DOM|Dominican Republic|Dominican
EC|ECU|Ecuador|Ecuadorian; Ecuadorean
EG|EGY|Egypt; Arab Republic of Egypt|Egyptian
SV|SLV|El Salvador|Salvadoran; Salvadorian; Salvadorean
GQ|GNQ|Equatorial Guinea|Equatorial Guinean; Equatoguinean
ER|ERI|Eritrea|Eritrean
EE|EST|Estonia|Estonian
SZ|SWZ|Eswatini; Swaziland; Kingdom of Eswatini|Swazi; Swati
ET|ETH|Ethiopia|Ethiopian
FK|FLK|Falkland Islands; Falkland Islands (Malvinas); Malvinas|Falkland Islander
FO|FRO|Faroe Islands; Faeroe Islands; Faroes|Faroese
FJ|FJI|Fiji|Fijian
FI|FIN|Finland|Finnish; Finn
FR|FRA|France; French Republic|French
GF|GUF|French Guiana|French Guianese
PF|PYF|French Polynesia|French Polynesian
TF|ATF|French Southern Territories|
GA|GAB|Gabon|Gabonese
GM|GMB|Gambia; The Gambia|Gambian
GE|GEO|Georgia|Georgian
DE|DEU|Germany; Federal Republic of Germany; Deutschland|German
GH|GHA|Ghana|Ghanaian
GI|GIB|Gibraltar|Gibraltarian
GR|GRC|Greece; Hellenic Republic|Greek
GL|GRL|Greenland|Greenlandic; Greenlander
GD|GRD|Grenada|Grenadian
GP|GLP|Guadeloupe|Guadeloupean
GU|GUM|Guam|Guamanian
GT|GTM|Guatemala|Guatemalan
GG|GGY|Guernsey|
GN|GIN|Guinea; Republic of Guinea; Guinea-Conakry|Guinean
GW|GNB|Guinea-Bissau; Guinea Bissau|Bissau-Guinean
GY|GUY|Guyana|Guyanese
HT|HTI|Haiti|Haitian
HM|HMD|Heard Island and McDonald Islands|
VA|VAT|Holy See; Vatican City; Vatican; Vatican City State; Holy See (Vatican City State)|
HN|HND|Honduras|Honduran
HK|HKG|Hong Kong; Hong Kong SAR; Hong Kong Special Administrative Region of China; Hong Kong SAR China; Hong Kong, China; Hongkong|Hong Konger; Hongkonger
HU|HUN|Hungary|Hungarian
IS|ISL|Iceland|Icelandic; Icelander
IN|IND|India; Republic of India|Indian
ID|IDN|Indonesia|Indonesian
IR|IRN|Iran; Islamic Republic of Iran; Iran, Islamic Republic of; Iran (Islamic Republic of)|Iranian; Persian
IQ|IRQ|Iraq|Iraqi
IE|IRL|Ireland; Republic of Ireland; Eire|Irish
IM|IMN|Isle of Man|Manx
IL|ISR|Israel; State of Israel|Israeli
IT|ITA|Italy; Italia; Italian Republic|Italian
JM|JAM|Jamaica|Jamaican
JP|JPN|Japan|Japanese
JE|JEY|Jersey|
JO|JOR|Jordan; Hashemite Kingdom of Jordan|Jordanian
KZ|KAZ|Kazakhstan|Kazakh; Kazakhstani
KE|KEN|Kenya|Kenyan
KI|KIR|Kiribati|
KP|PRK|North Korea; Democratic People's Republic of Korea; Democratic Peoples Republic of Korea; DPRK; Korea, Democratic People's Republic of; Korea (North); Korea, North|North Korean
KR|KOR|South Korea; Republic of Korea; Korea, Republic of; Korea (South); Korea, South; Korea|South Korean; Korean
KW|KWT|Kuwait|Kuwaiti
KG|KGZ|Kyrgyzstan; Kyrgyz Republic; Kirghizia|Kyrgyz; Kyrgyzstani
LA|LAO|Laos; Lao People's Democratic Republic; Lao PDR; Lao|Laotian
LV|LVA|Latvia|Latvian
LB|LBN|Lebanon|Lebanese
LS|LSO|Lesotho|Basotho; Mosotho
LR|LBR|Liberia|Liberian
LY|LBY|Libya; Libyan Arab Jamahiriya; State of Libya|Libyan
LI|LIE|Liechtenstein|Liechtensteiner
LT|LTU|Lithuania|Lithuanian
LU|LUX|Luxembourg; Luxemburg|Luxembourgish; Luxembourger
MO|MAC|Macao; Macau; Macao SAR; Macau SAR; Macao Special Administrative Region of China; Macau Special Administrative Region of China; Macao, China; Macau, China|Macanese
MG|MDG|Madagascar|Malagasy
MW|MWI|Malawi|Malawian
MY|MYS|Malaysia|Malaysian
MV|MDV|Maldives|Maldivian
ML|MLI|Mali|Malian
MT|MLT|Malta|Maltese
MH|MHL|Marshall Islands|Marshallese
MQ|MTQ|Martinique|Martinican
MR|MRT|Mauritania|Mauritanian
MU|MUS|Mauritius|Mauritian
YT|MYT|Mayotte|
MX|MEX|Mexico; United Mexican States|Mexican
FM|FSM|Micronesia; Federated States of Micronesia; Micronesia, Federated States of|Micronesian
MD|MDA|Moldova; Republic of Moldova; Moldova, Republic of|Moldovan
MC|MCO|Monaco|Monegasque; Monacan
MN|MNG|Mongolia|Mongolian
ME|MNE|Montenegro|Montenegrin
MS|MSR|Montserrat|Montserratian
MA|MAR|Morocco|Moroccan
MZ|MOZ|Mozambique|Mozambican
MM|MMR|Myanmar; Burma; Myanmar (Burma)|Burmese
NA|NAM|Namibia|Namibian
NR|NRU|Nauru|Nauruan
NP|NPL|Nepal|Nepali; Nepalese
NL|NLD|Netherlands; The Netherlands; Holland; Kingdom of the Netherlands|Dutch
NC|NCL|New Caledonia|New Caledonian
NZ|NZL|New Zealand; Aotearoa|New Zealander
NI|NIC|Nicaragua|Nicaraguan
NE|NER|Niger|Nigerien
NG|NGA|Nigeria; Federal Republic of Nigeria|Nigerian
NU|NIU|Niue|Niuean
NF|NFK|Norfolk Island|
MK|MKD|North Macedonia; Macedonia; Republic of North Macedonia; Former Yugoslav Republic of Macedonia; FYROM; Macedonia, the former Yugoslav Republic of|Macedonian
MP|MNP|Northern Mariana Islands; Commonwealth of the Northern Mariana Islands; CNMI|
NO|NOR|Norway|Norwegian
OM|OMN|Oman|Omani
PK|PAK|Pakistan; Islamic Republic of Pakistan|Pakistani
PW|PLW|Palau|Palauan
PS|PSE|Palestine; State of Palestine; Palestinian Territories; Palestinian Territory; Palestina; Occupied Palestinian Territory; Palestine, State of; West Bank; Gaza|Palestinian
PA|PAN|Panama|Panamanian
PG|PNG|Papua New Guinea|Papua New Guinean
PY|PRY|Paraguay|Paraguayan
PE|PER|Peru|Peruvian
PH|PHL|Philippines; The Philippines|Filipino; Philippine; Filipina
PN|PCN|Pitcairn; Pitcairn Islands|
PL|POL|Poland|Polish; Pole
PT|PRT|Portugal|Portuguese
PR|PRI|Puerto Rico|Puerto Rican
QA|QAT|Qatar|Qatari
RE|REU|Reunion|
RO|ROU|Romania|Romanian
RU|RUS|Russia; Russian Federation|Russian
RW|RWA|Rwanda|Rwandan
BL|BLM|Saint Barthelemy; St Barthelemy; St Barts|
SH|SHN|Saint Helena; St Helena; Saint Helena, Ascension and Tristan da Cunha|
KN|KNA|Saint Kitts and Nevis; St Kitts and Nevis; St Kitts & Nevis; Saint Kitts & Nevis; St Kitts|Kittitian; Nevisian
LC|LCA|Saint Lucia; St Lucia|Saint Lucian; St Lucian
MF|MAF|Saint Martin; St Martin; Saint Martin (French part)|
PM|SPM|Saint Pierre and Miquelon; St Pierre and Miquelon|
VC|VCT|Saint Vincent and the Grenadines; St Vincent and the Grenadines; St Vincent & the Grenadines; Saint Vincent; St Vincent|Vincentian
WS|WSM|Samoa; Western Samoa|Samoan
SM|SMR|San Marino|Sammarinese
ST|STP|Sao Tome and Principe; Sao Tome & Principe|Sao Tomean
SA|SAU|Saudi Arabia; Kingdom of Saudi Arabia; KSA|Saudi; Saudi Arabian
SN|SEN|Senegal|Senegalese
RS|SRB|Serbia; Republic of Serbia|Serbian; Serb
SC|SYC|Seychelles|Seychellois
SL|SLE|Sierra Leone|Sierra Leonean
SG|SGP|Singapore; Republic of Singapore|Singaporean
SX|SXM|Sint Maarten; Sint Maarten (Dutch part)|
SK|SVK|Slovakia; Slovak Republic|Slovak; Slovakian
SI|SVN|Slovenia|Slovenian; Slovene
SB|SLB|Solomon Islands|Solomon Islander
SO|SOM|Somalia|Somali; Somalian
ZA|ZAF|South Africa; Republic of South Africa; RSA|South African
GS|SGS|South Georgia and the South Sandwich Islands|
SS|SSD|South Sudan; Republic of South Sudan|South Sudanese
ES|ESP|Spain; Espana; Kingdom of Spain|Spanish; Spaniard
LK|LKA|Sri Lanka; Ceylon|Sri Lankan
SD|SDN|Sudan; Republic of the Sudan; North Sudan|Sudanese
SR|SUR|Suriname; Surinam|Surinamese
SJ|SJM|Svalbard and Jan Mayen; Svalbard|
SE|SWE|Sweden|Swedish; Swede
CH|CHE|Switzerland; Swiss Confederation|Swiss
SY|SYR|Syria; Syrian Arab Republic|Syrian
TW|TWN|Taiwan; Taiwan, Province of China; Republic of China; Chinese Taipei; Taiwan (Province of China); Taiwan, China|Taiwanese
TJ|TJK|Tajikistan|Tajik; Tajikistani
TZ|TZA|Tanzania; United Republic of Tanzania; Tanzania, United Republic of|Tanzanian
TH|THA|Thailand|Thai
TL|TLS|Timor-Leste; East Timor; Timor Leste|Timorese; East Timorese
TG|TGO|Togo|Togolese
TK|TKL|Tokelau|
TO|TON|Tonga|Tongan
TT|TTO|Trinidad and Tobago; Trinidad & Tobago; Trinidad|Trinidadian; Tobagonian
TN|TUN|Tunisia|Tunisian
TR|TUR|Turkey; Turkiye; Republic of Turkey; Republic of Turkiye|Turkish; Turk
TM|TKM|Turkmenistan|Turkmen
TC|TCA|Turks and Caicos Islands; Turks & Caicos; Turks and Caicos|
TV|TUV|Tuvalu|Tuvaluan
UG|UGA|Uganda|Ugandan
UA|UKR|Ukraine|Ukrainian
AE|ARE|United Arab Emirates; UAE; U.A.E.; Emirates|Emirati
GB|GBR|United Kingdom; UK; U.K.; Great Britain; Britain; United Kingdom of Great Britain and Northern Ireland; England; Scotland; Wales; Northern Ireland|British; Briton; English; Scottish; Welsh; Northern Irish
US|USA|United States; United States of America; USA; U.S.A.; US; U.S.; America; The United States|American
UM|UMI|United States Minor Outlying Islands|
UY|URY|Uruguay|Uruguayan
UZ|UZB|Uzbekistan|Uzbek; Uzbekistani
VU|VUT|Vanuatu|Vanuatuan
VE|VEN|Venezuela; Bolivarian Republic of Venezuela; Venezuela, Bolivarian Republic of|Venezuelan
VN|VNM|Vietnam; Viet Nam; Socialist Republic of Vietnam|Vietnamese
VG|VGB|British Virgin Islands; Virgin Islands, British; Virgin Islands (British); BVI|
VI|VIR|United States Virgin Islands; US Virgin Islands; U.S. Virgin Islands; Virgin Islands, U.S.; Virgin Islands (U.S.); USVI|
WF|WLF|Wallis and Futuna|
EH|ESH|Western Sahara|Sahrawi
YE|YEM|Yemen|Yemeni
ZM|ZMB|Zambia|Zambian
ZW|ZWE|Zimbabwe|Zimbabwean
XK|XKX|Kosovo; Republic of Kosovo|Kosovar; Kosovan
"""

# Region words that sit in country fields but are not countries.
NOT_COUNTRIES = frozenset([
    "international", "europe", "asia", "africa", "global", "worldwide", "world",
    "european union", "eu", "middle east", "americas", "latin america", "north america",
    "south america", "central america", "oceania", "caribbean", "unknown", "none", "null",
    "n a", "na", "not available", "",
])

IGNORED = "-"  # resolve() result for a region word: not a country, and not unknown either


def _key(text):
    """Fold a country string: no case, accents, punctuation or leading 'the'."""
    text = fold(text).replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if text.startswith("the "):
        text = text[4:]
    return text


NAMES = {}       # folded name or alias -> code
DEMONYMS = {}    # folded nationality -> code
ISO2 = {}        # 'GB' -> 'GB'
ISO3 = {}        # 'GBR' -> 'GB'
DISPLAY = {}     # code -> main English name
ALIASES = {}     # code -> folded names, for searching text

for _line in _TABLE.strip().splitlines():
    _code, _iso3, _names, _demonyms = [part.strip() for part in _line.split("|")]
    _name_list = [n.strip() for n in _names.split(";") if n.strip()]
    ISO2[_code] = _code
    ISO3[_iso3] = _code
    DISPLAY[_code] = _name_list[0]
    ALIASES[_code] = []
    for _n in _name_list:
        _k = _key(_n)
        NAMES.setdefault(_k, _code)
        if _k not in ALIASES[_code]:
            ALIASES[_code].append(_k)
    for _d in _demonyms.split(";"):
        if _d.strip():
            DEMONYMS.setdefault(_key(_d), _code)

_TAG = re.compile(r"\[[^\]]*\]|\([^)]*\)")


def resolve(value):
    """The country code for a country field value. Returns None when the value is not
    recognised and IGNORED when it is a region word such as 'International'."""
    if value is None:
        return IGNORED
    raw = str(value).strip()
    if not raw or raw.upper() in ("NA", "N/A", "N.A."):
        return IGNORED  # a placeholder, not Namibia
    if raw in ISO2:
        return raw
    if raw in ISO3:
        return ISO3[raw]
    key = _key(raw)
    if key in NAMES:
        return NAMES[key]
    if key in DEMONYMS:
        return DEMONYMS[key]
    stripped = _key(_TAG.sub(" ", raw))  # "United States [Associated]"
    if stripped in NAMES:
        return NAMES[stripped]
    if stripped in DEMONYMS:
        return DEMONYMS[stripped]
    if key in NOT_COUNTRIES or stripped in NOT_COUNTRIES:
        return IGNORED
    return None


def resolve_place(value):
    """The country of a place such as 'Zamora, Zamora, Spain [Business]': the whole
    string if it is a country, otherwise its last comma part."""
    if value is None:
        return IGNORED
    raw = _TAG.sub(" ", str(value)).strip().strip(",").strip()
    if not raw:
        return IGNORED
    whole = resolve(raw)
    if whole is not None:
        return whole
    return resolve(raw.split(",")[-1])


def split_values(value):
    """Items of a multi-valued field, given as a list or a ';' separated string."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    return [part.strip() for part in str(value).split(";") if part.strip()]


# -- countries mentioned in sentences -----------------------------------------
# Aliases too short or too ordinary to trust inside free text.
_NOT_IN_TEXT = frozenset("america korea lao gaza us uk man eu".split())
_ABBREVIATIONS = [
    (re.compile(r"(?<![A-Za-z.])U\.?S\.?A?\.?(?![A-Za-z$])"), "US"),
    (re.compile(r"(?<![A-Za-z.])U\.?K\.?(?![A-Za-z])"), "GB"),
    (re.compile(r"(?<![A-Za-z.])U\.?A\.?E\.?(?![A-Za-z])"), "AE"),
]
# A country name that is part of another place name.
_FALSE_CONTEXT = {
    "jersey": re.compile(r"new $"), "mexico": re.compile(r"new $"), "guinea": re.compile(r"new $"),
}
_FALSE_AFTER = {"benin": re.compile(r"^ city"), "jersey": re.compile(r"^ city")}

_TEXT_ALIASES = sorted(
    ((alias, code) for code, aliases in ALIASES.items() for alias in aliases
     if len(alias) >= 4 and alias not in _NOT_IN_TEXT),
    key=lambda item: -len(item[0]),
)
_TEXT_PATTERN = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(alias) for alias, _ in _TEXT_ALIASES) + r")(?![a-z0-9])"
)
_TEXT_CODE = dict(_TEXT_ALIASES)


def _text_key(text):
    """Fold a sentence the way aliases are folded, keeping one space between words."""
    text = fold(text).replace("&", " and ")
    return " " + re.sub(r"[^a-z0-9]+", " ", text).strip() + " "


_TEXT_DEMONYMS = sorted(
    (d for d in DEMONYMS if len(d) >= 4 and d not in ("pole", "finn", "dane", "turk")),
    key=lambda item: -len(item),
)
_DEMONYM_PATTERN = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(d) for d in _TEXT_DEMONYMS) + r")(?![a-z0-9])"
)


def find_in_text(text, demonyms=False):
    """Country codes named in a sentence, in order of first mention. With
    demonyms=True a nationality ('a Nigerian passport') names its country too."""
    if not text:
        return []
    found = []
    folded = _text_key(text)
    if demonyms:
        for m in _DEMONYM_PATTERN.finditer(folded):
            code = DEMONYMS[m.group(1)]
            if code not in found:
                found.append(code)
    for m in _TEXT_PATTERN.finditer(folded):
        alias = m.group(1)
        before, after = folded[:m.start()], folded[m.end():]
        if alias in _FALSE_CONTEXT and _FALSE_CONTEXT[alias].search(before):
            continue
        if alias in _FALSE_AFTER and _FALSE_AFTER[alias].search(after):
            continue
        code = _TEXT_CODE[alias]
        if code not in found:
            found.append(code)
    for pattern, code in _ABBREVIATIONS:
        if code not in found and pattern.search(text):
            found.append(code)
    return found


def mentions(text, code):
    """True when the sentence names this country."""
    return code in find_in_text(text)


def name_of(code):
    return DISPLAY.get(code, code)
