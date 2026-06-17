import pandas as pd, sys

df = pd.read_csv(
    r"C:\Users\dheke\Desktop\TUT'TOP\agent_identification\data\contacts.csv"
)
print(f"Total contacts: {len(df)}")
print(f"Schools: {df['domaine'].nunique()}")
print()

for domaine in df["domaine"].unique():
    sub = df[df["domaine"] == domaine]
    print(f"--- {domaine} ({len(sub)} contacts) ---")
    for _, row in sub.iterrows():
        n = str(row["contact_nom"]).strip()
        r = str(row["contact_titre"]).strip()
        e = str(row["email"]).strip()
        n = n if n != "nan" and n else ""
        r_text = f" [{r}]" if r and r != "nan" else ""
        e_text = f" {e}" if e and e != "nan" else ""
        line = f"  {n:40s}{r_text}{e_text}"
        try:
            print(line)
        except:
            print(f"  {n[:30]}... [encoding err]")
    print()
