import csv
import random
import re

# ------------------------------------------------------------
# 1. The original list of names (as provided)
# ------------------------------------------------------------
raw_names = [
    "Owoeye Charles Akinsola",
    "Badmus Samad Eniola",
    "Agada Victory Iko-ojo",
    "Jimba Adams Girima",
    "Shadrach Auta John (All courses last semester and IFT313)",
    "Manus Samuel",
    "Shuaib Alamin Hassan",
    "Daka Deborah Chenwolo",
    "Jimoh Abbas",
    "Ndayako Ibrahim Ibrahim",
    "Igboh Mhenuter",
    "Adamu Saidu",
    "Kalu Joshua Hapuruchukwu",
    "Arinze Michael CHUKWU",
    "Ibrahim Amina",
    "Mohammed Ibrahim Idris",
    "Ononenyi Abuchi Emmanuel",
    "Abubakar Sediq Abdullahi",
    "Momohjimoh Abdulqudus Adeiza",
    "Ukah Emmanuel Ukah",
    "Joseph Michael",
    "Kange Michael Mvendaga",
    "Akpan Emmanuel Joseph",
    "Muhammad kolo Zahradin",
    "Emmanuel Victor adakole",
    "Akinola Samson Damilola",
    "Awal Musa Erena",
    "Nurudeen musa",
    "Obilor Chidiukwu Norbert",
    "Falodun Tunmise",
    "Emmanuel Ayomide Gbenga",
    "Innocent Apeh",
    "Victor olayinka Kehinde",
    "Nsidibe saviour Henry",
    "ILO JEREMIAH AJIBOLA",
    "Muhammad ozomata m",
    "Michael Joseph",
    "Abbah Abraham",
    "Abdullahi Muhammad Rabba",
    "Jibayo Olakunle Samuel",
    "Hassan Dauda",
    "Adam Muhammad",
    "Jibrin Bashir",
    "Usman Isaac Anoze",
    "Abdullahi kasim Abbas",
    "Nasiru Jacob James",
    "Ukpoju Aboje Paul",
    "Adeniran Abdganiy Adekunle (Plus 300L Second semester Courses)",
    "Zughumret Desmond Patrick",
    "Abdulrahman Umar Yari",
    "Barde Jennifer",
    "Umar Abubakar",
    "Nuhu Muhammad nazir",
    "Ahmad munir shehu",
    "Saleem isah",
    "Moses Jeffery Emmanuel",
    "Ezekiel Clifford",
    "Samuel Owen",
    "Kester Apuyor",
    "Olusegun Israel Ayomide",
    "Makama Wilson Sheyiye",
    "Ajayi Daniel Moyinoluwa",
    "Jonathan Usman Justice",
    "Gideon Joseph Zugwai",
    "Uzo Newton",
    "Yahaya Abdulrazaq A",
    "Adikwu Wesley J",
    "Favour Christopher Egwuonwu",
    "Awajimijan Paul Goodluck",
    "OSAYI OYEFU GODSWILL",
    "Ben Emmanuel Mfoniso",
    "Akighir Silas Aondongu",
    "Adelaju Shittu Gbolahan"
]

# ------------------------------------------------------------
# 2. Helper to clean a name and split into (first, last, middle)
# ------------------------------------------------------------
def parse_name(full_name):
    # Remove zero-width characters and notes in parentheses
    name = full_name.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    name = re.sub(r'\(.*?\)', '', name).strip()
    parts = name.split()
    if not parts:
        return ("", "", "")
    if len(parts) == 1:
        return (parts[0], "", "")
    if len(parts) == 2:
        # Assume "Surname FirstName" -> last=parts[0], first=parts[1]
        return (parts[1], parts[0], "")
    # 3 or more parts: last = parts[0], first = parts[1], middle = rest joined
    last = parts[0]
    first = parts[1]
    middle = " ".join(parts[2:])
    return (first, last, middle)

# ------------------------------------------------------------
# 3. Build the initial 73 records
# ------------------------------------------------------------
students = []
for full in raw_names:
    first, last, middle = parse_name(full)
    students.append({
        "first_name": first,
        "last_name": last,
        "middle_name": middle
    })

# ------------------------------------------------------------
# 4. Generate 127 additional random Nigerian names
# ------------------------------------------------------------
first_names = ["Chinedu", "Aisha", "Emeka", "Fatima", "Tunde", "Ngozi", "Ibrahim", "Blessing",
               "Oluwaseun", "Zainab", "Chidi", "Halima", "Segun", "Amaka", "Yusuf", "Efe",
               "Kelechi", "Sadiq", "Ifeoma", "Bello", "Tobi", "Rukayat", "Uche", "Maryam",
               "Damilare", "Onyeka", "Abdul", "Grace", "Samuel", "Joy", "Peter", "Esther"]
last_names = ["Adeyemi", "Okafor", "Bello", "Eze", "Mohammed", "Olawale", "Nwosu", "Abubakar",
              "Ojo", "Chukwu", "Ibrahim", "Adebayo", "Okonkwo", "Sani", "Ogunleye", "Ali",
              "Nwachukwu", "Yakubu", "Balogun", "Adamu", "Obi", "Musa", "Afolabi", "Danjuma"]
middle_names = ["Chukwu", "Amina", "Oluwaseun", "Ijeoma", "Bello", "Ngozi", "Abdul", "Temitope",
                "Ifeanyi", "Zainab", "Olawale", "Chiamaka", "Musa", "Folake", "Emeka", "Hauwa",
                "Oluwatobi", "Nneka", "Suleiman", "Adekunle", "Yemi", "Kelechi", "Rashidat", "Obinna"]

for _ in range(127):
    fn = random.choice(first_names)
    ln = random.choice(last_names)
    mn = random.choice(middle_names)
    students.append({
        "first_name": fn,
        "last_name": ln,
        "middle_name": mn
    })

# ------------------------------------------------------------
# 5. Assign random matric numbers and levels
# ------------------------------------------------------------
def generate_matric():
    year = random.choice([2022, 2023, 2024, 2025, 2026])
    num = random.randint(10000, 99999)
    return f"{year}/1/{num}CF"

levels = [100, 200, 300, 400, 500]

for s in students:
    s["matric_number"] = generate_matric()
    s["level"] = random.choice(levels)

# ------------------------------------------------------------
# 6. Write the CSV
# ------------------------------------------------------------
with open("students.csv", "w", newline="", encoding="utf-8") as f:
    fieldnames = ["first_name", "last_name", "middle_name", "matric_number", "level"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for s in students:
        writer.writerow(s)

print(f"CSV created: students.csv ({len(students)} rows)")