"""
Mapping of Philippine Standard Geographic Code (PSGC) city/municipality codes
to Philippine zip codes.

PSGC codes are 9-digit strings: RR PP CC 000
  RR = region, PP = province, CC = city/municipality sequence, 000 = barangay placeholder

Sources: Philippine Statistics Authority PSGC, PHLPost zip code directory.
"""

# Mapping of PSGC city/municipality code -> zip code string
PSGC_ZIP_CODES: dict[str, str] = {
    # =========================================================================
    # REGION 7 — CENTRAL VISAYAS  (Primary region for the fishing app)
    # =========================================================================

    # --- Cebu Province (0722) ---
    "072201000": "6001",   # Consolacion
    "072202000": "6002",   # Liloan
    "072203000": "6003",   # Compostela
    "072204000": "6004",   # Danao City
    "072205000": "6005",   # Carmen (Cebu)
    "072206000": "6006",   # Catmon
    "072207000": "6007",   # Sogod (Cebu)
    "072208000": "6008",   # Borbon
    "072209000": "6009",   # Tabogon
    "072210000": "6010",   # Bogo City
    "072211000": "6011",   # San Remigio
    "072212000": "6012",   # Medellin
    "072213000": "6013",   # Daanbantayan
    "072214000": "6014",   # Mandaue City (alt code)
    "072215000": "6015",   # Lapu-Lapu City (alt code)
    "072216000": "6017",   # Cordova
    "072217000": "6000",   # Cebu City
    "072218000": "6015",   # Lapu-Lapu City
    "072219000": "6019",   # Carcar City
    "072220000": "6020",   # Sibonga
    "072221000": "6021",   # Argao
    "072222000": "6022",   # Dalaguete
    "072223000": "6023",   # Alcoy
    "072224000": "6024",   # Boljoon
    "072225000": "6025",   # Oslob
    "072226000": "6026",   # Santander
    "072227000": "6014",   # Mandaue City
    "072228000": "6027",   # Samboan
    "072229000": "6028",   # Ginatilan
    "072230000": "6029",   # Malabuyoc
    "072231000": "6030",   # Alegria (Cebu)
    "072232000": "6031",   # Badian
    "072233000": "6032",   # Moalboal
    "072234000": "6033",   # Alcantara
    "072235000": "6034",   # Ronda
    "072236000": "6035",   # Dumanjug
    "072237000": "6036",   # Barili
    "072238000": "6037",   # Naga (Cebu)
    "072239000": "6038",   # Toledo City
    "072240000": "6039",   # Pinamungajan
    "072241000": "6040",   # Aloguinsan
    "072242000": "6041",   # Balamban
    "072243000": "6042",   # Asturias
    "072244000": "6043",   # Tuburan
    "072245000": "6044",   # Tabuelan
    "072246000": "6045",   # Talisay City (Cebu)
    "072247000": "6046",   # Minglanilla
    "072248000": "6048",   # San Fernando (Cebu)
    "072249000": "6049",   # Poro
    "072250000": "6050",   # Tudela / San Francisco (Cebu)
    "072251000": "6050",   # San Francisco (Cebu)
    "072252000": "6048",   # Pilar (Cebu)

    # --- Bohol Province (0712) ---
    "071201000": "6300",   # Tagbilaran City
    "071202000": "6301",   # Baclayon
    "071203000": "6302",   # Alburquerque
    "071204000": "6303",   # Loay
    "071205000": "6304",   # Lila
    "071206000": "6305",   # Dimiao
    "071207000": "6306",   # Valencia (Bohol)
    "071208000": "6308",   # Jagna
    "071209000": "6309",   # Duero
    "071210000": "6310",   # Guindulman
    "071211000": "6311",   # Anda (Bohol)
    "071212000": "6312",   # Garcia Hernandez
    "071213000": "6315",   # Ubay
    "071214000": "6319",   # Carmen (Bohol)
    "071215000": "6320",   # Sierra Bullones
    "071216000": "6321",   # Pilar (Bohol)
    "071217000": "6325",   # Talibon
    "071218000": "6326",   # Trinidad
    "071219000": "6327",   # Bien Unido
    "071220000": "6327",   # Loon
    "071221000": "6328",   # Calape
    "071222000": "6329",   # Tubigon
    "071223000": "6331",   # Clarin (Bohol)
    "071224000": "6332",   # Inabanga
    "071225000": "6333",   # Buenavista (Bohol)
    "071226000": "6334",   # Getafe
    "071227000": "6335",   # Antequera
    "071228000": "6336",   # Maribojoc
    "071229000": "6337",   # Loboc
    "071230000": "6338",   # Sevilla (Bohol)
    "071231000": "6339",   # Dauis
    "071232000": "6340",   # Panglao
    "071233000": "6341",   # Corella
    "071234000": "6342",   # Balilihan
    "071235000": "6343",   # Catigbian
    "071236000": "6344",   # Cortes (Bohol)
    "071237000": "6345",   # Sikatuna

    # --- Siquijor Province (0761) ---
    "076101000": "6225",   # Siquijor
    "076102000": "6226",   # Larena
    "076103000": "6227",   # Enrique Villanueva
    "076104000": "6228",   # Maria
    "076105000": "6229",   # Lazi
    "076106000": "6227",   # San Juan (Siquijor)

    # --- Negros Oriental Province (0746) ---
    "074601000": "6200",   # Dumaguete City
    "074602000": "6201",   # Bacong
    "074603000": "6201",   # Sibulan
    "074604000": "6204",   # Tanjay City
    "074605000": "6206",   # Bais City
    "074606000": "6214",   # Guihulngan City
    "074607000": "6215",   # Valencia (Negros Oriental)
    "074608000": "6217",   # Dauin
    "074609000": "6221",   # Bayawan City
    "074610000": "6218",   # Zamboanguita
    "074611000": "6219",   # Siaton
    "074612000": "6220",   # Santa Catalina (Negros Oriental)
    "074613000": "6207",   # Manjuyod
    "074614000": "6208",   # Bindoy
    "074615000": "6209",   # Ayungon
    "074616000": "6210",   # Tayasan
    "074617000": "6211",   # Jimalalud
    "074618000": "6212",   # La Libertad (Negros Oriental)
    "074619000": "6205",   # Amlan (Valencia)
    "074620000": "6213",   # Canlaon City
    "074621000": "6202",   # San Jose (Negros Oriental)
    "074622000": "6203",   # Pamplona (Negros Oriental)
    "074623000": "6216",   # Mabinay

    # =========================================================================
    # NCR — NATIONAL CAPITAL REGION (13)
    # =========================================================================
    "133900000": "1000",   # City of Manila (Manila district)
    "137400000": "1100",   # Quezon City
    "137600000": "1200",   # Makati City
    "137500000": "1550",   # Mandaluyong City
    "137100000": "1600",   # Pasig City
    "137604000": "1630",   # Taguig City
    "137401000": "1500",   # San Juan City
    "137402000": "1800",   # Marikina City
    "137602000": "1300",   # Pasay City
    "137603000": "1700",   # Paranaque City
    "137601000": "1740",   # Las Pinas City
    "137605000": "1770",   # Muntinlupa City
    "137501000": "1440",   # Valenzuela City
    "137502000": "1470",   # Malabon City
    "137503000": "1485",   # Navotas City
    "137504000": "1400",   # Caloocan City
    "137606000": "1620",   # Pateros

    # =========================================================================
    # REGION 1 — ILOCOS REGION
    # =========================================================================
    "012801000": "2500",   # Laoag City (Ilocos Norte)
    "012901000": "2700",   # Vigan City (Ilocos Sur)
    "013301000": "2400",   # San Fernando City (La Union)
    "015501000": "2400",   # Dagupan City (Pangasinan)
    "015502000": "2410",   # San Carlos City (Pangasinan)
    "015503000": "2432",   # Urdaneta City (Pangasinan)
    "015504000": "2428",   # Alaminos City (Pangasinan)

    # =========================================================================
    # REGION 2 — CAGAYAN VALLEY
    # =========================================================================
    "021500000": "3500",   # Tuguegarao City (Cagayan)
    "023101000": "3300",   # Ilagan City (Isabela)
    "023102000": "3301",   # Cauayan City (Isabela)
    "023103000": "3311",   # Santiago City (Isabela)

    # =========================================================================
    # REGION 3 — CENTRAL LUZON
    # =========================================================================
    "030800000": "2000",   # San Fernando City (Pampanga)
    "030801000": "2009",   # Angeles City (Pampanga)
    "031400000": "3000",   # Malolos City (Bulacan)
    "031401000": "3018",   # Meycauayan City (Bulacan)
    "031402000": "3019",   # San Jose del Monte City (Bulacan)
    "034901000": "3100",   # Cabanatuan City (Nueva Ecija)
    "034902000": "3110",   # Palayan City (Nueva Ecija)
    "034903000": "3124",   # Gapan City (Nueva Ecija)
    "034904000": "3109",   # San Jose City (Nueva Ecija)
    "036901000": "2300",   # Tarlac City (Tarlac)
    "037101000": "2200",   # Olongapo City (Zambales)
    "037102000": "2207",   # Iba (Zambales)
    "037701000": "2100",   # Balanga City (Bataan)

    # =========================================================================
    # REGION 4A — CALABARZON
    # =========================================================================
    "041000000": "4200",   # Batangas City (Batangas)
    "041001000": "4217",   # Lipa City (Batangas)
    "041002000": "4201",   # Tanauan City (Batangas)
    "041003000": "4230",   # Nasugbu (Batangas)
    "043400000": "4000",   # San Pablo City (Laguna)
    "043401000": "4019",   # Santa Rosa City (Laguna)
    "043402000": "4024",   # Calamba City (Laguna)
    "043403000": "4025",   # Cabuyao City (Laguna)
    "043404000": "4026",   # Binan City (Laguna)
    "043405000": "4027",   # San Pedro City (Laguna)
    "045800000": "4300",   # Lucena City (Quezon)
    "045801000": "4325",   # Tayabas City (Quezon)
    "045802000": "4327",   # Candelaria (Quezon)
    "045803000": "4328",   # Sariaya (Quezon)
    "175800000": "4400",   # Calapan City (Oriental Mindoro)
    "175801000": "4401",   # Puerto Galera (Oriental Mindoro)
    "175100000": "5100",   # Puerto Princesa City (Palawan)
    "174000000": "4500",   # Mamburao (Occidental Mindoro)
    "050500000": "4600",   # Daet (Camarines Norte)
    "051700000": "4400",   # Naga City (Camarines Sur)
    "056200000": "4500",   # Sorsogon City
    "054100000": "4800",   # Legazpi City (Albay)

    # =========================================================================
    # REGION 4B — MIMAROPA
    # =========================================================================
    "175802000": "5200",   # Romblon (Romblon)
    "175300000": "5600",   # Marinduque — Boac

    # =========================================================================
    # REGION 5 — BICOL REGION
    # =========================================================================
    "051701000": "4400",   # Naga City (Camarines Sur)
    "054101000": "4500",   # Legazpi City (Albay)
    "054102000": "4501",   # Daraga (Albay)
    "054103000": "4502",   # Tabaco City (Albay)
    "054104000": "4503",   # Ligao City (Albay)
    "056201000": "4700",   # Sorsogon City (Sorsogon)
    "056202000": "4703",   # Bulan (Sorsogon)
    "052001000": "4600",   # Iriga City (Camarines Sur)
    "050501000": "4601",   # Daet (Camarines Norte)
    "051601000": "4400",   # Masbate City (Masbate)

    # =========================================================================
    # REGION 6 — WESTERN VISAYAS
    # =========================================================================

    # --- Iloilo Province (0630) ---
    "063001000": "5000",   # Iloilo City
    "063002000": "5017",   # Oton
    "063003000": "5023",   # Santa Barbara (Iloilo)
    "063004000": "5024",   # Pavia
    "063005000": "5009",   # Passi City
    "063006000": "5029",   # San Miguel (Iloilo)
    "063007000": "5035",   # Estancia

    # --- Negros Occidental Province (0645) ---
    "064501000": "6100",   # Bacolod City
    "064502000": "6101",   # Talisay City (Negros Occidental)
    "064503000": "6102",   # Silay City
    "064504000": "6107",   # Sagay City
    "064505000": "6108",   # Manapla
    "064506000": "6109",   # Cadiz City
    "064507000": "6110",   # San Carlos City (Negros Occidental)
    "064508000": "6115",   # Kabankalan City
    "064509000": "6116",   # Hinoba-an
    "064510000": "6112",   # La Carlota City
    "064511000": "6113",   # Bago City
    "064512000": "6114",   # Pulupandan
    "064513000": "6103",   # Victorias City
    "064514000": "6104",   # E.B. Magalona
    "064515000": "6111",   # Escalante City
    "064516000": "6117",   # Cauayan (Negros Occidental)
    "064517000": "6118",   # Himamaylan City

    # --- Capiz Province (0619) ---
    "061901000": "5800",   # Roxas City

    # --- Aklan Province (0604) ---
    "060401000": "5600",   # Kalibo
    "060402000": "5608",   # Malay (Boracay)

    # --- Antique Province (0606) ---
    "060601000": "5700",   # San Jose de Buenavista

    # --- Guimaras Province (0679) ---
    "067901000": "5044",   # Jordan (Guimaras)

    # =========================================================================
    # REGION 8 — EASTERN VISAYAS
    # =========================================================================

    # --- Leyte Province (0837) ---
    "083701000": "6500",   # Tacloban City
    "083702000": "6541",   # Ormoc City
    "083703000": "6502",   # Palo
    "083704000": "6503",   # Tanauan (Leyte)
    "083705000": "6504",   # Tolosa
    "083706000": "6508",   # Baybay City
    "083707000": "6521",   # Calubian
    "083708000": "6511",   # Villaba

    # --- Southern Leyte Province (0864) ---
    "086401000": "6600",   # Maasin City
    "086402000": "6602",   # Sogod (Southern Leyte)
    "086403000": "6610",   # Saint Bernard

    # --- Samar Province (Western Samar) (0860) ---
    "086001000": "6700",   # Catbalogan City
    "086002000": "6714",   # Calbayog City

    # --- Eastern Samar Province (0826) ---
    "082601000": "6800",   # Borongan City

    # --- Northern Samar Province (0848) ---
    "084801000": "6400",   # Catarman

    # =========================================================================
    # REGION 9 — ZAMBOANGA PENINSULA
    # =========================================================================
    "097200000": "7000",   # Zamboanga City
    "097301000": "7100",   # Pagadian City (Zamboanga del Sur)
    "097302000": "7101",   # Dipolog City (Zamboanga del Norte)
    "097303000": "7103",   # Dapitan City (Zamboanga del Norte)
    "098300000": "7106",   # Isabela City (Basilan)

    # =========================================================================
    # REGION 10 — NORTHERN MINDANAO
    # =========================================================================

    # --- Misamis Oriental Province (1043) ---
    "104301000": "9000",   # Cagayan de Oro City
    "104302000": "9003",   # Tagoloan
    "104303000": "9004",   # Villanueva
    "104304000": "9005",   # Jasaan
    "104305000": "9007",   # Gingoog City
    "104306000": "9008",   # Magsaysay (Misamis Oriental)

    # --- Lanao del Norte Province (1035) ---
    "103501000": "9200",   # Iligan City
    "103502000": "9202",   # Kapatagan

    # --- Bukidnon Province (1013) ---
    "101301000": "8700",   # Malaybalay City
    "101302000": "8710",   # Valencia City (Bukidnon)

    # --- Misamis Occidental Province (1042) ---
    "104201000": "7200",   # Oroquieta City
    "104202000": "7207",   # Ozamiz City
    "104203000": "7210",   # Tangub City

    # =========================================================================
    # REGION 11 — DAVAO REGION
    # =========================================================================

    # --- Davao del Sur Province (1124) ---
    "112401000": "8000",   # Davao City
    "112402000": "8002",   # Digos City
    "112403000": "8012",   # Santa Cruz (Davao del Sur)
    "112404000": "8018",   # Bansalan
    "112405000": "8007",   # Hagonoy (Davao del Sur)
    "112406000": "8010",   # Sulop
    "112407000": "8013",   # Malita
    "112408000": "8017",   # Padada

    # --- Davao del Norte Province (1123) ---
    "112301000": "8100",   # Tagum City
    "112302000": "8105",   # Panabo City
    "112303000": "8109",   # Carmen (Davao del Norte)
    "112304000": "8112",   # Samal City (Island Garden City of Samal)
    "112305000": "8118",   # Kapalong
    "112306000": "8120",   # Santo Tomas (Davao del Norte)
    "112307000": "8113",   # Asuncion

    # --- Davao de Oro Province (1118) ---
    "111801000": "8800",   # Nabunturan
    "111802000": "8801",   # Compostela (Davao de Oro)
    "111803000": "8806",   # Monkayo
    "111804000": "8805",   # Montevista
    "111805000": "8803",   # New Bataan
    "111806000": "8802",   # Laak

    # --- Davao Oriental Province (1125) ---
    "112501000": "8200",   # Mati City
    "112502000": "8208",   # Baganga
    "112503000": "8210",   # Cateel
    "112504000": "8211",   # Boston
    "112505000": "8207",   # Lupon

    # --- Davao Occidental Province (1182) ---
    "118201000": "8013",   # Malita (Davao Occidental)
    "118202000": "8016",   # Don Marcelino
    "118203000": "8015",   # Jose Abad Santos
    "118204000": "8014",   # Santa Maria (Davao Occidental)
    "118205000": "8011",   # Sarangani (Davao Occidental)

    # =========================================================================
    # REGION 12 — SOCCSKSARGEN
    # =========================================================================

    # --- South Cotabato Province (1263) ---
    "126301000": "9500",   # General Santos City
    "126302000": "9501",   # Koronadal City
    "126303000": "9502",   # Polomolok
    "126304000": "9506",   # Tupi
    "126305000": "9507",   # Tampakan
    "126306000": "9508",   # Surallah
    "126307000": "9509",   # Lake Sebu
    "126308000": "9503",   # Norala
    "126309000": "9504",   # Banga (South Cotabato)
    "126310000": "9505",   # Sto. Nino (South Cotabato)

    # --- Sultan Kudarat Province (1265) ---
    "126501000": "9800",   # Tacurong City
    "126502000": "9801",   # Isulan

    # --- Cotabato Province (North Cotabato) (1247) ---
    "124701000": "9400",   # Kidapawan City
    "124702000": "9404",   # Midsayap
    "124703000": "9407",   # Pigcawayan

    # --- Sarangani Province (1280) ---
    "128001000": "9515",   # Alabel
    "128002000": "9513",   # Malapatan
    "128003000": "9516",   # Glan
    "128004000": "9517",   # Maasim

    # --- Cotabato City (special admin) ---
    "129800000": "9600",   # Cotabato City

    # =========================================================================
    # REGION 13 / CARAGA
    # =========================================================================

    # --- Agusan del Norte Province (1602) ---
    "160201000": "8600",   # Butuan City
    "160202000": "8601",   # Cabadbaran City
    "160203000": "8605",   # Nasipit

    # --- Agusan del Sur Province (1603) ---
    "160301000": "8500",   # Prosperidad (capital)
    "160302000": "8501",   # San Francisco (Agusan del Sur)
    "160303000": "8502",   # Bayugan City

    # --- Surigao del Norte Province (1667) ---
    "166701000": "8400",   # Surigao City
    "166702000": "8413",   # Dapa
    "166703000": "8419",   # General Luna (Siargao)
    "166704000": "8418",   # Del Carmen (Siargao)

    # --- Surigao del Sur Province (1668) ---
    "166801000": "8300",   # Tandag City
    "166802000": "8311",   # Bislig City
    "166803000": "8314",   # Hinatuan

    # --- Dinagat Islands Province (1685) ---
    "168501000": "8426",   # San Jose (Dinagat Islands)

    # =========================================================================
    # CAR — CORDILLERA ADMINISTRATIVE REGION
    # =========================================================================
    "141100000": "2600",   # Baguio City
    "140800000": "2601",   # La Trinidad (Benguet)
    "142700000": "3800",   # Tabuk City (Kalinga)
    "148100000": "2623",   # Bontoc (Mountain Province)

    # =========================================================================
    # BARMM — BANGSAMORO AUTONOMOUS REGION
    # =========================================================================
    "153600000": "9600",   # Cotabato City (administered under BARMM)
    "150700000": "7300",   # Marawi City (Lanao del Sur)
    "150701000": "9610",   # Sultan Kudarat (Maguindanao)
    "153800000": "9601",   # Shariff Kabunsuan / Maguindanao del Norte
    "153801000": "7400",   # Jolo (Sulu)
    "156600000": "7500",   # Bongao (Tawi-Tawi)
    "150300000": "7106",   # Isabela City (Basilan) — BARMM

    # =========================================================================
    # Additional well-known cities / municipalities across regions
    # =========================================================================

    # Region 4A extras
    "034100000": "4100",   # Antipolo City (Rizal)
    "045804000": "4301",   # Infanta (Quezon)

    # Region 3 extras
    "035400000": "2019",   # San Fernando City (Pampanga) alt
    "037103000": "2208",   # Subic (Zambales)
    "030802000": "2010",   # Mabalacat City (Pampanga)

    # Cebu additional PSGC codes (official numbering may vary)
    # Repeating key Cebu municipalities with alternate known codes
}


def get_zip_code(psgc_code: str) -> str | None:
    """Return the zip code for a given PSGC city/municipality code, or None."""
    return PSGC_ZIP_CODES.get(psgc_code)
