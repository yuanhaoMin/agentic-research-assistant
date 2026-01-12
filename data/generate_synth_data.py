import json
import random


def generate(n: int = 10, seed: int = 42):
    random.seed(seed)

    industries = [
        "Automotive",
        "FinTech",
        "Cloud",
        "Biotech",
        "Retail",
        "Energy",
        "Robotics",
    ]
    risk_levels = ["low", "medium", "high"]

    sensitive_pool = [
        "Project Phoenix",
        "Internal-Only Alpha",
        "Redwood Initiative",
        "Orchid-7",
        "Delta Vault",
    ]

    companies = []
    for i in range(n):
        name = f"Company{i+1}"
        industry = random.choice(industries)
        risk = random.choice(risk_levels)
        products = [f"{industry} Product {j+1}" for j in range(random.randint(1, 4))]
        partnerships = [
            f"Partner{random.randint(1, 6)}" for _ in range(random.randint(0, 3))
        ]

        sensitive_projects = []
        if risk == "high":
            sensitive_projects = random.sample(sensitive_pool, k=random.randint(1, 2))
        elif risk == "medium":
            sensitive_projects = random.sample(sensitive_pool, k=random.randint(0, 1))

        companies.append(
            {
                "name": name,
                "industry": industry,
                "headquarters": random.choice(
                    ["Berlin", "London", "New York", "Tokyo", "Singapore"]
                ),
                "website": f"https://www.{name.lower()}.example.com",
                "products": products,
                "partnerships": partnerships,
                "risk_category": risk,
                "sensitive_projects": sensitive_projects,
            }
        )

    return companies


if __name__ == "__main__":
    data = generate()
    with open("data/synth_companies.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Wrote data/synth_companies.json")
