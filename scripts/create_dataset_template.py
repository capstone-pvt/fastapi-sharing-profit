"""Create a dataset template with all 41 species, each labeled with full taxonomy."""

import os
import shutil

from PIL import Image, ImageDraw

SPECIES_DATA = [
    {"name": "Bangus", "family": "Chanidae", "genus": "Chanos", "scientific": "Chanos chanos", "color": (70, 130, 180)},
    {"name": "Big Head Carp", "family": "Cyprinidae", "genus": "Hypophthalmichthys", "scientific": "H. nobilis", "color": (100, 149, 237)},
    {"name": "Black Sea Sprat", "family": "Clupeidae", "genus": "Clupeonella", "scientific": "C. cultriventris", "color": (47, 79, 79)},
    {"name": "Black Spotted Barb", "family": "Cyprinidae", "genus": "Dawkinsia", "scientific": "D. filamentosa", "color": (85, 107, 47)},
    {"name": "Catfish", "family": "Clariidae", "genus": "Clarias", "scientific": "Clarias batrachus", "color": (105, 105, 105)},
    {"name": "Climbing Perch", "family": "Anabantidae", "genus": "Anabas", "scientific": "A. testudineus", "color": (139, 119, 101)},
    {"name": "Fourfinger Threadfin", "family": "Polynemidae", "genus": "Eleutheronema", "scientific": "E. tetradactylum", "color": (192, 192, 192)},
    {"name": "Freshwater Eel", "family": "Anguillidae", "genus": "Anguilla", "scientific": "A. marmorata", "color": (107, 142, 35)},
    {"name": "Gilt-Head Bream", "family": "Sparidae", "genus": "Sparus", "scientific": "Sparus aurata", "color": (218, 165, 32)},
    {"name": "Glass Perchlet", "family": "Ambassidae", "genus": "Ambassis", "scientific": "A. urotaenia", "color": (176, 224, 230)},
    {"name": "Goby", "family": "Gobiidae", "genus": "Glossogobius", "scientific": "G. giuris", "color": (160, 82, 45)},
    {"name": "Gold Fish", "family": "Cyprinidae", "genus": "Carassius", "scientific": "Carassius auratus", "color": (255, 165, 0)},
    {"name": "Gourami", "family": "Osphronemidae", "genus": "Osphronemus", "scientific": "O. goramy", "color": (0, 128, 128)},
    {"name": "Grass Carp", "family": "Cyprinidae", "genus": "Ctenopharyngodon", "scientific": "C. idella", "color": (34, 139, 34)},
    {"name": "Green Spotted Puffer", "family": "Tetraodontidae", "genus": "Tetraodon", "scientific": "T. nigroviridis", "color": (0, 100, 0)},
    {"name": "Hourse Mackerel", "family": "Carangidae", "genus": "Trachurus", "scientific": "T. trachurus", "color": (95, 158, 160)},
    {"name": "Indian Carp", "family": "Cyprinidae", "genus": "Catla", "scientific": "Catla catla", "color": (188, 143, 143)},
    {"name": "Indo-Pacific Tarpon", "family": "Megalopidae", "genus": "Megalops", "scientific": "M. cyprinoides", "color": (169, 169, 169)},
    {"name": "Jaguar Gapote", "family": "Cichlidae", "genus": "Parachromis", "scientific": "P. managuensis", "color": (128, 128, 0)},
    {"name": "Janitor Fish", "family": "Loricariidae", "genus": "Pterygoplichthys", "scientific": "P. disjunctivus", "color": (112, 128, 144)},
    {"name": "Knifefish", "family": "Notopteridae", "genus": "Chitala", "scientific": "Chitala ornata", "color": (119, 136, 153)},
    {"name": "Long-Snouted Pipefish", "family": "Syngnathidae", "genus": "Syngnathus", "scientific": "S. temminckii", "color": (46, 139, 87)},
    {"name": "Mosquito Fish", "family": "Poeciliidae", "genus": "Gambusia", "scientific": "G. affinis", "color": (143, 188, 143)},
    {"name": "Mudfish", "family": "Channidae", "genus": "Channa", "scientific": "Channa striata", "color": (139, 69, 19)},
    {"name": "Mullet", "family": "Mugilidae", "genus": "Mugil", "scientific": "Mugil cephalus", "color": (176, 196, 222)},
    {"name": "Pangasius", "family": "Pangasiidae", "genus": "Pangasianodon", "scientific": "P. hypophthalmus", "color": (135, 206, 235)},
    {"name": "Perch", "family": "Percidae", "genus": "Perca", "scientific": "Perca fluviatilis", "color": (184, 134, 11)},
    {"name": "Red Mullet", "family": "Mullidae", "genus": "Mullus", "scientific": "Mullus barbatus", "color": (205, 92, 92)},
    {"name": "Red Sea Bream", "family": "Sparidae", "genus": "Pagrus", "scientific": "Pagrus major", "color": (220, 20, 60)},
    {"name": "Scat Fish", "family": "Scatophagidae", "genus": "Scatophagus", "scientific": "S. argus", "color": (72, 61, 139)},
    {"name": "Sea Bass", "family": "Latidae", "genus": "Lates", "scientific": "Lates calcarifer", "color": (65, 105, 225)},
    {"name": "Shrimp", "family": "Penaeidae", "genus": "Penaeus", "scientific": "Penaeus monodon", "color": (233, 150, 122)},
    {"name": "Silver Barb", "family": "Cyprinidae", "genus": "Barbonymus", "scientific": "B. gonionotus", "color": (170, 170, 170)},
    {"name": "Silver Carp", "family": "Cyprinidae", "genus": "Hypophthalmichthys", "scientific": "H. molitrix", "color": (211, 211, 211)},
    {"name": "Silver Perch", "family": "Terapontidae", "genus": "Leiopotherapon", "scientific": "L. plumbeus", "color": (190, 190, 190)},
    {"name": "Snakehead", "family": "Channidae", "genus": "Channa", "scientific": "Channa striata", "color": (85, 85, 0)},
    {"name": "Striped Red Mullet", "family": "Mullidae", "genus": "Mullus", "scientific": "M. surmuletus", "color": (178, 34, 34)},
    {"name": "Tenpounder", "family": "Elopidae", "genus": "Elops", "scientific": "Elops machnata", "color": (127, 255, 212)},
    {"name": "Tilapia", "family": "Cichlidae", "genus": "Oreochromis", "scientific": "O. niloticus", "color": (60, 179, 113)},
    {"name": "Trout", "family": "Salmonidae", "genus": "Oncorhynchus", "scientific": "O. mykiss", "color": (250, 128, 114)},
    {"name": "Tuna", "family": "Scombridae", "genus": "Thunnus", "scientific": "Thunnus albacares", "color": (200, 34, 34)},
]

