import urllib.request, json

r = urllib.request.urlopen("http://localhost:8001/api/v1/tournament/standings")
data = json.loads(r.read())
for g, teams in sorted(data.items()):
    print(f"Grupo {g}:")
    for t in teams:
        code = t["country_code"]
        pts = t["points"]
        played = t["played"]
        gd = t["goal_difference"]
        print(f"  {code:5s} PJ:{played} Pts:{pts} GD:{gd}")
