import pandas as pd

h = pd.read_csv("data/hack_et_event_hackathons.csv", encoding="utf-8-sig")
e = pd.read_csv("data/hack_et_event_evenements.csv", encoding="utf-8-sig")

with pd.ExcelWriter("data/hack_et_event.xlsx", engine="openpyxl") as w:
    h.to_excel(w, sheet_name="Hackathons", index=False)
    e.to_excel(w, sheet_name="Evenements", index=False)

print(f"OK - {len(h)} hackathons + {len(e)} evenements")