BASE = "datasets/my_fish_dataset"


def main():
    if os.path.exists(BASE):
        shutil.rmtree(BASE)

    for sp in SPECIES_DATA:
        name = sp["name"]
        color = sp["color"]
        for split, count in [("train", 3), ("val", 1)]:
            folder = os.path.join(BASE, split, name)
            os.makedirs(folder, exist_ok=True)
            for i in range(1, count + 1):
                img = Image.new("RGB", (224, 224), color)
                draw = ImageDraw.Draw(img)
                body = tuple(min(c + 40, 255) for c in color)
                draw.ellipse([30, 65, 195, 165], fill=body)
                draw.polygon([(185, 115), (218, 75), (218, 155)], fill=body)
                draw.ellipse([50, 95, 65, 110], fill=(255, 255, 255))
                draw.ellipse([53, 98, 62, 107], fill=(0, 0, 0))
                draw.text((5, 3), name, fill=(255, 255, 255))
                draw.text((5, 180), f"Family: {sp['family']}", fill=(200, 200, 200))
                draw.text((5, 195), f"Genus: {sp['genus']}", fill=(200, 200, 200))
                draw.text((5, 210), sp["scientific"], fill=(180, 180, 180))
                safe = name.replace(" ", "_").replace("-", "_").lower()
                img.save(os.path.join(folder, f"{safe}_{i:03d}.jpg"), "JPEG")

    total_train = len(SPECIES_DATA) * 3
    total_val = len(SPECIES_DATA) * 1
    print(f"Dataset template created at: {BASE}")
    print(f"  Species: {len(SPECIES_DATA)}")
    print(f"  Train:   {total_train} placeholder images")
    print(f"  Val:     {total_val} placeholder images")
    print(f"  Total:   {total_train + total_val} images")
    print()
    print("Replace placeholder images with real fish photos.")
    print("Folder name = species label (do NOT rename folders).")
    print("File names can be anything (.jpg, .jpeg, .png).")


if __name__ == "__main__":
    main()
