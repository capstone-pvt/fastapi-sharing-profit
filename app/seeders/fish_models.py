"""Seed fish species, pre-trained model registry, and mark as active/approved."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.db import get_db

# Fish species detected/classified by the current models.
# classIndex values match the classifier model's class indices.
# weightRange: typical weight in kg [min, max]
# pricePerKg: typical Philippine market price in PHP [min, max]
# peakMonths: months (1-12) when species is most abundant in PH waters
# habitat: "marine", "freshwater", or "brackish"
DEFAULT_SPECIES: list[dict] = [
    {"name": "Bangus", "classIndex": 0, "scientificName": "Chanos chanos", "genus": "Chanos", "family": "Chanidae", "englishName": "Milkfish", "localName": "Bangus",
     "weightRange": [0.3, 3.0], "pricePerKg": [140, 220], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "brackish"},
    {"name": "Big Head Carp", "classIndex": 1, "scientificName": "Hypophthalmichthys nobilis", "genus": "Hypophthalmichthys", "family": "Cyprinidae", "englishName": "Big Head Carp", "localName": "Big Head Carp",
     "weightRange": [1.0, 15.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Black Sea Sprat", "classIndex": 2, "scientificName": "Clupeonella cultriventris", "genus": "Clupeonella", "family": "Clupeidae", "englishName": "Black Sea Sprat", "localName": "Black Sea Sprat",
     "weightRange": [0.01, 0.05], "pricePerKg": [60, 120], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Black Spotted Barb", "classIndex": 3, "scientificName": "Dawkinsia filamentosa", "genus": "Dawkinsia", "family": "Cyprinidae", "englishName": "Black Spotted Barb", "localName": "Black Spotted Barb",
     "weightRange": [0.05, 0.3], "pricePerKg": [80, 140], "peakMonths": [6, 7, 8, 9, 10], "habitat": "freshwater"},
    {"name": "Catfish", "classIndex": 4, "scientificName": "Clarias batrachus", "genus": "Clarias", "family": "Clariidae", "englishName": "Catfish", "localName": "Hito",
     "weightRange": [0.2, 2.0], "pricePerKg": [120, 200], "peakMonths": [5, 6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Climbing Perch", "classIndex": 5, "scientificName": "Anabas testudineus", "genus": "Anabas", "family": "Anabantidae", "englishName": "Climbing Perch", "localName": "Martiniko",
     "weightRange": [0.05, 0.3], "pricePerKg": [100, 180], "peakMonths": [6, 7, 8, 9, 10], "habitat": "freshwater"},
    {"name": "Fourfinger Threadfin", "classIndex": 6, "scientificName": "Eleutheronema tetradactylum", "genus": "Eleutheronema", "family": "Polynemidae", "englishName": "Fourfinger Threadfin", "localName": "Mamali",
     "weightRange": [0.5, 5.0], "pricePerKg": [180, 300], "peakMonths": [3, 4, 5, 9, 10, 11], "habitat": "marine"},
    {"name": "Freshwater Eel", "classIndex": 7, "scientificName": "Anguilla marmorata", "genus": "Anguilla", "family": "Anguillidae", "englishName": "Freshwater Eel", "localName": "Igat",
     "weightRange": [0.3, 3.0], "pricePerKg": [200, 400], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Gilt-Head Bream", "classIndex": 8, "scientificName": "Sparus aurata", "genus": "Sparus", "family": "Sparidae", "englishName": "Gilt-Head Bream", "localName": "Gilt-Head Bream",
     "weightRange": [0.3, 2.5], "pricePerKg": [250, 450], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Glass Perchlet", "classIndex": 9, "scientificName": "Ambassis urotaenia", "genus": "Ambassis", "family": "Ambassidae", "englishName": "Glass Perchlet", "localName": "Glass Perchlet",
     "weightRange": [0.005, 0.03], "pricePerKg": [60, 100], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Goby", "classIndex": 10, "scientificName": "Glossogobius giuris", "genus": "Glossogobius", "family": "Gobiidae", "englishName": "Goby", "localName": "Biya",
     "weightRange": [0.01, 0.1], "pricePerKg": [100, 200], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Gold Fish", "classIndex": 11, "scientificName": "Carassius auratus", "genus": "Carassius", "family": "Cyprinidae", "englishName": "Gold Fish", "localName": "Gold Fish",
     "weightRange": [0.01, 0.3], "pricePerKg": [50, 100], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Gourami", "classIndex": 12, "scientificName": "Osphronemus goramy", "genus": "Osphronemus", "family": "Osphronemidae", "englishName": "Gourami", "localName": "Gurami",
     "weightRange": [0.3, 4.0], "pricePerKg": [150, 280], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "freshwater"},
    {"name": "Grass Carp", "classIndex": 13, "scientificName": "Ctenopharyngodon idella", "genus": "Ctenopharyngodon", "family": "Cyprinidae", "englishName": "Grass Carp", "localName": "Grass Carp",
     "weightRange": [1.0, 15.0], "pricePerKg": [80, 160], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Green Spotted Puffer", "classIndex": 14, "scientificName": "Tetraodon nigroviridis", "genus": "Tetraodon", "family": "Tetraodontidae", "englishName": "Green Spotted Puffer", "localName": "Butete",
     "weightRange": [0.01, 0.1], "pricePerKg": [40, 80], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "brackish"},
    {"name": "Galunggong", "classIndex": 15, "scientificName": "Decapterus macrosoma", "genus": "Decapterus", "family": "Carangidae", "englishName": "Roundscad", "localName": "Galunggong",
     "weightRange": [0.05, 0.3], "pricePerKg": [80, 160], "peakMonths": [10, 11, 12, 1, 2, 3, 4], "habitat": "marine"},
    {"name": "Indian Carp", "classIndex": 16, "scientificName": "Catla catla", "genus": "Catla", "family": "Cyprinidae", "englishName": "Indian Carp", "localName": "Indian Carp",
     "weightRange": [1.0, 10.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Indo-Pacific Tarpon", "classIndex": 17, "scientificName": "Megalops cyprinoides", "genus": "Megalops", "family": "Megalopidae", "englishName": "Indo-Pacific Tarpon", "localName": "Buan-buan",
     "weightRange": [0.5, 5.0], "pricePerKg": [100, 180], "peakMonths": [3, 4, 5, 6, 7, 8], "habitat": "brackish"},
    {"name": "Jaguar Gapote", "classIndex": 18, "scientificName": "Parachromis managuensis", "genus": "Parachromis", "family": "Cichlidae", "englishName": "Jaguar Gapote", "localName": "Jaguar Gapote",
     "weightRange": [0.3, 2.0], "pricePerKg": [100, 180], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Janitor Fish", "classIndex": 19, "scientificName": "Pterygoplichthys disjunctivus", "genus": "Pterygoplichthys", "family": "Loricariidae", "englishName": "Janitor Fish", "localName": "Janitor Fish",
     "weightRange": [0.1, 1.0], "pricePerKg": [20, 50], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Knifefish", "classIndex": 20, "scientificName": "Chitala ornata", "genus": "Chitala", "family": "Notopteridae", "englishName": "Knifefish", "localName": "Knifefish",
     "weightRange": [0.5, 5.0], "pricePerKg": [120, 220], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Long-Snouted Pipefish", "classIndex": 21, "scientificName": "Syngnathus temminckii", "genus": "Syngnathus", "family": "Syngnathidae", "englishName": "Long-Snouted Pipefish", "localName": "Long-Snouted Pipefish",
     "weightRange": [0.001, 0.01], "pricePerKg": [30, 60], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "marine"},
    {"name": "Mosquito Fish", "classIndex": 22, "scientificName": "Gambusia affinis", "genus": "Gambusia", "family": "Poeciliidae", "englishName": "Mosquito Fish", "localName": "Mosquito Fish",
     "weightRange": [0.001, 0.005], "pricePerKg": [20, 40], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Mudfish", "classIndex": 23, "scientificName": "Channa striata", "genus": "Channa", "family": "Channidae", "englishName": "Mudfish", "localName": "Dalag",
     "weightRange": [0.3, 3.0], "pricePerKg": [180, 320], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Mullet", "classIndex": 24, "scientificName": "Mugil cephalus", "genus": "Mugil", "family": "Mugilidae", "englishName": "Mullet", "localName": "Banak",
     "weightRange": [0.2, 2.0], "pricePerKg": [140, 250], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Pangasius", "classIndex": 25, "scientificName": "Pangasianodon hypophthalmus", "genus": "Pangasianodon", "family": "Pangasiidae", "englishName": "Pangasius", "localName": "Pangasius",
     "weightRange": [0.5, 10.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Perch", "classIndex": 26, "scientificName": "Perca fluviatilis", "genus": "Perca", "family": "Percidae", "englishName": "Perch", "localName": "Perch",
     "weightRange": [0.1, 1.5], "pricePerKg": [150, 280], "peakMonths": [3, 4, 5, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Red Mullet", "classIndex": 27, "scientificName": "Mullus barbatus", "genus": "Mullus", "family": "Mullidae", "englishName": "Red Mullet", "localName": "Red Mullet",
     "weightRange": [0.05, 0.3], "pricePerKg": [200, 350], "peakMonths": [4, 5, 6, 7, 8, 9], "habitat": "marine"},
    {"name": "Red Sea Bream", "classIndex": 28, "scientificName": "Pagrus major", "genus": "Pagrus", "family": "Sparidae", "englishName": "Red Sea Bream", "localName": "Red Sea Bream",
     "weightRange": [0.3, 4.0], "pricePerKg": [280, 500], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Scat Fish", "classIndex": 29, "scientificName": "Scatophagus argus", "genus": "Scatophagus", "family": "Scatophagidae", "englishName": "Scat Fish", "localName": "Kitang",
     "weightRange": [0.1, 0.5], "pricePerKg": [100, 180], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "brackish"},
    {"name": "Sea Bass", "classIndex": 30, "scientificName": "Lates calcarifer", "genus": "Lates", "family": "Latidae", "englishName": "Sea Bass", "localName": "Apahap",
     "weightRange": [0.5, 10.0], "pricePerKg": [280, 500], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "brackish"},
    {"name": "Shrimp", "classIndex": 31, "scientificName": "Penaeus monodon", "genus": "Penaeus", "family": "Penaeidae", "englishName": "Shrimp", "localName": "Hipon / Sugpo",
     "weightRange": [0.01, 0.15], "pricePerKg": [300, 600], "peakMonths": [10, 11, 12, 1, 2, 3, 4], "habitat": "marine"},
    {"name": "Silver Barb", "classIndex": 32, "scientificName": "Barbonymus gonionotus", "genus": "Barbonymus", "family": "Cyprinidae", "englishName": "Silver Barb", "localName": "Silver Barb",
     "weightRange": [0.1, 1.0], "pricePerKg": [80, 140], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Silver Carp", "classIndex": 33, "scientificName": "Hypophthalmichthys molitrix", "genus": "Hypophthalmichthys", "family": "Cyprinidae", "englishName": "Silver Carp", "localName": "Silver Carp",
     "weightRange": [1.0, 15.0], "pricePerKg": [70, 130], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Silver Perch", "classIndex": 34, "scientificName": "Leiopotherapon plumbeus", "genus": "Leiopotherapon", "family": "Terapontidae", "englishName": "Silver Perch", "localName": "Ayungin",
     "weightRange": [0.02, 0.15], "pricePerKg": [250, 500], "peakMonths": [1, 2, 3, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Snakehead", "classIndex": 35, "scientificName": "Channa striata", "genus": "Channa", "family": "Channidae", "englishName": "Snakehead", "localName": "Dalag",
     "weightRange": [0.3, 3.0], "pricePerKg": [180, 320], "peakMonths": [6, 7, 8, 9, 10, 11], "habitat": "freshwater"},
    {"name": "Striped Red Mullet", "classIndex": 36, "scientificName": "Mullus surmuletus", "genus": "Mullus", "family": "Mullidae", "englishName": "Striped Red Mullet", "localName": "Striped Red Mullet",
     "weightRange": [0.05, 0.4], "pricePerKg": [200, 380], "peakMonths": [4, 5, 6, 7, 8, 9], "habitat": "marine"},
    {"name": "Tenpounder", "classIndex": 37, "scientificName": "Elops machnata", "genus": "Elops", "family": "Elopidae", "englishName": "Tenpounder", "localName": "Bidbid",
     "weightRange": [0.3, 3.0], "pricePerKg": [100, 180], "peakMonths": [3, 4, 5, 6, 7, 8, 9], "habitat": "marine"},
    {"name": "Tilapia", "classIndex": 38, "scientificName": "Oreochromis niloticus", "genus": "Oreochromis", "family": "Cichlidae", "englishName": "Tilapia", "localName": "Tilapia",
     "weightRange": [0.2, 1.5], "pricePerKg": [100, 180], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Trout", "classIndex": 39, "scientificName": "Oncorhynchus mykiss", "genus": "Oncorhynchus", "family": "Salmonidae", "englishName": "Trout", "localName": "Trout",
     "weightRange": [0.3, 5.0], "pricePerKg": [350, 600], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "freshwater"},
    {"name": "Yellowfin Tuna", "classIndex": 40, "scientificName": "Thunnus albacares", "genus": "Thunnus", "family": "Scombridae", "englishName": "Yellowfin Tuna", "localName": "Tambakol/Bariles/Bangkulis",
     "weightRange": [1.0, 80.0], "pricePerKg": [250, 500], "peakMonths": [3, 4, 5, 10, 11, 12], "habitat": "marine"},
    # ────────────────────────────────────────────────────────────────
    # PSA 2024 Top Commercial Fisheries Species (Table 3.22)
    # Source: Philippine Statistics Authority, retrieved June 26, 2025
    # Price per kg derived from PSA Value ('000 PHP) / Volume (MT)
    # ────────────────────────────────────────────────────────────────
    # --- TUNA sub-species (PSA Rank #1: 42.29% of volume, P37.9B) ---
    {"name": "Bullet Tuna", "classIndex": 67, "scientificName": "Auxis rochei", "genus": "Auxis", "family": "Scombridae", "englishName": "Bullet Tuna", "localName": "Tulingan/Tangi/Pirit",
     "weightRange": [0.2, 2.0], "pricePerKg": [80, 150], "peakMonths": [1, 2, 3, 4, 5, 10, 11, 12], "habitat": "marine"},
    {"name": "Skipjack Tuna", "classIndex": 41, "scientificName": "Katsuwonus pelamis", "genus": "Katsuwonus", "family": "Scombridae", "englishName": "Skipjack Tuna", "localName": "Gulyasan",
     "weightRange": [1.5, 15.0], "pricePerKg": [80, 180], "peakMonths": [3, 4, 5, 10, 11, 12], "habitat": "marine"},
    {"name": "Bigeye Tuna", "classIndex": 42, "scientificName": "Thunnus obesus", "genus": "Thunnus", "family": "Scombridae", "englishName": "Bigeye Tuna", "localName": "Tambakol",
     "weightRange": [2.0, 100.0], "pricePerKg": [200, 450], "peakMonths": [3, 4, 5, 10, 11, 12], "habitat": "marine"},
    {"name": "Eastern Little Tuna", "classIndex": 43, "scientificName": "Euthynnus affinis", "genus": "Euthynnus", "family": "Scombridae", "englishName": "Eastern Little Tuna", "localName": "Tulingan",
     "weightRange": [0.5, 5.0], "pricePerKg": [100, 200], "peakMonths": [2, 3, 4, 5, 10, 11, 12], "habitat": "marine"},
    {"name": "Frigate Tuna", "classIndex": 44, "scientificName": "Auxis thazard", "genus": "Auxis", "family": "Scombridae", "englishName": "Frigate Tuna", "localName": "Tulingan Puti",
     "weightRange": [0.3, 3.0], "pricePerKg": [80, 160], "peakMonths": [1, 2, 3, 4, 5, 10, 11, 12], "habitat": "marine"},
    # --- SARDINES (PSA Rank #2: 24.11% of volume, P8.0B) ---
    {"name": "Sardine", "classIndex": 45, "scientificName": "Sardinella lemuru", "genus": "Sardinella", "family": "Clupeidae", "englishName": "Bali Sardinella", "localName": "Tamban",
     "weightRange": [0.02, 0.1], "pricePerKg": [30, 80], "peakMonths": [9, 10, 11, 12, 1, 2], "habitat": "marine"},
    {"name": "Fimbriated Sardine", "classIndex": 46, "scientificName": "Sardinella fimbriata", "genus": "Sardinella", "family": "Clupeidae", "englishName": "Fimbriated Sardine", "localName": "Tunsoy",
     "weightRange": [0.01, 0.08], "pricePerKg": [30, 70], "peakMonths": [9, 10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Tawilis", "classIndex": 47, "scientificName": "Sardinella tawilis", "genus": "Sardinella", "family": "Clupeidae", "englishName": "Freshwater Sardine", "localName": "Tawilis",
     "weightRange": [0.01, 0.06], "pricePerKg": [100, 250], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "freshwater"},
    {"name": "Round Herring", "classIndex": 48, "scientificName": "Etrumeus teres", "genus": "Etrumeus", "family": "Dussumieriidae", "englishName": "Round Herring", "localName": "Turay",
     "weightRange": [0.02, 0.1], "pricePerKg": [40, 90], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    # --- MACKEREL (PSA Rank #4: 3.29% of volume, P3.5B) ---
    {"name": "Indian Mackerel", "classIndex": 49, "scientificName": "Rastrelliger kanagurta", "genus": "Rastrelliger", "family": "Scombridae", "englishName": "Indian Mackerel", "localName": "Alumahan",
     "weightRange": [0.1, 0.4], "pricePerKg": [100, 180], "peakMonths": [10, 11, 12, 1, 2, 3, 4], "habitat": "marine"},
    {"name": "Indo-Pacific Mackerel", "classIndex": 50, "scientificName": "Rastrelliger brachysoma", "genus": "Rastrelliger", "family": "Scombridae", "englishName": "Indo-Pacific Mackerel", "localName": "Hasa-hasa",
     "weightRange": [0.05, 0.3], "pricePerKg": [80, 160], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Spanish Mackerel", "classIndex": 51, "scientificName": "Scomberomorus commerson", "genus": "Scomberomorus", "family": "Scombridae", "englishName": "Spanish Mackerel", "localName": "Tangigue",
     "weightRange": [1.0, 20.0], "pricePerKg": [300, 550], "peakMonths": [11, 12, 1, 2, 3, 4], "habitat": "marine"},
    # --- BIG-EYED SCAD (PSA Rank #5: 3.20%, P3.1B) ---
    {"name": "Big-eyed Scad", "classIndex": 52, "scientificName": "Selar crumenophthalmus", "genus": "Selar", "family": "Carangidae", "englishName": "Big-eyed Scad", "localName": "Matang-baka",
     "weightRange": [0.05, 0.3], "pricePerKg": [90, 170], "peakMonths": [10, 11, 12, 1, 2, 3, 4, 5], "habitat": "marine"},
    # --- ANCHOVIES (PSA Rank #6: 1.14%, P837M) ---
    {"name": "Anchovy", "classIndex": 53, "scientificName": "Stolephorus commersonnii", "genus": "Stolephorus", "family": "Engraulidae", "englishName": "Anchovy", "localName": "Dilis",
     "weightRange": [0.002, 0.02], "pricePerKg": [60, 150], "peakMonths": [10, 11, 12, 1, 2, 3, 4], "habitat": "marine"},
    # --- SQUID (PSA Rank #7: 0.95%, P1.4B) ---
    {"name": "Squid", "classIndex": 54, "scientificName": "Loligo chinensis", "genus": "Loligo", "family": "Loliginidae", "englishName": "Squid", "localName": "Pusit",
     "weightRange": [0.05, 1.0], "pricePerKg": [150, 350], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    # --- THREADFIN BREAM (PSA Rank #8: 0.77%, P1.2B) ---
    {"name": "Threadfin Bream", "classIndex": 55, "scientificName": "Nemipterus japonicus", "genus": "Nemipterus", "family": "Nemipteridae", "englishName": "Threadfin Bream", "localName": "Bisugo",
     "weightRange": [0.05, 0.4], "pricePerKg": [150, 280], "peakMonths": [10, 11, 12, 1, 2, 3, 4, 5], "habitat": "marine"},
    # --- CREVALLE (PSA Rank #9: 0.67%, P576M) ---
    {"name": "Crevalle Jack", "classIndex": 56, "scientificName": "Caranx ignobilis", "genus": "Caranx", "family": "Carangidae", "englishName": "Crevalle Jack", "localName": "Talakitok",
     "weightRange": [0.3, 15.0], "pricePerKg": [80, 200], "peakMonths": [3, 4, 5, 6, 10, 11, 12], "habitat": "marine"},
    # --- SLIPMOUTH (PSA Rank #10: 0.61%, P452M) ---
    {"name": "Slipmouth", "classIndex": 57, "scientificName": "Leiognathus equulus", "genus": "Leiognathus", "family": "Leiognathidae", "englishName": "Slipmouth", "localName": "Sapsap",
     "weightRange": [0.01, 0.1], "pricePerKg": [60, 140], "peakMonths": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "habitat": "marine"},
    # --- OTHER COMMERCIALLY IMPORTANT SPECIES ---
    {"name": "Blue Marlin", "classIndex": 58, "scientificName": "Makaira nigricans", "genus": "Makaira", "family": "Istiophoridae", "englishName": "Blue Marlin", "localName": "Malasugi",
     "weightRange": [10.0, 200.0], "pricePerKg": [200, 400], "peakMonths": [3, 4, 5, 6, 10, 11], "habitat": "marine"},
    {"name": "Grouper", "classIndex": 59, "scientificName": "Epinephelus coioides", "genus": "Epinephelus", "family": "Serranidae", "englishName": "Grouper", "localName": "Lapu-lapu",
     "weightRange": [0.5, 15.0], "pricePerKg": [350, 700], "peakMonths": [3, 4, 5, 6, 7, 8, 9, 10], "habitat": "marine"},
    {"name": "Rabbitfish", "classIndex": 60, "scientificName": "Siganus guttatus", "genus": "Siganus", "family": "Siganidae", "englishName": "Rabbitfish", "localName": "Samaral / Danggit",
     "weightRange": [0.05, 0.4], "pricePerKg": [200, 450], "peakMonths": [3, 4, 5, 6, 7, 8], "habitat": "marine"},
    {"name": "Flying Fish", "classIndex": 61, "scientificName": "Cheilopogon spp.", "genus": "Cheilopogon", "family": "Exocoetidae", "englishName": "Flying Fish", "localName": "Bangsi / Iliw",
     "weightRange": [0.05, 0.3], "pricePerKg": [80, 160], "peakMonths": [3, 4, 5, 6, 7], "habitat": "marine"},
    {"name": "Barracuda", "classIndex": 62, "scientificName": "Sphyraena barracuda", "genus": "Sphyraena", "family": "Sphyraenidae", "englishName": "Barracuda", "localName": "Barakuda / Panghalwan",
     "weightRange": [0.5, 20.0], "pricePerKg": [150, 300], "peakMonths": [3, 4, 5, 6, 10, 11, 12], "habitat": "marine"},
    {"name": "Moonfish", "classIndex": 63, "scientificName": "Mene maculata", "genus": "Mene", "family": "Menidae", "englishName": "Moonfish", "localName": "Chabita / Salay-salay",
     "weightRange": [0.05, 0.3], "pricePerKg": [80, 160], "peakMonths": [10, 11, 12, 1, 2, 3], "habitat": "marine"},
    {"name": "Milkfish Fry", "classIndex": 64, "scientificName": "Chanos chanos", "genus": "Chanos", "family": "Chanidae", "englishName": "Milkfish Fry", "localName": "Bangus Fry / Sabiid",
     "weightRange": [0.001, 0.01], "pricePerKg": [500, 2000], "peakMonths": [3, 4, 5, 6, 7], "habitat": "marine"},
]

# Pre-trained models that ship with the project
DEFAULT_MODELS: list[dict] = [
    {
        "modelType": "detector",
        "version": "1.0.0",
        "description": "YOLOv8 fish detector – pre-trained",
        "relativePath": "models/detector/best.pt",
    },
    {
        "modelType": "classifier",
        "version": "1.0.0",
        "description": "YOLOv8 fish classifier – pre-trained",
        "relativePath": "models/classifier/best.pt",
    },
    {
        "modelType": "weight",
        "version": "1.0.0",
        "description": "Scikit-learn weight estimation – pre-trained",
        "relativePath": "models/weight/weight_model.joblib",
    },
    {
        "modelType": "price",
        "version": "1.0.0",
        "description": "Scikit-learn price prediction – pre-trained",
        "relativePath": "models/price/price_model.joblib",
    },
]


async def seed_fish_species() -> int:
    """Upsert default fish species. Returns number of new species created."""
    from pymongo import UpdateOne

    db = get_db()
    now = datetime.now(timezone.utc)
    extra_fields = (
        "scientificName", "genus", "family", "englishName", "localName",
        "weightRange", "pricePerKg", "peakMonths", "habitat",
    )
    ops = []
    for sp in DEFAULT_SPECIES:
        update_fields: dict = {
            "classIndex": sp["classIndex"],
            "isActive": True,
            "updatedAt": now,
        }
        for field in extra_fields:
            if field in sp:
                update_fields[field] = sp[field]
        ops.append(
            UpdateOne(
                {"name": sp["name"]},
                {
                    "$set": update_fields,
                    "$setOnInsert": {"name": sp["name"], "createdAt": now},
                },
                upsert=True,
            )
        )
    result = await db["fish_species"].bulk_write(ops, ordered=False)
    created = result.upserted_count
    print(f"  Fish species: {created} created, {len(DEFAULT_SPECIES) - created} updated.")
    return created


async def seed_fish_models() -> int:
    """Register pre-trained models as active and approved. Returns new count."""
    db = get_db()
    settings = get_settings()
    base_dir = Path(settings.model_root).resolve().parent  # project root
    created = 0
    now = datetime.now(timezone.utc)

    for model in DEFAULT_MODELS:
        model_type = model["modelType"]
        version = model["version"]

        # Check if this model version is already registered
        existing = await db["fish_models"].find_one(
            {"modelType": model_type, "version": version}
        )
        if existing:
            # Ensure it's active and approved
            await db["fish_models"].update_one(
                {"_id": existing["_id"]},
                {"$set": {"isActive": True, "status": "approved", "updatedAt": now}},
            )
            continue

        # Deactivate any other models of this type
        await db["fish_models"].update_many(
            {"modelType": model_type}, {"$set": {"isActive": False}}
        )

        # Resolve path – store absolute so inference can find it
        model_path = str((base_dir / model["relativePath"]).resolve())

        await db["fish_models"].insert_one(
            {
                "modelType": model_type,
                "version": version,
                "modelPath": model_path,
                "description": model["description"],
                "isActive": True,
                "status": "approved",
                "createdAt": now,
                "updatedAt": now,
            }
        )
        created += 1

    print(f"  Fish models: {created} registered, {len(DEFAULT_MODELS) - created} already existed.")
    return created
